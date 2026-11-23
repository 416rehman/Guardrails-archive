# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: The Guardrails ADR Authors
"""Claude Code settings verification for the install-smoke choose step (D-48, D-49)."""

import dataclasses
import json
import os
import pathlib
import shlex
import sys
from typing import Any, Mapping

_HERE = str(pathlib.Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from snapshot import (
    ERR_SETTINGS,
    DiffEntry,
    DiffKind,
    EntryKind,
    OracleError,
    OsName,
    Profile,
    SnapshotEntry,
    detect_host_os,
    diff_snapshots,
    expand_path,
    format_diff,
    is_ours_ancestor_dir,
    is_under_ours,
    normalize_for_match,
    ours_patterns,
    sha256_bytes,
)

SHELL_META_TOKENS = (";", "|", "&", ">", "<", "`", "$(", "\n", "\r")


@dataclasses.dataclass(frozen=True)
class JsonNode:
    start: int
    end: int
    value: Any
    members: tuple[tuple[int, int, str, "JsonNode"], ...] = ()
    items: tuple["JsonNode", ...] = ()


def _skip_ws(text: str, pos: int) -> int:
    while pos < len(text) and text[pos] in " \t\r\n":
        pos += 1
    return pos


def _parse_json_node(text: str, pos: int, decoder: json.JSONDecoder) -> tuple[JsonNode, int]:
    pos = _skip_ws(text, pos)
    if pos >= len(text):
        raise ValueError("unexpected end of JSON")
    ch = text[pos]
    if ch == "{":
        return _parse_json_object(text, pos, decoder)
    if ch == "[":
        return _parse_json_array(text, pos, decoder)
    val, end = decoder.raw_decode(text, pos)
    return JsonNode(pos, end, val), end


def _parse_json_object(text: str, pos: int, decoder: json.JSONDecoder) -> tuple[JsonNode, int]:
    start = pos
    pos = _skip_ws(text, pos + 1)
    members: list[tuple[int, int, str, JsonNode]] = []
    result: dict[str, Any] = {}
    if pos < len(text) and text[pos] == "}":
        return JsonNode(start, pos + 1, result, members=()), pos + 1
    while True:
        pos = _skip_ws(text, pos)
        if pos >= len(text) or text[pos] != '"':
            raise ValueError("expected JSON object key")
        key_start = pos
        key, key_end = decoder.raw_decode(text, pos)
        pos = _skip_ws(text, key_end)
        if pos >= len(text) or text[pos] != ":":
            raise ValueError("expected ':'")
        val_node, pos = _parse_json_node(text, pos + 1, decoder)
        members.append((key_start, key_end, key, val_node))
        result[key] = val_node.value
        pos = _skip_ws(text, pos)
        if pos >= len(text):
            raise ValueError("unterminated JSON object")
        if text[pos] == "}":
            return JsonNode(start, pos + 1, result, members=tuple(members)), pos + 1
        if text[pos] != ",":
            raise ValueError("expected ',' or '}'")
        pos += 1


def _parse_json_array(text: str, pos: int, decoder: json.JSONDecoder) -> tuple[JsonNode, int]:
    start = pos
    pos = _skip_ws(text, pos + 1)
    items: list[JsonNode] = []
    result: list[Any] = []
    if pos < len(text) and text[pos] == "]":
        return JsonNode(start, pos + 1, result, items=()), pos + 1
    while True:
        item_node, pos = _parse_json_node(text, pos, decoder)
        items.append(item_node)
        result.append(item_node.value)
        pos = _skip_ws(text, pos)
        if pos >= len(text):
            raise ValueError("unterminated JSON array")
        if text[pos] == "]":
            return JsonNode(start, pos + 1, result, items=tuple(items)), pos + 1
        if text[pos] != ",":
            raise ValueError("expected ',' or ']'")
        pos += 1


def parse_json_spans(text: str) -> JsonNode:
    decoder = json.JSONDecoder()
    node, end = _parse_json_node(text, 0, decoder)
    if _skip_ws(text, end) != len(text):
        raise ValueError("trailing data after JSON document")
    if not isinstance(node.value, dict):
        raise ValueError("root settings value must be a JSON object")
    return node


def _extract_command_exe(command: str, os_name: OsName) -> str | None:
    if not isinstance(command, str) or not command.strip():
        return None
    if any(token in command for token in SHELL_META_TOKENS):
        return None
    try:
        tokens = shlex.split(command, posix=(os_name != OsName.WINDOWS))
    except ValueError:
        return None
    if not tokens:
        return None
    exe = tokens[0]
    if os_name == OsName.WINDOWS:
        exe = exe.strip('"')
    return exe


def _is_valid_ours_command(command: str, patterns: list[str], os_name: OsName) -> bool:
    exe = _extract_command_exe(command, os_name)
    if exe is None:
        return False
    path_cls = pathlib.PureWindowsPath if os_name == OsName.WINDOWS else pathlib.PurePosixPath
    parsed = path_cls(exe)
    if not parsed.is_absolute() or ".." in parsed.parts:
        return False
    if not is_under_ours(exe, patterns, os_name):
        return False
    if os_name == detect_host_os() and os.path.lexists(exe) and not is_under_ours(os.path.realpath(exe), patterns, os_name):
        return False
    return True


def is_ours_hook_matcher_entry(entry: Any, patterns: list[str], os_name: OsName) -> bool:
    if not isinstance(entry, dict):
        return False
    hooks = entry.get("hooks")
    if not isinstance(hooks, list) or not hooks:
        return False
    for item in hooks:
        if not isinstance(item, dict) or item.get("type") != "command":
            return False
        if not _is_valid_ours_command(item.get("command", ""), patterns, os_name):
            return False
    return True


def _cut_slices(text: str, cuts: list[tuple[int, int]]) -> str:
    if not cuts:
        return text
    out = []
    cursor = 0
    for start, end in sorted(cuts):
        if start < cursor:
            raise ValueError("overlapping edit cuts")
        out.append(text[cursor:start])
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


def _contiguous_cuts(spans: list[tuple[int, int]], kept_indices: set[int]) -> list[tuple[int, int]]:
    cuts: list[tuple[int, int]] = []
    idx = 0
    total = len(spans)
    while idx < total:
        if idx in kept_indices:
            idx += 1
            continue
        end_idx = idx
        while end_idx + 1 < total and (end_idx + 1) not in kept_indices:
            end_idx += 1
        if idx > 0 and (idx - 1) in kept_indices:
            cuts.append((spans[idx - 1][1], spans[end_idx][1]))
        elif end_idx + 1 < total and (end_idx + 1) in kept_indices:
            cuts.append((spans[idx][0], spans[end_idx + 1][0]))
        else:
            cuts.append((spans[idx][0], spans[end_idx][1]))
        idx = end_idx + 1
    return cuts


def _match_event_array(
    seeded_text: str,
    after_text: str,
    seeded_arr: JsonNode,
    after_arr: JsonNode,
    patterns: list[str],
    os_name: OsName,
) -> tuple[list[tuple[int, int]], int]:
    s_items, a_items = seeded_arr.items, after_arr.items
    s_idx = 0
    kept_indices: set[int] = set()
    ours_count = 0

    for a_idx, a_item in enumerate(a_items):
        if s_idx < len(s_items):
            s_item = s_items[s_idx]
            if after_text[a_item.start:a_item.end] == seeded_text[s_item.start:s_item.end]:
                kept_indices.add(a_idx)
                s_idx += 1
                continue
        if not is_ours_hook_matcher_entry(a_item.value, patterns, os_name):
            raise OracleError(ERR_SETTINGS, "non-ours hook entry added or seeded entry modified")
        ours_count += 1

    if s_idx != len(s_items):
        raise OracleError(ERR_SETTINGS, "seeded hook entry missing or modified")

    spans = [(item.start, item.end) for item in a_items]
    return _contiguous_cuts(spans, kept_indices), ours_count


def verify_user_claude_settings(
    seeded_bytes: bytes,
    after_bytes: bytes,
    patterns: list[str],
    os_name: OsName,
) -> tuple[int, list[str]]:
    try:
        seeded_text = seeded_bytes.decode("utf-8")
        after_text = after_bytes.decode("utf-8")
        seeded_root = parse_json_spans(seeded_text)
        after_root = parse_json_spans(after_text)
    except (UnicodeDecodeError, ValueError) as error:
        return 0, [f"invalid Claude settings JSON: {type(error).__name__}"]

    s_members = {k: (ks, vn) for ks, _, k, vn in seeded_root.members}
    a_members = {k: (ks, vn) for ks, _, k, vn in after_root.members}
    if set(s_members) != set(a_members) or "hooks" not in s_members:
        return 0, ["top-level keys changed outside hooks"]

    for key, (ks, vn) in s_members.items():
        if key == "hooks":
            continue
        aks, avn = a_members[key]
        if after_text[aks:avn.end] != seeded_text[ks:vn.end]:
            return 0, [f"top-level member '{key}' bytes changed"]

    s_hooks, a_hooks = s_members["hooks"][1], a_members["hooks"][1]
    if not isinstance(s_hooks.value, dict) or not isinstance(a_hooks.value, dict):
        return 0, ["hooks must be a JSON object"]

    sh_map = {k: vn for _, _, k, vn in s_hooks.members}
    ah_list = a_hooks.members
    kept_ev_indices: set[int] = set()
    cuts: list[tuple[int, int]] = []
    total_ours = 0

    for idx, (_, _, ev_name, a_ev_node) in enumerate(ah_list):
        if not isinstance(a_ev_node.value, list):
            return 0, [f"hooks.{ev_name} must be a JSON array"]
        if ev_name in sh_map:
            kept_ev_indices.add(idx)
            try:
                ev_cuts, ev_ours = _match_event_array(
                    seeded_text, after_text, sh_map[ev_name], a_ev_node, patterns, os_name
                )
            except OracleError as err:
                return 0, [f"hooks.{ev_name}: {err}"]
            cuts.extend(ev_cuts)
            total_ours += ev_ours
            continue
        if not a_ev_node.items:
            return 0, [f"hooks.{ev_name} added empty"]
        for item in a_ev_node.items:
            if not is_ours_hook_matcher_entry(item.value, patterns, os_name):
                return 0, [f"hooks.{ev_name} contains entry outside ours"]
            total_ours += 1

    if len(kept_ev_indices) != len(sh_map):
        return 0, ["seeded hook event missing"]

    cuts.extend(_contiguous_cuts([(ks, node.end) for ks, _, _, node in ah_list], kept_ev_indices))
    try:
        reconstructed = _cut_slices(after_text, cuts)
    except ValueError as err:
        return 0, [str(err)]

    if reconstructed != seeded_text:
        return 0, ["seeded bytes outside our entries were altered"]
    if total_ours == 0:
        return 0, ["no entries pointing to ours were added"]
    return total_ours, []


def verify_dropin_claude_settings(dropin_bytes: bytes, patterns: list[str], os_name: OsName) -> tuple[int, list[str]]:
    try:
        doc = json.loads(dropin_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        return 0, [f"invalid Claude drop-in JSON: {type(error).__name__}"]
    if not isinstance(doc, dict) or not isinstance(doc.get("hooks"), dict):
        return 0, ["drop-in must be a JSON object with a hooks object"]
    total_ours = 0
    for ev_name, entries in doc["hooks"].items():
        if not isinstance(entries, list) or not entries:
            return 0, [f"drop-in hooks.{ev_name} must be a non-empty array"]
        for entry in entries:
            if not is_ours_hook_matcher_entry(entry, patterns, os_name):
                return 0, [f"drop-in hooks.{ev_name} contains entry outside ours"]
            total_ours += 1
    if total_ours == 0:
        return 0, ["drop-in contains no hook entries"]
    return total_ours, []


def _is_allowed_dropin_path(diff: DiffEntry, norm_p: str, norm_dropin_dir: str, os_name: OsName) -> bool:
    if diff.kind == DiffKind.REMOVED:
        return False
    sep = "\\" if os_name == OsName.WINDOWS else "/"
    parent_dir = normalize_for_match(os.path.dirname(norm_dropin_dir), os_name)
    if norm_p in (parent_dir, norm_dropin_dir) and diff.after is not None and diff.after.kind == EntryKind.DIR:
        return True
    return norm_p.startswith(norm_dropin_dir.rstrip(sep) + sep) and norm_p.endswith(".json")


def verify_choose_changes(
    before: Mapping[str, SnapshotEntry],
    after: Mapping[str, SnapshotEntry],
    config: Mapping[str, Any],
    os_name: OsName,
    profile: Profile,
    seeded_bytes: bytes,
    env: Mapping[str, str] | None = None,
) -> list[str]:
    source = os.environ if env is None else env
    patterns = ours_patterns(config, os_name, profile, source)
    user_settings = expand_path(config["limits"]["claude_user_settings"], os_name, source)
    norm_user = normalize_for_match(user_settings, os_name)
    dropin_dir = expand_path(config["os"][os_name.value]["claude_dropin_dir"], os_name, source)
    norm_dropin_dir = normalize_for_match(dropin_dir, os_name)

    diffs = diff_snapshots(before, after)
    errors: list[str] = []
    dropin_files: list[str] = []
    user_modified = False

    for diff in diffs:
        if is_under_ours(diff.path, patterns, os_name) or is_ours_ancestor_dir(diff, after, patterns, os_name):
            continue
        norm_p = normalize_for_match(diff.path, os_name)
        if norm_p == norm_user:
            user_modified = True
            continue
        if profile == Profile.PROTECTED and _is_allowed_dropin_path(diff, norm_p, norm_dropin_dir, os_name):
            if diff.after is not None and diff.after.kind == EntryKind.FILE:
                dropin_files.append(diff.path)
            continue
        errors.extend(format_diff([diff]))

    if errors:
        return ["changes outside ours and Claude Code settings:\n" + "\n".join(errors)]

    total_entries = 0
    if user_modified:
        try:
            actual_bytes = pathlib.Path(user_settings).read_bytes()
        except OSError as err:
            return [f"cannot read {user_settings}: {type(err).__name__}"]
        count, errs = verify_user_claude_settings(seeded_bytes, actual_bytes, patterns, os_name)
        if errs:
            return [
                f"{user_settings} (seeded sha256={sha256_bytes(seeded_bytes)}, "
                f"actual sha256={sha256_bytes(actual_bytes)}): {'; '.join(errs)}"
            ]
        total_entries += count
    elif profile == Profile.PROTECTED and dropin_files:
        try:
            actual_user = pathlib.Path(user_settings).read_bytes()
        except OSError as err:
            return [f"cannot read {user_settings}: {type(err).__name__}"]
        if actual_user != seeded_bytes:
            return [
                f"{user_settings} changed in protected mode "
                f"(seeded sha256={sha256_bytes(seeded_bytes)}, actual sha256={sha256_bytes(actual_user)})"
            ]
        for dropin_path in dropin_files:
            try:
                raw = pathlib.Path(dropin_path).read_bytes()
            except OSError as err:
                return [f"cannot read {dropin_path}: {type(err).__name__}"]
            count, errs = verify_dropin_claude_settings(raw, patterns, os_name)
            if errs:
                return [f"{dropin_path} (sha256={sha256_bytes(raw)}): {'; '.join(errs)}"]
            total_entries += count

    if total_entries == 0:
        return ["choose step wrote no Claude Code hook entries"]
    return []

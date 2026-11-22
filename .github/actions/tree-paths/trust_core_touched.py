"""List the paths that touch the trust core.

Usage: python3 -I trust_core_touched.py --list <file> (--diff <base> <head> | --paths <path>...)

Each line of the list matches as a git :(glob,icase) pathspec from the root, and git does the
matching. --diff takes the paths of git diff --name-only --no-renames, so a rename gives both names,
and then prints the findings of check_tree.py, beside this file, on <head>. Exit 0 when nothing is
printed, 1 when something is, and 2 on an input error.
"""

import argparse
import dataclasses
import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile

CHECK_TREE_SPEC = importlib.util.spec_from_file_location(
    "check_tree", pathlib.Path(__file__).resolve().parent / "check_tree.py",
)
check_tree = importlib.util.module_from_spec(CHECK_TREE_SPEC)
CHECK_TREE_SPEC.loader.exec_module(check_tree)

MAGIC = ":(glob,icase)"
FILE_MODE = "100644"

# Settings that change which paths git takes into an index or how it reads a pathspec, fixed so
# the answer does not depend on the host or the caller's environment.
GIT_SETTINGS = ["-c", "core.ignorecase=false", "-c", "core.protectNTFS=false", "-c", "core.protectHFS=false"]
PATHSPEC_ENVIRONMENT = ("GIT_LITERAL_PATHSPECS", "GIT_GLOB_PATHSPECS", "GIT_NOGLOB_PATHSPECS", "GIT_ICASE_PATHSPECS")


class InputError(Exception):
    pass


@dataclasses.dataclass
class IndexGroup:
    paths: set
    folders: set


def git(args, stdin=b"", index=None):
    environment = {key: value for key, value in os.environ.items() if key not in PATHSPEC_ENVIRONMENT}
    if index is not None:
        environment["GIT_INDEX_FILE"] = index
    result = subprocess.run(
        ["git", *GIT_SETTINGS, *args], input=stdin, env=environment, capture_output=True, check=False,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise InputError(message or f"git {args[0]} exited {result.returncode}")
    return result.stdout


def read_list(path):
    try:
        text = pathlib.Path(path).read_bytes()
    except OSError as error:
        raise InputError(f"cannot read {path}: {type(error).__name__}") from None
    lines = [line.strip() for line in text.splitlines()]
    patterns = [line for line in lines if line and not line.startswith(b"#")]
    if not patterns:
        raise InputError(f"{path} holds no pattern")
    if any(byte not in check_tree.PRINTABLE for pattern in patterns for byte in pattern):
        raise InputError(f"{path} holds a line outside printable ASCII")
    return [pattern.decode("ascii") for pattern in patterns]


def folders_above(path):
    return {path[:at] for at, byte in enumerate(path) if byte == ord("/")}


def index_groups(paths):
    """Split the paths so that no group holds both a path and a path below it: one index cannot."""
    groups = []
    for path in paths:
        above = folders_above(path)
        group = next((g for g in groups if path not in g.folders and g.paths.isdisjoint(above)), None)
        if group is None:
            group = IndexGroup(set(), set())
            groups.append(group)
        group.paths.add(path)
        group.folders.update(above)
    return [group.paths for group in groups]


def fill_index(top, index, blob, paths):
    entries = b"".join(f"{FILE_MODE} {blob}\t".encode("ascii") + path + b"\0" for path in sorted(paths))
    git(["-C", top, "update-index", "--add", "-z", "--index-info"], stdin=entries, index=index)
    held = git(["-C", top, "ls-files", "-z", "--full-name"], index=index)
    if set(held.split(b"\0")) - {b""} != paths:
        raise InputError("git did not take every path into the index")


def listed(top, index, patterns):
    pathspecs = [MAGIC + pattern for pattern in patterns]
    return set(git(["-C", top, "ls-files", "-z", "--full-name", "--", *pathspecs], index=index).split(b"\0"))


def matched_sets(pattern_lists, paths):
    """For each list of patterns, the set of paths that one of its patterns matches."""
    top = git(["rev-parse", "--show-toplevel"]).strip().decode("utf-8", "surrogateescape")
    blob = git(["-C", top, "hash-object", "-t", "blob", "--stdin"]).strip().decode("ascii")
    results = [set() for _ in pattern_lists]
    for group in index_groups(dict.fromkeys(paths)):
        with tempfile.TemporaryDirectory() as scratch:
            index = os.path.join(scratch, "index")
            fill_index(top, index, blob, group)
            for result, patterns in zip(results, pattern_lists):
                result |= listed(top, index, patterns) & group
    return results


def matching(patterns, paths):
    """Return the paths, in their first order and each once, that a pattern matches."""
    unique = list(dict.fromkeys(paths))
    if not unique:
        return []
    matched = matched_sets([patterns], unique)[0]
    return [path for path in unique if path in matched]


def changed_paths(base, head):
    names = git(["diff", "--name-only", "--no-renames", "--no-relative", "-z", "--end-of-options", base, head, "--"])
    return [name for name in names.split(b"\0") if name]


def tree_findings(head):
    try:
        return check_tree.report_lines(head)
    except check_tree.Unreadable as error:
        raise InputError(f"cannot read the tree of {head!a}: {error}") from None


def report_lines(arguments):
    patterns = read_list(arguments.list)
    if arguments.diff is None:
        paths = [os.fsencode(path) for path in arguments.paths]
        return [check_tree.shown(path) for path in matching(patterns, paths)]
    base, head = arguments.diff
    touched = matching(patterns, changed_paths(base, head))
    return [check_tree.shown(path) for path in touched] + tree_findings(head)


def main(argv):
    parser = argparse.ArgumentParser(description="List the paths that touch the trust core.")
    parser.add_argument("--list", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--diff", nargs=2, metavar=("BASE", "HEAD"))
    source.add_argument("--paths", nargs="+", metavar="PATH")
    arguments = parser.parse_args(argv)
    try:
        lines = report_lines(arguments)
    except InputError as error:
        print(f"::error::GRDR-GATE-0002 {error}", file=sys.stderr)
        return 2
    for line in lines:
        print(line)
    return 1 if lines else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

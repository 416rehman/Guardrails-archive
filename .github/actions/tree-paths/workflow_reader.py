"""A reader for the part of YAML the workflows and local actions are written in.

It reads block mappings and sequences, plain, quoted and block scalars, and comments, and raises
Unreadable for anything else (flow collections other than [words] and {}, anchors, aliases, tags,
explicit keys, escapes, a character outside printable ASCII), so what it reads is what YAML reads.
It splits lines on line feeds only.
"""

import dataclasses
import re

BLOCK_SCALAR = "<block scalar>"
PRINTABLE = re.compile(r"[ -~]*")
WORD_KEY = r"[A-Za-z_][A-Za-z0-9_-]*"
KEY_LINE = re.compile(rf"(?P<key>{WORD_KEY}|\"{WORD_KEY}\"|'{WORD_KEY}') *:(?: +(?P<rest>.*))?")
BLOCK_INDICATOR = re.compile(r"[|>][+-]?(?: +#.*)?")
SINGLE_QUOTED = re.compile(r"'((?:[^']|'')*)'(?: +#.*)?")
DOUBLE_QUOTED = re.compile(r'"([^"\\]*)"(?: +#.*)?')
FLOW_OF_WORDS = re.compile(r"\[[A-Za-z0-9_., -]*\]|\{\}")
PLAIN_START = re.compile(r"[^-?:,\[\]{}#&*!|>'\"%@`]|[-?:][^ ]")


@dataclasses.dataclass
class ItemStart:
    number: int
    indent: int


@dataclasses.dataclass
class Line:
    number: int
    indent: int
    text: str


@dataclasses.dataclass
class Value:
    """A YAML node and the line it starts on: a scalar's text, a mapping or a sequence."""
    number: int
    data: str | dict | list


class Unreadable(Exception):
    pass


def lines_of(text):
    """The lines YAML reads as structure, with each "- " split into an item start and the line after it.

    Blank lines, comments and the text of block scalars are left out. A block scalar's text is
    every following line that is blank or deeper than the key that opens it.
    """
    text_deeper_than = None
    for number, line in enumerate(text.split("\n"), 1):
        if not PRINTABLE.fullmatch(line):
            raise Unreadable(f"line {number}: a character outside printable ASCII")
        content = line.lstrip(" ")
        indent = len(line) - len(content)
        if text_deeper_than is not None and (not content or indent > text_deeper_than):
            continue
        text_deeper_than = None
        if not content or content.startswith("#"):
            continue
        if content.startswith("- "):
            yield ItemStart(number, indent)
            content, indent = content[2:], indent + 2
        key_line = KEY_LINE.fullmatch(content)
        if key_line and key_line["rest"] and BLOCK_INDICATOR.fullmatch(key_line["rest"]):
            text_deeper_than = indent
        yield Line(number, indent, content)


def scalar(text, number):
    """The value of a scalar written on one line, as YAML reads it."""
    if BLOCK_INDICATOR.fullmatch(text):
        return BLOCK_SCALAR
    single = SINGLE_QUOTED.fullmatch(text)
    if single:
        return single[1].replace("''", "'")
    double = DOUBLE_QUOTED.fullmatch(text)
    if double:
        return double[1]
    value = text.split(" #", 1)[0].rstrip()
    if FLOW_OF_WORDS.fullmatch(value):
        return value
    if not PLAIN_START.match(value) or ": " in value or value.endswith(":"):
        raise Unreadable(f"line {number}: a value the reader does not read")
    return value


def parse_block(lines, at, indent):
    """The mapping or sequence that starts at lines[at] at this indent, and where it ends."""
    number = lines[at].number
    entries, items = {}, []
    while at < len(lines) and lines[at].indent == indent:
        if isinstance(lines[at], ItemStart):
            item, at = parse_item(lines, at + 1, indent + 2, lines[at].number)
            items.append(item)
            continue
        key, value, at = parse_entry(lines, at, indent)
        if key in entries:
            raise Unreadable(f"line {value.number}: {key} repeated in one mapping")
        entries[key] = value
    if entries and items:
        raise Unreadable(f"line {number}: sequence items and keys in one block")
    return Value(number, items or entries), at


def parse_item(lines, at, indent, number):
    first = lines[at]
    if KEY_LINE.fullmatch(first.text) is None:
        return Value(number, scalar(first.text, first.number)), at + 1
    block, at = parse_block(lines, at, indent)
    return Value(number, block.data), at


def parse_entry(lines, at, indent):
    line = lines[at]
    key_line = KEY_LINE.fullmatch(line.text) if isinstance(line, Line) else None
    if key_line is None:
        raise Unreadable(f"line {line.number}: not a key the reader reads")
    key, rest = key_line["key"].strip("'\""), key_line["rest"]
    at += 1
    if rest and not rest.startswith("#"):
        return key, Value(line.number, scalar(rest, line.number)), at
    if at < len(lines) and lines[at].indent > indent:
        block, at = parse_block(lines, at, lines[at].indent)
        return key, Value(line.number, block.data), at
    return key, Value(line.number, ""), at


def parse(text):
    lines = list(lines_of(text))
    if not lines:
        raise Unreadable("an empty file")
    root, at = parse_block(lines, 0, 0)
    if at != len(lines):
        raise Unreadable(f"line {lines[at].number}: indented out of place")
    return root


def as_mapping(value, what):
    if not isinstance(value.data, dict):
        raise Unreadable(f"line {value.number}: {what} is not a mapping")
    return value.data


def as_sequence(value, what):
    if not isinstance(value.data, list):
        raise Unreadable(f"line {value.number}: {what} is not a sequence")
    return value.data


def text_of(value):
    return value.data if value is not None and isinstance(value.data, str) else None


def values_of(value, what):
    return {} if value is None else {key: text_of(child) for key, child in as_mapping(value, what).items()}


def jobs_of(root):
    """Each job as (job id, its keys, its steps' keys in order)."""
    workflow = as_mapping(root, "the workflow")
    if "jobs" not in workflow:
        raise Unreadable("no jobs at the top level")
    for job_id, job in as_mapping(workflow["jobs"], "jobs").items():
        keys = as_mapping(job, job_id)
        steps = as_sequence(keys["steps"], f"the steps of {job_id}") if "steps" in keys else []
        yield job_id, keys, [as_mapping(step, f"a step of {job_id}") for step in steps]


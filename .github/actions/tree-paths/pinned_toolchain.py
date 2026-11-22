"""Print the toolchain that rust-toolchain.toml pins as KEY=value lines for GITHUB_ENV or GITHUB_OUTPUT.

Usage: python3 -I pinned_toolchain.py <rust-toolchain.toml>

Prints RUSTUP_TOOLCHAIN (the channel), TOOLCHAIN_PROFILE, and TOOLCHAIN_COMPONENTS and
TOOLCHAIN_TARGETS separated by commas; a value the file leaves out is empty. Nothing is printed
unless the file parses, its [toolchain] table has a channel and no path key, and every value is one
toolchain word. A refusal exits 1 with a GRDR-GATE code on stderr.
"""

import re
import sys
import tomllib

WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class Refusal(Exception):
    def __init__(self, code, message):
        super().__init__(f"{code} {message}")


def read_toolchain(path):
    try:
        with open(path, "rb") as pinned:
            table = tomllib.load(pinned).get("toolchain")
    except (OSError, ValueError, RecursionError) as error:
        raise Refusal("GRDR-GATE-0003", f"cannot read {path}: {type(error).__name__}") from None
    if not isinstance(table, dict):
        raise Refusal("GRDR-GATE-0004", f"{path} has no [toolchain] table")
    if "path" in table:
        raise Refusal("GRDR-GATE-0004", f"{path} names a toolchain by path")
    return table


def word(path, key, value):
    if not isinstance(value, str) or not WORD.fullmatch(value):
        raise Refusal("GRDR-GATE-0004", f"{path} [toolchain] {key} is not a toolchain word")
    return value


def words(path, key, values):
    if not isinstance(values, list):
        raise Refusal("GRDR-GATE-0004", f"{path} [toolchain] {key} is not a list")
    return ",".join(word(path, key, value) for value in values)


def pin_lines(path, table):
    if "channel" not in table:
        raise Refusal("GRDR-GATE-0004", f"{path} [toolchain] has no channel")
    profile = table.get("profile")
    return [
        f"RUSTUP_TOOLCHAIN={word(path, 'channel', table['channel'])}",
        f"TOOLCHAIN_PROFILE={'' if profile is None else word(path, 'profile', profile)}",
        f"TOOLCHAIN_COMPONENTS={words(path, 'components', table.get('components', []))}",
        f"TOOLCHAIN_TARGETS={words(path, 'targets', table.get('targets', []))}",
    ]


def main(argv):
    if len(argv) != 2:
        raise Refusal("GRDR-GATE-0003", "usage: pinned_toolchain.py <rust-toolchain.toml>")
    path = argv[1]
    print("\n".join(pin_lines(path, read_toolchain(path))))


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Refusal as refusal:
        print(f"::error::{refusal}", file=sys.stderr)
        sys.exit(1)

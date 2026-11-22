"""Refuse the path kinds a revision's tree may not hold.

Usage: python3 -I check_tree.py --rev <rev>

The tree comes from git objects (git ls-tree -r -t -z), never from a working tree, so every runner
gives the same answer. Each refused path is printed with the rule it breaks. Exit 0 when no rule is
broken, 1 when one is, and 2 when the revision cannot be read.
"""

import argparse
import subprocess
import sys

PRINTABLE = range(0x20, 0x7F)
TOOLCHAIN_FILE = b"rust-toolchain"

RULE_BYTES = "a byte outside printable ASCII"
RULE_CASE = "a path equal to another under ASCII case folding"
RULE_TOOLCHAIN = "a rust-toolchain file"


class Unreadable(Exception):
    pass


def shown(path):
    return "".join(chr(byte) if byte in PRINTABLE else f"\\x{byte:02x}" for byte in path)


def git(*args):
    result = subprocess.run(["git", *args], capture_output=True, check=False)
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise Unreadable(message or f"git {args[0]} exited {result.returncode}")
    return result.stdout


def tree_paths(rev):
    tree = git("rev-parse", "--verify", "--quiet", "--end-of-options", f"{rev}^{{tree}}").strip()
    listing = git("ls-tree", "-r", "-t", "-z", "--full-tree", tree.decode("ascii"))
    return [entry.partition(b"\t")[2] for entry in listing.split(b"\0") if entry]


def findings(paths):
    found = []
    folded = {}
    for path in paths:
        folded.setdefault(path.lower(), set()).add(path)
        if any(byte not in PRINTABLE for byte in path):
            found.append((RULE_BYTES, path))
        if path.rpartition(b"/")[2].lower() == TOOLCHAIN_FILE:
            found.append((RULE_TOOLCHAIN, path))
    for variants in folded.values():
        if len(variants) > 1:
            found.extend((RULE_CASE, path) for path in variants)
    return sorted(found)


def report_lines(rev):
    return [f"refused ({rule}): {shown(path)}" for rule, path in findings(tree_paths(rev))]


def main(argv):
    parser = argparse.ArgumentParser(description="Refuse the path kinds a tree may not hold.")
    parser.add_argument("--rev", required=True)
    rev = parser.parse_args(argv).rev
    try:
        lines = report_lines(rev)
    except Unreadable as error:
        print(f"::error::GRDR-GATE-0001 cannot read the tree of {rev!a}: {error}", file=sys.stderr)
        return 2
    for line in lines:
        print(line)
    return 1 if lines else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

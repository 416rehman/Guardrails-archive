"""Tests for trust_core_touched.py:
python -I -m unittest discover -s .github/actions/tree-paths -p "test_trust_core_touched.py" -v

The oracle is a reference matcher written here with no call to git: the :(glob,icase) rules over
ASCII-lower-cased paths, where a `**/` segment matches zero or more folders. A differential run
compares it with git's pathspec matching, pattern by pattern, over every path of origin/main's and
the head's trees with random ASCII case changes, an instance of every list line, and the seeded
trees of tree_fixtures.py.
"""

import pathlib
import random
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest

import check_tree
import trust_core_touched
from tree_fixtures import CLEAN, SEEDED, FixtureRepo

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MATCHER = HERE / "trust_core_touched.py"
TRUST_CORE = ROOT / "security" / "trust-core.paths"
RISK_TIERS = ROOT / ".claude" / "risk-tiers.toml"
CORPUS_REVS = ["origin/main", "HEAD"]
CASE_VARIANTS = 16
MINIMUM_CASES = 10000
SEED = 1923
ASCII_FOLD = bytes.maketrans(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ", b"abcdefghijklmnopqrstuvwxyz")
WILDCARDS = b"*?[\\"


def list_lines(path):
    lines = [line.strip() for line in path.read_text(encoding="ascii").splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def risk_tier_globs():
    tiers = tomllib.loads(RISK_TIERS.read_text(encoding="ascii"))
    return [glob for table in tiers.values() if isinstance(table, dict) for glob in table.get("paths", [])]


def reference_regex(pattern):
    """The :(glob) rules as a regular expression over folded bytes; brackets and escapes are refused."""
    if any(byte in b"[\\" for byte in pattern):
        raise ValueError(f"the reference model has no rule for {pattern!r}")
    parts, at = [], 0
    while at < len(pattern):
        rest = pattern[at:]
        at_segment_start = at == 0 or pattern[at - 1:at] == b"/"
        if at_segment_start and rest.startswith(b"**/"):
            parts.append(b"(?:.*/)?")
            at += 3
        elif at_segment_start and rest == b"**":
            parts.append(b".*")
            at += 2
        elif rest.startswith(b"*"):
            parts.append(b"[^/]*")
            at += len(rest) - len(rest.lstrip(b"*"))
        elif rest.startswith(b"?"):
            parts.append(b"[^/]")
            at += 1
        else:
            parts.append(re.escape(rest[:1]))
            at += 1
    return re.compile(b"".join(parts), re.DOTALL)


def reference_matches(pattern, path):
    folded_pattern = pattern.encode("ascii").translate(ASCII_FOLD)
    folded_path = path.translate(ASCII_FOLD)
    if not any(byte in WILDCARDS for byte in folded_pattern):
        return folded_path == folded_pattern or folded_path.startswith(folded_pattern + b"/")
    return reference_regex(folded_pattern).fullmatch(folded_path) is not None


def tree_paths(rev):
    result = subprocess.run(
        ["git", "ls-tree", "-r", "-z", "--name-only", "--full-tree", rev],
        cwd=ROOT, capture_output=True, check=False,
    )
    return [path for path in result.stdout.split(b"\0") if path] if result.returncode == 0 else []


def instance(pattern, rng):
    """A path the pattern is written to match, with random folders and names in its wildcards."""
    text = pattern.replace("**/", rng.choice(["", "a/", "a/b/"]))
    text = re.sub(r"/\*\*$", rng.choice(["/x", "/x/y.rs"]), text)
    text = text.replace("**", "w").replace("*", rng.choice(["n", "name-2"])).replace("?", "q")
    return text.encode("ascii")


def case_variant(path, rng):
    return bytes(byte ^ 0x20 if chr(byte).isascii() and chr(byte).isalpha() and rng.random() < 0.5 else byte
                 for byte in path)


def corpus(patterns):
    rng = random.Random(SEED)
    sources = {rev: tree_paths(rev) for rev in CORPUS_REVS}
    base = [path for paths in sources.values() for path in paths]
    base += [instance(pattern, rng) for pattern in patterns for _ in range(3)]
    base += [path for paths, _ in SEEDED.values() for path in paths]
    cases = []
    for path in dict.fromkeys(base):
        cases.append(path)
        cases.extend(case_variant(path, rng) for _ in range(CASE_VARIANTS))
    return list(dict.fromkeys(cases)), {rev: len(paths) for rev, paths in sources.items()}


def run_matcher(*args, cwd=ROOT):
    return subprocess.run(
        [sys.executable, "-I", str(MATCHER), *args], cwd=cwd, capture_output=True, text=True, check=False,
    )


class DifferentialTest(unittest.TestCase):
    def test_git_matching_agrees_with_the_reference_model(self):
        patterns = list(dict.fromkeys(list_lines(TRUST_CORE) + risk_tier_globs()))
        cases, sources = corpus(patterns)
        self.assertTrue(sources["HEAD"], "the head's tree could not be listed")
        self.assertGreaterEqual(len(cases), MINIMUM_CASES)
        per_pattern = trust_core_touched.matched_sets([[pattern] for pattern in patterns], cases)
        mismatches = []
        for pattern, matched in zip(patterns, per_pattern):
            mismatches += [(pattern, path) for path in cases if (path in matched) != reference_matches(pattern, path)]
        print(f"\ndifferential: {len(patterns)} patterns, {len(cases)} cases from {sources}, "
              f"{len(mismatches)} mismatches", file=sys.stderr)
        self.assertEqual(mismatches[:20], [])

    def test_whole_list_agrees_with_the_reference_model(self):
        patterns = list_lines(TRUST_CORE)
        cases, _ = corpus(patterns)
        matched = set(trust_core_touched.matching(patterns, cases))
        expected = {path for path in cases if any(reference_matches(pattern, path) for pattern in patterns)}
        self.assertEqual(matched, expected)


class PathsModeTest(unittest.TestCase):
    def test_prints_each_matching_path_once_in_order(self):
        paths = ["docs/a.md", "CARGO.TOML", "crates/grdr-core/src/lib.rs", "CARGO.TOML", "crates/x/BUILD.RS"]
        result = run_matcher("--list", str(TRUST_CORE), "--paths", *paths)
        self.assertEqual((result.returncode, result.stdout), (1, "CARGO.TOML\ncrates/x/BUILD.RS\n"))

    def test_prints_nothing_when_no_path_matches(self):
        result = run_matcher("--list", str(TRUST_CORE), "--paths", "docs/a.md", "crates/grdr-core/src/lib.rs")
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_a_path_and_a_path_below_it_are_both_matched(self):
        result = run_matcher("--list", str(TRUST_CORE), "--paths", "Cargo.toml", "Cargo.toml/x")
        self.assertEqual((result.returncode, result.stdout), (1, "Cargo.toml\nCargo.toml/x\n"))


class InputErrorTest(unittest.TestCase):
    def test_input_errors_exit_2(self):
        with tempfile.TemporaryDirectory() as scratch:
            empty = pathlib.Path(scratch) / "empty.paths"
            empty.write_text("# only a comment\n\n", encoding="ascii")
            outside = pathlib.Path(scratch) / "outside.paths"
            outside.write_bytes("café/**\n".encode("utf-8"))
            for name, args in {
                "missing-list": ["--list", str(pathlib.Path(scratch) / "absent"), "--paths", "x"],
                "empty-list": ["--list", str(empty), "--paths", "x"],
                "list-outside-ascii": ["--list", str(outside), "--paths", "x"],
                "refused-path": ["--list", str(TRUST_CORE), "--paths", "../x"],
                "unknown-base": ["--list", str(TRUST_CORE), "--diff", "0" * 40, "HEAD"],
                "option-like-head": ["--list", str(TRUST_CORE), "--diff", "HEAD", "--output=x"],
            }.items():
                with self.subTest(case=name):
                    result = run_matcher(*args)
                    self.assertEqual((result.returncode, result.stdout), (2, ""), result.stderr)


class DiffModeTest(unittest.TestCase):
    def setUp(self):
        self.repo = FixtureRepo()
        self.addCleanup(self.repo.close)
        self.base = self.repo.tree(CLEAN + [b"crates/grdr-crypto/src/lib.rs"])

    def diff(self, head_paths):
        head = self.repo.tree(head_paths)
        return run_matcher("--list", str(TRUST_CORE), "--diff", self.base, head, cwd=self.repo.root)

    def test_a_rename_reports_the_listed_name(self):
        result = self.diff(CLEAN + [b"docs/moved.rs", b".Cargo/config"])
        self.assertEqual((result.returncode, result.stdout), (1, ".Cargo/config\ncrates/grdr-crypto/src/lib.rs\n"))

    def test_tree_findings_on_the_head_follow_the_paths(self):
        for name, (paths, named) in SEEDED.items():
            with self.subTest(case=name):
                result = self.diff(paths + [b"crates/grdr-crypto/src/lib.rs"])
                lines = result.stdout.splitlines()
                self.assertEqual(result.returncode, 1, result.stderr)
                findings = [line for line in lines if line.startswith("refused (")]
                self.assertTrue(findings, lines)
                self.assertEqual(lines[len(lines) - len(findings):], findings)
                shown = {line.partition("): ")[2] for line in findings}
                self.assertTrue({check_tree.shown(path) for path in named} <= shown, shown)

    def test_a_change_outside_the_list_passes(self):
        result = self.diff(CLEAN + [b"crates/grdr-crypto/src/lib.rs", b"docs/new.md"])
        self.assertEqual((result.returncode, result.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()

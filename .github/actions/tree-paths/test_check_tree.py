"""Tests for check_tree.py:
python -I -m unittest discover -s .github/actions/tree-paths -p "test_check_tree.py" -v

The oracle is git's own record of each fixture tree (git ls-tree -r -t), checked by a naive
all-pairs loop under an ASCII case-folding table written here, apart from check_tree.py.
"""

import pathlib
import subprocess
import sys
import unittest

import check_tree
from tree_fixtures import CLEAN, SEEDED, FixtureRepo

CHECK_TREE = pathlib.Path(__file__).resolve().parent / "check_tree.py"
ASCII_FOLD = bytes.maketrans(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ", b"abcdefghijklmnopqrstuvwxyz")


def rendered(path):
    return "".join(chr(byte) if 0x20 <= byte <= 0x7E else "\\x%02x" % byte for byte in path)


def reference(paths):
    expected = {check_tree.RULE_BYTES: set(), check_tree.RULE_CASE: set(), check_tree.RULE_TOOLCHAIN: set()}
    for at, path in enumerate(paths):
        for other in paths[at + 1:]:
            if path != other and path.translate(ASCII_FOLD) == other.translate(ASCII_FOLD):
                expected[check_tree.RULE_CASE] |= {path, other}
        if any(byte < 0x20 or byte > 0x7E for byte in path):
            expected[check_tree.RULE_BYTES].add(path)
        if path.split(b"/")[-1].translate(ASCII_FOLD) == b"rust-toolchain":
            expected[check_tree.RULE_TOOLCHAIN].add(path)
    return {rule: {rendered(path) for path in found} for rule, found in expected.items()}


def printed(stdout):
    found = {check_tree.RULE_BYTES: set(), check_tree.RULE_CASE: set(), check_tree.RULE_TOOLCHAIN: set()}
    for line in stdout.splitlines():
        rule, _, path = line.removeprefix("refused (").partition("): ")
        found[rule].add(path)
    return found


class CheckTreeTest(unittest.TestCase):
    def setUp(self):
        self.repo = FixtureRepo()
        self.addCleanup(self.repo.close)

    def run_check(self, rev):
        return subprocess.run(
            [sys.executable, "-I", str(CHECK_TREE), f"--rev={rev}"],
            cwd=self.repo.root, capture_output=True, text=True, check=False,
        )

    def test_clean_tree_passes(self):
        result = self.run_check(self.repo.tree(CLEAN))
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_each_seeded_case_is_refused(self):
        for name, (paths, named) in SEEDED.items():
            with self.subTest(case=name):
                tree = self.repo.tree(paths)
                result = self.run_check(tree)
                self.assertEqual(result.returncode, 1, result.stderr)
                found = printed(result.stdout)
                self.assertEqual(found, reference(self.repo.listed(tree)))
                every = set().union(*found.values())
                self.assertTrue({rendered(path) for path in named} <= every, every)

    def test_reads_git_objects_not_the_working_tree(self):
        tree = self.repo.tree(CLEAN)
        (pathlib.Path(self.repo.root) / "rust-toolchain").write_text("[toolchain]\n", encoding="ascii")
        self.assertEqual(self.run_check(tree).returncode, 0)

    def test_unreadable_revision_exits_2(self):
        for rev in ["0" * 40, "no-such-branch", "--output=x"]:
            with self.subTest(rev=rev):
                result = self.run_check(rev)
                self.assertEqual(result.returncode, 2)
                self.assertIn("GRDR-GATE-0001", result.stderr)


if __name__ == "__main__":
    unittest.main()

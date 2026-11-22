"""Tests for pinned_toolchain.py and the jobs that use it:
python -I -m unittest discover -s .github/actions/tree-paths -p "test_pinned_toolchain.py" -v

The oracles are rustup's documented toolchain file format (a [toolchain] table with channel,
components, targets, profile or path), the real rust-toolchain.toml, and the workflows, where every
job that runs rustup or cargo must write RUSTUP_TOOLCHAIN to GITHUB_ENV before its first such line.
"""

import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
READER = HERE / "pinned_toolchain.py"
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
JOB_HEADER = re.compile(r"^  (?=[a-z][a-z0-9-]*:\s*$)", re.M)
RUST_LINE = re.compile(r"(?:^|[\s;&|(])(?:rustup|cargo) ")
PIN_LINE = re.compile(r"pinned_toolchain\.py|RUSTUP_TOOLCHAIN=")

FULL = """[toolchain]
channel = "1.99.1"
components = ["rustfmt", "clippy"]
targets = ["wasm32-unknown-unknown"]
profile = "minimal"
"""

SEEDED = {
    "no-table": ('channel = "1.99.1"\n', "GRDR-GATE-0004"),
    "no-channel": ('[toolchain]\nprofile = "minimal"\n', "GRDR-GATE-0004"),
    "path-key": ('[toolchain]\npath = "/opt/tc"\n', "GRDR-GATE-0004"),
    "path-key-beside-channel": (FULL + 'path = "/opt/tc"\n', "GRDR-GATE-0004"),
    "channel-not-a-word": ('[toolchain]\nchannel = "/opt/tc"\n', "GRDR-GATE-0004"),
    "channel-two-lines": ('[toolchain]\nchannel = "1.99.1\\nX=1"\n', "GRDR-GATE-0004"),
    "channel-not-text": ("[toolchain]\nchannel = 1\n", "GRDR-GATE-0004"),
    "component-not-a-word": ('[toolchain]\nchannel = "1.99.1"\ncomponents = ["a b"]\n', "GRDR-GATE-0004"),
    "targets-not-a-list": ('[toolchain]\nchannel = "1.99.1"\ntargets = "x"\n', "GRDR-GATE-0004"),
    "does-not-parse": ("[toolchain\n", "GRDR-GATE-0003"),
}


def run_reader(*args):
    return subprocess.run([sys.executable, "-I", str(READER), *args], capture_output=True, text=True, check=False)


def env_file(text):
    """GITHUB_ENV as the runner reads it: KEY=value per line."""
    return dict(line.split("=", 1) for line in text.splitlines())


def run_lines(job):
    for line in job.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            yield stripped


class ReaderTest(unittest.TestCase):
    def read(self, text):
        with tempfile.TemporaryDirectory() as scratch:
            path = pathlib.Path(scratch) / "rust-toolchain.toml"
            path.write_text(text, encoding="utf-8")
            return run_reader(str(path))

    def test_full_table(self):
        result = self.read(FULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(env_file(result.stdout), {
            "RUSTUP_TOOLCHAIN": "1.99.1",
            "TOOLCHAIN_PROFILE": "minimal",
            "TOOLCHAIN_COMPONENTS": "rustfmt,clippy",
            "TOOLCHAIN_TARGETS": "wasm32-unknown-unknown",
        })

    def test_values_left_out_are_empty(self):
        result = self.read('[toolchain]\nchannel = "stable"\n')
        self.assertEqual(env_file(result.stdout), {
            "RUSTUP_TOOLCHAIN": "stable", "TOOLCHAIN_PROFILE": "", "TOOLCHAIN_COMPONENTS": "", "TOOLCHAIN_TARGETS": "",
        })

    def test_the_repository_file(self):
        result = run_reader(str(ROOT / "rust-toolchain.toml"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(env_file(result.stdout)["RUSTUP_TOOLCHAIN"], r"^[0-9]+\.[0-9]+\.[0-9]+$")

    def test_seeded_files_are_refused(self):
        for name, (text, code) in SEEDED.items():
            with self.subTest(case=name):
                result = self.read(text)
                self.assertEqual((result.returncode, result.stdout), (1, ""))
                self.assertIn(code, result.stderr)

    def test_a_missing_file_is_refused(self):
        result = run_reader(str(ROOT / "target" / "no-such-toolchain.toml"))
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertIn("GRDR-GATE-0003", result.stderr)


class WorkflowTest(unittest.TestCase):
    def test_every_rust_job_pins_before_its_first_rustup_or_cargo_line(self):
        checked = 0
        for workflow in WORKFLOWS:
            jobs = workflow.read_text(encoding="utf-8").partition("\njobs:\n")[2]
            for job in JOB_HEADER.split(jobs)[1:]:
                lines = list(run_lines(job))
                rust = [at for at, line in enumerate(lines) if RUST_LINE.search(line)]
                if not rust:
                    continue
                checked += 1
                name = f"{workflow.name} {job.partition(':')[0]}"
                pins = [at for at, line in enumerate(lines) if PIN_LINE.search(line)]
                self.assertTrue(pins and pins[0] < rust[0], name)
                pin_step = "\n".join(lines[pins[0]:pins[0] + 8])
                self.assertIn('>> "$GITHUB_ENV"', pin_step, name)
                for line in lines:
                    if "rustup toolchain install" in line:
                        self.assertIn('rustup toolchain install "$RUSTUP_TOOLCHAIN"', line, name)
        self.assertGreaterEqual(checked, 3)


if __name__ == "__main__":
    unittest.main()

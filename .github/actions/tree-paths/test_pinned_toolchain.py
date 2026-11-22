"""Tests for pinned_toolchain.py and the jobs that use it:
python -I -m unittest discover -s .github/actions/tree-paths -p "test_pinned_toolchain.py" -v

The oracles are rustup's documented toolchain file format (a [toolchain] table with channel,
components, targets, profile or path), the real rust-toolchain.toml, and the workflows: every job
that runs rustup or cargo, on a run line or through an action declared below, calls the pin action
and writes its channel to GITHUB_ENV as RUSTUP_TOOLCHAIN before its first such step, and that
action is the only place the pin is read or installed.
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
PIN_ACTION_FILE = HERE / "action.yml"
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
JOB_HEADER = re.compile(r"^  (?=[a-z][a-z0-9-]*:\s*$)", re.M)
STEP_HEADER = re.compile(r"^      - ", re.M)
USES = re.compile(r"^\s*(?:- )?uses: ([^@\s]+)", re.M)
RUST_LINE = re.compile(r"(?:^|[\s;&|(])(?:rustup|cargo) ")
PIN_ACTION = "$/.github/actions/tree-paths"
PIN_ID = "id: toolchain"
PIN_WRITE_ENV = "CHANNEL: ${{ steps.toolchain.outputs.channel }}"
PIN_WRITE_RUN = 'run: echo "RUSTUP_TOOLCHAIN=$CHANNEL" >> "$GITHUB_ENV"'
STEP_PIN = "RUSTUP_TOOLCHAIN: ${{ env.RUSTUP_TOOLCHAIN }}"

# Every action the workflows use, and whether it runs rustup or cargo. An action missing here fails
# the test, so a new one is classified before it lands.
ACTIONS = {
    "$/.github/actions/pins": False,
    "EmbarkStudios/cargo-deny-action": True,
    "Swatinem/rust-cache": True,
    "actions/attest-build-provenance": False,
    "actions/checkout": False,
    "actions/upload-artifact": False,
    "github/codeql-action/analyze": True,
    "github/codeql-action/init": True,
    "github/codeql-action/upload-sarif": False,
    "google/clusterfuzzlite/actions/build_fuzzers": True,
    "google/clusterfuzzlite/actions/run_fuzzers": True,
    "google/osv-scanner-action/osv-scanner-action": False,
    "googleapis/release-please-action": False,
    "ossf/scorecard-action": False,
    "sigstore/cosign-installer": False,
    "step-security/harden-runner": False,
    "zizmorcore/zizmor-action": False,
}
# The actions above that run cargo in their own container, which takes the pin as step env.
CONTAINER_ACTIONS = {
    "EmbarkStudios/cargo-deny-action",
    "google/clusterfuzzlite/actions/build_fuzzers",
    "google/clusterfuzzlite/actions/run_fuzzers",
}
# The jobs that run rustup or cargo. A job found doing so that is not listed fails, and so does a
# listed job that no longer does.
RUST_JOBS = {
    ("codeql.yml", "analyze"),
    ("dast.yml", "baseline"),
    ("fuzz.yml", "fuzz"),
    ("release-please.yml", "artefacts"),
    ("verify.yml", "deny"),
    ("verify.yml", "rust"),
}

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


def jobs():
    """Each job as (workflow file name, job id, its steps' text in order)."""
    for workflow in WORKFLOWS:
        body = workflow.read_text(encoding="utf-8").partition("\njobs:\n")[2]
        for job in JOB_HEADER.split(body)[1:]:
            steps = STEP_HEADER.split(job.partition("\n    steps:\n")[2])[1:]
            yield workflow.name, job.partition(":")[0], steps


def step_action(step):
    found = USES.search(step)
    return found.group(1) if found else None


def runs_rust(step):
    action = step_action(step)
    if action is not None:
        return action != PIN_ACTION and ACTIONS[action]
    return any(RUST_LINE.search(line) for line in run_lines(step))


class WorkflowTest(unittest.TestCase):
    def test_every_action_is_classified(self):
        used = {step_action(step) for _, _, steps in jobs() for step in steps} - {None, PIN_ACTION}
        self.assertEqual(used - ACTIONS.keys(), set())

    def test_the_jobs_that_run_rust_are_the_declared_ones(self):
        found = {
            (workflow, job) for workflow, job, steps in jobs()
            if any(runs_rust(step) or step_action(step) == PIN_ACTION for step in steps)
        }
        self.assertEqual(found, RUST_JOBS)

    def test_every_rust_job_pins_before_its_first_rust_step(self):
        for workflow, job, steps in jobs():
            if (workflow, job) not in RUST_JOBS:
                continue
            with self.subTest(job=f"{workflow} {job}"):
                rust = [at for at, step in enumerate(steps) if runs_rust(step)]
                pins = [at for at, step in enumerate(steps) if step_action(step) == PIN_ACTION]
                writes = [at for at, step in enumerate(steps) if PIN_WRITE_RUN in step]
                self.assertEqual(len(pins), 1, steps)
                self.assertEqual(writes, [pins[0] + 1], steps)
                self.assertIn(PIN_ID, steps[pins[0]])
                self.assertIn(PIN_WRITE_ENV, steps[writes[0]])
                self.assertTrue(all(writes[0] < at for at in rust), steps)
                for step in steps:
                    if step_action(step) in CONTAINER_ACTIONS:
                        self.assertIn(STEP_PIN, step)

    def test_only_the_pin_action_reads_or_installs_the_toolchain(self):
        for workflow, job, steps in jobs():
            for step in steps:
                self.assertNotIn("pinned_toolchain.py", step, f"{workflow} {job}")
                self.assertNotIn("rustup toolchain install", step, f"{workflow} {job}")
                if "RUSTUP_TOOLCHAIN=" in step:
                    self.assertIn(PIN_WRITE_RUN, step, f"{workflow} {job}")
        action = PIN_ACTION_FILE.read_text(encoding="utf-8")
        self.assertIn('pinned_toolchain.py" rust-toolchain.toml >> "$GITHUB_OUTPUT"', action)
        self.assertIn('rustup toolchain install "$CHANNEL"', action)
        self.assertNotIn("GITHUB_ENV", action.partition("\nruns:\n")[2])


if __name__ == "__main__":
    unittest.main()

"""Tests for pinned_toolchain.py and the jobs that use it:
python -I -m unittest discover -s .github/actions/tree-paths -p "test_pinned_toolchain.py" -v

The oracles are rustup's documented toolchain file format (a [toolchain] table with channel,
components, targets, profile or path), the real rust-toolchain.toml, and the workflows: every job
that runs rustup or cargo, on a run line or through an action declared below, calls the pin action
and writes its channel to GITHUB_ENV as RUSTUP_TOOLCHAIN before its first such step, and that
action is the only place the pin is read or installed. A workflow laid out in a way the job reader
does not read fails, so no job passes by being misread.
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
WORKFLOWS = sorted(
    path for path in (ROOT / ".github" / "workflows").iterdir() if path.suffix.lower() in (".yml", ".yaml")
)
KEY_END = r"[ \t]*:[ \t]*(?:#.*)?$"
JOBS_LINE = re.compile(r"jobs" + KEY_END)
JOB_HEADER = re.compile(r"^  ([\"']?)([A-Za-z_][A-Za-z0-9_-]*)\1" + KEY_END, re.M)
STEPS_LINE = re.compile(r"^    steps" + KEY_END, re.M)
STEP_HEADER = re.compile(r"^      - ", re.M)
STEP_ITEM = re.compile(r"      - [^\s{\[&*!?]")
# A job that calls a reusable workflow in this repository, whose own jobs this test reads.
LOCAL_WORKFLOW_CALL = re.compile(r"    uses:[ \t]+[.$]/\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml[ \t]*(?:#.*)?")
USES = re.compile(r"^[ \t]*(?:-[ \t]+)?uses[ \t]*:\s*([^@\s]+)", re.M)
BLOCK_SCALAR = re.compile(r"[^#]*[:-][ \t]+[|>][1-9+-]{0,2}[ \t]*(?:#.*)?")
QUOTED_KEY = re.compile(r"[ \t]*(?:-[ \t]+)?[\"'][^\"']*[\"'][ \t]*:")
QUOTED_TEXT = re.compile(r"\"(?:[^\"\\]|\\.)*\"|'(?:[^']|'')*'")
# A quoted scalar that runs on past its line, whose next lines would read as keys and steps.
OPEN_QUOTE = re.compile(r"(?:^[ \t]*(?:-[ \t]+)?|:[ \t]+|[\[{,][ \t]*)(?:\"(?:[^\"\\]|\\.)*|'(?:[^']|'')*)$")
# Anchors and aliases, merge keys, tags and explicit keys, each of which can hide a key or a step.
NOT_PLAIN = re.compile(r"(?:^|[\s\[{,])[&*][^\s\]},&*]|<<[ \t]*:|(?:^[ \t]*(?:-[ \t]+)?|:[ \t]+)[!?]")
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
# Job ids of each legal form: letters of either case, digits, '-' and '_'.
JOB_ID_FIXTURE = """name: fixture
jobs:
  build_docs:
    runs-on: ubuntu-26.04
    steps:
      - run: cargo doc --workspace
  Build-2:
    runs-on: ubuntu-26.04
    steps:
      - uses: Swatinem/rust-cache@0000000000000000000000000000000000000000
  _lint:
    runs-on: ubuntu-26.04
    steps:
      - run: rustup show
  plain:
    runs-on: ubuntu-26.04
    steps:
      - run: echo done
"""
# A job that keeps the pin, followed in each header fixture by a job that runs cargo unpinned.
PINNED_JOB = """  pinned:
    runs-on: ubuntu-26.04
    steps:
      - id: toolchain
        uses: $/.github/actions/tree-paths
      - name: Write RUSTUP_TOOLCHAIN to GITHUB_ENV
        env:
          CHANNEL: ${{ steps.toolchain.outputs.channel }}
        run: echo "RUSTUP_TOOLCHAIN=$CHANNEL" >> "$GITHUB_ENV"
      - run: cargo test --workspace
"""
# Key lines YAML reads as a job id, and the id each one names.
JOB_KEY_LINES = {
    "trailing-comment": ("  docs: # the API docs", "docs"),
    "double-quoted": ('  "docs":', "docs"),
    "single-quoted": ("  'docs':", "docs"),
    "space-before-colon": ("  docs :", "docs"),
    "quoted-underscore-capitals-comment": ('  "Build_Docs_2" : # docs', "Build_Docs_2"),
}
# Layouts the job reader does not read, each in a job that runs rustup or cargo unpinned.
UNREAD_LAYOUTS = {
    "jobs-indented-four": "jobs:\n    docs:\n      steps:\n        - run: cargo doc\n",
    "escaped-job-key": 'jobs:\n  "d\\x6fcs":\n    steps:\n      - run: cargo doc\n',
    "top-level-key-after-jobs": "jobs:\n  docs:\n    steps:\n      - run: echo\nenv:\n  A: b\n",
    "steps-at-four": "jobs:\n  docs:\n    steps:\n    - run: cargo doc\n",
    "steps-at-seven": "jobs:\n  docs:\n    steps:\n       - run: cargo doc\n",
    "quoted-steps-key": "jobs:\n  docs:\n    'steps':\n      - run: cargo doc\n",
    "steps-in-flow": "jobs:\n  docs:\n    steps: [{run: cargo doc}]\n",
    "step-in-flow": "jobs:\n  docs:\n    steps:\n      - {uses: Swatinem/rust-cache@0}\n",
    "step-two-spaces-after-dash": "jobs:\n  docs:\n    steps:\n      -   uses: Swatinem/rust-cache@0\n",
    "quoted-uses-key": 'jobs:\n  docs:\n    steps:\n      - "uses": Swatinem/rust-cache@0\n',
    "explicit-uses-key": "jobs:\n  docs:\n    steps:\n      - name: x\n        ? uses\n        : Swatinem/rust-cache@0\n",
    "tagged-uses-key": "jobs:\n  docs:\n    steps:\n      - name: x\n        !!str uses: Swatinem/rust-cache@0\n",
    "alias-step": "jobs:\n  docs:\n    steps:\n      - &cargo\n        run: cargo doc\n  other:\n    steps:\n      - *cargo\n",
    "merge-key": "jobs:\n  docs:\n    steps:\n      - <<: {run: cargo doc}\n",
    "no-jobs-line": '"jobs":\n  docs:\n    steps:\n      - run: cargo doc\n',
    "remote-reusable-workflow": "jobs:\n  docs:\n    uses: example/rust/.github/workflows/docs.yml@0\n",
    "quoted-scalar-over-lines": 'jobs:\n  docs:\n    name: "docs\n    steps:\n      - run: x"\n    steps:\n      - run: cargo doc\n',
    "quoted-scalar-over-lines-before-jobs": 'env:\n  A: "a\njobs:\n  docs:\n    steps:\n      - run: x"\n',
    "quoted-key-beside-block-scalar": 'jobs:\n  docs:\n    steps:\n      - run: |\n          echo\n        "uses": Swatinem/rust-cache@0\n',
}
LOCAL_WORKFLOW_CALL_FIXTURE = "name: fixture\njobs:\n  docs:\n    uses: ./.github/workflows/docs.yml\n"

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


def after_jobs_line(text):
    lines = text.splitlines(keepends=True)
    found = (at for at, line in enumerate(lines) if JOBS_LINE.fullmatch(line.rstrip("\n")))
    return "".join(lines[next(found, len(lines)) + 1:])


def jobs_in(name, text):
    """Each job of one workflow as (workflow file name, job id, its steps' text in order)."""
    section = after_jobs_line(text)
    headers = list(JOB_HEADER.finditer(section))
    ends = [header.start() for header in headers[1:]] + [len(section)]
    for header, end in zip(headers, ends):
        parts = STEPS_LINE.split(section[header.end():end], maxsplit=1)
        steps = STEP_HEADER.split(parts[1])[1:] if len(parts) == 2 else []
        yield name, header.group(2), steps


def structure_lines(text):
    """(line number, indent, line) of each line YAML reads as structure, skipping blank lines,
    comments and the text of block scalars."""
    scalar_key_column = None
    for number, line in enumerate(text.splitlines(), 1):
        content = line.lstrip(" ")
        indent = len(line) - len(content)
        if scalar_key_column is not None and (not content.strip() or indent > scalar_key_column):
            continue
        is_opener = BLOCK_SCALAR.fullmatch(line)
        scalar_key_column = len(line) - len(line.lstrip(" -")) if is_opener else None
        if content.strip() and not content.startswith("#"):
            yield number, indent, line


def is_plain(line):
    """No anchor, alias, merge key, tag, explicit key or quoted scalar that runs past the line."""
    return not (NOT_PLAIN.search(QUOTED_TEXT.sub('""', line)) or OPEN_QUOTE.search(line))


def unread_lines(text):
    """The lines of a workflow that jobs_in would misread, so a layout it cannot read fails.

    jobs_in reads plain block YAML: one jobs: line with no top-level key after it, each job a key
    at two spaces, steps: at four and each step at six, and no quoted key but a job id.
    """
    lines = list(structure_lines(text))
    jobs_at = [at for at, (_, _, line) in enumerate(lines) if JOBS_LINE.fullmatch(line)]
    if len(jobs_at) != 1:
        return [(0, "no single jobs: line")]
    section = lines[jobs_at[0] + 1:]
    job_headers = {number for number, _, line in section if JOB_HEADER.fullmatch(line)}
    unread = [(number, line) for number, _, line in lines
              if not is_plain(line) or (number not in job_headers and QUOTED_KEY.match(line))]
    if section and section[0][0] not in job_headers:
        unread.append((section[0][0], section[0][2]))
    in_steps = False
    for number, indent, line in section:
        if indent < 4:
            in_steps = False
            readable = number in job_headers
        elif indent == 4:
            in_steps = bool(STEPS_LINE.fullmatch(line))
            readable = (in_steps or LOCAL_WORKFLOW_CALL.fullmatch(line)
                        or not line.lstrip().startswith(("steps", "uses", "-")))
        else:
            readable = not in_steps or indent > 7 or STEP_ITEM.match(line)
        if not readable:
            unread.append((number, line))
    return unread


def jobs():
    for workflow in WORKFLOWS:
        yield from jobs_in(workflow.name, workflow.read_text(encoding="utf-8"))


def step_action(step):
    found = USES.search(step)
    return found.group(1) if found else None


def runs_rust(step):
    action = step_action(step)
    if action is not None:
        return action != PIN_ACTION and ACTIONS[action]
    return any(RUST_LINE.search(line) for line in run_lines(step))


def pin_problems(steps):
    """What breaks the pin rule in a job that runs rustup or cargo; empty when the job keeps it."""
    pins = [at for at, step in enumerate(steps) if step_action(step) == PIN_ACTION]
    if len(pins) != 1:
        return [f"{len(pins)} calls of the pin action"]
    pin = pins[0]
    writes = [at for at, step in enumerate(steps) if PIN_WRITE_RUN in step]
    problems = []
    if PIN_ID not in steps[pin]:
        problems.append("the pin step has no id toolchain")
    if writes != [pin + 1]:
        problems.append("RUSTUP_TOOLCHAIN is not written once, in the step after the pin")
    elif PIN_WRITE_ENV not in steps[pin + 1]:
        problems.append("the write step does not take the pin's channel")
    problems += [f"step {at} runs rustup or cargo before the write" for at, step in enumerate(steps)
                 if at <= pin + 1 and runs_rust(step)]
    problems += [f"step {at} runs a container action without the pin" for at, step in enumerate(steps)
                 if step_action(step) in CONTAINER_ACTIONS and STEP_PIN not in step]
    return problems


class WorkflowTest(unittest.TestCase):
    def test_every_legal_job_id_is_found(self):
        found = {(job, any(map(runs_rust, steps))) for _, job, steps in jobs_in("fixture.yml", JOB_ID_FIXTURE)}
        self.assertEqual(found, {("build_docs", True), ("Build-2", True), ("_lint", True), ("plain", False)})

    def test_an_unpinned_job_is_found_whatever_its_key_line(self):
        for name, (key_line, job_id) in JOB_KEY_LINES.items():
            with self.subTest(case=name):
                text = f"name: fixture\njobs:\n{PINNED_JOB}{key_line}\n    steps:\n      - run: cargo doc --workspace\n"
                found = {job: steps for _, job, steps in jobs_in("fixture.yml", text)}
                self.assertEqual(set(found), {"pinned", job_id})
                self.assertEqual(pin_problems(found["pinned"]), [])
                self.assertNotEqual(pin_problems(found[job_id]), [])
                self.assertEqual(unread_lines(text), [])

    def test_a_uses_key_is_read_however_it_is_spaced(self):
        for step in ("uses: Swatinem/rust-cache@0", "uses:   Swatinem/rust-cache@0",
                     "-   uses : Swatinem/rust-cache@0", "uses:\n          Swatinem/rust-cache@0"):
            with self.subTest(step=step):
                self.assertEqual(step_action(step), "Swatinem/rust-cache")

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
                self.assertEqual(pin_problems(steps), [], steps)

    def test_every_workflow_has_the_layout_the_reader_reads(self):
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow.name):
                self.assertEqual(unread_lines(workflow.read_text(encoding="utf-8")), [])

    def test_a_layout_the_reader_does_not_read_is_refused(self):
        for name, jobs_section in UNREAD_LAYOUTS.items():
            with self.subTest(case=name):
                self.assertNotEqual(unread_lines(f"name: fixture\n{jobs_section}"), [])
        self.assertEqual(unread_lines(LOCAL_WORKFLOW_CALL_FIXTURE), [])

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
        self.assertIn("RUSTUP_TOOLCHAIN: ${{ steps.read.outputs.RUSTUP_TOOLCHAIN }}", action)
        self.assertNotIn("GITHUB_ENV", action.partition("\nruns:\n")[2])


if __name__ == "__main__":
    unittest.main()

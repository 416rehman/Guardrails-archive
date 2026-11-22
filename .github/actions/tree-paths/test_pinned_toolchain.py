"""Tests for pinned_toolchain.py and the jobs that use it:
python -I -m unittest discover -s .github/actions/tree-paths -p "test_pinned_toolchain.py" -v

The oracles are rustup's documented toolchain file format (a [toolchain] table with channel,
components, targets, profile or path), git's own objects for each fixture commit, the real
rust-toolchain.toml, and the workflows read as YAML reads them. Every job that checks out the
repository calls the pin action in the step after its checkout and writes the channel to
GITHUB_ENV as RUSTUP_TOOLCHAIN in the step after that, nothing in a workflow overrides that
toolchain, and the pin action is the only place the pin is read or installed. The reader takes a
small part of YAML and refuses the rest, so no workflow it cannot read passes.
"""

import dataclasses
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

PIN_ACTION = "$/.github/actions/tree-paths"
PIN_KEYS = {"id", "uses", "with"}
PIN_INPUTS = {"install"}
PIN_ID = "toolchain"
WRITE_STEP = {
    "name": "Write RUSTUP_TOOLCHAIN to GITHUB_ENV",
    "shell": "bash",
    "run": 'echo "RUSTUP_TOOLCHAIN=${CHANNEL:?}" >> "$GITHUB_ENV"',
}
WRITE_ENV = {"CHANNEL": "${{ steps.toolchain.outputs.channel }}"}
STEP_PIN = ("RUSTUP_TOOLCHAIN", "${{ env.RUSTUP_TOOLCHAIN }}")
LOCAL_WORKFLOW = re.compile(r"[.$]/\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml")
BLOCK_SCALAR = "<block scalar>"

CHECKS_OUT = "checks out the repository"
RUNS_CARGO_IN_A_CONTAINER = "runs cargo in its own container, which takes the pin as step env"
# What each action the workflows use does that the pin cares about. An action missing here fails
# the test, so a new one is classified before it lands.
ACTIONS = {
    "$/.github/actions/pins": None,
    "EmbarkStudios/cargo-deny-action": RUNS_CARGO_IN_A_CONTAINER,
    "Swatinem/rust-cache": None,
    "actions/attest-build-provenance": None,
    "actions/checkout": CHECKS_OUT,
    "actions/upload-artifact": None,
    "github/codeql-action/analyze": None,
    "github/codeql-action/init": None,
    "github/codeql-action/upload-sarif": None,
    "google/clusterfuzzlite/actions/build_fuzzers": RUNS_CARGO_IN_A_CONTAINER,
    "google/clusterfuzzlite/actions/run_fuzzers": RUNS_CARGO_IN_A_CONTAINER,
    "google/osv-scanner-action/osv-scanner-action": None,
    "googleapis/release-please-action": None,
    "ossf/scorecard-action": None,
    "sigstore/cosign-installer": None,
    "step-security/harden-runner": None,
    "zizmorcore/zizmor-action": None,
}

PRINTABLE = re.compile(r"[ -~]*")
WORD_KEY = r"[A-Za-z_][A-Za-z0-9_-]*"
KEY_LINE = re.compile(rf"(?P<key>{WORD_KEY}|\"{WORD_KEY}\"|'{WORD_KEY}') *:(?: +(?P<rest>.*))?")
BLOCK_INDICATOR = re.compile(r"[|>][+-]?(?: +#.*)?")
SINGLE_QUOTED = re.compile(r"'((?:[^']|'')*)'(?: +#.*)?")
DOUBLE_QUOTED = re.compile(r'"([^"\\]*)"(?: +#.*)?')
FLOW_OF_WORDS = re.compile(r"\[[A-Za-z0-9_., -]*\]|\{\}")
PLAIN_START = re.compile(r"[^-?:,\[\]{}#&*!|>'\"%@`]|[-?:][^ ]")
# A toolchain chosen past RUSTUP_TOOLCHAIN: a +toolchain argument to a rustup proxy, or a rustup
# command that installs, runs, links or sets one. Quotes, backslashes and line breaks may sit between
# the words, as in a folded scalar or a continued shell line; a word followed by ':' is a YAML key.
TOOLCHAIN_OVERRIDE = re.compile(
    r"\b(?:cargo|rust[a-z-]*|clippy-driver)(?:\.exe)?[\s\\\"']+\+"
    r"|\brustup(?:\.exe)?[\s\\\"']+(?:run|default|override|toolchain[\s\\\"']+(?:link|install))(?![\w:-])",
    re.I,
)
RUSTUP_VARIABLE = re.compile(r"rustup_(?:toolchain|home)", re.I)

FULL = """[toolchain]
channel = "1.99.1"
components = ["rustfmt", "clippy"]
targets = ["wasm32-unknown-unknown"]
profile = "minimal"
"""
OTHER_CHANNEL = '[toolchain]\nchannel = "1.70.0"\n'

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
    "not-utf-8": ("[toolchain]\nchannel = \"1.99.1\"\n# \udcff\n", "GRDR-GATE-0003"),
}

CHECKOUT = (
    "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n"
    "        with:\n"
    "          persist-credentials: false\n"
)
PIN = "      - id: toolchain\n        uses: $/.github/actions/tree-paths\n"
WRITE = (
    "      - name: Write RUSTUP_TOOLCHAIN to GITHUB_ENV\n"
    "        shell: bash\n"
    "        env:\n"
    "          CHANNEL: ${{ steps.toolchain.outputs.channel }}\n"
    '        run: echo "RUSTUP_TOOLCHAIN=${CHANNEL:?}" >> "$GITHUB_ENV"\n'
)
CARGO = "      - run: cargo test --workspace\n"
PINNED = CHECKOUT + PIN + WRITE
LOCAL_WORKFLOW_CALL = "name: fixture\non: push\njobs:\n  docs:\n    uses: ./.github/workflows/docs.yml\n"

# Key lines YAML reads as a job id, and the id each one names.
JOB_KEY_LINES = {
    "trailing-comment": ("  docs: # the API docs", "docs"),
    "double-quoted": ('  "docs":', "docs"),
    "single-quoted": ("  'docs':", "docs"),
    "space-before-colon": ("  docs :", "docs"),
    "underscore-and-capitals": ("  Build_Docs_2:", "Build_Docs_2"),
    "quoted-underscore-capitals-comment": ('  "Build_Docs_2" : # docs', "Build_Docs_2"),
}
# Jobs that check out the repository and do not keep the pin, whatever their steps run.
UNPINNED = {
    "plain-cargo": CHECKOUT + CARGO,
    "no-cargo-at-all": CHECKOUT + "      - run: make docs\n",
    "cargo-by-path": CHECKOUT + "      - run: $HOME/.cargo/bin/cargo doc\n",
    "folded-cargo": CHECKOUT + "      - run: >-\n          cargo\n          doc --workspace\n",
    "cargo-from-python": CHECKOUT + "      - run: python3 -c \"import subprocess; subprocess.run(['cargo', 'doc'])\"\n",
    "checkout-through-a-quoted-key": '      - "uses": actions/checkout@0\n' + CARGO,
    "checkout-with-spaces-around-the-colon": "      - uses :   actions/checkout@0\n" + CARGO,
    "step-before-the-pin": CHECKOUT + CARGO + PIN + WRITE,
    "pin-without-the-write": CHECKOUT + PIN + CARGO,
    "write-without-the-pin": CHECKOUT + WRITE + CARGO,
    "pin-before-the-checkout": PIN + WRITE + CHECKOUT + CARGO,
}
# Jobs that keep the pin's steps, but something else in the workflow picks the toolchain.
DEFEATED = {
    "plus-toolchain": PINNED + "      - run: cargo +stable test\n",
    "plus-toolchain-quoted": PINNED + "      - run: cargo '+stable' test\n",
    "plus-toolchain-folded": PINNED + "      - run: >-\n          cargo\n          +stable test\n",
    "plus-toolchain-continued": PINNED + "      - run: |\n          cargo \\\n            +stable test\n",
    "plus-toolchain-upper-case": PINNED + "      - run: CARGO.EXE +stable test\n",
    "plus-toolchain-rustc": PINNED + "      - run: rustc +nightly -vV\n",
    "rustup-run": PINNED + "      - run: rustup run stable cargo test\n",
    "rustup-default": PINNED + "      - run: rustup default stable\n",
    "rustup-override": PINNED + "      - run: rustup override set stable\n",
    "rustup-toolchain-link": PINNED + "      - run: rustup toolchain link local ./tc\n",
    "rustup-toolchain-install": PINNED + "      - run: rustup toolchain install stable\n",
    "step-env": PINNED + "      - env:\n          RUSTUP_TOOLCHAIN: stable\n        run: cargo test\n",
    "step-env-lower-case": PINNED + "      - env:\n          rustup_toolchain: stable\n        run: cargo test\n",
    "step-env-rustup-home": PINNED + "      - env:\n          RUSTUP_HOME: ./rustup\n        run: cargo test\n",
    "run-line-export": PINNED + "      - run: export RUSTUP_TOOLCHAIN=stable && cargo test\n",
    "heredoc-write": PINNED + "      - run: |\n          cat >> \"$GITHUB_ENV\" <<EOF\n          RUSTUP_TOOLCHAIN=stable\n          EOF\n",
    "continue-on-error-on-the-pin": CHECKOUT + PIN + "        continue-on-error: true\n" + WRITE + CARGO,
    "continue-on-error-on-the-write": PINNED + "        continue-on-error: true\n" + CARGO,
    "if-on-the-pin": CHECKOUT + PIN + "        if: false\n" + WRITE + CARGO,
    "if-on-the-write": PINNED + "        if: false\n" + CARGO,
    "env-on-the-pin": CHECKOUT + PIN + "        env:\n          GIT_DIR: other/.git\n" + WRITE + CARGO,
    "unknown-pin-input": CHECKOUT + PIN + "        with:\n          path: other\n" + WRITE + CARGO,
    "pin-id-is-a-prefix": CHECKOUT + PIN.replace("id: toolchain", "id: toolchain2") + WRITE + CARGO,
    "pin-in-a-heredoc": CHECKOUT
    + "      - id: toolchain\n        run: |\n          cat > /dev/null <<'EOF'\n"
    "          uses: $/.github/actions/tree-paths\n          EOF\n" + WRITE + CARGO,
    "write-without-the-empty-check": CHECKOUT + PIN + WRITE.replace("${CHANNEL:?}", "$CHANNEL") + CARGO,
    "write-in-another-shell": CHECKOUT + PIN + WRITE.replace("shell: bash", "shell: cmd") + CARGO,
    "write-of-another-output": CHECKOUT + PIN + WRITE.replace("outputs.channel", "outputs.other") + CARGO,
    "container-action-without-the-pin": PINNED + "      - uses: EmbarkStudios/cargo-deny-action@0\n",
    "unclassified-action": PINNED + "      - uses: dtolnay/rust-toolchain@0\n",
}
DEFEATED_BY_ENV = {
    "job-env": ("", "    env:\n      RUSTUP_TOOLCHAIN: stable\n"),
    "job-env-from-the-pin-form": ("", "    env:\n      RUSTUP_TOOLCHAIN: ${{ env.RUSTUP_TOOLCHAIN }}\n"),
    "workflow-env": ("env:\n  RUSTUP_TOOLCHAIN: stable\n", ""),
    "workflow-rustup-home": ("env:\n  RUSTUP_HOME: ./rustup\n", ""),
}
# Workflows the reader does not read, each holding a job that checks out without the pin.
UNREADABLE = {
    **{
        f"line-break-{name}": f"    steps: # c{char}    a: |\n      - {{uses: actions/checkout@0}}\n"
        for name, char in {"NEL": "\x85", "LS": "\u2028", "PS": "\u2029", "FS": "\x1c", "VT": "\x0b"}.items()
    },
    "tab": "    steps:\n      - run: cargo\tdoc\n",
    "carriage-return": "    steps:\r\n      - uses: actions/checkout@0\n",
    "escaped-line-break": '    name: "docs\\\n      more"\n    steps:\n      - uses: actions/checkout@0\n',
    "quoted-scalar-over-lines": '    name: "docs\n    steps:\n      - run: x"\n    steps:\n      - uses: actions/checkout@0\n',
    "escape-in-a-quoted-scalar": '    steps:\n      - uses: "actions/checkout@0\\x20"\n',
    "flow-step": "    steps:\n      - {uses: actions/checkout@0}\n",
    "flow-steps": "    steps: [{uses: actions/checkout@0}]\n",
    "anchor-and-alias": "    steps:\n      - &out\n        uses: actions/checkout@0\n      - *out\n",
    "alias-value": "    steps:\n      - uses: *out\n",
    "tag": "    steps:\n      - !!map\n        uses: actions/checkout@0\n",
    "explicit-key": "    steps:\n      - ? uses\n        : actions/checkout@0\n",
    "merge-key": "    steps:\n      - <<: {uses: actions/checkout@0}\n",
    "steps-at-the-key-indent": "    steps:\n    - uses: actions/checkout@0\n",
    "dash-alone": "    steps:\n      -\n        uses: actions/checkout@0\n",
    "spaces-after-the-dash": "    steps:\n      -   uses: actions/checkout@0\n",
    "plain-scalar-over-lines": "    steps:\n      - name: x\n          uses: actions/checkout@0\n",
    "repeated-key": "    steps:\n      - uses: actions/upload-artifact@0\n        uses: actions/checkout@0\n",
    "second-document": "    steps:\n      - run: x\n---\njobs:\n  docs:\n    steps:\n      - uses: actions/checkout@0\n",
    "remote-reusable-workflow": "    uses: example/rust/.github/workflows/docs.yml@0\n",
}


@dataclasses.dataclass
class Line:
    number: int
    indent: int
    text: str
    item: bool


@dataclasses.dataclass
class Node:
    number: int
    key: str | None
    value: str | None
    children: list


class Unreadable(Exception):
    pass


def run_reader(rev, cwd):
    return subprocess.run(
        [sys.executable, "-I", "-B", str(READER), rev], cwd=cwd, capture_output=True, text=True, check=False,
    )


def git(repository, *args, stdin=b""):
    return subprocess.run(
        ["git", "-C", str(repository), *args], input=stdin, capture_output=True, check=True,
    ).stdout.decode("utf-8").strip()


def commit_files(repository, files):
    """A commit whose tree holds exactly these files, made from git objects with no working tree."""
    entries = []
    for name, text in sorted(files.items()):
        blob = git(repository, "hash-object", "-w", "--stdin", stdin=text.encode("utf-8", "surrogateescape"))
        entries.append(f"100644 blob {blob}\t{name}\n")
    tree = git(repository, "mktree", stdin="".join(entries).encode("utf-8"))
    return git(repository, "-c", "user.name=fixture", "-c", "user.email=fixture@example.test",
               "commit-tree", tree, "-m", "fixture")


def new_repository(scratch):
    repository = pathlib.Path(scratch) / "repository"
    repository.mkdir()
    git(repository, "init", "-q")
    return repository


def env_file(text):
    """GITHUB_ENV or GITHUB_OUTPUT as the runner reads it: KEY=value per line."""
    return dict(line.split("=", 1) for line in text.splitlines())


def lines_of(text):
    """The lines YAML reads as structure, splitting each "- " into an item and the line after it.

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
        if content == "-" or content.startswith(("-  ", "- - ")):
            raise Unreadable(f"line {number}: a sequence item laid out another way")
        if content.startswith("- "):
            yield Line(number, indent, "", True)
            content, indent = content[2:], indent + 2
        key_line = KEY_LINE.fullmatch(content)
        if key_line and key_line["rest"] and BLOCK_INDICATOR.fullmatch(key_line["rest"]):
            text_deeper_than = indent
        yield Line(number, indent, content, False)


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
    """The nodes of the block that starts at lines[at] at this indent, and where it ends."""
    nodes = []
    while at < len(lines) and lines[at].indent == indent:
        if lines[at].item:
            node, at = parse_item(lines, at + 1, indent + 2, lines[at].number)
        else:
            node, at = parse_entry(lines, at, indent)
        nodes.append(node)
    if at < len(lines) and lines[at].indent > indent:
        raise Unreadable(f"line {lines[at].number}: indented where nothing opens a block")
    keys = [node.key for node in nodes]
    if None in keys and keys != [None] * len(keys):
        raise Unreadable(f"line {nodes[0].number}: sequence items and keys in one block")
    if len({key for key in keys if key is not None}) != len(keys) - keys.count(None):
        raise Unreadable(f"line {nodes[0].number}: a key repeated in one mapping")
    return nodes, at


def parse_item(lines, at, indent, number):
    first = lines[at]
    if KEY_LINE.fullmatch(first.text) is None:
        value = scalar(first.text, first.number)
        if value == BLOCK_SCALAR:
            raise Unreadable(f"line {number}: a block scalar as a sequence item")
        return Node(number, None, value, []), at + 1
    children, at = parse_block(lines, at, indent)
    return Node(number, None, None, children), at


def parse_entry(lines, at, indent):
    line = lines[at]
    key_line = KEY_LINE.fullmatch(line.text)
    if key_line is None:
        raise Unreadable(f"line {line.number}: not a key the reader reads")
    key, rest = key_line["key"].strip("'\""), key_line["rest"]
    at += 1
    if rest and not rest.startswith("#"):
        return Node(line.number, key, scalar(rest, line.number), []), at
    if at < len(lines) and lines[at].indent > indent:
        children, at = parse_block(lines, at, lines[at].indent)
        return Node(line.number, key, None, children), at
    return Node(line.number, key, "", []), at


def parse(text):
    lines = list(lines_of(text))
    nodes, at = parse_block(lines, 0, 0)
    if at != len(lines):
        raise Unreadable(f"line {lines[at].number}: indented out of place")
    return nodes


def mapping(node, number):
    if node.value is not None or any(child.key is None for child in node.children):
        raise Unreadable(f"line {number}: {node.key or 'an item'} is not a mapping")
    return {child.key: child for child in node.children}


def jobs_of(nodes):
    """Each job as (job id, its keys, its steps' keys in order)."""
    root = {node.key: node for node in nodes}
    if "jobs" not in root or None in root:
        raise Unreadable("no jobs mapping at the top level")
    for job in mapping(root["jobs"], root["jobs"].number).values():
        keys = mapping(job, job.number)
        steps = keys["steps"].children if "steps" in keys else []
        if any(step.key is not None for step in steps):
            raise Unreadable(f"line {job.number}: {job.key} has steps that are not a sequence")
        yield job.key, keys, [mapping(step, step.number) for step in steps]


def action_of(step):
    uses = step.get("uses")
    return None if uses is None else (uses.value or BLOCK_SCALAR).partition("@")[0]


def values_of(node):
    return {} if node is None else {child.key: child.value for child in mapping(node, node.number).values()}


def pin_step_problems(job_id, step):
    problems = [f"{job_id}: the pin step has {key}" for key in sorted(set(step) - PIN_KEYS)]
    if (step.get("id") and step["id"].value) != PIN_ID or (step.get("uses") and step["uses"].value) != PIN_ACTION:
        problems.append(f"{job_id}: the step after the checkout is not the pin action with id {PIN_ID}")
    problems += [f"{job_id}: the pin step takes {key}" for key in sorted(set(values_of(step.get("with"))) - PIN_INPUTS)]
    return problems


def write_step_problems(job_id, step, allowed_lines):
    written = {key: node.value for key, node in step.items() if key != "env"}
    if written != WRITE_STEP or set(step) - set(WRITE_STEP) != {"env"} or values_of(step["env"]) != WRITE_ENV:
        return [f"{job_id}: the step after the pin does not write its channel as RUSTUP_TOOLCHAIN"]
    allowed_lines.update((step["name"].number, step["run"].number))
    return []


def job_problems(job_id, job, steps, allowed_lines):
    if "uses" in job:
        called = job["uses"].value or ""
        return [] if LOCAL_WORKFLOW.fullmatch(called) else [f"{job_id}: calls a workflow outside this repository"]
    actions = [action_of(step) for step in steps]
    unknown = sorted({action for action in actions if action not in ACTIONS and action not in (None, PIN_ACTION)})
    if unknown:
        return [f"{job_id}: {action} is not classified in ACTIONS" for action in unknown]
    problems = []
    for step, action in zip(steps, actions):
        if ACTIONS.get(action) != RUNS_CARGO_IN_A_CONTAINER:
            continue
        pinned = mapping(step["env"], step["env"].number).get(STEP_PIN[0]) if "env" in step else None
        if pinned is None or pinned.value != STEP_PIN[1]:
            problems.append(f"{job_id}: {action} does not take the pin as step env")
        else:
            allowed_lines.add(pinned.number)
    checkouts = [at for at, action in enumerate(actions) if ACTIONS.get(action) == CHECKS_OUT]
    if not checkouts:
        return problems
    pin_at = checkouts[0] + 1
    if pin_at + 1 >= len(steps):
        return problems + [f"{job_id}: checks out and does not pin the toolchain in the next two steps"]
    return (problems + pin_step_problems(job_id, steps[pin_at])
            + write_step_problems(job_id, steps[pin_at + 1], allowed_lines))


def workflow_problems(text):
    """Why a workflow does not keep the pin in every job that checks out; empty when it does."""
    try:
        jobs = list(jobs_of(parse(text)))
        allowed_lines = set()
        problems = [problem for job_id, job, steps in jobs for problem in job_problems(job_id, job, steps, allowed_lines)]
    except Unreadable as error:
        return [str(error)]
    problems += [f"chooses a toolchain past the pin: {found[0]!r}" for found in TOOLCHAIN_OVERRIDE.finditer(text)]
    problems += [
        f"line {number}: sets RUSTUP_TOOLCHAIN or RUSTUP_HOME outside the pin"
        for number, line in enumerate(text.split("\n"), 1)
        if RUSTUP_VARIABLE.search(line) and number not in allowed_lines
    ]
    return problems


def fixture(steps, key_line="  docs:", job_lines="", top_lines=""):
    return f"name: fixture\non: push\n{top_lines}jobs:\n{key_line}\n    runs-on: ubuntu-26.04\n{job_lines}    steps:\n{steps}"


class ReaderTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.repository = new_repository(scratch.name)

    def read(self, files):
        return run_reader(commit_files(self.repository, files), self.repository)

    def test_full_table(self):
        result = self.read({"rust-toolchain.toml": FULL})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(env_file(result.stdout), {
            "RUSTUP_TOOLCHAIN": "1.99.1",
            "TOOLCHAIN_PROFILE": "minimal",
            "TOOLCHAIN_COMPONENTS": "rustfmt,clippy",
            "TOOLCHAIN_TARGETS": "wasm32-unknown-unknown",
        })

    def test_values_left_out_are_empty(self):
        result = self.read({"rust-toolchain.toml": '[toolchain]\nchannel = "stable"\n'})
        self.assertEqual(env_file(result.stdout), {
            "RUSTUP_TOOLCHAIN": "stable", "TOOLCHAIN_PROFILE": "", "TOOLCHAIN_COMPONENTS": "", "TOOLCHAIN_TARGETS": "",
        })

    def test_the_repository_file(self):
        result = run_reader("HEAD", ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(env_file(result.stdout)["RUSTUP_TOOLCHAIN"], r"^[0-9]+\.[0-9]+\.[0-9]+$")

    def test_seeded_files_are_refused(self):
        for name, (text, code) in SEEDED.items():
            with self.subTest(case=name):
                result = self.read({"rust-toolchain.toml": text})
                self.assertEqual((result.returncode, result.stdout), (1, ""))
                self.assertIn(code, result.stderr)

    def test_a_commit_without_the_file_is_refused(self):
        result = self.read({"rust-toolchain": FULL, "rust-toolchain.toml.orig": FULL})
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertIn("GRDR-GATE-0003", result.stderr)

    def test_an_unknown_revision_is_refused(self):
        result = run_reader("0" * 40, self.repository)
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertIn("GRDR-GATE-0003", result.stderr)

    def test_the_working_tree_does_not_change_the_channel(self):
        commit = commit_files(self.repository, {"rust-toolchain.toml": FULL})
        git(self.repository, "update-ref", "HEAD", commit)
        (self.repository / "rust-toolchain.toml").write_text(OTHER_CHANNEL, encoding="utf-8")
        (self.repository / "rust-t~1.tom").write_text(OTHER_CHANNEL, encoding="utf-8")
        result = run_reader("HEAD", self.repository)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(env_file(result.stdout)["RUSTUP_TOOLCHAIN"], "1.99.1")

    def test_a_replacement_ref_is_refused(self):
        pinned = commit_files(self.repository, {"rust-toolchain.toml": FULL})
        other = commit_files(self.repository, {"rust-toolchain.toml": OTHER_CHANNEL})
        git(self.repository, "replace", pinned, other)
        self.assertNotEqual(git(self.repository, "rev-parse", f"{pinned}^{{tree}}"),
                            git(self.repository, "--no-replace-objects", "rev-parse", f"{pinned}^{{tree}}"))
        result = run_reader(pinned, self.repository)
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertIn("GRDR-GATE-0007", result.stderr)


class WorkflowTest(unittest.TestCase):
    def test_every_workflow_keeps_the_pin(self):
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow.name):
                self.assertEqual(workflow_problems(workflow.read_bytes().decode("ascii", "replace")), [])

    def test_a_pinned_job_passes(self):
        self.assertEqual(workflow_problems(fixture(PINNED + CARGO)), [])
        self.assertEqual(workflow_problems(fixture(PINNED + "      - name: Show rustup\n        run: rustup show\n")), [])
        self.assertEqual(workflow_problems(fixture("      - run: cargo doc\n")), [])
        self.assertEqual(workflow_problems(LOCAL_WORKFLOW_CALL), [])

    def test_a_job_is_read_whatever_its_key_line(self):
        for name, (key_line, job_id) in JOB_KEY_LINES.items():
            with self.subTest(case=name):
                pinned = fixture(PINNED + CARGO, key_line="  pinned:") + f"{key_line}\n    steps:\n"
                self.assertEqual(workflow_problems(pinned + PINNED), [])
                problems = workflow_problems(pinned + CHECKOUT + CARGO)
                self.assertEqual(len(problems), 1, problems)
                self.assertTrue(problems[0].startswith(f"{job_id}: "), problems)

    def test_a_job_that_checks_out_without_the_pin_is_refused(self):
        for name, steps in UNPINNED.items():
            with self.subTest(case=name):
                self.assertNotEqual(workflow_problems(fixture(steps)), [])

    def test_a_pin_that_something_else_overrides_is_refused(self):
        for name, steps in DEFEATED.items():
            with self.subTest(case=name):
                self.assertNotEqual(workflow_problems(fixture(steps)), [])
        for name, (top_lines, job_lines) in DEFEATED_BY_ENV.items():
            with self.subTest(case=name):
                self.assertNotEqual(workflow_problems(fixture(PINNED + CARGO, job_lines=job_lines, top_lines=top_lines)), [])

    def test_a_workflow_the_reader_does_not_read_is_refused(self):
        for name, job in UNREADABLE.items():
            with self.subTest(case=name):
                problems = workflow_problems(f"name: fixture\non: push\njobs:\n  docs:\n{job}")
                self.assertNotEqual(problems, [])

    def test_only_the_pin_action_reads_or_installs_the_toolchain(self):
        for workflow in WORKFLOWS:
            self.assertNotIn("pinned_toolchain.py", workflow.read_text(encoding="utf-8"), workflow.name)
        action = PIN_ACTION_FILE.read_text(encoding="utf-8")
        self.assertIn('pinned_toolchain.py" HEAD >> "$GITHUB_OUTPUT"', action)
        self.assertIn('rustup toolchain install "$CHANNEL"', action)
        self.assertIn("RUSTUP_TOOLCHAIN: ${{ steps.read.outputs.RUSTUP_TOOLCHAIN }}", action)
        self.assertNotIn("GITHUB_ENV", action.partition("\nruns:\n")[2])


if __name__ == "__main__":
    unittest.main()

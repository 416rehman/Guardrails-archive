"""Tests for pinned_toolchain.py and the workflows and local actions that use it:
python -I -m unittest discover -s .github/actions/tree-paths -p "test_pinned_toolchain.py" -v

The oracles are rustup's documented toolchain file format (a [toolchain] table with channel,
components, targets, profile or path), git's own objects for each fixture commit, the real
rust-toolchain.toml, cargo's and rustup's lists of the variables they read, and the workflows and
local actions read as YAML reads them. Every job that checks out the repository calls the pin
action in the step after its checkout and writes the channel to GITHUB_ENV as RUSTUP_TOOLCHAIN in
the step after that. Steps, jobs and actions hold only the keys listed below. No workflow or local
action outside the pin action names rustup, gives a rustup proxy a +toolchain argument, sets a
variable that chooses the toolchain or the compiler, or writes GITHUB_ENV or GITHUB_PATH. A
toolchain name built at run time (a matrix value, a variable, a split string) is not something a
text check can see; review of the workflow change is the control for that. The reader takes a small
part of YAML and refuses the rest.
"""

import dataclasses
import os
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
ACTION_FILES = sorted(
    path for path in (ROOT / ".github" / "actions").rglob("*")
    if path.is_file() and HERE not in path.parents and "__pycache__" not in path.parts
)
ACTION_DEFINITIONS = [path for path in ACTION_FILES if path.name in ("action.yml", "action.yaml")]

PIN_ACTION = "$/.github/actions/tree-paths"
PIN_ID = "toolchain"
WRITE_STEP = {
    "name": "Write RUSTUP_TOOLCHAIN to GITHUB_ENV",
    "shell": "bash",
    "run": 'echo "RUSTUP_TOOLCHAIN=${CHANNEL:?}" >> "$GITHUB_ENV"',
}
WRITE_ENV = {"CHANNEL": "${{ steps.toolchain.outputs.channel }}"}
STEP_PIN = ("RUSTUP_TOOLCHAIN", "${{ env.RUSTUP_TOOLCHAIN }}")
CHANNEL_OUTPUT = "${{ steps.read.outputs.RUSTUP_TOOLCHAIN }}"
READ_STEP = """    - id: read
      shell: bash
      run: |
        for python in python3 python; do
          if "$python" -I -c "import tomllib" > /dev/null 2>&1; then
            "$python" -I -B "$GITHUB_ACTION_PATH/pinned_toolchain.py" HEAD >> "$GITHUB_OUTPUT"
            exit 0
          fi
        done
        echo "::error::GRDR-GATE-0006 no Python with tomllib on this runner"
        exit 1
    - if: inputs.install == 'true'
"""
LOCAL_WORKFLOW = re.compile(r"[.$]/\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml")
BLOCK_SCALAR = "<block scalar>"

# The keys a step, a job or a local action may hold: those today's workflows use. A key GitHub adds
# later (parallel, background, wait and the like) is refused until it is read here.
STEP_KEYS = {"name", "id", "uses", "with", "run", "shell", "env", "if", "working-directory", "timeout-minutes",
             "continue-on-error"}
PIN_KEYS = {"id", "uses", "with"}
PIN_INPUTS = {"install"}
WRITE_KEYS = {"name", "shell", "env", "run"}
CHECKOUT_INPUTS = {"persist-credentials", "fetch-depth", "sparse-checkout", "sparse-checkout-cone-mode"}
# uses, with and secrets are the keys of a call to a reusable workflow in this repository.
JOB_KEYS = {"name", "needs", "if", "runs-on", "timeout-minutes", "permissions", "outputs", "strategy", "defaults",
            "steps", "uses", "with", "secrets"}
ACTION_KEYS = {"name", "description", "inputs", "outputs", "runs"}
COMPOSITE_KEYS = {"using", "steps"}

CHECKS_OUT = "checks out the repository"
RUNS_CARGO_IN_A_CONTAINER = "runs cargo in its own container, which takes the pin as step env"
# What each action the workflows and local actions use does that the pin cares about. An action
# missing here fails the test, so a new one is classified before it lands.
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

CARGO_READS = "cargo book, Environment variables, Environment variables Cargo reads"
CARGO_CONFIG = "cargo book, Environment variables, Configuration environment variables"
# Variables that choose the compiler, or that run code before the write step, and the page that
# lists each. Every RUSTUP_ variable (rustup book, Environment variables) is refused through RUSTUP.
REFUSED_VARIABLES = {
    "RUSTC": CARGO_READS,
    "RUSTC_WRAPPER": CARGO_READS,
    "RUSTC_WORKSPACE_WRAPPER": CARGO_READS,
    "RUSTDOC": CARGO_READS,
    "RUSTFMT": CARGO_READS,
    "CARGO": CARGO_READS,
    "CARGO_HOME": CARGO_READS,
    "CARGO_BUILD_RUSTC": CARGO_CONFIG,
    "CARGO_BUILD_RUSTC_WRAPPER": CARGO_CONFIG,
    "CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER": CARGO_CONFIG,
    "CARGO_BUILD_RUSTDOC": CARGO_CONFIG,
    "BASH_ENV": "bash manual, Bash Startup Files: sourced by every non-interactive bash, the write step's included",
    "ACTIONS_ALLOW_UNSECURE_COMMANDS": "GitHub Actions docs, Workflow commands: turns set-env and add-path back on",
}
# Lines outside the pin that may write GITHUB_ENV or GITHUB_PATH, as (file name, line) to a reason.
ENV_WRITES = {}
# Steps of a job that checks out whose if: runs after a failure, as (workflow, job, action) to a reason.
STATUS_CONDITIONS = {
    ("dast.yml", "baseline", "actions/upload-artifact"): "uploads the scan reports and the server log after a failed scan; runs no cargo",
}

PRINTABLE = re.compile(r"[ -~]*")
WORD_KEY = r"[A-Za-z_][A-Za-z0-9_-]*"
KEY_LINE = re.compile(rf"(?P<key>{WORD_KEY}|\"{WORD_KEY}\"|'{WORD_KEY}') *:(?: +(?P<rest>.*))?")
BLOCK_INDICATOR = re.compile(r"[|>][+-]?(?: +#.*)?")
SINGLE_QUOTED = re.compile(r"'((?:[^']|'')*)'(?: +#.*)?")
DOUBLE_QUOTED = re.compile(r'"([^"\\]*)"(?: +#.*)?')
FLOW_OF_WORDS = re.compile(r"\[[A-Za-z0-9_., -]*\]|\{\}")
PLAIN_START = re.compile(r"[^-?:,\[\]{}#&*!|>'\"%@`]|[-?:][^ ]")
RUSTUP = re.compile(r"rustup", re.I)
# A +toolchain argument to a rustup proxy, named by its basename with or without a path, quotes or
# .exe; quotes, backslashes and line breaks may sit before the +, as in a folded or continued line.
RUSTUP_PROXY = r"(?:cargo(?:-[a-z0-9_-]+)?|rustc|rustdoc|rustfmt|rust-[a-z0-9_-]+|clippy-driver|miri|rls)"
PLUS_TOOLCHAIN = re.compile(rf"(?<![\w-]){RUSTUP_PROXY}(?:\.exe)?[\"']?[\s\\\"']+\+", re.I)
VARIABLE_ASSIGNMENT = re.compile(rf"(?<![\w-])(?:{'|'.join(REFUSED_VARIABLES)})\s*=", re.I)
ENV_FILE_WRITE = re.compile(r"github_env|github_path|::set-env|::add-path", re.I)
STATUS_FUNCTION = re.compile(r"\b(?:always|failure|cancelled)\s*\(|!\s*success\s*\(", re.I)

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
ODD_CHARACTERS = {"NEL": "\x85", "LS": "\u2028", "PS": "\u2029", "FS": "\x1c", "VT": "\x0b", "tab": "\t", "CR": "\r"}

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
    "checkout-of-another-repository": CHECKOUT + "          repository: example/other\n" + PIN + WRITE + CARGO,
    "checkout-of-another-ref": CHECKOUT + "          ref: other\n" + PIN + WRITE + CARGO,
    "checkout-into-a-path": CHECKOUT + "          path: other\n" + PIN + WRITE + CARGO,
}
# Jobs that keep the pin's steps, but something else in the workflow picks the toolchain.
DEFEATED = {
    "plus-toolchain": PINNED + "      - run: cargo +stable test\n",
    "plus-toolchain-quoted": PINNED + "      - run: cargo '+stable' test\n",
    "plus-toolchain-folded": PINNED + "      - run: >-\n          cargo\n          +stable test\n",
    "plus-toolchain-continued": PINNED + "      - run: |\n          cargo \\\n            +stable test\n",
    "plus-toolchain-upper-case": PINNED + "      - run: CARGO.EXE +stable test\n",
    "plus-toolchain-by-path": PINNED + "      - run: $HOME/.cargo/bin/cargo +stable build\n",
    "plus-toolchain-quoted-path": PINNED + '      - run: echo; "$HOME/.cargo/bin/cargo" +stable build\n',
    **{
        f"plus-toolchain-{proxy}": PINNED + f"      - run: {proxy} +stable --version\n"
        for proxy in ("rustc", "rustdoc", "rustfmt", "cargo-clippy", "cargo-fmt", "cargo-miri", "miri", "rls",
                      "rust-analyzer", "rust-gdb", "clippy-driver")
    },
    "rustup-run": PINNED + "      - run: rustup run stable cargo test\n",
    "rustup-quiet-run": PINNED + "      - run: rustup -q run stable cargo test\n",
    "rustup-verbose-run": PINNED + "      - run: rustup --verbose run stable cargo test\n",
    "rustup-default": PINNED + "      - run: rustup default stable\n",
    "rustup-override": PINNED + "      - run: rustup override set stable\n",
    "rustup-toolchain-link": PINNED + "      - run: rustup toolchain link local ./tc\n",
    "rustup-toolchain-install": PINNED + "      - run: rustup toolchain install stable\n",
    "rustup-by-path": PINNED + "      - run: ~/.cargo/bin/rustup.exe show\n",
    "step-env": PINNED + "      - env:\n          RUSTUP_TOOLCHAIN: stable\n        run: cargo test\n",
    "step-env-lower-case": PINNED + "      - env:\n          rustup_toolchain: stable\n        run: cargo test\n",
    "step-env-rustup-home": PINNED + "      - env:\n          RUSTUP_HOME: ./rustup\n        run: cargo test\n",
    "step-env-rustup-dist-server": PINNED + "      - env:\n          RUSTUP_DIST_SERVER: http://mirror.example\n        run: cargo test\n",
    **{
        f"step-env-{variable.lower()}": PINNED + f"      - env:\n          {variable}: ./tool\n        run: cargo test\n"
        for variable in REFUSED_VARIABLES
    },
    "step-env-rustc-wrapper-lower-case": PINNED + "      - env:\n          rustc_wrapper: ./tool\n        run: cargo test\n",
    "run-line-export": PINNED + "      - run: export RUSTUP_TOOLCHAIN=stable && cargo test\n",
    "run-line-rustc": PINNED + "      - run: RUSTC=./tool cargo build\n",
    "run-line-cargo-home": PINNED + "      - run: export cargo_home=./home; cargo build\n",
    "heredoc-write": PINNED + "      - run: |\n          cat >> \"$GITHUB_ENV\" <<EOF\n          RUSTUP_TOOLCHAIN=stable\n          EOF\n",
    "env-file-write": PINNED + '      - run: echo "RUSTC_WRAPPER=sccache" >> "$GITHUB_ENV"\n',
    "path-file-write": PINNED + '      - run: echo "$PWD/bin" >> "$GITHUB_PATH"\n',
    "path-file-write-lower-case": PINNED + "      - shell: pwsh\n        run: Add-Content $env:github_path ./bin\n",
    "add-path-command": PINNED + '      - run: echo "::add-path::./bin"\n',
    "set-env-command": PINNED + '      - run: echo "::set-env name=CC::./cc"\n',
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
    "status-always": PINNED + "      - if: always()\n        run: cargo test\n",
    "status-always-capitals": PINNED + "      - if: ${{ Always() }}\n        run: cargo test\n",
    "status-failure": PINNED + "      - if: failure()\n        run: cargo test\n",
    "status-cancelled": PINNED + "      - if: ${{ !cancelled() }}\n        run: cargo test\n",
    "status-not-success": PINNED + "      - if: ${{ ! success() }}\n        run: cargo test\n",
    "status-allowed-action-with-a-run": PINNED + "      - if: always()\n        uses: actions/upload-artifact@0\n        run: cargo test\n",
    "status-on-an-unlisted-step": PINNED + "      - if: always()\n        uses: actions/upload-artifact@0\n",
}
DEFEATED_BY_ENV = {
    "job-env": ("", "    env:\n      RUSTUP_TOOLCHAIN: stable\n"),
    "job-env-from-the-pin-form": ("", "    env:\n      RUSTUP_TOOLCHAIN: ${{ env.RUSTUP_TOOLCHAIN }}\n"),
    "workflow-env": ("env:\n  RUSTUP_TOOLCHAIN: stable\n", ""),
    "workflow-rustup-home": ("env:\n  RUSTUP_HOME: ./rustup\n", ""),
    "workflow-rustup-dist-server": ("env:\n  RUSTUP_DIST_SERVER: http://mirror.example\n", ""),
    "workflow-rustc-wrapper": ("env:\n  RUSTC_WRAPPER: ./tool\n", ""),
    "workflow-bash-env": ("env:\n  BASH_ENV: ./setup.sh\n", ""),
}
# Keys outside the allowlists: step forms GitHub may run in another order or environment, and jobs
# that hold keys the reader does not read.
UNLISTED_KEYS = {
    "parallel-group-holding-the-checkout": "      - parallel:\n          - uses: actions/checkout@0\n" + CARGO,
    "background-step-before-the-checkout": "      - id: early\n        background: true\n        run: sleep 60; cargo build\n"
    + PINNED + CARGO + "      - wait: early\n",
    "pin-inside-a-parallel-group": CHECKOUT + "      - parallel:\n          - id: toolchain\n"
    "            uses: $/.github/actions/tree-paths\n" + WRITE + CARGO,
    "background-write": PINNED + "        background: true\n" + CARGO,
    "wait-all": PINNED + "      - wait-all: true\n" + CARGO,
    "unknown-step-key": PINNED + "      - run: cargo test\n        frobnicate: true\n",
}
UNLISTED_JOB_KEYS = {
    "unknown-job-key": "    frobnicate: true\n",
    "job-container": "    container: rust:1.80\n",
    "job-continue-on-error": "    continue-on-error: true\n",
}
# Workflows the reader does not read, each holding a job that checks out without the pin.
UNREADABLE = {
    **{
        f"line-break-{name}": f"    steps: # c{char}    a: |\n      - {{uses: actions/checkout@0}}\n"
        for name, char in ODD_CHARACTERS.items()
    },
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
    "dash-alone": "    steps:\n      -\n        uses: actions/checkout@0\n",
    "spaces-after-the-dash": "    steps:\n      -   uses: actions/checkout@0\n",
    "plain-scalar-over-lines": "    steps:\n      - name: x\n          uses: actions/checkout@0\n",
    "second-document": "    steps:\n      - run: x\n---\njobs:\n  docs:\n    steps:\n      - uses: actions/checkout@0\n",
    "remote-reusable-workflow": "    uses: example/rust/.github/workflows/docs.yml@0\n",
}
# One fixture for each refusal of the reader and the pin rules that no other fixture needs: each
# passes when that refusal alone is taken out.
NEEDS_ONE_REFUSAL = {
    **{f"{name}-in-a-comment": PINNED + f"      # note{char}more\n" + CARGO for name, char in ODD_CHARACTERS.items()},
    "checkout-beside-a-block-scalar": "      - run: |\n          echo\n        uses: actions/checkout@0\n" + CARGO,
    "repeated-key-checkout-first": "      - uses: actions/checkout@0\n        uses: actions/upload-artifact@0\n" + CARGO,
    "steps-at-the-key-indent": "    - uses: actions/checkout@0\n    - run: cargo doc\n",
    "keys-beside-the-steps": "      uses: actions/checkout@0\n      - run: cargo doc\n",
    "steps-as-a-mapping": "      checkout:\n        uses: actions/checkout@0\n      cargo:\n        run: cargo doc\n",
    "pin-step-of-another-action": CHECKOUT + "      - id: toolchain\n        uses: actions/upload-artifact@0\n" + WRITE + CARGO,
    "container-action-with-another-toolchain": PINNED
    + "      - uses: EmbarkStudios/cargo-deny-action@0\n        env:\n          RUSTUP_TOOLCHAIN: stable\n",
    "status-through-an-alias": PINNED + "      - name: &after always()\n        run: echo\n      - if: *after\n        run: cargo test\n",
}
# The step STATUS_CONDITIONS allows in dast.yml's baseline job, and the same step running a command.
LISTED_STATUS_STEP = "      - if: always()\n        uses: actions/upload-artifact@0\n"

COMPOSITE = "name: fixture\ndescription: fixture\nruns:\n  using: composite\n  steps:\n"
ECHO = "    - shell: bash\n      run: echo done\n"
# Local actions that a pinned job could call, each of which works past the pin.
ACTION_DEFEATS = {
    "env-file-write": "    - shell: bash\n      run: echo \"RUSTUP_TOOLCHAIN=stable\" >> \"$GITHUB_ENV\"\n",
    "plus-toolchain": "    - shell: bash\n      run: cargo +stable build\n",
    "rustup": "    - shell: bash\n      run: rustup default stable\n",
    "refused-variable": "    - shell: bash\n      env:\n        RUSTC: ./tool\n      run: cargo build\n",
    "status-condition": "    - if: always()\n      shell: bash\n      run: cargo build\n",
    "unknown-step-key": "    - shell: bash\n      background: true\n      run: cargo build\n",
    "unclassified-action": "    - uses: dtolnay/rust-toolchain@0\n",
}
ACTION_TEXT_DEFEATS = {
    "javascript-action": "name: fixture\ndescription: fixture\nruns:\n  using: node24\n  main: index.js\n",
    "steps-of-another-kind-of-action": COMPOSITE.replace("using: composite", "using: node24") + ECHO,
    "unknown-action-key": COMPOSITE + ECHO + "branding:\n  icon: x\n",
}


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


def run_reader(rev, cwd, env=None):
    return subprocess.run(
        [sys.executable, "-I", "-B", str(READER), rev], cwd=cwd, env=env, capture_output=True, text=True, check=False,
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


def new_repository(scratch, name):
    repository = pathlib.Path(scratch) / name
    repository.mkdir()
    git(repository, "init", "-q")
    return repository


def env_file(text):
    """GITHUB_ENV or GITHUB_OUTPUT as the runner reads it: KEY=value per line."""
    return dict(line.split("=", 1) for line in text.splitlines())


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


def action_of(step):
    uses = step.get("uses")
    return None if uses is None else (text_of(uses) or BLOCK_SCALAR).partition("@")[0]


def refused_env_keys(value, name):
    """Every env mapping at any depth that sets a variable REFUSED_VARIABLES lists, in any letter case."""
    if isinstance(value.data, list):
        return [problem for child in value.data for problem in refused_env_keys(child, name)]
    if not isinstance(value.data, dict):
        return []
    problems = []
    for key, child in value.data.items():
        if key == "env" and isinstance(child.data, dict):
            problems += [f"{name} line {child.number}: env sets {variable}" for variable in child.data
                         if variable.upper() in REFUSED_VARIABLES]
        problems += refused_env_keys(child, name)
    return problems


def step_problems(where, step):
    problems = [f"{where}: a step holds {key}" for key in sorted(set(step) - STEP_KEYS)]
    action = action_of(step)
    if action not in ACTIONS and action not in (None, PIN_ACTION):
        problems.append(f"{where}: {action} is not classified in ACTIONS")
    return problems


def status_problems(name, job_id, step):
    condition = text_of(step.get("if")) or ""
    allowed = (name, job_id, action_of(step)) in STATUS_CONDITIONS and "run" not in step
    if STATUS_FUNCTION.search(condition) and not allowed:
        return [f"{name} {job_id}: a step runs after a failure ({condition})"]
    return []


def pin_step_problems(job_id, step):
    problems = [f"{job_id}: the pin step has {key}" for key in sorted(set(step) - PIN_KEYS)]
    if text_of(step.get("id")) != PIN_ID or text_of(step.get("uses")) != PIN_ACTION:
        problems.append(f"{job_id}: the step after the checkout is not the pin action with id {PIN_ID}")
    inputs = values_of(step.get("with"), "the pin's inputs")
    problems += [f"{job_id}: the pin step takes {key}" for key in sorted(set(inputs) - PIN_INPUTS)]
    return problems


def write_step_problems(job_id, step, allowed_lines):
    written = {key: text_of(value) for key, value in step.items() if key != "env"}
    if set(step) != WRITE_KEYS or written != WRITE_STEP or values_of(step["env"], "the write's env") != WRITE_ENV:
        return [f"{job_id}: the step after the pin does not write its channel as RUSTUP_TOOLCHAIN"]
    allowed_lines.update((step["name"].number, step["run"].number))
    return []


def checkout_problems(job_id, steps, actions, allowed_lines):
    first = next(at for at, action in enumerate(actions) if ACTIONS.get(action) == CHECKS_OUT)
    inputs = values_of(steps[first].get("with"), "the checkout's inputs")
    problems = [f"{job_id}: the checkout takes {key}" for key in sorted(set(inputs) - CHECKOUT_INPUTS)]
    if first + 2 >= len(steps):
        return problems + [f"{job_id}: checks out and does not pin the toolchain in the next two steps"]
    return (problems + pin_step_problems(job_id, steps[first + 1])
            + write_step_problems(job_id, steps[first + 2], allowed_lines))


def job_problems(name, job_id, job, steps, allowed_lines):
    problems = [f"{job_id}: the job holds {key}" for key in sorted(set(job) - JOB_KEYS)]
    if "uses" in job:
        called = text_of(job["uses"]) or ""
        return problems + ([] if LOCAL_WORKFLOW.fullmatch(called) else [f"{job_id}: calls a workflow outside this repository"])
    problems += [problem for step in steps for problem in step_problems(job_id, step)]
    actions = [action_of(step) for step in steps]
    for step, action in zip(steps, actions):
        if ACTIONS.get(action) != RUNS_CARGO_IN_A_CONTAINER:
            continue
        pinned = as_mapping(step["env"], "a step's env").get(STEP_PIN[0]) if "env" in step else None
        if text_of(pinned) != STEP_PIN[1]:
            problems.append(f"{job_id}: {action} does not take the pin as step env")
        else:
            allowed_lines.add(pinned.number)
    if all(ACTIONS.get(action) != CHECKS_OUT for action in actions):
        return problems
    problems += [problem for step in steps for problem in status_problems(name, job_id, step)]
    return problems + checkout_problems(job_id, steps, actions, allowed_lines)


def text_problems(text, allowed_lines, name):
    """What the text of a workflow or a local action does past the pin."""
    problems = [f"{name}: gives a rustup proxy a +toolchain argument: {found[0]!r}" for found in PLUS_TOOLCHAIN.finditer(text)]
    problems += [f"{name}: sets {found[0]!r}" for found in VARIABLE_ASSIGNMENT.finditer(text)]
    for number, line in enumerate(text.split("\n"), 1):
        if number in allowed_lines or (name, line.strip()) in ENV_WRITES:
            continue
        if RUSTUP.search(line):
            problems.append(f"{name} line {number}: names rustup outside the pin")
        if ENV_FILE_WRITE.search(line):
            problems.append(f"{name} line {number}: writes GITHUB_ENV or GITHUB_PATH outside the pin")
    return problems


def workflow_problems(text, name="fixture.yml"):
    """Why a workflow does not keep the pin; empty when it does."""
    allowed_lines = set()
    try:
        root = parse(text)
        problems = [problem for job_id, job, steps in jobs_of(root)
                    for problem in job_problems(name, job_id, job, steps, allowed_lines)]
    except Unreadable as error:
        return [str(error)]
    return problems + refused_env_keys(root, name) + text_problems(text, allowed_lines, name)


def action_problems(text, name="fixture/action.yml"):
    """Why a local action, other than the pin action, does not leave the pin alone; empty when it does."""
    try:
        root = parse(text)
        action = as_mapping(root, "the action")
        problems = [f"{name}: the action holds {key}" for key in sorted(set(action) - ACTION_KEYS)]
        runs = as_mapping(action["runs"], "runs") if "runs" in action else {}
        problems += [f"{name}: runs holds {key}" for key in sorted(set(runs) - COMPOSITE_KEYS)]
        if text_of(runs.get("using")) != "composite":
            problems.append(f"{name}: not a composite action")
        steps = [as_mapping(step, "a step") for step in as_sequence(runs["steps"], "steps")] if "steps" in runs else []
    except Unreadable as error:
        return [str(error)]
    problems += [problem for step in steps for problem in step_problems(name, step)]
    problems += [f"{name}: a step runs after a failure" for step in steps if STATUS_FUNCTION.search(text_of(step.get("if")) or "")]
    return problems + refused_env_keys(root, name) + text_problems(text, set(), name)


def pin_action_problems(text):
    """Why the pin action could give a channel other than the reader's; empty when it cannot."""
    try:
        action = as_mapping(parse(text), "the pin action")
        outputs = as_mapping(action["outputs"], "outputs")
        channel = values_of(outputs.get("channel"), "the channel output") if set(outputs) == {"channel"} else {}
        runs = as_mapping(action["runs"], "runs")
        steps = [set(as_mapping(step, "a step")) for step in as_sequence(runs["steps"], "steps")]
    except (Unreadable, KeyError) as error:
        return [f"the pin action: {error}"]
    problems = [] if channel.get("value") == CHANNEL_OUTPUT else ["the channel output is not the reader's channel"]
    if steps != [{"id", "shell", "run"}, {"if", "shell", "env", "run"}] or READ_STEP not in text:
        problems.append("the pin action's steps are not the read step and the install step")
    if text.count("GITHUB_OUTPUT") != 1 or ENV_FILE_WRITE.search(text.partition("\nruns:\n")[2]):
        problems.append("the pin action writes an output or the environment outside the read step")
    return problems


def fixture(steps, key_line="  docs:", job_lines="", top_lines=""):
    return f"name: fixture\non: push\n{top_lines}jobs:\n{key_line}\n    runs-on: ubuntu-26.04\n{job_lines}    steps:\n{steps}"


class ReaderTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = scratch.name
        self.repository = new_repository(scratch.name, "repository")

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
        git(self.repository, "update-ref", "HEAD", commit_files(self.repository, {"rust-toolchain.toml": FULL}))
        (self.repository / "rust-toolchain.toml").write_text(OTHER_CHANNEL, encoding="utf-8")
        (self.repository / "rust-t~1.tom").write_text(OTHER_CHANNEL, encoding="utf-8")
        result = run_reader("HEAD", self.repository)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(env_file(result.stdout)["RUSTUP_TOOLCHAIN"], "1.99.1")

    def test_the_callers_git_variables_do_not_change_the_channel(self):
        git(self.repository, "update-ref", "HEAD", commit_files(self.repository, {"rust-toolchain.toml": FULL}))
        planted = new_repository(self.scratch, "planted")
        git(planted, "update-ref", "HEAD", commit_files(planted, {"rust-toolchain.toml": OTHER_CHANNEL}))
        environment = dict(os.environ, GIT_DIR=str(planted / ".git"), GIT_WORK_TREE=str(planted))
        self.assertIn("1.70.0", subprocess.run(["git", "show", "HEAD:rust-toolchain.toml"], cwd=self.repository,
                                               env=environment, capture_output=True, text=True, check=True).stdout)
        result = run_reader("HEAD", self.repository, environment)
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

    def replaced_blob(self):
        """A blob spec whose commit a replacement ref points at another commit, checked to differ."""
        pinned = commit_files(self.repository, {"rust-toolchain.toml": FULL})
        git(self.repository, "replace", pinned, commit_files(self.repository, {"rust-toolchain.toml": OTHER_CHANNEL}))
        blob = f"{pinned}:rust-toolchain.toml"
        self.assertEqual(git(self.repository, "cat-file", "blob", blob), OTHER_CHANNEL.strip())
        return blob

    def run_with_the_reader(self, script, *args):
        prelude = "import os, subprocess, sys; sys.path.insert(0, sys.argv[1]); import pinned_toolchain as reader; "
        return subprocess.run([sys.executable, "-I", "-B", "-c", prelude + script, str(HERE), *args],
                              cwd=self.repository, capture_output=True, check=False)

    def test_the_git_command_turns_replacement_off(self):
        scrub_only = "reader.git_environment = lambda: {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}; "
        result = self.run_with_the_reader(
            scrub_only + "sys.stdout.buffer.write(reader.git('cat-file', 'blob', sys.argv[2]))", self.replaced_blob())
        self.assertEqual((result.returncode, result.stdout.decode("utf-8")), (0, FULL), result.stderr)

    def test_the_git_environment_turns_replacement_off(self):
        result = self.run_with_the_reader(
            "sys.stdout.buffer.write(subprocess.run(['git', 'cat-file', 'blob', sys.argv[2]], env=reader.git_environment(),"
            " capture_output=True, check=True).stdout)", self.replaced_blob())
        self.assertEqual((result.returncode, result.stdout.decode("utf-8")), (0, FULL), result.stderr)


class WorkflowTest(unittest.TestCase):
    def test_every_workflow_keeps_the_pin(self):
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow.name):
                text = workflow.read_bytes().decode("ascii", "replace")
                self.assertEqual(workflow_problems(text, workflow.name), [])

    def test_every_local_action_leaves_the_pin_alone(self):
        for path in ACTION_FILES:
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = path.read_bytes().decode("ascii", "replace")
                problems = action_problems(text, path.name) if path in ACTION_DEFINITIONS else text_problems(text, set(), path.name)
                self.assertEqual(problems, [])

    def test_the_pin_action_outputs_only_the_readers_channel(self):
        action = PIN_ACTION_FILE.read_text(encoding="utf-8")
        self.assertEqual(pin_action_problems(action), [])
        self.assertIn('rustup toolchain install "$CHANNEL"', action)
        self.assertIn("RUSTUP_TOOLCHAIN: ${{ steps.read.outputs.RUSTUP_TOOLCHAIN }}", action)
        changed = {
            "literal-channel": action.replace(f"value: {CHANNEL_OUTPUT}", "value: 1.70.0"),
            "second-output": action.replace("outputs:\n  channel:", "outputs:\n  other:\n    value: x\n  channel:"),
            "third-step": action + "    - shell: bash\n      run: echo \"RUSTUP_TOOLCHAIN=1.70.0\" >> \"$GITHUB_OUTPUT\"\n",
            "read-step-changed": action.replace("pinned_toolchain.py\" HEAD", "pinned_toolchain.py\" HEAD~1"),
            "env-write": action.replace("        rustup toolchain install", "        echo x >> \"$GITHUB_ENV\"; rustup toolchain install"),
        }
        for name, text in changed.items():
            with self.subTest(case=name):
                self.assertNotEqual(text, action)
                self.assertNotEqual(pin_action_problems(text), [])

    def test_a_pinned_job_passes(self):
        self.assertEqual(workflow_problems(fixture(PINNED + CARGO)), [])
        self.assertEqual(workflow_problems(fixture(PINNED + "      - name: Show the toolchain\n        run: cargo --version\n")), [])
        self.assertEqual(workflow_problems(fixture("      - run: cargo doc\n")), [])
        second_checkout = CHECKOUT + "          repository: example/rules\n          path: rules\n"
        self.assertEqual(workflow_problems(fixture(PINNED + second_checkout + CARGO)), [])
        self.assertEqual(workflow_problems(LOCAL_WORKFLOW_CALL), [])
        self.assertEqual(action_problems(COMPOSITE + ECHO), [])

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

    def test_a_key_outside_the_allowlists_is_refused(self):
        for name, steps in UNLISTED_KEYS.items():
            with self.subTest(case=name):
                self.assertNotEqual(workflow_problems(fixture(steps)), [])
        for name, job_lines in UNLISTED_JOB_KEYS.items():
            with self.subTest(case=name):
                self.assertNotEqual(workflow_problems(fixture(PINNED + CARGO, job_lines=job_lines)), [])

    def test_a_workflow_the_reader_does_not_read_is_refused(self):
        for name, job in UNREADABLE.items():
            with self.subTest(case=name):
                self.assertNotEqual(workflow_problems(f"name: fixture\non: push\njobs:\n  docs:\n{job}"), [])

    def test_each_refusal_has_a_fixture_that_needs_it(self):
        for name, steps in NEEDS_ONE_REFUSAL.items():
            with self.subTest(case=name):
                self.assertNotEqual(workflow_problems(fixture(steps)), [])

    def test_only_the_listed_step_runs_after_a_failure(self):
        listed = fixture(PINNED + CARGO + LISTED_STATUS_STEP, key_line="  baseline:")
        self.assertEqual(workflow_problems(listed, "dast.yml"), [])
        self.assertNotEqual(workflow_problems(listed, "verify.yml"), [])
        self.assertNotEqual(workflow_problems(listed + "        run: cargo test\n", "dast.yml"), [])

    def test_a_local_action_that_works_past_the_pin_is_refused(self):
        for name, steps in ACTION_DEFEATS.items():
            with self.subTest(case=name):
                self.assertNotEqual(action_problems(COMPOSITE + steps), [])
        for name, text in ACTION_TEXT_DEFEATS.items():
            with self.subTest(case=name):
                self.assertNotEqual(action_problems(text), [])

    def test_only_the_pin_action_reads_or_installs_the_toolchain(self):
        for path in [*WORKFLOWS, *ACTION_FILES]:
            self.assertNotIn("pinned_toolchain.py", path.read_bytes().decode("ascii", "replace"), path.name)
        action = PIN_ACTION_FILE.read_text(encoding="utf-8")
        self.assertIn('pinned_toolchain.py" HEAD >> "$GITHUB_OUTPUT"', action)
        self.assertNotIn("GITHUB_ENV", action.partition("\nruns:\n")[2])


if __name__ == "__main__":
    unittest.main()

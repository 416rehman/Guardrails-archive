"""The rules the workflow test runs over the workflows, the local actions and the pin action.

Each rule is a text match, over the keys and values workflow_reader.py gives it or over the raw
text. A job that has an actions/checkout step must call the pin action in the step after its first
checkout, and write the channel to GITHUB_ENV as RUSTUP_TOOLCHAIN in the step after that. Steps,
jobs, local actions and a job's first checkout may hold only the keys and inputs listed here. The
other matches each refuse one spelling, in any letter case: a line other than the pin's own that
holds rustup, github_env, github_path, ::set-env or ::add-path; a RUSTUP_PROXY name, with or
without a path, a quote or .exe, followed by quotes, backslashes or whitespace and a +; a
REFUSED_VARIABLES name as an env key, or followed by optional whitespace and = with no letter,
digit, underscore or hyphen before it; and a step's if: whose text holds the word always, failure
or cancelled followed by (, or ! followed by success(, with optional whitespace between the parts.

The fixture tables in test_pinned_toolchain.py are the list of forms the test claims to refuse. It
claims nothing about a form no fixture exercises, even one of the same kind as a fixture's. Every
file these rules read is under .github/**, which is trust core, and review of an edit there by the
trust-core evaluator set is the control for every other form (design/02 TB-11, D-63).
"""

import re

from workflow_reader import (
    BLOCK_SCALAR, Unreadable, as_mapping, as_sequence, jobs_of, parse, text_of, values_of,
)

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
# Variable names refused as an env key or as NAME=, each with the page that lists it: they choose
# the compiler, or run code before the write step. RUSTUP_ names are not listed: a line outside the
# pin that holds one is refused by the RUSTUP text match.
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
# Steps of a job with an actions/checkout step whose if: may run after a failure, as (workflow, job,
# action) to a reason.
STATUS_CONDITIONS = {
    ("dast.yml", "baseline", "actions/upload-artifact"): "uploads the scan reports and the server log after a failed scan; runs no cargo",
}

RUSTUP = re.compile(r"rustup", re.I)
# Matches a rustup proxy's basename, with or without a path, quotes or .exe, then quotes, backslashes
# or whitespace and a +, as in a plain, folded or continued line. It matches only that spelling.
RUSTUP_PROXY = r"(?:cargo(?:-[a-z0-9_-]+)?|rustc|rustdoc|rustfmt|rust-[a-z0-9_-]+|clippy-driver|miri|rls)"
PLUS_TOOLCHAIN = re.compile(rf"(?<![\w-]){RUSTUP_PROXY}(?:\.exe)?[\"']?[\s\\\"']+\+", re.I)
VARIABLE_ASSIGNMENT = re.compile(rf"(?<![\w-])(?:{'|'.join(REFUSED_VARIABLES)})\s*=", re.I)
ENV_FILE_WRITE = re.compile(r"github_env|github_path|::set-env|::add-path", re.I)
STATUS_FUNCTION = re.compile(r"\b(?:always|failure|cancelled)\s*\(|!\s*success\s*\(", re.I)


def action_of(step):
    uses = step.get("uses")
    return None if uses is None else (text_of(uses) or BLOCK_SCALAR).partition("@")[0]


def refused_env_keys(value, name):
    """The keys of env mappings at any depth that match a REFUSED_VARIABLES name in any letter case."""
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
    """The raw text matches over a workflow or a local action, outside the allowed lines."""
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
    """What the rules find in a workflow; empty when no rule matches."""
    allowed_lines = set()
    try:
        root = parse(text)
        problems = [problem for job_id, job, steps in jobs_of(root)
                    for problem in job_problems(name, job_id, job, steps, allowed_lines)]
    except Unreadable as error:
        return [str(error)]
    return problems + refused_env_keys(root, name) + text_problems(text, allowed_lines, name)


def action_problems(text, name="fixture/action.yml"):
    """What the rules find in a local action other than the pin action; empty when no rule matches."""
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
    """Where the pin action's outputs, steps, read step or writes differ from what the checks expect."""
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


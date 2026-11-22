// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
// The owner rule of #1875, one issue, one branch `issue/<n>`, one pull request, checked against
// the remote branches and open pull requests of GH_REPO, or against a JSON file with `--state`.
// Exit 0 with no findings, 1 with findings, 2 when it could not look, which never counts as clean.
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";

const RULES_FILE = fileURLToPath(new URL("./branch-rules.json", import.meta.url));
const EXIT = { clean: 0, findings: 1, couldNotLook: 2 };
const FIX_SECTION = 'skill grdr-work-issue, "Branches and pull requests"';

function issuePattern(raw, key, flags) {
  const source = raw?.[key];
  if (typeof source !== "string") throw new Error(`branch-rules.json has no ${key} pattern`);
  const expression = new RegExp(source, flags);
  const groups = new RegExp(`(?:${source})|`).exec("")?.length ?? 0;
  if (groups !== 2) throw new Error(`branch-rules.json ${key} needs exactly one capture group, the issue number`);
  return expression;
}

export function loadRules(text) {
  const raw = JSON.parse(text);
  const exempt = raw?.exempt_from_name;
  if (!Array.isArray(exempt) || !exempt.every((entry) => typeof entry?.prefix === "string" && entry.prefix)) {
    throw new Error("branch-rules.json exempt_from_name needs a list of entries with a prefix");
  }
  if (!Number.isSafeInteger(raw.gh_output_limit_bytes) || raw.gh_output_limit_bytes <= 0) {
    throw new Error("branch-rules.json gh_output_limit_bytes needs a positive integer");
  }
  return {
    workBranch: issuePattern(raw, "work_branch", ""),
    closingKeyword: issuePattern(raw, "closing_keyword", "gi"),
    referenceLine: issuePattern(raw, "reference_line", "gim"),
    exemptPrefixes: exempt.map((entry) => entry.prefix),
    outputLimitBytes: raw.gh_output_limit_bytes,
  };
}

function isPull(pull) {
  return (
    Number.isSafeInteger(pull?.number) &&
    typeof pull.head === "string" &&
    (pull.head_repo === null || typeof pull.head_repo === "string") &&
    (pull.body === null || typeof pull.body === "string")
  );
}

export function checkState(state) {
  const shaped =
    typeof state?.repo === "string" &&
    typeof state.default_branch === "string" &&
    Array.isArray(state.branches) &&
    state.branches.every((branch) => typeof branch === "string") &&
    Array.isArray(state.pulls) &&
    state.pulls.every(isPull);
  if (!shaped) throw new Error("the state needs repo, default_branch, branches and pulls in the documented shape");
  if (!state.branches.includes(state.default_branch)) {
    throw new Error(`the branch list lacks the default branch ${state.default_branch}, so it is not the whole list`);
  }
  return state;
}

function lines(text) {
  return text.split(/\r?\n/).filter(Boolean);
}

function liveState(rules) {
  const gh = (args) =>
    execFileSync("gh", args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], maxBuffer: rules.outputLimitBytes });
  const repo = JSON.parse(gh(["repo", "view", "--json", "nameWithOwner,defaultBranchRef"]));
  const branches = lines(gh(["api", "repos/{owner}/{repo}/branches", "--paginate", "--jq", ".[].name"]));
  const pullFields = "{number, head: .head.ref, head_repo: .head.repo.full_name, body}";
  const pulls = lines(gh(["api", "repos/{owner}/{repo}/pulls?state=open", "--paginate", "--jq", `.[] | ${pullFields}`]));
  return {
    repo: repo.nameWithOwner,
    default_branch: repo.defaultBranchRef?.name,
    branches,
    pulls: pulls.map((line) => JSON.parse(line)),
  };
}

function stateFrom(argv, rules) {
  const at = argv.indexOf("--state");
  if (at === -1) return checkState(liveState(rules));
  const file = argv[at + 1];
  if (!file) throw new Error("--state needs a file");
  return checkState(JSON.parse(readFileSync(file, "utf8")));
}

function linkedIssues(pull, repo, rules) {
  const issues = new Set();
  const head = pull.head_repo === repo ? rules.workBranch.exec(pull.head) : null;
  if (head) issues.add(head[1]);
  const body = (pull.body ?? "").replace(/\r\n?/g, "\n");
  for (const match of body.matchAll(rules.closingKeyword)) issues.add(match[1]);
  for (const match of body.matchAll(rules.referenceLine)) issues.add(match[1]);
  return issues;
}

function branchFindings(state, rules) {
  const heads = new Set(state.pulls.filter((pull) => pull.head_repo === state.repo).map((pull) => pull.head));
  const found = [];
  for (const branch of state.branches.filter((name) => name !== state.default_branch)) {
    if (!heads.has(branch)) {
      found.push({
        kind: "no-pull-request",
        subject: branch,
        message: `${branch}: no open pull request. Open its draft pull request, or, when its issue is closed, record its last commit on the issue and delete the branch (${FIX_SECTION}).`,
      });
    }
    const exempt = rules.exemptPrefixes.some((prefix) => branch.startsWith(prefix));
    if (!exempt && !rules.workBranch.test(branch)) {
      found.push({
        kind: "bad-name",
        subject: branch,
        message: `${branch}: not named issue/<n>. Move its commits to issue/<n> of its issue, replace its pull request and delete the branch (${FIX_SECTION}).`,
      });
    }
  }
  return found;
}

function pullFindings(state, rules) {
  const pullsByIssue = new Map();
  for (const pull of state.pulls) {
    for (const issue of linkedIssues(pull, state.repo, rules)) {
      pullsByIssue.set(issue, [...(pullsByIssue.get(issue) ?? []), pull.number]);
    }
  }
  return [...pullsByIssue]
    .filter(([, numbers]) => numbers.length > 1)
    .map(([issue, numbers]) => ({
      kind: "second-pull-request",
      subject: `#${issue}`,
      message: `#${issue}: linked from open pull requests ${numbers.map((n) => `#${n}`).join(", ")}. Keep the one on issue/${issue} and close each other one with a comment naming it (${FIX_SECTION}).`,
    }));
}

export function findings(state, rules) {
  return [...branchFindings(state, rules), ...pullFindings(state, rules)];
}

function main(argv) {
  try {
    const rules = loadRules(readFileSync(RULES_FILE, "utf8"));
    const state = stateFrom(argv, rules);
    const found = findings(state, rules);
    for (const finding of found) process.stdout.write(`${finding.message}\n`);
    process.stdout.write(
      `branch-check: ${state.branches.length} branches, ${state.pulls.length} open pull requests, ${found.length} findings.\n`,
    );
    return found.length ? EXIT.findings : EXIT.clean;
  } catch (error) {
    process.stderr.write(`branch-check could not look: ${error.message}\n`);
    return EXIT.couldNotLook;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = main(process.argv.slice(2));
}

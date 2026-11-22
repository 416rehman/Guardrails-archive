// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
// The CI stop condition of skill grdr-build: is CI on `main` red? It judges each required
// workflow by its latest push run on `main`, never by the newest runs of any kind, and reads job
// names only from runs of merged code, so a pull request that renames its jobs cannot make a red
// `main` read green. Exit 0 green, 1 red, 2 could not judge; the last line of stdout is the summary
// only when it judged.
import { execFileSync } from "node:child_process";

const EXIT = { green: 0, red: 1, couldNotJudge: 2 };
const REQUIRED_CHECKS = '[.[] | select(.type == "required_status_checks") | .parameters.required_status_checks[].context]';
const PUSH_ON_MAIN = ["--branch", "main", "--event", "push"];

class CouldNotJudge extends Error {}

function lines(text) {
  return text.split(/\r?\n/).filter(Boolean);
}

function firstRun(text) {
  const runs = JSON.parse(text || "[]");
  if (!Array.isArray(runs)) throw new CouldNotJudge("gh run list did not return a list");
  return runs[0];
}

function jobNames(gh, runId) {
  return lines(gh(["run", "view", String(runId), "--json", "jobs", "--jq", ".jobs[].name"]));
}

function finished(gh, run) {
  if (run.status === "completed") return run;
  gh(["run", "watch", String(run.databaseId)]);
  return { ...run, ...JSON.parse(gh(["run", "view", String(run.databaseId), "--json", "conclusion,status"])) };
}

// Job names come from the latest push run on `main`. A run that never started has none, so they
// come from the last successful push run on `main` instead; with no such run there is no merged
// code to say which checks the workflow provides, and it counts as red.
function judgeWorkflow(gh, id, required) {
  const latest = firstRun(gh(["run", "list", "--workflow", id, ...PUSH_ON_MAIN, "--limit", "1", "--json", "databaseId,conclusion,status"]));
  if (!latest) return { id, verdict: "not judged" };
  const run = finished(gh, latest);
  const jobs = run.conclusion === "startup_failure" ? [] : jobNames(gh, run.databaseId);
  if (jobs.length > 0) {
    if (!jobs.some((job) => required.includes(job))) return { id, verdict: "not required" };
    return { id, verdict: run.conclusion === "success" ? "green" : "red", conclusion: run.conclusion };
  }
  const merged = firstRun(gh(["run", "list", "--workflow", id, ...PUSH_ON_MAIN, "--status", "success", "--limit", "1", "--json", "databaseId"]));
  if (!merged) return { id, verdict: "red", conclusion: `${run.conclusion}, no successful push run on main` };
  if (!jobNames(gh, merged.databaseId).some((job) => required.includes(job))) return { id, verdict: "not required" };
  return { id, verdict: "red", conclusion: run.conclusion };
}

export function judge(gh) {
  const required = JSON.parse(gh(["api", "repos/{owner}/{repo}/rules/branches/main", "--jq", REQUIRED_CHECKS]));
  if (!Array.isArray(required) || required.length === 0) throw new CouldNotJudge("the ruleset of main lists no required checks");
  const workflows = lines(gh(["workflow", "list", "--json", "id", "--jq", ".[].id"])).map((id) => judgeWorkflow(gh, id, required));
  const red = workflows.filter((workflow) => workflow.verdict === "red");
  if (red.length > 0) return { verdict: "red", workflows: red };
  const green = workflows.filter((workflow) => workflow.verdict === "green");
  if (green.length === 0) throw new CouldNotJudge("no workflow's latest push run on main provides a required check");
  return { verdict: "green", workflows: green };
}

function runGh(args) {
  return execFileSync("gh", args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
}

export function main(gh = runGh) {
  try {
    const result = judge(gh);
    const named = result.workflows.map((workflow) => `${workflow.id}=${workflow.conclusion ?? "success"}`).join(", ");
    process.stdout.write(`ci-stop: ${result.verdict}: required workflows ${named}.\n`);
    return result.verdict === "red" ? EXIT.red : EXIT.green;
  } catch (error) {
    const reason = error instanceof CouldNotJudge ? error.message : `gh failed: ${error.message}`;
    process.stderr.write(`ci-stop could not judge: ${reason}\n`);
    return EXIT.couldNotJudge;
  }
}

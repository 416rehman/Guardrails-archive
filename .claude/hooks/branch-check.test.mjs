// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
// Tests for branch-check.mjs: node --test .claude/hooks/branch-check.test.mjs
// Each fixture's `expect` is written by hand from the owner rule on #1875, never from the script.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { checkState, findings, loadRules } from "./branch-check.mjs";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const SCRIPT = join(HERE, "branch-check.mjs");
const FIXTURES = join(HERE, "fixtures", "branch-check");
const RULES_TEXT = readFileSync(join(HERE, "branch-rules.json"), "utf8");
const STATE_FIXTURES = readdirSync(FIXTURES).filter((name) => /^(pass|fail)-.+\.json$/.test(name));

function run(...args) {
  return spawnSync(process.execPath, [SCRIPT, ...args], { encoding: "utf8" });
}

function kindsAndSubjects(list) {
  return list.map(({ kind, subject }) => `${kind} ${subject}`).sort();
}

function withoutRule(key) {
  const raw = JSON.parse(RULES_TEXT);
  delete raw[key];
  return JSON.stringify(raw);
}

test("the fixture set seeds failures and clean states", () => {
  assert.ok(STATE_FIXTURES.filter((name) => name.startsWith("fail-")).length >= 4);
  assert.ok(STATE_FIXTURES.filter((name) => name.startsWith("pass-")).length >= 2);
});

for (const name of STATE_FIXTURES) {
  const fixture = JSON.parse(readFileSync(join(FIXTURES, name), "utf8"));
  const seededFailure = name.startsWith("fail-");

  test(`${name}: findings match the hand-written expectation`, () => {
    const found = findings(checkState(fixture), loadRules(RULES_TEXT));
    assert.deepEqual(kindsAndSubjects(found), kindsAndSubjects(fixture.expect));
    assert.equal(fixture.expect.length > 0, seededFailure);
  });

  test(`${name}: the command exits ${seededFailure ? 1 : 0}`, () => {
    const result = run("--state", join(FIXTURES, name));
    assert.equal(result.status, seededFailure ? 1 : 0, result.stderr);
    const printed = result.stdout.split(/\r?\n/);
    for (const { subject } of fixture.expect) assert.ok(printed.some((line) => line.startsWith(`${subject}: `)), subject);
  });
}

test("every finding names the fix and where it is written", () => {
  const fixture = JSON.parse(readFileSync(join(FIXTURES, "fail-replaced-pull-request-left-open.json"), "utf8"));
  for (const finding of findings(checkState(fixture), loadRules(RULES_TEXT))) {
    assert.match(finding.message, /grdr-work-issue, "Branches and pull requests"/);
  }
});

test("Dependabot's prefix and release-please's one branch are the only exemptions from the name", () => {
  const rules = loadRules(RULES_TEXT);
  assert.deepEqual(rules.exemptPrefixes, ["dependabot/"]);
  assert.deepEqual(rules.exemptNames, ["release-please--branches--main"]);
});

test("an exemption names exactly one of prefix and name", () => {
  for (const entry of [{ why: "neither" }, { prefix: "a/", name: "b", why: "both" }, { name: "", why: "empty" }]) {
    const raw = JSON.parse(RULES_TEXT);
    raw.exempt_from_name = [entry];
    assert.throws(() => loadRules(JSON.stringify(raw)), /exempt_from_name/);
  }
});

test("unreadable state exits 2, not 0", () => {
  const result = run("--state", join(FIXTURES, "unreadable.txt"));
  assert.equal(result.status, 2);
  assert.match(result.stderr, /^branch-check could not look: /);
  assert.equal(result.stdout, "");
});

test("--state with no file exits 2", () => {
  assert.equal(run("--state").status, 2);
});

test("a state of the wrong shape could not be looked at", () => {
  assert.throws(() => checkState({ repo: "example/repo", default_branch: "main", branches: ["main"] }), /documented shape/);
  assert.throws(
    () => checkState({ repo: "example/repo", default_branch: "main", branches: ["main"], pulls: [{ number: "1", head: "issue/1", head_repo: null, body: null }] }),
    /documented shape/,
  );
});

test("a branch list without the default branch is incomplete", () => {
  assert.throws(() => checkState({ repo: "example/repo", default_branch: "main", branches: [], pulls: [] }), /lacks the default branch/);
});

test("rules without a pattern, or with a pattern that has no issue number group, are refused", () => {
  assert.throws(() => loadRules(withoutRule("work_branch")), /no work_branch pattern/);
  assert.throws(() => loadRules(withoutRule("exempt_from_name")), /exempt_from_name/);
  assert.throws(() => loadRules(withoutRule("gh_output_limit_bytes")), /gh_output_limit_bytes/);
  const raw = JSON.parse(RULES_TEXT);
  raw.reference_line = "^refs #[0-9]+$";
  assert.throws(() => loadRules(JSON.stringify(raw)), /exactly one capture group/);
});

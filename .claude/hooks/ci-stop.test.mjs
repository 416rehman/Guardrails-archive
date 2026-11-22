// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
// Tests for ci-stop.mjs: node --test .claude/hooks/ci-stop.test.mjs
// Each fixture records GitHub's answers to the exact gh commands of grdr-build's CI stop condition,
// keyed by the start of the command, and the verdict the session's rulings on #1875 call for.
// `never_asked` lists answers that are there as a trap: reading them would be the defect.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { judge, main } from "./ci-judge.mjs";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const FIXTURES = join(HERE, "fixtures", "ci-stop");
const EXIT_FOR = { green: 0, red: 1, "could not judge": 2 };

function fakeGh(answers) {
  const asked = [];
  const gh = (args) => {
    const command = args.join(" ");
    asked.push(command);
    const match = answers.filter(([key]) => command.startsWith(key)).sort(([a], [b]) => b.length - a.length)[0];
    if (!match) throw new Error(`unexpected gh call: gh ${command}`);
    return match[1];
  };
  return { gh, asked };
}

function verdictOf(gh) {
  try {
    return judge(gh).verdict;
  } catch (error) {
    if (/^unexpected gh call/.test(error.message)) throw error;
    return "could not judge";
  }
}

function quietly(run) {
  const write = process.stdout.write;
  const writeError = process.stderr.write;
  const printed = [];
  process.stdout.write = (text) => printed.push(String(text)) > 0;
  process.stderr.write = (text) => printed.push(String(text)) > 0;
  try {
    return { status: run(), printed: printed.join("") };
  } finally {
    process.stdout.write = write;
    process.stderr.write = writeError;
  }
}

const FIXTURE_NAMES = readdirSync(FIXTURES).filter((name) => name.endsWith(".json"));

test("the fixtures cover green, a workflow that fails to start, and a pull request that renames its jobs", () => {
  for (const name of ["green.json", "verify-fails-to-start.json", "renamed-jobs-pull-request.json"]) assert.ok(FIXTURE_NAMES.includes(name), name);
});

for (const name of FIXTURE_NAMES) {
  const fixture = JSON.parse(readFileSync(join(FIXTURES, name), "utf8"));

  test(`${name}: reads ${fixture.expect}`, () => {
    const { gh, asked } = fakeGh(fixture.answers);
    assert.equal(verdictOf(gh), fixture.expect);
    for (const trap of fixture.never_asked ?? []) assert.ok(!asked.some((command) => command.startsWith(trap)), `asked: ${trap}`);
  });

  test(`${name}: main exits ${EXIT_FOR[fixture.expect]} and, when it judged, ends with the summary`, () => {
    const { gh } = fakeGh(fixture.answers);
    const { status, printed } = quietly(() => main(gh));
    assert.equal(status, EXIT_FOR[fixture.expect], printed);
    if (fixture.expect === "could not judge") assert.match(printed, /^ci-stop could not judge: /);
    else assert.match(printed.trim().split(/\r?\n/).at(-1) ?? "", new RegExp(`^ci-stop: ${fixture.expect}: required workflows .+\\.$`));
  });
}

test("a gh failure could not be judged, never green", () => {
  const gh = () => {
    throw new Error("HTTP 401");
  };
  const { status, printed } = quietly(() => main(gh));
  assert.equal(status, 2);
  assert.match(printed, /^ci-stop could not judge: gh failed: HTTP 401/);
});

test("no workflow providing a required check could not be judged", () => {
  const answers = [
    ["api repos/{owner}/{repo}/rules/branches/main", '["cargo-deny"]'],
    ["workflow list", "415167653\n"],
    ["run list --workflow 415167653 --branch main --event push --limit 1", '[{"databaseId":20,"conclusion":"success","status":"completed"}]'],
    ["run view 20 --json jobs", "Secrets (gitleaks)\n"],
  ];
  assert.equal(verdictOf(fakeGh(answers).gh), "could not judge");
});

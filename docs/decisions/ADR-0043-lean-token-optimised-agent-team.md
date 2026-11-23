# ADR-0043: Lean token-optimised agent team and evaluator consolidation

- Status: accepted
- Date: 2026-11-23
- Decided by: owner
- Spine: D-47, D-61, D-63, P14, P17
- Requires: ADR-0042
- RFC: not required: owner instruction optimising the agent kit workflow to eliminate token waste
- Work items: #2005

## Context
Running the full split evaluator suite (`eval-diff` twice, `eval-docs`, `eval-acceptance`, `eval-architecture`, `eval-security`, `eval-adversarial`, plus kind evaluators and the 9-seat persona council for RFCs) across up to 3 rounds consumed excessive AI tokens and repeatedly stalled progress on multi-round paperwork before writing product code. Evaluators also re-ran CI commands (`cargo fmt/clippy/test/deny`, static scans), GraphQL edit-history/timeline queries, and multi-prompt `grdr-audit` fan-outs already covered by deterministic CI workflows or unneeded for routine changes.

## Decision
1. **Consolidate evaluators to at most 2 roles (0 / 1 / 2 by tier):**
   - `low` docs, ADR, or additive test changes with green CI: **0** LLM evaluators.
   - `medium` (normal Rust/TS/UI/adapter changes) and `low` code changes: **1** lean evaluator (`eval-review`, combining diff, docs, acceptance, architecture, and structure in a single diff-focused pass).
   - `high` and `trust-core` (including RFCs): **2** evaluators (`eval-review` + `eval-security`, where `eval-security` covers security, adversarial abuse scenarios, and licence/reference-model checks), run on **2 distinct models or providers** per `.agents/models.toml` so D-63 remains satisfied.
   - Inline `[checklist_addons]` in `.claude/risk-tiers.toml` replace separate `eval-ux`, `eval-a11y`, `eval-api`, `eval-licence`, `eval-platform`, `eval-performance`, and the 9-seat RFC persona council fan-out. Legacy agent files stay inactive unless explicitly invoked.
2. **CI-first verification:** Evaluators check `gh pr checks` on the exact head `<sha>` and do not re-run `cargo`, `branch-check`, `docs-check`, or static security scans locally when CI is already green on that commit.
3. **Skip unnecessary leads and ceremony:** When an issue already states a clear goal, target paths, and check command, implement directly without spawning a separate spec-writer lead. Trivial `low` fixes may be applied directly by the orchestrating session.
4. **Compact context and 2-round cap:** Agents load only the issue, the diff, and cited design sections rather than full decision logs; review caps at 2 rounds (`[limits].max_rounds = 2` in `.claude/risk-tiers.toml`), with round 2 checking only the new commits.

## Consequences
Token usage per issue drops substantially (0 to 2 focused runs instead of 4 to 16 runs per round, with no redundant tool execution or persona council loops), unblocking fast Rust delivery while keeping `high` and `trust-core` protected by two-model independent review (D-63) and full deterministic CI gates.

## Alternatives rejected
- Keeping 6 to 16 evaluators per issue across 3 rounds: rejected due to unsustainable token cost and latency.
- Dropping independent review on `trust-core` paths altogether: rejected because D-63 requires two passing evaluations on distinct models for security-critical paths.

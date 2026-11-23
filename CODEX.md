# CODEX.md

OpenAI Codex and ChatGPT sessions read `AGENTS.md` automatically at repository start and use this overlay
for provider-specific execution rules.

## Codex and ChatGPT specifics
- Model routing: read `.agents/models.toml` (`[providers.openai]`).
  - `architect` and `high` (`tier:high` or `trust-core`): `gpt-5.4`.
  - `standard` and `fast`: `gpt-5.4-mini`.
  - Cross-model review (`D-63`): for `tier:high` or `trust-core`, satisfy `distinct_models = 2` either
    across providers (for example Codex/ChatGPT plus Claude or Gemini) or across distinct models, and
    record `Provider:` and `Model:` in every evaluator verdict.
- Skills and roles: read `.claude/agents/<role>.md` for role duties and `.claude/skills/<name>/SKILL.md`
  for procedures (`grdr-work-issue`, `grdr-build`, `grdr-start-item`, `grdr-structure`, `grdr-verify`,
  `grdr-handoff`, `grdr-evaluate`, `cleanup`).
- Gates and hooks (run directly before pushing or opening/merging a PR, since Codex CLI does not fire
  `.claude/settings.json` or `.agents/hooks.json` automatically):
  - Set `GH_REPO=416rehman/Guardrails`, `GH_PROMPT_DISABLED=1`, and `CARGO_TERM_COLOR=never`.
  - Run `node .claude/hooks/branch-check.mjs` before and after `gh pr create` / `gh pr merge`.
  - Run `node .claude/hooks/docs-check.mjs --ci` (or verify `Docs:` and `[release_note]` rules) before
    creating or editing a pull request.
  - Run `node --test .claude/hooks/branch-check.test.mjs .claude/hooks/ci-stop.test.mjs .agents/hooks/agy-pre-tool-use.test.mjs`
    when changing agent-kit files.
- Worktrees, branches and commits:
  - Work in a dedicated git worktree (such as `.agent/worktrees/wt-<n>`) on `issue/<n>-<slug>`.
  - Every non-exempt PR must target an issue (`Refs #<n>` / `Closes #<n>`), include the issue name in both
    its branch slug and its PR title or `Issue: #<n> <title>` header, and be the sole open PR for `#<n>`.
  - Commit with `git commit -m '<subject>'`: one Conventional Commit line (<= 72 characters), no body, no
    trailers, no AI credit line.

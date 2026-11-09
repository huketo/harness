# Focused verification

Harness is a Node.js 24 + TypeScript repository: `.ts` files run directly through Node's type stripping, so there is no build step. Python collectors and analyzers live inside skills. `mise.toml` pins Node and rulesync and owns every repository command; run them through `mise run` so the pinned versions are used. Select the narrowest boundary that proves the change.

For behavior changes, test edits, flaky failures, or fixture/runner changes, use the tracked `skills/tdd/SKILL.md` procedure when available. When a required runtime is unavailable, report the exact missing prerequisite and describe source inspection only as source inspection.

## Repository check

```bash
mise install
mise run check
```

`mise run check` installs the pinned development dependencies (`npm ci`), runs `tsc --noEmit`, runs every maintained `node --test` suite, and confirms that the tracked plugin files (`plugin/.claude-plugin/plugin.json`, `plugin/hooks/hooks.json`) match `node plugin/build.mjs --host claude`. CI runs the same task on every push and pull request. It reads no host configuration.

## Node tests

Tests use `node:test` with `node:assert/strict` and live beside the mechanism they exercise. Pass the changed test file or owning directory explicitly through the pinned Node, for example:

```bash
mise exec -- node --test t3/scheduled/host-sync.test.mjs
mise exec -- node --test plugin/hooks/merge-guard.test.mjs plugin/build.test.mjs plugin/install.test.mjs
mise exec -- node --test codex/review.test.ts
mise exec -- node --test t3/scheduled/guard.test.mjs
mise exec -- node --test 'scripts/skill-eval/**/*.test.ts'
mise exec -- node --test scripts/install.test.ts scripts/safe-generate.test.ts
```

The host-sync test uses temporary local Git repositories and is the focused boundary for `t3/scheduled/host-sync.mjs`. The merge-guard test covers both `plugin/hooks/merge-guard.mjs` and `skills/full-send/scripts/harness-mode` with temporary repositories, a temporary `HOME`, and a synthetic full-send allowlist. The plugin installer test puts fake `claude` and `agy` executables first on `PATH`; it does not prove the real CLIs accept the artifacts. The Codex reviewer test skips its five installed-binary cases when `codex` is not on `PATH`, as on CI; with `codex` installed, a PATH shim answers `exec` and `debug models` with synthetic output, and the sandbox, feature, and MCP probes run the installed binary under a temporary `HOME` and `CODEX_HOME`; no model is called. The T3 guard test uses temporary job files and `XDG_STATE_HOME`; it covers timeouts, daily run limits, failure stop, and `daysOfMonth` admission. The skill-eval tests run the runner and grader against temporary repositories with a fake agent and synthetic captures; they call no model and do not prove a real comparison run.

`scripts/install.test.ts` covers the skill, agy, and Codex links and `scripts/update.ts` against a temporary `HOME` and temporary local Git remotes: skills-only ownership, `CLAUDE_CONFIG_DIR`, conflicts that are preserved, fast-forward reinstallation, and refusal of dirty, topic-branch, or divergent checkouts. `scripts/safe-generate.test.ts` runs the pinned rulesync against synthetic Claude Code and agy settings in a temporary `HOME`; it proves that existing entries survive, that `CLAUDE_CONFIG_DIR` is honored, and that a second run changes nothing. It skips the rulesync cases when rulesync is not installed, and it does not prove the agents enforce the generated rules.

To check built plugin artifacts against installed CLIs, validate the tracked Claude plugin and build the agy copy into a temporary directory only:

```bash
claude plugin validate --strict plugin
out=$(mktemp -d)
node plugin/build.mjs --host agy --out "$out"
agy plugin validate "$out/agy" --strict
rm -rf "$out"
```

Nothing under `archived/` is tested or maintained; do not run or repair its tests as part of current work. `mise run test` lists the maintained suites explicitly so `archived/` is never collected.

## Python

The daily-report GitLab collector has a focused regression file:

```bash
python3 -m unittest discover -s skills/daily-report/scripts -p test_collect_gitlab.py -v
```

This collector test does not prove authentication, upstream availability, draft quality, or manual Daou Office submission. The public repository contains no Daou Office API or automatic-submission test boundary.

The cost-audit analyzer and the MR watcher have synthetic, offline suites; neither reads real session logs nor contacts GitLab or GitHub:

```bash
python3 -m unittest discover -s skills/cost-audit -p 'test_*.py'
python3 -m unittest discover -s skills/babysit-mr/scripts -p 'test_*.py'
```

For the `diagram-design` logo helper (offline) and render check (needs Playwright with Chromium; `uv run --with playwright` avoids a system install):

```bash
python3 -m unittest discover -s skills/diagram-design/scripts -p test_logos.py -v
uv run --with playwright python3 -m unittest discover -s skills/diagram-design/scripts -p test_render_check.py -v
```

These prove the safety verdicts, inlining, and the render checks against fixtures; they do not fetch live logos. A live fetch (`scripts/logos.py fetch`) is network evidence and is reported separately.

## Shell

For an edited shell script, first check the exact file with Bash's parser, for example:

```bash
bash -n skills/full-send/scripts/harness-mode
bash skills/review-loop/scripts/review-tier.test.sh
bash skills/review-loop/scripts/tree-unchanged.test.sh
```

Use `shellcheck` only when it is available; it is not a repository-installed mandatory tool. Parser or static-analysis success does not prove link ownership, backup behavior, installed tool versions, or live configuration.

## Host-aware inspections

These source-defined checks inspect the current machine and are appropriate only when the task authorizes host inspection:

```bash
mise run plan
```

`mise run plan` reports planned links, backups, conflicts, and permission changes without applying them. Its permission step runs rulesync in a throwaway `HOME` seeded with copies of the agent settings files; its plugin step reads `claude plugin marketplace list --json` and `claude plugin list --json` when `claude` is on `PATH` but installs nothing. It does not replace a focused unit or integration test of changed source.

To exercise a full installation without touching the real configuration, point `HOME` (and `CLAUDE_CONFIG_DIR`, when set) at a temporary directory and keep mise's own directories on the real ones so the checkout stays trusted:

```bash
real="$HOME" fake=$(mktemp -d)
MISE_DATA_DIR="$real/.local/share/mise" MISE_CONFIG_DIR="$real/.config/mise" \
  MISE_STATE_DIR="$real/.local/state/mise" MISE_CACHE_DIR="$real/.cache/mise" \
  HOME="$fake" mise run install
```

Without `claude` or `agy` settings directories under the fake `HOME`, their steps are skipped. The mutating form against the real `HOME` is governed by [`authority.md`](authority.md) and is not routine verification.

## Authenticated collection

Daily-report collection can authenticate to GitLab and read private calendar feeds. Its output can contain private work and schedule data even though final Daou Office entry is manual. Obtain the authority required by [`authority.md`](authority.md), keep artifacts outside version control, and label the evidence precisely.

## Delivery evidence

For each requested contract, report separately:

- the focused command and selected test or scenario;
- pass, failure, or skip with the observed reason;
- whether dependencies were synthetic, temporary-local, installed-host, or live external;
- every relevant check not run;
- generated artifacts and whether they were removed or kept outside version control.

A successful command is evidence only for the boundary it exercised. Do not describe source review as a runtime pass, a dry run as a live operation, or a mocked suite as proof of an external service.

# Focused verification

Harness is a Node.js 24 + TypeScript repository: `.ts` files run directly through Node's type stripping, so there is no build step. Python collectors and analyzers live inside skills. `mise.toml` pins Node and rulesync and owns every repository command; run them through `mise run` so the pinned versions are used. Select the narrowest boundary that proves the change.

For behavior changes, test edits, flaky failures, or fixture/runner changes, use the tracked `skills/tdd/SKILL.md` procedure when available. When a required runtime is unavailable, report the exact missing prerequisite and describe source inspection only as source inspection.

## Repository check

```bash
mise install
mise run check
```

`mise run check` installs the pinned development dependencies (`npm ci`), runs `tsc --noEmit`, runs every maintained `node --test` suite, runs `scripts/check-repo.ts` (`mise run rules`: skill frontmatter, skill cases, and relative Markdown links), and confirms that the tracked plugin files (`plugin/.claude-plugin/plugin.json`, `plugin/hooks/hooks.json`) match `node plugin/build.mjs --host claude`. CI runs the same task on every push and pull request. It reads no host configuration.

## Node tests

Tests use `node:test` with `node:assert/strict` and live beside the mechanism they exercise. Pass the changed test file or owning directory explicitly through the pinned Node, for example:

```bash
mise exec -- node --test t3/scheduled/host-sync.test.mjs
mise exec -- node --test plugin/hooks/merge-guard.test.mjs plugin/hooks/allowlist.property.test.mjs plugin/build.test.mjs plugin/install.test.mjs
mise exec -- node --test codex/review.test.ts
mise exec -- node --test t3/scheduled/guard.test.mjs
mise exec -- node --test 'scripts/skill-eval/**/*.test.ts'
mise exec -- node --test scripts/install.test.ts scripts/safe-generate.test.ts scripts/check-repo.test.ts
mise exec -- node --test skills/harness-flow/scripts/flow-status.test.mjs
mise exec -- node --test skills/design-md/scripts/oklch.test.mjs
mise exec -- node --test skills/make-logo/scripts/collection.test.mjs skills/make-logo/scripts/book_pages.test.mjs
mise exec -- node --test 'skills/awesome-interface/scripts/*.test.mjs'
mise exec -- node --test scripts/skill-eval/route.test.ts
```

`plugin/hooks/allowlist.property.test.mjs` is a property test (fast-check, fixed seed, 200 generated cases): it asserts that `harness-mode allowlist` and the merge guard's `allowedRepo` give the same answer for generated remote URLs and allowlist lines. It covers that agreement only, not whether either reading is the intended one.

To observe a change to the merge guard, `harness-mode`, or the installer end to end, follow the repository's own verification skill, [`.agents/skills/verify-hstack/SKILL.md`](../../.agents/skills/verify-hstack/SKILL.md). It drives the real files against a synthetic `HOME` under `var/verify/` and is not part of `mise run check`.

`skills/harness-flow/scripts/flow-status.test.mjs` runs the read-only status script against synthetic repositories and checks which skill it names next. `mise run test` collects every `skills/*/scripts/*.test.mjs`.

The host-sync test uses temporary local Git repositories and is the focused boundary for `t3/scheduled/host-sync.mjs`. The merge-guard test covers both `plugin/hooks/merge-guard.mjs` and `skills/full-send/scripts/harness-mode` with temporary repositories, a temporary `HOME`, and a synthetic full-send allowlist; its repositories carry a CI definition and a `verify-*` skill unless a case removes them to exercise the readiness degrade. The plugin installer test puts fake `claude` and `agy` executables first on `PATH`; it does not prove the real CLIs accept the artifacts. The Codex reviewer test skips its five installed-binary cases when `codex` is not on `PATH`, as on CI; with `codex` installed, a PATH shim answers `exec` and `debug models` with synthetic output, and the sandbox, feature, and MCP probes run the installed binary under a temporary `HOME` and `CODEX_HOME`; no model is called. The T3 guard test uses temporary job files and `XDG_STATE_HOME`; it covers timeouts, daily run limits, failure stop, and `daysOfMonth` admission. The skill-eval tests run the runner and grader against temporary repositories with a fake agent and synthetic captures; they call no model and do not prove a real comparison run. `scripts/skill-eval/route.test.ts` runs the description routing runner the same way, with a fake agent against a temporary repository; it calls no model.

`skills/design-md/scripts/oklch.test.mjs` checks the color forms `oklch.mjs` reads and refuses, and its CLI output, offline. `skills/make-logo/scripts/collection.test.mjs` and `book_pages.test.mjs` check collection manifests and pulls against a stubbed `fetch` in a temporary cache, and the logo book's page-image cleanup; they reach no network. The awesome-interface capture tests (`capture.test.mjs`, `capture-guard.test.mjs`, `pixdiff.test.mjs`, `find-chromium.test.mjs`) serve a synthetic page that sends POST, PUT, PATCH, DELETE, and GET to a local server and check which requests arrived. Their browser cases skip when `find-chromium.mjs` finds no Playwright package or no Chromium that launches. Playwright is not a repository dependency, so exercising those cases needs both: run them from a folder whose `node_modules` has Playwright, and a browser it can launch; `PW_CHROMIUM` only selects which Chromium executable Playwright launches. All of these run in `mise run test` and `mise run check`.

`mise run skill-route` is the paid live routing run: one model call per distinct prompt in `scripts/skill-eval/routing/design.json`, classifying from the design skills' descriptions alone. It is not part of `check` or CI, it observes description-based selection rather than actual skill activation, and it assumes a login without server-managed policy. Run it only after a person approves the paid run, except where [`authority.md`](authority.md#actions-that-need-no-question) lists the `make-skill` runs; `mise run skill-route -- --dry-run` prints the requests without calling a model.

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

### make-font and make-logo gates

The make-font and make-logo gate tests are Python `unittest` suites on synthetic inputs: FontBuilder fonts built in the test, never a downloaded font, and synthetic images. They are not part of `mise run check` or CI. Run them after changing either skill and before integrating that change:

```bash
mise run test-font-gates
mise run test-logo-gates
mise run test-skill-gates   # both
```

The tasks run under `uv` with Python 3.12 (`uv run --no-project --python 3.12`), so the first run downloads Python and the packages and later runs reuse the cache. `test-logo-gates` needs `potrace` on `PATH` (or in the make-logo cache): without it the trace and seal cases are skipped, and a run with skips does not prove the trace gates. The tasks and the child interpreters the tests start pass `-B`, so a run leaves no `__pycache__` in the script folders. They prove the gates' accept and refuse decisions against those fixtures; they do not call GitHub or Google Fonts, run fontbakery, or render a font or logo book in a browser, and those remain unverified until run separately.

## Shell

For an edited shell script, first check the exact file with Bash's parser, for example:

```bash
bash -n skills/full-send/scripts/harness-mode
bash skills/review-loop/scripts/review-tier.test.sh
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

## Delivery evidence

For each requested contract, report separately:

- the focused command and selected test or scenario;
- pass, failure, or skip with the observed reason;
- whether dependencies were synthetic, temporary-local, installed-host, or live external;
- every relevant check not run;
- generated artifacts and whether they were removed or kept outside version control.

A successful command is evidence only for the boundary it exercised. Do not describe source review as a runtime pass, a dry run as a live operation, or a mocked suite as proof of an external service.

# Focused verification

Harness has shell installers, Bun/TypeScript scripts and runners, and Python collectors and analyzers. It has no root package manifest or single universal quality command. Select the narrowest existing boundary that proves the change.

For behavior changes, test edits, flaky failures, or fixture/runner changes, use the tracked `skills/tdd/SKILL.md` procedure when available. When a required runtime is unavailable, report the exact missing prerequisite and describe source inspection only as source inspection.

## Bun and TypeScript

Bun tests import `bun:test` and live beside the mechanism they exercise. Pass the changed test file or owning directory explicitly, for example:

```bash
bun test t3/scheduled/host-sync.test.mjs
bun test plugin/hooks/merge-guard.test.mjs plugin/build.test.mjs plugin/install.test.mjs
bun test codex/review.test.ts
bun test t3/scheduled/guard.test.mjs
```

The host-sync test uses temporary local Git repositories and is the focused boundary for `t3/scheduled/host-sync.mjs`. The merge-guard test covers both `plugin/hooks/merge-guard.mjs` and `skills/full-send/scripts/harness-mode` with temporary repositories, a temporary `HOME`, and a synthetic full-send allowlist. The plugin installer test puts fake `claude` and `agy` executables first on `PATH`; it does not prove the real CLIs accept the artifacts. The Codex reviewer test needs an installed `codex`: a PATH shim answers `exec` and `debug models` with synthetic output, and the sandbox, feature, and MCP probes run the installed binary under a temporary `HOME` and `CODEX_HOME`; no model is called. The T3 guard test uses temporary job files and `XDG_STATE_HOME`; it covers timeouts, daily run limits, failure stop, and `daysOfMonth` admission.

To check built plugin artifacts against installed CLIs, build into a temporary directory only:

```bash
out=$(mktemp -d)
node plugin/build.mjs --out "$out"
claude plugin validate --strict "$out/claude"
agy plugin validate "$out/agy" --strict
rm -rf "$out"
```

When a change crosses components, pass each owning directory with a `./` prefix so Bun does not also collect tests under `archived/`:

```bash
bun test ./t3 ./plugin ./codex
```

Nothing under `archived/` is tested or maintained; do not run or repair its tests as part of current work.

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

## Shell

For an edited shell script, first check the exact file with Bash's parser:

```bash
bash -n install.sh
```

The installer/update integration test uses temporary local Git remotes and an
isolated HOME. It proves skills-only ownership, fast-forward reinstallation,
and refusal of dirty, topic-branch, or divergent checkouts without a live install:

```bash
bash -n update.sh update.test.sh
bash update.test.sh
bash skills/review-loop/scripts/review-tier.test.sh
bash skills/review-loop/scripts/tree-unchanged.test.sh
```

Use `shellcheck` only when it is available; it is not a repository-installed mandatory tool. Parser or static-analysis success does not prove link ownership, backup behavior, installed tool versions, or live configuration.

## Host-aware inspections

These source-defined checks inspect the current machine and are appropriate only when the task authorizes host inspection:

```bash
bash install.sh --dry-run
```

`install.sh --dry-run` reports planned links, backups, and conflicts without applying them. Its plugin step runs `plugin/install.mjs --dry-run`, which reads `claude plugin marketplace list --json` and `claude plugin list --json` when `claude` is on `PATH` but installs nothing. It does not replace a focused unit or integration test of changed source.

The mutating form of the installation command is governed by [`authority.md`](authority.md) and are not routine verification.

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

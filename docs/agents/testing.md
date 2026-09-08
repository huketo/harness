# Focused verification

Harness has shell installers, Bun/TypeScript extensions and runners, and Python collectors and benchmarks. It has no root package manifest or single universal quality command. Select the narrowest existing boundary that proves the change.

For behavior changes, test edits, flaky failures, or fixture/runner changes, use the tracked `skills/tdd/SKILL.md` procedure when available. When a required runtime is unavailable, report the exact missing prerequisite and describe source inspection only as source inspection.

## Bun and TypeScript

Bun tests import `bun:test` and live beside the mechanism they exercise. Pass the changed test file or owning directory explicitly, for example:

```bash
bun test omp/native-runtime.test.ts
bun test omp/extensions/profiles/profiles.test.ts
bun test herdr/scripts/harness-run.test.ts
bun test herdr/cron/host-sync.test.mjs
```

The host-sync test uses temporary local Git repositories and is the focused boundary for `herdr/cron/host-sync.mjs`. Some extension tests resolve packages or authentication storage from an installed OMP CLI; inspect their setup before running and report that prerequisite instead of silently substituting Bun's package cache.

Use the aggregate Bun boundary only when a change crosses those components:

```bash
bun test omp/extensions omp/native-runtime.test.ts herdr/scripts/harness-run.test.ts
```

## Python

The benchmark runner uses standard-library `unittest`; its regression suite does not invoke models or read task fixtures:

```bash
python3 -m unittest discover -s bench/tests
```

The daily-report GitLab collector has a focused regression file:

```bash
python3 -m unittest discover -s skills/daily-report/scripts -p test_collect_gitlab.py -v
```

This collector test does not prove authentication, upstream availability, draft quality, or manual Daou Office submission. The public repository contains no Daou Office API or automatic-submission test boundary.

## Shell

For an edited shell script, first check the exact file with Bash's parser:

```bash
bash -n install.sh
bash -n omp/config.apply.sh
```

Use `shellcheck` only when it is available; it is not a repository-installed mandatory tool. Parser or static-analysis success does not prove link ownership, backup behavior, installed tool versions, or live configuration.

## Host-aware inspections

These source-defined checks inspect the current machine and are appropriate only when the task authorizes host inspection:

```bash
bash install.sh --dry-run
bash omp/config.apply.sh --check
bun omp/native-runtime.ts --check
```

`install.sh --dry-run` reports planned links, backups, conflicts, and the runtime patch without applying them. `config.apply.sh --check` reports managed OMP drift and exits nonzero when differences exist. `native-runtime.ts --check` requires OMP 18.1.13 or 18.1.14 and verifies its compatibility patch. None replaces a focused unit or integration test of changed source.

The mutating forms of installation and configuration commands are governed by [`authority.md`](authority.md) and are not routine verification.

## Benchmarks and authenticated collection

`python3 bench/bench.py run --dry-run` validates selection and estimates cost without invoking candidate models. An actual benchmark run invokes providers and writes run data.

Daily-report collection can authenticate to GitLab and read private calendar feeds. Its output can contain private work and schedule data even though final Daou Office entry is manual. Obtain the authority required by [`authority.md`](authority.md), keep artifacts outside version control, and label the evidence precisely.

## Delivery evidence

For each requested contract, report separately:

- the focused command and selected test or scenario;
- pass, failure, or skip with the observed reason;
- whether dependencies were synthetic, temporary-local, installed-host, or live external;
- every relevant check not run;
- generated artifacts and whether they were removed or kept outside version control.

A successful command is evidence only for the boundary it exercised. Do not describe source review as a runtime pass, a dry run as a live operation, or a mocked suite as proof of an external service.

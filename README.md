# Harness

[English](README.md) · [한국어](README.ko.md)

**A version-controlled personal workstation setup for coding agents: shared skills, model profiles, visible execution, and task-based evaluation.**

Harness connects an existing [Oh My Pi](https://github.com/can1357/oh-my-pi) (OMP), [Herdr](https://github.com/herdrdev/herdr), and Antigravity CLI (`agy`) environment. Its OMP layer installs only the `profiles` and `herdr` extensions. Harness is a personal configuration and extension showcase, not a standalone agent, a hosted service, or a replacement for those tools.

[Installation](docs/guides/installation.md) · [Documentation](docs/index.md) · [Usage](docs/guides/usage.md) · [Benchmarks](bench/README.md) · [Reuse policy](CONTRIBUTING.md) · [MIT License](LICENSE)

## What it adds

| Capability | What you get |
| --- | --- |
| Shared skills | Repository-owned instructions linked into OMP, Claude Code, and AGY, with retained notices for adopted material. |
| Model profiles | Purpose-based model and effort selection through `/profile` and `omp-profile`; `/effort` can remain local to one session. |
| Session account pinning | OMP's built-in `/session pin` provides manual, per-session account selection. Harness does not synchronize an account choice across sessions. |
| Context compaction | OMP's built-in compaction, managed through six policy keys, without a custom OMP build or runtime patch. |
| Visible execution | `harness-run` launches and revisits commands or independent agents in Herdr without moving existing task subagents. |
| Task-based evaluation | Replayable fixtures, protected grading material, cost accounting, and routing proposals—not a universal model leaderboard. |
| Personal operations | Cost audits, guarded host synchronization, and a human-reviewed daily-report drafting workflow. These are not hosted services. |

## Recommended environment

The maintained showcase target is **Linux or WSL2 with Bash, GNU-compatible utilities, a stock OMP installation available as `omp`, and Bun 1.3.14**. Python 3 is needed for configuration inspection and benchmarks. An existing `~/.claude/CLAUDE.md` is required by the current installer. Install and authenticate the underlying tools separately. Native Windows and macOS are not maintained installation targets. Future OMP or Bun releases must be reviewed rather than assumed compatible.

```bash
git clone https://github.com/huketo/harness.git
cd harness
bash install.sh --dry-run
```

Review the [installation guide](docs/guides/installation.md), the source, and the proposed workstation changes before proceeding.

```bash
bash install.sh
bash omp/config.apply.sh --check
```

**Installation changes your workstation:** it links shared assets, backs up eligible existing configuration files, and retires old `harness-accounts` and `harness-native-compaction` links only when they are owned by this checkout. A foreign or unexpected entry remains a conflict and is not removed; dry-run reports the plan without mutating it. The installer leaves authentication, saved preferences, session transcripts, and backups unchanged. Legacy Harness native-compaction replay and portable migration are no longer available, so a preserved legacy session is not guaranteed to resume. Restart every OMP process that was already loaded after installation.

The settings check does not apply changes; exit `1` reports differences. To opt into the repository's personal OMP defaults after inspecting them:

```bash
bash install.sh --with-config
```

This includes model routing, fallback behavior, skill discovery, the built-in compaction policy, and Auto QA consent. It is not required merely to link extensions. AGY settings and cron jobs are not restored by the installer.

## Everyday use

Inside OMP:

```text
/session pin
/profile code
/effort high
/compact
```

- `/session pin` is OMP's built-in manual account selector. Its choice applies only to the current session; Harness provides no shared account synchronization.
- `/effort high` changes the current session and model. Adding `--profile` explicitly changes shared model-profile state.
- `/compact` uses stock OMP compaction. The managed policy sets `enabled: true`, `methodOrder: remote → handoff → soft`, `keepRecentTokens: 40000`, `thresholdPercent: 75`, `thresholdTokens: -1`, and `handoffSaveToDisk: true`. See the [built-in compaction workflow](docs/guides/usage.md#내장-자동-압축).

From a terminal, with `~/.local/bin` on `PATH`:

```bash
omp-profile list
omp-profile show code
harness-run --help
```

Use Herdr when a command is long-running or benefits from human observation or interaction. Run short reads, builds, and tests with normal tools. Finite command runs automatically capture exit artifacts and logs, verify ownership, and close their created tab, preventing pager stalls with `PAGER=cat`. Detached commands require an explicit `--name` and remain retained. Completed command tabs can be cleaned with `harness-run prune --workspace current --dry-run` or `--apply`. For example, in a project that provides a development-server command:

```bash
harness-run command --name dev --detach -- bun run dev
harness-run read dev
```

Use `/delegation` to inspect session-local routing, `agy` for interactive AGY-first workers, `native` to restore native delegation, `off` to stop new delegation, and `model` to select the default AGY model. Existing workers survive mode changes. Ordinary startup remains native; `bun omp/herdr-trial.ts` is an optional AGY-start launcher. No OMP core rebuild or shared-setting change is required. See [routing behavior and limitations](docs/guides/usage.md#세션별-위임-모드).

A detached handle is not readiness evidence. Check the output and service before using it. Independent agents need an explicit brief; built-in task agents remain in OMP's Agent Hub. The `harness-herdr` extension gates OMP's built-in `ask` tool: each call runs `herdr-hitl channel` first and is blocked unless the channel is `terminal`. See [detailed usage and state boundaries](docs/guides/usage.md) (Korean).

## Evaluate before changing defaults

Preview the configured benchmark matrix without calling a model:

```bash
python3 bench/bench.py run --dry-run
```

Actual runs require authenticated model access and can incur charges. Results and collected work data belong under ignored `var/`, not in commits. See [benchmark commands and interpretation](bench/README.md), [benchmark research](docs/BENCH-SURVEY.md), and [pricing evidence](docs/PRICING.md). Recorded measurements are dated personal observations, not performance guarantees.

## Configuration and safety

- **One owner per asset:** hand-maintained assets are symlinked; tool-managed state stays with its owning tool. Distributed snapshots are review examples, not host backup or restore instructions.
- **Credentials stay local:** keep API keys, OAuth state, private calendar URLs, messaging tokens, session logs, and report inputs outside version control. `.gitignore` is not a secret scanner and does not erase history.
- **Review external effects:** cron activation, messages, plugin updates, remote writes, and Git publication require deliberate owner action. No distributed snapshot should be activated unchanged.
- **No sandbox claim:** permission policies and file-tool deny rules do not isolate arbitrary shell access. Treat permissive workstation settings as personal risk choices, not security defaults.
- **Live links matter:** editing or updating this checkout changes installed assets immediately. There is no automated uninstaller; [manual rollback boundaries](docs/guides/installation.md#updating-and-undoing) explain what link removal does not undo.

## Find your way around

| Path | Purpose |
| --- | --- |
| [`omp/`](omp/) | The `profiles` and `herdr` extensions, model profiles, prompts, and declarative settings. |
| [`herdr/`](herdr/) | Terminal integration, helper commands, plugin pins, cost audit, and guarded host sync. |
| [`skills/`](skills/) | Personal skills and adopted skills with retained notices. |
| [`agy/`](agy/) | AGY plugin and an example settings snapshot. |
| [`bench/`](bench/) | Benchmark runner, tasks, fixtures, references, and oracles. |
| [`third-party/`](third-party/) | External provenance, lock snapshots, and patches. |
| [`docs/`](docs/index.md) | Installation, usage, ownership, evidence, and maintenance guidance. |
| `var/` | Ignored local reports and generated state; only `.gitkeep` is tracked. |

## License, reuse, and maintenance

Harness is released under the [MIT License](LICENSE). Third-party and adopted components retain their own copyright notices and license terms; [adopted-skills.json](third-party/adopted-skills.json) records their provenance.

This repository is a personal showcase maintained only for its owner. Bug reports, feature requests, pull requests, other contributions, support requests, and vulnerability reports are not accepted. You may fork, modify, and redistribute the code under the MIT License, but no maintainer service or response is offered. See [CONTRIBUTING.md](CONTRIBUTING.md) for the complete policy.

Coding agents enter through [AGENTS.md](AGENTS.md). The README's language switch, capability overview, quick start, and deeper-documentation layout take structural inspiration from [oh-my-hermes](https://github.com/rlaope/oh-my-hermes); its branding, artwork, implementation, and product claims are not copied.

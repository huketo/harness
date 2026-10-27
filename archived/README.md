# Retired sources

This directory keeps sources that are no longer installed or run, for historical reference only. `install.sh`, `update.sh`, host sync, and T3 scheduled tasks do not read this directory, and its tests are not maintained or run as part of current verification.

| Path | Contents | Retired on |
| --- | --- | --- |
| `herdr/` | Herdr configuration, the plugin manifest, the empty herdr-cron snapshot, the manual cost-audit runner, the HITL configuration example, and the `harness-run` launcher | 2026-10-27 |
| `omp/` | Oh My Pi (OMP) settings application, model profiles, prompts, extensions, the restricted reviewer, and the Herdr/OMP human-in-the-loop rules (`APPEND_SYSTEM.md`) | 2026-10-27 |
| `skills/herdr-orchestrate`, `skills/herdr-quorum` | Skills that split agent work across Herdr panes | 2026-10-27 |
| `bench/` | The model benchmark that used OMP as its execution engine, its synthetic fixtures and oracles, and its design survey (`SURVEY.md`) | 2026-10-27 |

Agents now run as T3 Code threads. Parallel delegation belongs to `skills/t3-orchestrate`, scheduled runs to `t3/scheduled/`, and human questions to `docs/agents/hitl.md`. Herdr remains only as a plain terminal multiplexer, which T3 threads drive through `skills/t3-terminal`. The host-sync guard moved from `herdr/cron/` to `t3/scheduled/`.

Paths inside these files refer to their pre-retirement locations. Restoring any of them requires moving it back and reconnecting the installer and documentation in a separate change.

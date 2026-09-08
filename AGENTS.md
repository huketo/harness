# Harness agent guide

This file is the compact repository router for coding agents working for the owner. Apply higher-priority system and user instructions first. Read only the topic guide needed for the task; each linked guide owns its subject.

## Start here

1. Bound the requested outcome, owning files, affected callers, and external or sensitive effects.
2. Inspect the source, nearby tests, and relevant repository documentation before editing. Source behavior wins over stale prose.
3. Reuse the existing shell, Bun, or Python mechanism instead of adding a second convention.
4. Verify at the narrowest boundary that proves the requested behavior, then report exact evidence and relevant checks not run.

Before asking a person or handling an unattended run, read [`.omp/APPEND_SYSTEM.md`](.omp/APPEND_SYSTEM.md). It owns this repository's human-in-the-loop channel, approval-response, no-terminal-gate, and unattended-run rules.

## Repository map

- `omp/` — OMP configuration application, profiles, prompts, extensions, and the OMP 18.1.13/18.1.14 native-runtime compatibility patch.
- `herdr/` — Herdr configuration, launch helpers, plugin pins, cost audit, and guarded host-sync sources. The distributed cron snapshot contains no jobs.
- `skills/` — personal skill sources; preserve each adopted skill's license and provenance.
- `bench/` — Python benchmark runner, synthetic fixtures, oracles, references, and runner tests.
- `agy/` — Antigravity CLI integration owned by this repository.
- `third-party/` — public external pins, provenance records, and patches; it is not a second source tree.
- `docs/` — user, operational, ownership, evidence, pricing, benchmark, and owner-maintenance documentation.
- `var/` — ignored runtime output. Treat it as sensitive even though it is inside the checkout.

[`docs/REPO.md`](docs/REPO.md) owns source-versus-runtime boundaries. Keep credentials, private calendar URLs, report bodies, session transcripts, logs, databases, audit inputs, and benchmark run data out of tracked files. Read sensitive host or `var/` data only when the task requires it, and disclose only the minimum redacted evidence.

## Topic guides

- [`docs/agents/workflow.md`](docs/agents/workflow.md) — evidence-first work order, review, and completion.
- [`docs/agents/authority.md`](docs/agents/authority.md) — local autonomy, external writes, host changes, publication, and irreversible actions.
- [`docs/agents/writing.md`](docs/agents/writing.md) — document ownership, bilingual consistency, instruction writing, comments, and sensitive evidence.
- [`docs/agents/testing.md`](docs/agents/testing.md) — focused shell, Bun, and Python verification boundaries and grounded commands.

User documentation starts at [`docs/index.md`](docs/index.md). Installation, usage, and owner operations belong in `docs/guides/`. Enduring public-distribution rules belong in [`docs/public-release.md`](docs/public-release.md).

## Public and third-party boundary

The repository's own work is licensed under the root [MIT License](LICENSE). Adopted and externally managed components retain their original notices and terms. For changes to them, inspect `third-party/adopted-skills.json`, `third-party/skills.lock.json`, component license files, and `docs/REPO.md`; keep local changes distinguishable from upstream material.

This is owner-maintained software, not a community contribution project. Do not add issue, pull-request, support, or vulnerability-reporting invitations. The owner may update the repository directly; publication and other remote writes still require explicit task authority.

Keep `README.md` and `README.ko.md` aligned whenever shared claims, commands, prerequisites, safety warnings, or navigation change. `CONTRIBUTING.md` owns the no-contributions and independent-fork policy.

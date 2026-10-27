# Harness agent guide

This file is the compact repository router for coding agents working for the owner. Apply higher-priority system and user instructions first. Read only the topic guide needed for the task; each linked guide owns its subject.

## Start here

1. Bound the requested outcome, owning files, affected callers, and external or sensitive effects.
2. Inspect the source, nearby tests, and relevant repository documentation before editing. Source behavior wins over stale prose.
3. Reuse the existing shell, Bun, or Python mechanism instead of adding a second convention.
4. Verify at the narrowest boundary that proves the requested behavior, then report exact evidence and relevant checks not run.

Before asking a person, accepting an approval, or handling an unattended or scheduled run, read [`docs/agents/hitl.md`](docs/agents/hitl.md). It owns the channel, approval-response, completion-gate, and unattended-run rules for agents running as T3 Code threads.

## Repository map

- `plugin/` — one source for the Claude Code and AGY plugins (merge-guard hook, read-only reviewer agent, AGY rules), their builder and installer, and the deny rules merged into agent settings; [`docs/AGENT-CONFIG.md`](docs/AGENT-CONFIG.md) owns what ships where.
- `codex/` — the read-only `codex exec` reviewer (`review.ts`) used outside T3, and the execpolicy rules (`harness.rules`) that make Codex ask before merging.
- `t3/` — the guard for T3 Code scheduled tasks, its job definitions, and the guarded host-sync source; the distributed `jobs.json` contains no jobs.
- `skills/` — personal skill sources, including the T3-facing `t3-orchestrate`, `t3-handoff` (continue work in a new thread), `t3-terminal` (Herdr as a plain terminal multiplexer for work a person watches), and `t3-show` (interactive explanations, simulations, and data views shown inline in a thread); preserve each adopted skill's license and provenance.
- `agy/` — an example snapshot of Antigravity CLI settings; the AGY plugin source lives in `plugin/`.
- `third-party/` — public external pins, provenance records, and patches; it is not a second source tree.
- `docs/` — user, operational, ownership, evidence, pricing, and owner-maintenance documentation.
- `archived/` — frozen retired sources (the Herdr agent runtime, OMP, and the benchmark runner). Nothing installs, runs, or tests them; do not add or repair code there.
- `var/` — ignored runtime output. Treat it as sensitive even though it is inside the checkout.

[`docs/REPO.md`](docs/REPO.md) owns source-versus-runtime boundaries. Keep credentials, private calendar URLs, report bodies, session transcripts, logs, databases, audit inputs, and benchmark run data out of tracked files. Read sensitive host or `var/` data only when the task requires it, and disclose only the minimum redacted evidence.

## Topic guides

- [`docs/agents/workflow.md`](docs/agents/workflow.md) — evidence-first work order, review, and completion.
- [`docs/agents/authority.md`](docs/agents/authority.md) — local autonomy, external writes, host changes, publication, and irreversible actions.
- [`docs/agents/writing.md`](docs/agents/writing.md) — document ownership, bilingual consistency, instruction writing, comments, and sensitive evidence.
- [`docs/agents/testing.md`](docs/agents/testing.md) — focused shell, Bun, and Python verification boundaries and grounded commands.
- [`docs/agents/hitl.md`](docs/agents/hitl.md) — questions, approvals, delegated children, and unattended runs in T3 Code threads.

User documentation starts at [`docs/index.md`](docs/index.md). Installation, usage, and owner operations belong in `docs/guides/`. Enduring public-distribution rules belong in [`docs/public-release.md`](docs/public-release.md).

## Public and third-party boundary

The repository's own work is licensed under the root [MIT License](LICENSE). Adopted and externally managed components retain their original notices and terms. For changes to them, inspect `third-party/adopted-skills.json`, `third-party/skills.lock.json`, component license files, and `docs/REPO.md`; keep local changes distinguishable from upstream material.

This is owner-maintained software, not a community contribution project. Do not add issue, pull-request, support, or vulnerability-reporting invitations. The owner may update the repository directly; publication and other remote writes still require explicit task authority.

Keep `README.md` and `README.ko.md` aligned whenever shared claims, commands, prerequisites, safety warnings, or navigation change. `CONTRIBUTING.md` owns the no-contributions and independent-fork policy.

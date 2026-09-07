# Writing and documentation ownership

Write for the reader who performs the next action. Keep each rule, fact, command, and decision in one owning location, then link to it from shorter entry points.

## Document map

- `README.md` — concise English project overview and first route into the documentation.
- `README.ko.md` — Korean counterpart to shared README content.
- `docs/index.md` — documentation landing page and maintained navigation.
- `docs/guides/installation.md` — recommended environment, installation, update, and safe inspection steps.
- `docs/guides/usage.md` — supported day-to-day user workflows.
- `docs/guides/operations.md` — optional owner operations and external-effect boundaries.
- `docs/REPO.md` — source/runtime ownership and repository layout invariants.
- `docs/FACTS.md` — dated public technical observations and their limits.
- `docs/PRICING.md` — pricing inputs and cost calculations.
- `docs/BENCH-SURVEY.md` — benchmark design research.
- `docs/public-release.md` — enduring public-distribution policy.
- `CONTRIBUTING.md` — no-contributions, no-support, and independent-fork policy.
- `AGENTS.md` and `docs/agents/` — compact owner-agent router and topic rules.

Put a new page in `docs/index.md`. Prefer extending the page that already owns the topic over creating another category or parallel explanation.

## Bilingual consistency

When a shared claim, command, prerequisite, safety warning, compatibility statement, or navigation link changes, update `README.md` and `README.ko.md` in the same change. Preserve equivalent meaning rather than matching sentence order mechanically.

English is the default for agent-maintenance files (`CONTRIBUTING.md` and `docs/agents/`). Preserve Korean user-facing text where it is part of an interface or established guide, and quote commands, paths, identifiers, and error text exactly.

## Instructions

Before creating or changing `AGENTS.md`, `CLAUDE.md`, a skill, or another agent-consumed instruction, read `skills/writing-for-agents/SKILL.md` or load the `writing-for-agents` skill. Root `AGENTS.md` is a short router: it carries durable repository-wide boundaries and trigger-rich pointers, not command catalogs or narrated architecture. A same-directory Claude adapter contains only `@AGENTS.md`.

A topic rule has one owner. Other files link to it without paraphrasing it. Keep history and investigation diaries out of instruction files; place public policy in `docs/public-release.md`, ownership rationale in `docs/REPO.md`, and measured technical observations in `docs/FACTS.md`.

## Public evidence and sensitive material

Cite public repository evidence as `path:line` and explain what it proves. Record the exact command and relevant outcome for runtime evidence, including the environment or limitation that affects interpretation. Distinguish inspection, synthetic tests, temporary-repository integration, live-host checks, external-service runs, and paid-model results.

Tracked documentation must not contain credentials, private calendar URLs, report bodies, session transcripts, internal logs or databases, raw audit inputs, personal email, absolute personal paths, private project names, non-public endpoints, or identifying work records. Public facts derived from private material retain only the minimum non-identifying technical observation needed for the claim; omit the evidence location when it is not public.

Examples and fixtures must be synthetic at creation. Never copy a real report, identity, project, issue, or business metric and relabel it as synthetic. `var/` being ignored does not make its contents safe to quote, attach, or publish.

## Third-party text

Before copying or adapting external text, verify its license and required notices. Preserve component-level licenses and provenance records, distinguish local changes from upstream material, and avoid importing language that does not describe Harness. The root MIT license does not replace third-party terms.

## Comments and tone

Inline comments explain a non-obvious invariant, ownership seam, or failure prevented by the code. Keep change history, investigation diaries, and obvious syntax out of comments.

Use direct, factual language. Avoid marketing claims, unsupported compatibility promises, and claims that a check proves more than it exercised. Do not invite issues, pull requests, support requests, or vulnerability reports; `CONTRIBUTING.md` owns that policy.

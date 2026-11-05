# {{PROJECT_NAME}} agent guide

{{PROJECT_SUMMARY}} This file is the compact router for agents working in this repository. Apply higher-priority system and user instructions first. Read only the topic guide a task triggers; each linked guide owns its subject.

## Start here

1. Bound the requested outcome, owning files, affected callers, and external or irreversible effects.
2. Inspect current source, nearby tests, and the owning guide before editing. Source behavior wins over stale prose.
3. Reuse the existing mechanism instead of adding a second convention.
4. Verify at the narrowest boundary that proves the requested behavior, then report exact evidence and the relevant checks not run.

Before asking a person, accepting an approval, or handling an unattended or scheduled run, read [`docs/agents/hitl.md`](docs/agents/hitl.md).

## Ownership map

{{OWNERSHIP_MAP}}

## Topic guides

- [`docs/agents/workflow.md`](docs/agents/workflow.md) — evidence-first work order, caller migration, and completion.
- [`docs/agents/authority.md`](docs/agents/authority.md) — local autonomy, commits and pushes, external writes, and irreversible actions.
- [`docs/agents/writing.md`](docs/agents/writing.md) — document ownership, language, instruction writing, and sensitive evidence.
- [`docs/agents/testing.md`](docs/agents/testing.md) — verification commands and the source that defines each one.
- [`docs/agents/issue-tracker.md`](docs/agents/issue-tracker.md) — reading, filing, and linking issues.
{{STANDARDS_POINTERS}}

## Domain language

Domain terms live in [`{{GLOSSARY_ENTRY}}`]({{GLOSSARY_ENTRY}}); architectural decisions live in [`docs/adr/`](docs/adr/). Read both before naming a domain concept or reshaping an area, and surface any conflict with an ADR instead of silently overriding it.

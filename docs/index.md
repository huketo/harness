# Documentation / 문서 안내

[English README](../README.md) · [한국어 README](../README.ko.md) · [MIT License](../LICENSE)

Choose the document for the task rather than reading the entire directory. The READMEs are aligned English/Korean entry points; detailed usage, ownership, and research documents remain Korean where noted.

## Start and use / 설치와 사용

| Document | Read it for |
| --- | --- |
| [Installation](guides/installation.md) | Linux/WSL2 prerequisites, OMP and Bun pins, installer side effects, configuration opt-in, updates, and manual rollback. |
| [상세 사용법](guides/usage.md) | Accounts, profiles, session/shared effort, native compaction, Herdr execution, and Windows Chrome. |
| [소유자 운영 절차](guides/operations.md) | Cost audits, guarded host sync, GitLab/calendar draft collection, manual Daou Office entry, and snapshot boundaries. Not a general installation recipe. |
| [공개 배포 정책](public-release.md) | License, fresh-history, privacy, dependency, support, and publication invariants. |

## Maintenance / 유지관리와 Agent 지침

| Document | Read it for |
| --- | --- |
| [Contribution policy](../CONTRIBUTING.md) | No-contribution, no-support, no-reporting, and independent-fork policy. |
| [Agent entry point](../AGENTS.md) | Repository routing and task-specific guide selection. `CLAUDE.md` points to this same source. |
| [Workflow](agents/workflow.md) | Work order, source evidence, integration, and completion. |
| [Authority](agents/authority.md) | Local work versus host, external-write, and publication decisions. |
| [Writing](agents/writing.md) | Document ownership, bilingual parity, and progressive disclosure. |
| [Testing](agents/testing.md) | Focused Bash, Bun, and Python checks and what each proves. |
| [OMP human-decision rules](../.omp/APPEND_SYSTEM.md) | Channel resolution and unattended-run behavior; not a general installation setting. |

## Reference and evidence / 구조와 근거

| Document | Role and limits |
| --- | --- |
| [REPO](REPO.md) | Maintained ownership and placement rules; repository sources versus runtime state. |
| [FACTS](FACTS.md) | Dated compatibility, cost/model observations, and known technical limits without private work records. |
| [PRICING](PRICING.md) | Dated provider/catalog pricing and cost-accounting evidence; not a live price feed. |
| [BENCH-SURVEY](BENCH-SURVEY.md) | External benchmark research and design implications; historical descriptions may predate the current runner. |

These four reference paths remain stable because skills and benchmark documentation link to them.

## Component documentation / 구성요소별 문서

- [Benchmark guide](../bench/README.md) — selection, isolated runs, grading, reports, and routing proposals.
- [Benchmark taxonomy](../bench/TAXONOMY.md) — workload classification and recorded public/synthetic evidence.
- [Cost-audit guide](../skills/cost-audit/README.md) — detector semantics, CLI, and measurement limits.
- [Daily-report skill](../skills/daily-report/SKILL.md) — GitLab/calendar collection, grounded drafting, user review, and manual Daou Office UI entry.
- [Calendar setup](../skills/daily-report/references/calendar-setup.md) — private-feed handling and host prerequisites.
- [Adopted skill provenance](../third-party/adopted-skills.json) — origin and retained notices for repository-owned copies.
- [External skill snapshot](../third-party/skills.lock.json) and [Herdr plugin manifest](../herdr/plugins.manifest.json) — public manager-owned dependencies and pinned references.
- [Skill-doctor patch notice](../third-party/patches/skill-doctor-LICENSE) — upstream terms for retained patch context.

## Documentation rules / 문서 유지 원칙

Keep operational procedures in `guides/`, agent work rules in `agents/`, and dated technical evidence in the stable reference documents. Update both READMEs when shared claims change and migrate links whenever a page moves.

`var/` holds ignored local evidence and generated output. Do not move it into `docs/` or publish it as a release artifact. Public examples must be synthetic at creation; redact or omit facts derived from private material rather than relabeling that material.

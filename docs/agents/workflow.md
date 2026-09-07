# Evidence-first workflow

This guide owns the order of repository work for the owner. [`authority.md`](authority.md) owns permission boundaries, and [`testing.md`](testing.md) owns verification commands and execution boundaries.

## 1. Frame the contract

State the requested observable outcome, in-scope files, affected callers, and explicit non-goals. Identify whether the work can touch a live host, external service, paid model, sensitive data, third-party license, or publication boundary. The step is complete when every requested outcome has an owner and every effect has an authority class.

## 2. Establish the source of truth

Read the implementation, its callers, nearby tests, and the relevant ownership or user guide. Inspect command implementations and `--help` branches instead of guessing flags. Prefer current source behavior over prose; when they differ, fix the owning source or documentation rather than creating a second convention. The step is complete when the current mechanism and all affected call sites are accounted for.

For host configuration and installation work, [`../REPO.md`](../REPO.md) defines which repository file is canonical and which host file is tool-owned. For a human question or unattended execution, [`.omp/APPEND_SYSTEM.md`](../../.omp/APPEND_SYSTEM.md) is the sole project authority.

## 3. Make the evidence red when behavior changes

Choose the smallest observable boundary that would fail for the reported defect or missing behavior. Use the repository's tracked `tdd` skill when its procedure applies. Reproduce before fixing, except when the task is documentation-only or the behavior cannot be exercised safely. Record why an unsafe, paid, destructive, or unavailable boundary was not run.

The step is complete when the failure is observable or the reason a pre-change run is impossible is explicit.

## 4. Change the owning mechanism

Implement the narrow complete fix in the canonical source. Migrate affected callers, tests, and documentation together. Preserve ownership boundaries: declarative files belong in the repository; credentials, tool-written state, reports, sessions, caches, logs, databases, and generated run artifacts do not.

When work is split, define interfaces and file ownership before concurrent edits. Give each slice its own evidence boundary and integrate only after all callers of a changed contract are visible. The step is complete when no in-scope caller relies on the old contract.

## 5. Verify the actual boundary

Run the focused command from [`testing.md`](testing.md) that exercises the changed mechanism. A source audit, unit test, temporary-repository integration test, live-host check, external-service run, and paid benchmark are different evidence; name the one actually obtained. A zero exit proves only the command that ran, so confirm that the intended test or scenario was selected.

After behavior is proven, remove throwaway probes and update maintained documentation. The step is complete when the requested outcome is observed and the worktree contains no task-created runtime or sensitive artifacts.

## 6. Review public-facing effects

For public-facing changes, compare shared statements in `README.md` and `README.ko.md`, navigation in `docs/index.md`, detailed guides under `docs/guides/`, and enduring rules in `docs/public-release.md`. For adopted or managed components, confirm provenance and notices against `third-party/` and component license files.

The root MIT license and owner-only maintenance policy are settled. Do not reintroduce pending-license language, contribution onboarding, support channels, or vulnerability-reporting invitations. Public examples must be synthetic at creation, and references to removed private runners, corpora, histories, or dependencies must be removed rather than generalized.

The step is complete when every affected public claim, link, license notice, and privacy boundary is consistent.

## 7. Deliver evidence

Report behavior changed, files changed, exact commands and observed results, checks not run, and remaining risks or owner decisions. Redact sensitive values and avoid quoting private report or session content. Documentation-only work reports link and command inspections actually performed; if no runtime check was run, state that explicitly.

## Review findings

Treat each finding as a hypothesis. Confirm its premise at a source location, with a focused reproduction, or from a primary reference before editing. Judge the proposed remedy separately: a correct observation can still suggest an oversized fix. A claim that changes license terms, publication posture, or ownership requires explicit owner instruction.

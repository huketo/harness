# Evidence-first workflow

This guide owns the order of work in this repository. [`authority.md`](authority.md) owns permission boundaries, [`testing.md`](testing.md) owns verification commands, and [`hitl.md`](hitl.md) owns how to reach a person.

## 1. Frame the contract

State the requested observable outcome, in-scope files, affected callers, and explicit non-goals. Name every effect the work can have beyond the working tree (a push, an issue or merge request write, a deployment, a paid or authenticated service call, deleted data) and give each one an authority class from [`authority.md`](authority.md).

The step is complete when every requested outcome has an owner and every effect has an authority class.

## 2. Establish the source of truth

Read the implementation, its callers, nearby tests, and the owning guide. Inspect command implementations and `--help` output instead of guessing flags. Prefer current source behavior over prose; when they differ, fix the owning source or document rather than creating a second convention.

Read the domain glossary (see the root `AGENTS.md`) and the ADRs in `docs/adr/` that touch the area. Name domain concepts with the glossary's terms. When the change would contradict an ADR, say so explicitly and explain why it is worth reopening.

The step is complete when the current mechanism, all affected callers, and the relevant glossary terms and ADRs are accounted for.

## 3. Make the evidence red when behavior changes

Choose the smallest observable boundary that would fail for the reported defect or missing behavior. Use the `tdd` skill when it is available to the running agent. Reproduce before fixing, except when the work is documentation-only or the behavior cannot be exercised safely; record why an unsafe, paid, destructive, authenticated, or unavailable boundary was not run.

The step is complete when the failure is observable or the reason a pre-change run is impossible is explicit.

## 4. Change the owning mechanism

Implement the narrow complete fix in the canonical source. Migrate affected callers, tests, and documentation together. Keep credentials, tool-written state, caches, logs, and generated run artifacts out of tracked files.

When work is split, define interfaces and file ownership before concurrent edits, give each slice its own evidence boundary, and integrate only after the callers of a changed contract are visible.

The step is complete when no in-scope caller relies on the old contract.

## 5. Verify the actual boundary

Run the focused command from [`testing.md`](testing.md) that exercises the changed mechanism. Source audit, unit test, temporary-repository integration, live-service check, and remote publication are different evidence; name what was actually obtained. A zero exit proves only the selected command, so confirm the intended scenario ran.

After behavior is proven, remove throwaway probes. The step is complete when the requested outcome is observed and no task-created runtime or sensitive artifact entered tracked files.

## 6. Update the owning documents

Update the guide that owns each changed contract, following [`writing.md`](writing.md). Record a newly resolved domain term in the glossary, and record a decision in `docs/adr/` only when it is hard to reverse, surprising without context, and the result of a real trade-off.

The step is complete when every affected claim in maintained documentation matches the new behavior.

## 7. Deliver evidence

Report the behavior or documentation changed, the owning files, the exact commands or scenarios run with their observed results, the relevant checks not run and why, generated artifacts, and every commit or remote write made. Redact sensitive values.

## Review findings

Treat each finding as a hypothesis. Confirm its premise at a source location, with a focused reproduction, or from a primary reference before editing. Judge the remedy separately: a correct observation can still suggest an oversized fix. A finding is evidence, not authority to widen scope.

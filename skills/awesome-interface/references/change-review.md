# Change review

Execute only for explicit intent to review a branch, commit/range, pull request, index or uncommitted change. This workflow resolves scope and causality; [review.md](review.md) owns domain review, severity, ranking, coverage and verdict. Use its internal workflow directly, without requesting another skill invocation.

## Resolve a reproducible comparison

Preserve the author’s checkout and edits. Read refs in place; do not switch branches, stash or reset. Detect an in-progress merge, rebase or cherry-pick through `git rev-parse --git-path` and report that unresolved operation instead of presenting its partial diff as the requested change.

| Target | Comparison |
| --- | --- |
| `working` | Tracked staged and unstaged changes against HEAD, plus untracked files |
| `staged` | Index against HEAD; read index content, not unstaged working copies |
| `branch` or a named branch/ref | Merge base with the resolved default/base branch to target head |
| Explicit `a..b` | Endpoints a and b; preserve the requested two-dot semantics |
| Explicit `a...b` | Merge base of a/b to b; preserve the requested three-dot semantics |
| Pull request | Provider-reported base and head, including fork head; read metadata and files at those revisions |

For an explicit single-commit review, compare its parent to that commit; do not confuse a branch/ref comparison with a request to review one commit. For merge commits, resolve the requested parent from context; otherwise report the ambiguity.

With no target, first determine whether HEAD is ahead of the default branch’s merge base. If so, review that branch range plus uncommitted work and report their counts separately. Otherwise review uncommitted work if present. Include untracked paths with `git ls-files --others --exclude-standard`; `git diff HEAD` alone omits them. Inspect untracked content only when relevant and safe; do not ingest credentials or runtime output merely because it is untracked.

Resolve the default from existing remote HEAD metadata and the repository’s provider/configuration. A local main/master is a fallback only when unambiguous and disclosed. Resolve refs to SHAs. With missing refs, shallow history or unrelated histories, use authorized read-only provider metadata or bounded fetch/deepening under repository policy; record any `.git` writes. Never silently guess a base or treat an unavailable provider as proof that no pull request exists.

No commits, no changes, or no relevant files after exclusions means no change review: state the facts and the missing target, not `Approve`. Do not substitute the last commit or a whole-repository audit. Where questions are unavailable, report the blocker. An explicitly requested full audit instead uses [review.md](review.md) without change classifications.

## Inventory and affected screens

Read intent from the request, relevant change metadata and commit messages, then read both sides of every relevant hunk with surrounding context. For a fetched head, use content at that ref, not local files; citations must resolve at the head named in the report. Preserve rename/copy identity so moved unchanged code is not classified as new.

Exclude generated output, dependency locks, vendored sources and binary bytes from line-by-line UI review, naming exact paths and reasons. Inspect their authored owners and referencing code where they affect the interface. Font/image changes remain relevant through typography, rendering and accessible alternatives. Do not automatically exclude authored stories or fixtures that establish the requested states.

Map changed components to rendered consumers, not just filenames:

1. Expand direct callers/importers one hop. For tokens, themes and shared primitives, expand a second hop; search token usage as well as imports.
2. Prioritize route/layout entry points, then consumer reach, then proximity to the changed feature. Inspect up to five consumers by default and disclose the remainder and any uncertain ordering. An explicit broader scope still requires coverage or a stated gap, not a silently truncated approval.
3. Inspect consumers at the reviewed revision. For branch plus local changes, trace the effective combined state, retaining base/head/local evidence separately.
4. Read the change’s promised states: hover, focus, active, selected, disabled, loading, empty, error, themes, localization and narrow widths where applicable. Report incomplete implementation only when intent or the component contract warrants that state, not an invented requirement.

## Removed signals are leads

Examine deleted lines as carefully as additions. Check for equivalent replacements elsewhere in the change before judging a removal.

| Signal removed or weakened | Consult owner for confirmation |
| --- | --- |
| Accessible names, descriptions, live regions, labels, alt text, table associations, native semantics, keyboard handling or focus styles | [Accessibility](accessibility.md) |
| Reduced-motion or contrast-preference support | [Accessibility](accessibility.md) |
| Logical positioning, responsive containment, disclosure/scroll cues | [Layout](layout.md) |
| Language/direction metadata, wrapping, full-value access, numeric alignment | [Typography](typography.md), or the semantic owner where applicable |
| Semantic tokens, foreground/background pairing, non-color state cues | [Colors](colors.md) |
| Labels, recovery instructions, empty-state guidance or translation entries | [Writing](writing.md) |
| Persistent state cues, interrupted transitions, shared visual state treatment | [UI polish](ui.md) |

An `aria-label` replaced by a valid visible-label association, custom role replaced by a native element, focus outline replaced by a visible equivalent, or string moved to a translation catalog is not by itself a regression.

## Classify by cause, not proximity

- `Introduced`: evidence shows the change created the defect.
- `Regression`: the base supported behavior that the change demonstrably weakened or removed.
- `Pre-existing`: the same defect exists at the base and was not caused or worsened by the change.
- `Unclear`: a real candidate exists, but available base/head/runtime evidence cannot establish attribution. State exactly what is missing.

Compare base and head implementations and, when required, equivalent rendered states. History/blame may locate a change but does not establish user impact. An untouched consumer can regress because a changed token or primitive affects it; a nearby line can remain pre-existing. Attach base evidence and the causal changed source to each classification.

Finish using [review.md](review.md) and the [report format](../assets/review-format.md). Keep pre-existing and unclear items separate from confirmed change findings. General correctness/security concerns outside interface scope may be named briefly as separate concerns; do not silently expand into a general code audit.

## Runtime without checkout mutation

Use an existing safe preview matching the reviewed revision. If isolated rendering is needed and authorized, create a disposable local checkout/fixture through the project’s existing mechanism, isolate external services and remove only resources created for the review afterward. Never exercise destructive production paths. A preview of another revision does not verify this change. Record unavailable rendering or mismatched revisions as `Not verified`.

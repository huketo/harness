# Interface review

Use for a requested screen or flow review. A review is read-only unless implementation is explicitly requested. An explicit change-review request first follows [change-review.md](change-review.md), then uses the evidence, ranking and verdict rules here. Do not turn review into stress testing, variant generation or explanation without that intent.

## Resolve and inspect

1. State the requested screens, flows and boundaries. Identify the framework, styling system, shared components, tokens, supported viewports, existing preview and relevant project guidance. Preserve those conventions in proposed fixes; a review is not a stack or color-system migration.
2. For a full review, load and apply all six owners in order: [accessibility](accessibility.md), [layout](layout.md), [writing](writing.md), [typography](typography.md), [colors](colors.md), [UI polish](ui.md). For a partial request, load only its relevant owners and label the report partial. A missing owner is `Not reviewed`, not permission to reconstruct its rules from memory.
3. Map each requested surface to its actual states: default, empty, loading, error, disabled, selected, hover, focus, active and narrow width where applicable. Inspect the complete requested scope; if it cannot be covered, report the uninspected boundary rather than silently shrinking the task or claiming a full review.
4. Read source and inspect safe local rendering where the claim depends on appearance or interaction. Exercise keyboard paths, supported themes, 320px width and 200% zoom where relevant. For motion, observe normal playback and, when useful, slowed playback and interruption; slow playback alone does not prove the normal experience. Use existing preview mechanisms, not new infrastructure or live destructive actions.
5. Collect evidence by owner, then consolidate into the [report format](../assets/review-format.md). Review domain rules in their owning references; this workflow owns only evidence, severity, ranking and reporting.

## Evidence

Every source finding cites `path/to/file:line` at the reviewed revision and includes the current implementation. Every runtime finding names the screen/component, viewport, state, exact interaction and observed result; attach the relevant capture when available. A screenshot-only finding cites its artifact and region instead of inventing a source location.

Source can establish a missing attribute or an authored declaration, but cannot alone establish rendered contrast, clipping, focus visibility, animation quality or the winning cascade. Inspect the rendered state or mark that claim `Not verified`. Likewise, pixels alone cannot prove which source rule caused a symptom. Separate confirmed symptoms from suspected causes.

Project preferences are context, not findings. Report demonstrated user harm, not disagreement with density, radius or voice. If a shared token or documented convention causes the harm, cite that source once and list its confirmed affected consumers.

## Severity and ranking

- `HIGH`: blocks a task, misleads, hides content or controls, risks data loss, or causes a repeated systemic failure.
- `MEDIUM`: materially harms comprehension, efficiency, adaptability or consistency.
- `LOW`: isolated polish with limited task impact.

The owning domain establishes whether a defect exists. Once confirmed, these escalation triggers are `HIGH`:

- Interactive control without an accessible name.
- Keyboard-reachable control without a visible focus indicator, or a pointer path unavailable by keyboard.
- Motion or autoplay ignoring reduced-motion preferences.
- Content or controls clipped, overlapped or unreachable at 320px width or 200% zoom.
- Body or control text failing its required rendered contrast ratio.
- Meaning or state conveyed by color alone.
- Destructive action without confirmation, undo or distinct treatment.
- Truncated content with no way to access its full value.
- Content or controls beyond a scroll edge or disclosure without a visible cue.
- Error without a recovery path.
- Semantic color used against its meaning.
- State change conveyed only by motion, with no persistent static cue.

Rank triggers first, then severity, then reach and leverage of one correction. One root cause is one finding, even across domains or components; assign its underlying rule to one owner and describe secondary effects in the rationale. List confirmed locations together. Report at most 15 ranked findings, never pad. If more confirmed findings exist, disclose the excluded count and severity, including any additional HIGH blockers; the cap cannot produce an approval by hiding blockers.

Propose the smallest effective correction, in this order when viable: delete unnecessary work, use native platform behavior, reuse existing primitives/tokens, correct the value, then add structure. A symptom-specific patch is not preferable to correcting its shared source.

## Coverage and verdict

`Clear` means the stated evidence was inspected with no actionable finding. `Not reviewed` names an uninspected domain or state and why. `Not verified` names a required runtime check that was not exercised; absence of evidence is not a defect.

Choose the verdict in this order:

1. `Block` when a confirmed in-scope HIGH remains, including blockers beyond the table cap.
2. `Not verified` when required coverage or evidence is missing, or a material unresolved claim prevents a supported verdict. List what would resolve it.
3. `Needs changes` when only confirmed MEDIUM or LOW findings remain.
4. `Approve` when no actionable findings remain and the declared scope is covered. A partial approval applies only to the stated partial scope, never to the whole interface.

For change reviews, only confirmed `Introduced` and `Regression` findings enter the ranked cap and severity verdict. `Pre-existing` findings stay separate; `Unclear` attribution cannot become a confirmed change defect and is handled as an evidence gap. A domain demonstrably unaffected by the resolved change is not a missing check, but must be labeled rather than called clear.

If implementation was requested, use the agreed findings as its scope, apply the owning domain guidance in the project’s existing idiom, and re-exercise changed states. Distinguish proposed fixes from applied and verified fixes.

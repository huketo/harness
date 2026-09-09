# Review report format

Use with [review.md](../references/review.md), which owns evidence, severity, ranking, caps and verdicts. Replace template instructions with observed facts; omit empty optional sections.

## Scope

State mode (full, partial or change), requested surfaces, reviewed boundary, stack/styling conventions and project guidance consulted. Name exclusions and uninspected surfaces. For a screenshot, identify the artifact and captured state; for runtime, identify the reviewed route and viewport without exposing private data.

For change mode, add:

| Field | Resolved value |
| --- | --- |
| Target | User-specified target or documented default resolution |
| Base | Ref and SHA; merge base where applicable |
| Head | Ref and SHA, or working/index snapshot |
| Change inventory | Commit count and uncommitted file count separately |
| Files and exclusions | Reviewed files; excluded paths with reasons |
| Affected surfaces | Direct consumers, shared-source expansion and consumers not inspected |

## Coverage

| Domain | Evidence inspected: files, surfaces, states, checks | Result and limits |
| --- | --- | --- |
| Accessibility | Actual evidence | Findings count, Clear, or Not reviewed with reason |
| Layout | Actual evidence | Result |
| Writing | Actual evidence | Result |
| Typography | Actual evidence | Result |
| Colors | Actual evidence | Result |
| UI polish | Actual evidence | Result |

Full reviews include all six rows. Partial reviews include requested domains and explicitly name excluded domains. Change reviews label unaffected domains `Not reviewed: no evidence in the change scope`; do not call them clear. Name unverified runtime states alongside inspected source evidence.

## Ranked findings

| Severity | Domain | Location and evidence | Before | Proposed correction | Why: rule and user impact |
| --- | --- | --- | --- | --- | --- |
| Confirmed severity | Owning domain | Source path:line and/or runtime artifact, state and observation | Current implementation | Smallest effective fix | Demonstrated harm |

Change mode adds a `Status` column containing `Introduced` or `Regression`. One row per source cause; list its confirmed locations in that row. State overflow counts as required by review.md. With no findings, omit the table and say “No actionable interface findings” (or “No confirmed introduced or regression interface findings” in change mode), without implying all checks passed.

### Unclear attribution (change mode only)

List unresolved candidates separately with evidence, why causality is unclear, and the missing comparison. These are not confirmed change defects. Apply review.md’s evidence-gap verdict rule.

### Pre-existing (change mode only)

List at most three, highest severity first, with location, issue and base evidence. State that these predate the change and affect neither its ranked cap nor its verdict.

## Verification

| Command or interaction | Environment, surface and state | Observed result |
| --- | --- | --- |
| Exact executed steps | Source-only, local runtime, screenshot, or other actual boundary | Pass or observed failure |

List checks not exercised under **Not verified**, with the missing prerequisite and resulting limitation. Do not count a proposed command as a run or a source inspection as visual verification.

## Verdict

Use the verdict selected by [review.md](../references/review.md#coverage-and-verdict), its precise reviewed scope, remaining findings and any evidence gaps. A report with no findings but missing required runtime coverage is not an approval.

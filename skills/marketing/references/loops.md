# Marketing Loops

This file covers designing, operating, and reviewing recurring marketing workflows that produce bounded, evidence-based drafts and reports.

## When to use

Use a loop when a recurring signal deserves a repeatable check and someone owns the resulting decision.

| Need | Start here |
|---|---|
| Choose a recurring workflow | Representative loops |
| Define a new loop or adapt one | Loop anatomy, then Loop definition template |
| Set frequency or introduce automation | Cadence and scheduling |
| Prevent duplicate work or recover a failed run | State and idempotency |
| Compose several workflows | Adoption and ownership |
| Review a completed run | Run report format |

Inputs to collect: desired outcome, reliable data sources, baseline and evaluation window, review owner, artifact destination, durable state location, and any existing overlapping workflow.

Prefer a one-off brief when the task is primarily positioning, creative direction, or a new strategic decision. For sparse signals, widen the observation window or use a manual review rather than generating frequent noise.

## Loop anatomy

Define all nine parts before treating a workflow as ready:

| Part | Required decision |
|---|---|
| Check cadence | When the loop looks, with timezone and data freshness expectations. |
| Acts when | The condition that justifies producing new work rather than checking and skipping. |
| Purpose | One outcome to protect or improve, with a relevant success measure. |
| References used | The sibling references needed for this loop's diagnosis or drafting. |
| Body | Ordered, bounded steps from data collection through staged output. |
| Self-check | Evidence that the signal is real, comparable, sufficiently sampled, and actionable. |
| State / idempotency | Durable memory, stable dedupe keys, cooldowns, and overlap protection. |
| Stop / bail-out | No-op conditions, error handling, escalation, run limits, and a manual off switch. |
| Output | Destination, format, owner, review status, and the decision the artifact enables. |

Checking and acting are separate: a retention monitor might inspect activity frequently, but stage a recommendation only for a newly eligible case. A weekly review is a heartbeat: its report is useful even when no meaningful change occurred.

## Procedure

1. Choose the outcome and its owner. Define what decision a useful output will enable.
2. Select the closest representative loop; adapt its scope to the actual customer journey.
3. Specify the data contract: source, date range, completeness, comparison baseline, and freshness tolerance.
4. Set cadence independently from the action condition; choose thresholds using project evidence.
5. Define a bounded body, self-check, state model, stop conditions, and artifact destination.
6. Classify each step as inspection/analysis/staging or an externally effective action.
7. Run an initial manual, draft-only iteration. Inspect whether the output supports its intended decision.
8. Record state and a run report, including checked-but-no-action outcomes.
9. Introduce scheduling only when requested separately and the readiness checklist is satisfied.

Use the claim ledger from SKILL.md for product claims in staged content. Distinguish observations, hypotheses, and proposed responses in every report.

## Cadence and scheduling

Match check frequency to signal speed, evidence accumulation, and the useful response window—not the desire for more updates.

The following are starting rules of thumb, not market benchmarks; verify them against dated project research or a fresh cited lookup when choosing a cadence.

| Signal | Starting cadence | Adjustment rule |
|---|---|---|
| Search opportunity or ranking movement | Weekly | Separate meaningful movement from query volatility and seasonality. |
| Content freshness or gradual decay | Monthly | Extend the window where traffic is sparse or seasonal. |
| Activation or checkout cohorts | Weekly | Wait for sufficient complete cohorts; use longer windows at low volume. |
| Community conversations or acute retention risk | Daily or event-triggered | Match the response window and permitted source access. |
| Tracking integrity | Weekly and after releases | Check sooner when a release changes measurement dependencies. |
| Campaign learning | At campaign completion | Account for reporting delays before drawing final conclusions. |

An action threshold should include materiality, sample sufficiency, comparison period, and exclusions for known events. Define these before interpreting results; keep them stable through an evaluation window.

Scheduling is a separate requested action. When installed, use the `herdr-cron` skill; otherwise use the host's scheduler or a manual cadence. Keep the loop definition independent of the scheduling mechanism.

For a scheduling request, prepare a configuration specifying timezone, cadence, maximum runtime, overlap behavior, inputs, artifact location, state storage, error output, and disable procedure. Account for delayed jobs and missed windows; choose skip or catch-up behavior explicitly.

An unattended scheduled run never asks a person and never executes external effects. It writes staged drafts/reports and records missing inputs, permissions, or decisions as blockers in its output. A missing prerequisite produces a blocked report, not invented data or an interactive prompt.

Prepare the scheduling draft/checklist; execution needs explicit authorization naming the action (see SKILL.md).

## Representative loops

These ten patterns are starting points, not complete definitions. Apply the anatomy and readiness checklist to the selected row. All responses below are staged artifacts, not live actions.

| Loop | Checks / acts when | Body and output | Self-check and memory | References |
|---|---|---|---|---|
| Weekly marketing review | Weekly; always produces a pulse | Compare journey metrics with plan and prior comparable periods; report notable movers, owners, and next decisions. | Verify freshness and distinguish noise; store period snapshots and link existing issues. | [measurement](measurement.md) |
| Tracking integrity | Weekly or after a release; an expected measurement check fails | Inspect available event and attribution evidence; stage a prioritized issue report. | Compare with known-good behavior; update issues by event/source key. Halt dependent conclusions when critical data is unreliable. | [measurement](measurement.md) |
| Search opportunity | Weekly; relevant demand lacks a suitable page or an existing page has a credible improvement opportunity | Compare queries with page coverage; stage prioritized content briefs. | Check intent, relevance, and adequate evidence; dedupe query/topic briefs and respect open work. | [seo](seo.md) |
| Content decay | Monthly; a valuable page declines materially across a suitable window | Diagnose intent, freshness, and distribution changes; stage a refresh plan. | Rule out seasonality and search-layout shifts; track page version, last refresh, and cooldown. | [seo](seo.md), [measurement](measurement.md) |
| Content repurposing | Weekly; a new approved source asset lacks suitable channel variants | Extract useful ideas; stage self-contained channel-native drafts. | Verify fidelity and standalone value; dedupe by asset version and channel. | [social](social.md) |
| Community listening | Daily or event-triggered; a relevant conversation has a genuine help opportunity | Rank conversations; stage helpful replies or a resource brief. | Check community norms and context; dedupe thread IDs, record staged status, and apply interaction cooldowns. | [community](community.md), [social](social.md) |
| Activation leak | Weekly; a journey step regresses materially | Locate the largest supported obstacle; stage one focused intervention and measurement plan. | Verify tracking, cohort maturity, and sample; track open fixes and experiments to avoid conflicts. | [activation](activation.md), [measurement](measurement.md) |
| Competitor change | Weekly; a substantive public offer or positioning change appears | Compare dated snapshots; prepare an evidence-linked digest and response options. | Distinguish cosmetic changes from strategic ones; dedupe by source/version and known change. | [research](research.md) |
| Customer-language review | Weekly; new permitted feedback exists | Group recurring needs and objections; stage a language/insight digest and route sensitive issues. | Separate patterns from isolated views; retain source IDs, permission status, and processed-item keys. | [research](research.md) |
| Campaign postmortem | On campaign completion; results are sufficiently complete | Compare results with goals; prepare lessons, reusable assets, and next hypotheses. | Separate attribution evidence from causal claims; version one record per campaign as delayed data arrives. | [launch](launch.md), [measurement](measurement.md) |

Adapt the journey rather than assuming a trial-to-sales funnel: a consumer app may center first value and repeat use; a community may center participation; a marketplace may require separate supply- and demand-side checks.

## Guardrails and human checkpoints

Inspection, analysis, comparison, scoring, drafting, and staging fit an unattended body when the data access itself is permitted. Public communication, outbound messages, purchases, budget changes, submissions, live tracking changes, account changes, and destructive changes belong outside that body.

Prepare the draft/checklist; execution needs explicit authorization naming the action (see SKILL.md).

Every publish/send/spend proposal includes a human checkpoint, its intended scope, and relevant constraints. Describe the exact destination, audience, account, and proposed change so review is actionable.

- For spend proposals, include the ceiling, proposed change limit, eligible campaigns, and outcome-quality metric rather than a proxy alone.
- For outbound drafts, check consent or lawful basis, suppression status, recipient eligibility, volume limits, and required opt-out/disclosure elements.
- For testimonials and customer language, check permission, incentive disclosure, and faithful representation.
- For community/platform work, confirm current access, automation, and posting rules from dated sources.
- Handle personal data minimally; use internal IDs in state and logs, and keep restricted drafts in an appropriate destination.
- Flag crisis mentions, sensitive complaints, strategic customer risks, revenue/spend anomalies, destructive proposals, and large-audience actions for human review. Scheduled runs record that escalation in the output rather than contacting someone.
- If consent, permissions, source reliability, or applicable rules are unclear, stage only the blocker and supporting evidence.

Document an off switch for each schedule and a way to pause the whole set. Check the disabled flag before processing; disablement is a valid stop condition even for heartbeat reviews.

## State and idempotency

Choose an existing project artifact store or scheduler-backed durable store. Record its location in the definition; memory limited to one agent session is insufficient.

Keep separate meanings for `last_attempt`, `last_success`, processing cursor, staged artifact, review status, and confirmed external execution. Creating a draft is not proof that it was sent or published.

| Pattern | Use | Commit rule |
|---|---|---|
| Watermark | New feedback or events | Advance only through successfully processed, durable records; use an explicit tie-breaker where timestamps repeat. |
| Dedupe key | Topics, threads, issues, or drafts | Derive from stable entity + action type + relevant version; reuse/update an existing artifact instead of duplicating it. |
| Cooldown | Repeated recommendations or contact proposals | Track eligibility separately from staged work; base contact cooldown on confirmed contact, not a draft. |
| In-flight guard | Open fixes, experiments, or overlapping runs | Reserve one owner/key before work; release or reconcile interrupted reservations. |
| Attempt counter | Bounded retries or interventions | Record attempts and stop at the defined limit; retain the reason for the stop. |

A safe iteration reads state, checks overlap, identifies eligible items, writes durable staged artifacts, then commits the processed keys and cursor. Use atomic state updates or transactions where available. Deterministic artifact keys let a retry recover work written before a crash without creating duplicates.

If durable state cannot be read or written, halt rather than pretending deduplication succeeded. On partial failure, retain unprocessed items for the next run and report the exact completed scope.

For a first run, establish a baseline or start at the current watermark. Historical processing is an explicit backfill with a bounded date range and draft-only preview. A reset preserves valid cooldowns, confirmed execution history, and open-work ownership; document what is being reprocessed.

Keep state small by expiring obsolete entries only after their dedupe/cooldown window. Preserve sufficient audit evidence to explain a decision. Exclude raw personal data and secrets from state and run logs.

## Adoption and ownership

Start with one weekly marketing review, including a measurement-health check. If evidence is unreliable, its useful output is a tracking blocker rather than downstream recommendations.

Add one workflow at a time after the existing output has an owner who uses it:

1. Establish trusted measurement and a full-journey pulse.
2. Address observed retention or activation leaks before expanding acquisition.
3. Add acquisition and channel-maintenance loops where demand and capacity justify them.
4. Add monetization or advocacy checks only when the necessary evidence and review capacity exist.
5. Capture completed campaign lessons and feed a shared experiment backlog.

Use a simple flow: sensing → diagnosis → staged response → learning. The weekly review routes issues; one owner handles each issue. Other loops may add evidence to that record rather than creating competing actions. Keep experiment design and interpretation in [measurement](measurement.md).

Review the set periodically: recalibrate thresholds against dated evidence, retire unused outputs, and pause redundant work. Frequent no-op runs can be healthy; judge usefulness by the decision window and owner need, not output volume. Acting every run can indicate noise or an overly broad threshold.

## Loop definition template

Fill every field with concrete choices; the template describes a draft-only recurring body.

```markdown
### <Loop name>
- Purpose: <one outcome, success measure, review owner>
- Check cadence: <frequency/trigger, timezone, evidence window, freshness tolerance>
- Acts when: <materiality condition, minimum evidence, exclusions; otherwise no-op>
- References used: <sibling links required for this body>
- Inputs: <sources, access scope, baseline, expected completeness>
- Body:
  1. Read the disable flag and durable state; acquire overlap protection.
  2. Collect permitted inputs; compare with the defined baseline/cursor.
  3. Apply the action condition and self-check to eligible items.
  4. Write bounded staged artifacts using stable keys.
  5. Commit successful processing state and write the run report.
- Self-check: <tracking validity, sample/cohort maturity, seasonality, known changes>
- State / idempotency: <store, cursor, key scheme, cooldown, in-flight ownership>
- Limits: <maximum items/runtime, attempt limit, retention window>
- Stop / bail-out: <no-op, stale/missing data, state failure, conflict, sensitive case>
- Human checkpoint: <exact proposals needing review; no external effects in this body>
- Output: <artifact destination, deliverable format, reviewer, blocked/no-op format>
- Off switch: <disable location and mechanism; scheduler disable procedure>
- Scheduling status: <manual unless separately requested and authorized>
```

### Readiness checklist

- Every anatomy field is concrete, with a bounded body and explicit error path.
- Inputs and comparison windows support the action condition; unavailable evidence has a blocked outcome.
- A repeated or interrupted run produces one logical artifact per key and preserves unprocessed work.
- Staged work, human approval, and external execution have distinct statuses.
- The owner can inspect artifacts and disable the loop; review capacity covers expected output.
- Scheduling, if requested, has defined timezone, overlap, missed-run, and failure behavior.

## Run report format

Produce a report for every run, including skipped, blocked, and failed runs:

```markdown
### <Loop name> — <run ID and timestamp>
- Status: completed / no-action / blocked / failed / disabled
- Evidence: <sources, source dates, evaluated window, freshness/completeness>
- Scope: <items checked, eligible, staged, skipped, failed>
- Findings: <observed change, baseline, uncertainty, self-check result>
- Artifacts: <stable keys, locations, versions, review status>
- State: <cursor before/after, committed keys, unresolved reservations>
- Blockers: <missing evidence, permission, decision, or failed dependency>
- Next decision: <owner and proposed review; no unattended contact>
- Next check: <cadence or resume condition; disable status>
```

Record counts as staged work, not as completed external actions. Keep concise run history so an owner can detect duplicate artifacts, persistent blockers, and workflows that no longer earn their review time.

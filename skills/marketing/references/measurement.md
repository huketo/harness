# Measurement

This file covers decision-led tracking plans, early-stage measurement without an analytics SDK, experiments, and attribution.

## Route the request

| When the request is about… | Use this section | Deliver |
|---|---|---|
| What to measure or unreliable event data | Tracking plan | Event dictionary and validation checklist |
| A product with little traffic or no analytics SDK | Measure with existing records | Minimal measurement sheet |
| Whether one change improves an outcome | Experiments | Experiment brief and results readout |
| Which channel deserves credit or conflicting dashboards | Attribution | Model comparison and attribution readout |
| Campaign links or sources disappearing at conversion | UTM conventions and journey continuity | Link registry and gap specification |

Use existing project evidence before collecting new inputs. Inputs to collect: the decision, target audience, meaningful outcome, available records, baseline window, traffic or cohort size, privacy policy and consent behavior, owner, and decision deadline.

For product claims in interpretations or deliverables, use the claim ledger from SKILL.md.
Prepare the draft/checklist for publishing links or surveys, launching experiments, spending, or changing live tracking or ad conversions; execution needs explicit authorization naming the action (see SKILL.md).

## Tracking plan

### Start with questions and decisions

1. State the decision and what evidence would change it: for example, whether onboarding needs revision rather than whether page views increased.
2. Define success as an observed outcome: a completed useful action, confirmed purchase, retained contributor, or qualified opportunity. Separate intent, attempts, success, and failure.
3. Map the smallest funnel needed to explain that outcome. Add diagnostic events only when they distinguish actionable causes of drop-off.
4. Inventory existing events, database records, operational reports, logs, and surveys. Reuse working definitions before proposing instrumentation.
5. Define each metric's numerator, denominator, unit, time window, eligible population, exclusions, and source of truth.
6. Choose the smallest collection plan that answers the question. Finish with an owner, missing evidence, and the action each metric can support.

Raw event counts, people, sessions, accounts, and orders are different units. A repeat action should not silently become another customer. Document conversion counting explicitly: once per eligible person, once per account, or once per confirmed transaction.

### Event taxonomy and naming

Preserve a coherent existing convention. For a new taxonomy, use lowercase `object_action` names with underscores, such as `signup_completed`, `checkout_started`, or `purchase_completed`.

| Event family | Purpose | Choose only relevant examples |
|---|---|---|
| Exposure | Define who could take the action | `page_viewed`, `experiment_exposed` |
| Intent or attempt | Locate friction before success | `cta_clicked`, `form_started` |
| Confirmed outcome | Measure actual completion | `signup_completed`, `purchase_completed` |
| Value and return | Measure useful behavior and retention | `core_action_completed`, `membership_renewed` |
| Failure or reversal | Explain harm and lost value | `form_failed`, `refund_completed` |

Keep placement, feature, plan, device, and campaign in properties rather than creating an event name for every combination. Define the exact trigger: `form_submitted` means accepted by the backend if acceptance is the outcome, not merely a click on Submit.

For reliable business outcomes, prefer the authoritative server record when available. UI events explain attempts; they do not replace confirmed purchases or successful account creation. Map tool-required event names to the canonical dictionary if needed; verify current specifications before use.

### Properties and identity

For every property, specify its decision purpose, type, allowed values, null behavior, and scope: event, session, person, account, or item. Keep a small shared schema and add contextual properties only when useful.

| Property category | Candidate fields | Decision rule |
|---|---|---|
| Integrity | `event_id`, occurrence time, schema version, environment | Support deduplication, ordering, and change audits |
| Context | Safe page path, placement, action type, error category | Use structured categories rather than raw text |
| Outcome | Transaction ID, amount, currency, refund state | Define gross/net value and confirmed status |
| Experiment | Experiment ID, assigned variant, exposure time | Separate assignment from actual exposure |
| Acquisition | Source, medium, campaign, landing page | Preserve provenance and acquisition timestamp |
| Identity | Pseudonymous person/account IDs where approved | Add only for justified joins or cohorts |

Document browser/server ownership and deduplication keys, including refreshes, retries, repeated callbacks, and webhook redelivery. Distinguish occurrence time from receipt time, choose a reporting timezone, and allow for late records.

Identity plan:
- Define anonymous, authenticated, and account identities separately; use a stable internal identifier rather than an email as an analytics key where possible.
- Join anonymous history to a known person only at a verified identity transition and within approved consent and policy rules.
- Specify logout, shared-device, account-switching, deletion, and revoked-consent behavior. Ambiguous identities remain unjoined.
- Use explicit membership records for account rollups; a shared email domain alone does not establish account membership.
- Report unmatched conversions and linked-journey coverage. Missing identity is a limitation, not a reason to invent a source.

### Consent, privacy, and owner decisions

Collect only what is needed, respect the project's privacy policy and consent state, and add no tracking without the owner's decision.

For each proposed field or destination, document purpose, permitted consent state, storage location, access, retention, and deletion handling. Treat pseudonymous identifiers as potentially personal data; first-party storage and server-side collection are not consent exemptions.

Use structured error codes and sanitized URLs. Exclude credentials, payment details, personal messages, form contents, and sensitive free text from analytics payloads. Query strings, referrers, search terms, and survey responses need explicit review because they can contain personal data.

Specify what happens before a choice, after acceptance, after rejection, and after withdrawal. Ask the owner to resolve policy or legal ambiguity; proposed implementation should preserve the restricted state until that decision is made.

### Data-quality checklist

Prepare a validation checklist before any authorized deployment:
- Each trigger produces the intended event with valid types and expected nulls.
- Attempts and confirmed outcomes remain distinct, including failed submissions.
- Refresh, navigation, retries, and duplicate callbacks preserve counting rules.
- Browser and server events reconcile without double counting.
- Consent states and withdrawal apply to every destination, not just one tag.
- Payloads contain only approved properties and sanitized context.
- Cross-domain or subdomain transitions preserve only approved continuity.
- Test, staff, bot, and development traffic have documented exclusion rules.
- Revenue reconciles with authoritative transactions, reversals, and currency rules.
- Named owner reviews event volume, missing fields, duplicates, and coverage after release.

Specify live changes, affected surfaces and destinations, expected data impact, proposed validation, and rollback. Treat conversion labels, filters, attribution settings, identity merges, and ad-conversion imports as production changes even when no code deploy is involved.

## Measure with existing records

Use existing authorized records before making an SDK a prerequisite. An early product can answer a narrow decision with a dated, repeatable sheet.

| Method | Useful for | Caveat |
|---|---|---|
| Read-only database queries | Signups, completed actions, purchases, repeat use | State changes may erase history; define status and timestamp semantics |
| Existing server logs | Request failures and operational funnel steps | Requests are not unique people; bots, caching, and retries distort counts |
| UTM-tagged acquisition links | Comparing identifiable campaign arrivals | A click is not a conversion; joining requires approved retained source data |
| Optional surveys or interviews | Discovery source, motivation, confusing steps | Recall and response bias; participation may not represent all users |
| Manual cohort counts | Small groups' activation and return | Keep eligibility, windows, evidence, and handling of missing records consistent |

Procedure:
1. Choose one question and an existing record that can answer it. Use read-only queries or exports within existing access permissions.
2. Define a cohort by entry date and eligibility. Compare equally mature windows: a newly joined group has not yet had the same chance to return.
3. Count unique units and confirmed outcomes. Show numerator and denominator alongside every rate.
4. Reconcile a small sample with underlying records and list missing history, delayed data, and known exclusions.
5. Record the query or counting rule, source, extraction date, timezone, and owner so the next period is comparable.
6. Separate observed outcomes from inferred causes. Add new instrumentation only when a recurring decision cannot be answered with these records.

For retention, define the useful return action and observation window rather than assuming a login means value. For marketplaces, report participant sides separately; for communities, distinguish membership from contributing; for sales-assisted products, distinguish inquiry from qualified and realized outcomes.

Keep individual records in approved storage; share aggregate summaries when sufficient. Logs, exports, and spreadsheets inherit the same privacy and access obligations as analytics tools.

## Experiments

### Design the brief

Write: “Because [dated observation], changing [specific experience] for [eligible audience] should improve [outcome] through [mechanism]. We will judge this using [primary metric and decision threshold].”

Prefer one coherent change per test. A complete redesign can be tested as a bundle, but its result identifies the bundle's effect rather than which element caused it.

1. Define eligibility and randomization unit: person, account, household, or region. Choose a unit that limits spillover; account members influencing each other should not be treated as independent people.
2. Describe control and variant precisely; keep assignment consistent on return visits. Plan exposure logging and outcome observation windows.
3. Select one primary metric tied to the hypothesis. Define secondary metrics for explanation, not alternate routes to declaring a winner.
4. Set guardrails with thresholds and actions: failed payments, latency, complaints, unsubscribe rate, refunds, or harm to the other marketplace side.
5. Declare allocation, analysis method, sample target, minimum duration, maximum decision date, and stopping rules before launch.
6. Check existing measurement quality, eligibility, variant rendering, consent, and exposure records. Prepare launch and rollback checklists.

An equal split is a planning rule of thumb for a simple two-arm test because it usually uses sample efficiently. Risk-limiting ramps or unequal splits require a corresponding sample calculation and a documented allocation schedule.

### Sample size and duration

Calculate sample size using the metric's distribution, recent eligible-population baseline, minimum detectable effect (MDE), chosen error tolerance, desired power, allocation, and randomization unit. MDE is the smallest effect worth detecting; specify absolute percentage points versus relative lift explicitly.

Rules of thumb, not market benchmarks: a two-sided significance level of 0.05 and power of 0.80 are common planning choices, and at least a full weekly cycle can help capture weekday variation. Verify their suitability using dated project research or a fresh cited methods lookup; cover the project's actual buying, usage, and outcome-delay cycles.

For each arm, estimate `days = required sample / expected eligible assignments per day`; the slowest arm constrains duration. Allow time for outcomes to mature after assignment stops. More variants, cluster randomization, and confirmatory segment comparisons need appropriate power and multiple-comparison handling.

Use a validated calculation rather than an inherited sample-size table. If duration exceeds a stable decision window, simplify to two arms, target a larger worthwhile change, or choose a lower-traffic method. An upstream click metric can be diagnostic but does not prove downstream value improved.

### Low-traffic alternatives

| Approach | Use when | Interpret honestly |
|---|---|---|
| Task-based qualitative tests | The question is comprehension, discoverability, or usability | Observe failure mechanisms; do not claim a population conversion lift |
| Interviews or message comparisons | Unclear motivation or language precedes metric design | Use evidence to refine a hypothesis, not declare a statistical winner |
| Before/after cohorts | Randomization is unavailable and a practical choice is needed | Match eligibility and maturity; seasonality, channel mix, and other changes confound results |
| Alternating-time or staged rollout | Experience must change by period or group | Specify washout/carryover and concurrent controls where feasible; calendar effects remain |
| Formal sequential inference | Interim decisions are necessary | Predefine valid sequential boundaries; it does not create information from scarce traffic |

Prefer reversible decisions with explicit uncertainty to an underpowered “winner.” Increasing rigor should follow decision stakes, not tool availability. Participant recruitment, invitations, surveys, and live rollouts fall under the authorization line above.

### Stopping and analysis

For fixed-horizon tests, inspect data quality and safety during the test but evaluate efficacy at the predeclared sample and duration. Repeatedly checking ordinary p-values and stopping on a favorable result inflates false positives.

Stop or pause according to predefined safety thresholds, broken instrumentation, assignment errors, or severe contamination. Mark affected data and determine whether the test is invalid or needs a fresh run; a safety stop is not evidence of a positive effect.

At the maximum date, an unmet sample target produces an underpowered or inconclusive readout. Extend only through a documented method-consistent rule, not because the result is close to a desired threshold. Formal sequential or Bayesian designs need their own predeclared decision rules.

Before interpreting outcomes, check sample-ratio mismatch against planned allocation, missing exposure, cross-arm leakage, and differential data loss. Keep the original assignment-based analysis; filtering to people who engaged after treatment can introduce selection bias.

Report counts, rates, absolute and relative effect, an appropriate uncertainty interval, guardrails, and practical value. A p-value is not the probability that the result is random, and statistical significance alone does not establish a worthwhile effect. Separate planned segment analyses from exploratory observations.

An inconclusive interval can still rule out some effects; state which worthwhile gains or harms remain plausible. Carry the decision and evidence into the next hypothesis, rather than treating every test as a reusable universal rule.

## Attribution

### Define what is being credited

Attribution assigns credit among observed touches; it does not by itself establish causation. Anchor actual conversions and value in the authoritative order, payment, membership, or qualified-outcome system.

Choose the conversion, unit, lookback window, click/view eligibility, refund treatment, reporting date basis, and model before comparing channels. Report source evidence and confidence separately from the credit rule.

| Model | Credit rule | Useful interpretation and limitation |
|---|---|---|
| First-touch | First observed eligible touch receives credit | Discovery lens; misses earlier untracked awareness and later influence |
| Last-touch | Last eligible touch receives credit | Closing lens; can over-credit branded search and retargeting |
| Last non-direct | Last known non-direct touch receives credit | Keeps a later direct visit from overwriting a known source; still single-touch |
| Linear | Equal credit across eligible touches | Descriptive path summary; frequent touches gain credit without proving impact |
| Time-decay | More weight near conversion | Recency lens; half-life is an assumption to disclose |
| Position-based | Weight selected milestones or first/last touches | Useful bookend lens; weights are chosen, not discovered facts |
| Data-driven | Algorithm estimates contributions from available paths | Requires sufficient stable data and documented methods; missing touches and confounding remain |

For short, simple journeys, a consistent last non-direct view plus self-report may suffice. For long or multi-person journeys, compare first and last views and roll up only verified account relationships. Separate acquisition, repeat purchase, and expansion journeys.

Multi-touch attribution describes tracked paths. Marketing mix modeling relates aggregate activity and outcomes with controls and requires suitable history and variation. Controlled holdouts estimate incremental effects when randomization, contamination control, and sufficient data support the design. Use the latter for high-stakes causal questions, not as an automatic promise of certainty.

### Self-reported attribution and limits

Prepare an optional question near conversion: “How did you first hear about us?” An open answer captures unanticipated sources; a short channel list with “other” and optional detail is easier to categorize. Ask about discovery separately from what prompted action today when that distinction matters.

Keep self-report alongside observed attribution, with response date, response rate, coding rules, and confidence. Recall and nonresponse bias mean a channel's survey share is not automatically its share of caused conversions.

Direct includes typed URLs but also missing referrers and unobserved journeys. Branded search can capture demand created elsewhere. Private sharing, offline conversations, cross-device behavior, and AI-assisted discovery may leave no observable touch. Report these as gaps; their presence does not prove a particular channel caused demand.

### UTM conventions and journey continuity

| Parameter | Meaning | Neutral example |
|---|---|---|
| `utm_source` | Named publisher or source | `newsletter` |
| `utm_medium` | Controlled channel category | `email` |
| `utm_campaign` | Stable campaign identifier | `autumn_workshop` |
| `utm_content` | Creative or placement identifier | `footer_link` |
| `utm_term` | Search term or approved targeting label when needed | `intro_course` |

Use lowercase values and one separator convention. Maintain a link registry with destination, parameters, purpose, owner, and dates. Keep campaign taxonomy stable, validate URL encoding and redirects, and keep personal identifiers out of UTMs. Preserve acquisition source through internal navigation rather than tagging internal links as new campaigns.

Distinguish paid, owned, earned, direct, and unknown using explicit taxonomy rules. Preserve first acquisition separately from subsequent touches; collect an ordered path only if the decision justifies its privacy and storage cost.

Audit existing domain, authentication, and hosted-checkout transitions before specifying a new join. Exclude self-referrals and redirect intermediaries from acquisition classification without discarding genuinely external discovery sources. For approved external continuity, prefer scoped opaque tokens and supported metadata with verified callbacks; never pass personal identifiers in public URLs. Ambiguous joins remain unknown.

### Reconcile sources

1. Fix conversion definitions, timezone, windows, click/view rules, refund handling, and data freshness before treating a mismatch as channel performance.
2. Deduplicate against authoritative conversion IDs where permitted. Never sum platform-claimed conversions as if they were unique outcomes.
3. Compare models, observed sources, and self-reports on the same eligible period. Distinguish conversions from revenue and mature from incomplete cohorts.
4. Explain coverage and disagreement: modeled outcomes, overlapping claims, missing joins, offline influence, and recall bias.
5. Recommend a bounded decision with confidence. Use a suitable holdout for costly unresolved causal questions; prepare its brief rather than changing spend.

Keep raw observations separate from any evidence-based allocation adjustment. Label adjustment basis and applicable dates; preserve unknowns instead of inserting invented touches or applying a platform-gap multiplier.

## Deliverable formats

### Tracking plan template

- Decision, owner, date, eligible population, source of truth, and existing coverage.
- Metric definition: numerator / denominator, unit, observation window, exclusions, and decision threshold.
- Event dictionary:

| Event and exact trigger | Decision served | Properties and types | Identity / dedupe rule | Source / owner | Consent and retention |
|---|---|---|---|---|---|
| One row per proposed or existing event | Action this enables | Required / optional; null rules | Unique unit and replay handling | Current record or proposed change | Permitted state and deletion |

- Gaps and proposed changes, validation cases, rollback, and owner decisions awaiting authorization.
- Without an SDK: cohort, dated source/query/counting rule, eligible count, outcome count, mature window, uncertainty, and next decision.

### Experiment brief template

- Experiment ID, owner, dates, decision, and hypothesis with dated evidence.
- Audience, exclusions, randomization unit, control, variant, allocation, and exposure definition.
- Primary metric and calculation; baseline period; worthwhile effect / MDE in explicit units.
- Secondary metrics; guardrail thresholds and prescribed actions.
- Analysis method, sample calculation assumptions, target per arm, minimum duration, maximum date, and outcome-maturity window.
- Planned segments, comparison handling, stopping rules, quality checks, rollback, and launch authorization status.

Results add: assigned/exposed counts, outcome counts, effect and interval, guardrails, integrity checks, deviations, supported versus unresolved conclusions, decision, and next hypothesis.

### Attribution readout template

- Decision, period, authoritative conversion/value totals, model, windows, and count definitions.
- Channel comparison: observed touches, credited outcomes, platform claims, self-report, source basis, and confidence; overlapping claims stay separate.
- Model sensitivity, linked-journey coverage, unknown share, survey response rate, and reconciliation gaps.
- Recommended decision with uncertainty, evidence needed to change it, proposed causal test if warranted, and authorization required for any live change.

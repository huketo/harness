# Conversion, Signup, and Activation

This file covers evidence-based page conversion reviews, account-creation flows, and the minimum onboarding path to meaningful product value.

## Route the work

| Situation | Start here | Deliverable |
|---|---|---|
| Visitors understand little, hesitate, or fail to take the page's intended action | [Page conversion review](#page-conversion-review) | Findings, copy alternatives, prioritized changes |
| Visitors start a form or account flow but fail to complete it | [Signup and form flows](#signup-and-form-flows) | Field decisions, state copy, handoff and recovery specs |
| New users create accounts but fail to experience value | [Onboarding and activation](#onboarding-and-activation) | Activation definition, first-run flow, checklist and nudge drafts |
| A proposed change needs validation | [Experiment hooks](#experiment-hooks) | Hypothesis and measurement brief |

Produce findings, copy, and implementation specs here. Implementation of UI changes belongs to the `awesome-interface` skill when installed.
For a full messaging rewrite use [copy](copy.md); for missing audience or objection evidence use [research](research.md).

## Evidence before recommendations

Inspect the actual flow through source code or the running application and cite what you inspected. Screenshots alone can support visual findings, but cannot establish unobserved transitions or backend outcomes.

1. Identify the audience, traffic source, page or entry route, intended action, and downstream value.
2. Inspect each relevant screen, field, CTA destination, success state, and recovery path.
3. Record the observed path and distinguish observed behavior from source-derived behavior and hypotheses.
4. Where available, use dated funnel data, cohort analysis, support reports, or research to locate the constraint.
5. Separate a functional blocker from a persuasion hypothesis: a broken return path needs repair, not a button-color experiment.

Collect only missing inputs: flow URLs or source locations, audience/source, conversion goal, access constraints, required data or verification, and existing funnel evidence.
If access is partial, name the uninspected states and limit conclusions to the evidence available; give an inspection checklist rather than a completed audit of those states.
Use the claim ledger from SKILL.md for product capabilities, pricing, privacy assurances, guarantees, testimonials, counts, security, and outcome claims.
Cite a source path and line range, or a route/URL with observation date and reproduction steps, for each material finding. Cite metric definitions, date windows, and segments for numerical findings.
Treat unsupported uplift estimates as hypotheses; prioritize by evidence, user impact, reach, effort, and dependencies rather than invented precision.

## Page conversion review

### Establish the page's job

Define one primary conversion and its qualifying condition. A click, completed submission, verified account, purchase, and activated user are different outcomes.
Map the visitor's promise-to-value journey: traffic message → page promise → CTA → destination → delivered outcome.
Compare the page with the actual ad, search intent, referral, email, or social post where available; record unavailable source messaging as a gap.

| Page type | Decision the page should support |
|---|---|
| Homepage | Understand the offer and find a path for both ready and researching visitors |
| Campaign landing page | Recognize the promised offer and take a focused next action |
| Pricing or purchase page | Understand total cost, plan fit, limits, and commitment |
| Feature or use-case page | Connect a capability to a relevant outcome and a way to try or obtain it |
| Resource or article | Take a contextual next step consistent with reading intent |
| Contact, application, or request page | Understand what will happen after submitting and why information is needed |

### Review in decision order

| Dimension | Inspect | Recommendation rule |
|---|---|---|
| Value proposition | What it is, who it serves, useful outcome, meaningful distinction | Lead with one concrete benefit in audience language; explain unfamiliar categories |
| Message match | Audience, offer, terms, visual promise, and CTA against the traffic source | Preserve the promise through the next step; resolve material mismatches before polishing copy |
| CTA hierarchy | Primary/secondary actions, placement, repetition, destination, expected result | Make the next action explicit and prominent at decision points; retain useful alternatives for lower intent |
| Scannability | Headings, section order, imagery, mobile presentation | Let a scan reveal the argument; use visuals that explain actual value |
| Trust and proof | Attribution, relevance, permission, date, claim support, placement | Put supported proof beside the claim or commitment it substantiates |
| Objections | Fit, price, setup effort, risk, access, delivery, support | Address evidence-backed objections where they arise with accurate terms or process explanation |
| Friction | Fields, navigation, loading, unclear steps, device/accessibility barriers | Remove avoidable effort while retaining necessary safety, consent, and compliance controls |

### Copy and proof decisions

- Write headlines that state the relevant outcome or capability; use specificity only when supported.
- Use the subheading to explain audience, mechanism, or limitation rather than repeat the headline.
- Name the CTA's actual next step: a request is not an instant result, and account creation is not activation.
- Offer two or three alternatives for disputed headlines or CTAs, each with a rationale and intended audience.
- Select proof for fit, not decoration: a relevant customer outcome may answer more than an unrelated logo wall.
- Attribute testimonials accurately and preserve qualifications around results; flag missing permissions or provenance.
- Make price, renewal, eligibility, trial limits, refund conditions, and delivery expectations clear before commitment.
- Express privacy and security assurances in terms the project can substantiate.
- Use genuine availability or deadlines only when evidenced; avoid fabricated urgency or scarcity.

### Prioritize the review

**Quick wins:** localized clarity or recovery improvements with strong evidence and few dependencies.
**High-impact:** larger changes to promise, structure, qualification, flow, or value delivery that address a material constraint.
**Test ideas:** plausible competing approaches whose relative effect needs validation.
These are recommendation categories, not guarantees of uplift or authorization to change a live page.

## Signup and form flows

### Map completion end to end

Record entry → first interaction → each step → submission → verification or payment if applicable → usable account or delivered request.
Include existing users, invited users, returning abandoners, and a fresh visitor where those paths exist.
For lead capture, contact, or applications, define completion as successful delivery and confirmation rather than account creation.

### Decide fields by necessity

For each field, record its purpose, consumer, required status, validation, and earliest necessary collection point.
Keep a field required only when the user cannot proceed safely or receive the promised outcome without it. Defer profile enrichment or sales qualification that is unnecessary for that outcome.
Use authorized, reliable prefill where available; let users inspect and correct it. Treat inferred company or role data as uncertain, not identity truth.

| Field or control | Specification considerations |
|---|---|
| Email or phone | Appropriate input/keyboard, autofill, recoverable typo guidance, relevant country handling |
| Password | Explain actual policy upfront; support paste, password managers, and visibility control |
| Name | Match the product's real identity needs and international naming conventions |
| Organization, role, use case | Collect when it changes the immediate path; explain required questions |
| Long lists or free text | Use sensible grouping, search or conditional questions; provide an applicable alternative |
| Consent and terms | Clear choices and accurate terms; distinguish account consent from optional marketing consent |

Keep labels visible; use placeholders for examples. Identify required versus optional inputs and put help beside the decision it explains.
Validate when users can act on the feedback rather than interrupting unfinished typing. Preserve entered non-sensitive data on recoverable errors.
Specify keyboard access, accessible error association and focus, suitable input types, readable contrast, and mobile behavior; hand implementation to the UI skill.

### Choose structure by the task

Use a single step for a coherent, low-effort task. Use multiple steps when grouping, branching, or genuinely necessary complexity helps comprehension; choose by observed behavior rather than a universal field-count threshold.
For multi-step flows, specify truthful progress, one coherent topic per step, back navigation, resumability, and handling of changed answers.
Explain the commitment and what happens next. Any timing promise needs measured support.
Where the product allows it, compare experiencing value before signup with signing up first; preserve data ownership and security requirements.
For purchases, consider the existing guest or post-purchase account path rather than assuming an account must precede value.

### Authentication and external identity handoffs

Evaluate email/password, passwordless, social sign-in, organizational SSO, or delegated/hosted account creation against audience access, product constraints, and recovery needs.
A product may hand account creation to an external identity provider; audit the complete handoff rather than treating absence of a local form as missing signup.

1. Identify the initiating CTA, provider boundary, requested permissions, expected account type, and return destination.
2. Inspect what explains the change of site or app, whether signup versus sign-in remains clear, and how pre-auth intent is retained.
3. Inspect completion returning to the intended product route with the expected identity and usable session.
4. Inspect cancel/back, denied consent, unavailable provider, interrupted callback, expired link/session, and repeated submission paths that exist.
5. Check existing-account and account-linking behavior, including a user who previously used another method; preserve privacy and account-security safeguards.
6. Specify recovery copy, safe retry or alternate access, and the destination after recovery. Mark provider-owned UI constraints separately from product-owned changes.

Recommend only authentication methods the product can support. Adding a provider is a product/security decision, not simply a copy change.

### States and recovery

| State | Findings or copy spec to produce |
|---|---|
| Empty form | Clear value, visible labels, essential requirements, and expected next step |
| Loading/submitting | Honest progress, duplicate-submit handling, and recovery from a stalled request |
| Field error | Specific correction beside the field; accessible focus and retained safe inputs |
| Service or network failure | What failed, what was retained, how to retry or seek help |
| Existing account | Safe sign-in/recovery path consistent with enumeration protections |
| Verification pending | Destination, resend behavior, wrong-address correction, and link expiry recovery |
| External handoff failure | Explain the incomplete transition and provide a product-owned return path |
| Success | Confirm the real completed action and lead to the next useful step |

Change verification timing only when product security, abuse prevention, and compliance permit it. Explain which value remains available while verification is pending.
Separate form submission, provider completion, account readiness, and first value in both findings and measurement.

## Onboarding and activation

### Define activation from product evidence

Activation is the earliest observable event or sequence that demonstrates meaningful delivered value for the relevant user, not merely a completed tutorial or profile.

1. Identify the user goal and the product behavior that actually delivers it from source, the running flow, and product research.
2. Compare retained or successful users with unsuccessful cohorts when data exists; inspect whether a candidate event precedes later success.
3. Specify the event, actor/unit, prerequisites, time window, and whether it reflects sample or real use.
4. Label a definition without outcome evidence as a candidate activation event, with a validation plan.
5. Separate correlation from causation and distinguish individual from account or multi-sided activation.

Examples are hypotheses, not defaults: a consumer app may deliver a useful first result; a collaboration product may require a shared outcome; a marketplace may require a completed exchange; a community may require a meaningful response rather than profile completion.
Choose retention, purchase, repeat value, or another relevant downstream outcome to validate activation; use windows appropriate to the product's natural usage cycle.

### Fit access and commitment to value

Work within the evidenced access model: free tier, time-limited trial, paid access/trial, refundable purchase, or assisted evaluation.
Check whether the user can experience the promised outcome within the available access and setup time.
Evaluate payment or qualification gates using end-to-end activated and successful users, not signup volume alone.
Propose access-model or pricing changes as separate decisions with cost, risk, and user-fit evidence; an onboarding review does not silently change commercial terms.

### Build the minimum path to value

Inventory every screen, field, permission, confirmation, import, wait, setup action, and empty state from account readiness to the candidate activation event.
For each step, mark **essential now**, **defer**, **prefill**, or **optional** and state why. Preserve safety and genuinely required prerequisites.
Reconstruct a value-first path around one achievable first-session outcome; introduce advanced setup after it becomes relevant.
Measure elapsed time-to-value as well as active effort. Include external waits, approval, installation, data ingestion, and other dependencies.
Offer templates or clearly labeled sample data when they help demonstrate value, and specify the transition to real user data.
Separate a sample-based preview from activation that requires a real outcome.

### Select first-run guidance

| Approach | Use when | Risk to address |
|---|---|---|
| Product-first | The useful action is discoverable and needs little setup | Blank-slate confusion |
| Guided setup | Necessary configuration unlocks value | Configuration becoming the whole first session |
| Demonstration-first | Real data or results take time to obtain | Sample output mistaken for delivered value |
| Assisted path | Complexity or coordination requires human help | Scheduling delay and capacity constraints |

Give one primary next action and contextual help. Make optional tours dismissible, resumable where useful, and sensitive to prior completion.
Personalize only when a short question or existing signal changes the immediate value path; collecting segmentation for its own sake adds friction.
Diagnose a stalled step as unclear value, excessive effort, missing ability/resource, or a poorly timed prompt before adding more messaging.

### Checklists and empty states

Use a checklist when several real steps are necessary. Keep it short, order by value and dependency, and make each item actionable.
Progress should reflect actual completed work, including genuine work already done for the user. Acknowledge a meaningful outcome rather than manufacturing completion.
Specify dismiss/resume behavior and distinguish required setup from optional exploration.

For each empty state, provide:
- What this area enables and why it matters now.
- A clear primary action to create, import, discover, or request the first useful item.
- A realistic example or preview when useful, explicitly labeled as illustrative.
- Loading, permission-denied, failed-load, and genuinely empty variants where applicable.
- A next path if the user cannot supply data or perform the action yet.

### Lifecycle nudges and returning users

Draft nudges around behavior, not a universal day-based schedule: welcome/orientation, a blocked essential step, achieved value, or a relevant next capability.
Define “stalled” using the product's normal value cadence and the incomplete action; distinguish waiting on the system from user inactivity.
For every draft specify trigger, eligibility, channel, timing rationale, stop condition, frequency constraint, message, and destination.
Use one useful concept and one actionable next step; deep-link to resumable work when supported.
Suppress completed or irrelevant prompts and respect channel consent, preferences, and applicable communication requirements.
The return experience should preserve progress, explain any changed state, and offer contextual recovery rather than replaying the whole introduction.
For complex paths, propose human assistance only with a capacity and routing plan.
Prepare the draft/checklist; execution needs explicit authorization naming the action (see SKILL.md).

## Experiment hooks

Use [measurement](measurement.md) for metric definitions, instrumentation specs, experiment design, sample feasibility, and decision rules.
Choose tests from the observed bottleneck: promise clarity, proof placement, deferred fields, step structure, handoff reassurance, value-first ordering, templates, contextual help, or behavior-triggered nudges.
Treat functional correctness, truthful claims, security, and accessibility requirements as baseline acceptance criteria rather than optional experiment variants.

For each experiment specify the evidence, affected cohort, mechanism, control/variant, primary outcome, downstream guardrails, eligibility, and expected direction without claiming a numerical uplift.
Use a funnel appropriate to the task: qualified visit → intended action → completed request or ready account → meaningful value → repeat success.
Segment by relevant source, device, intent, access model, or authentication route where volumes support interpretation.
Track denominators and elapsed windows consistently; compare activation quality alongside signup completion to detect transferred friction.
Specify event names and state transitions rather than collecting raw field contents, credentials, or unnecessary personal data.
Prepare the draft/checklist; execution needs explicit authorization naming the action (see SKILL.md).

## Output format

### Review brief

- Scope: audience, source, goal, flow boundaries, inspected surfaces, and dated evidence.
- Journey: observed steps, ownership boundaries, completion definition, activation candidate, and uninspected states.
- Baseline: available rates, denominators, windows, segment differences, and evidence gaps.

### Quick wins / High-impact / Test ideas

Group findings under those three headings. For each use:

| Finding and evidence | User consequence | Proposed change or copy | Priority and rationale | Dependency/owner | Success measure |
|---|---|---|---|---|---|
| Observed issue with citation; uncertainty labeled | Mechanism, not invented uplift | Specific draft/spec | Reach, confidence, impact, effort | Product, provider, UI, or measurement boundary | Outcome and guardrail |

### Flow and copy specification

Include only the relevant deliverables:
- Page: proposed section order, primary/secondary CTA destinations, proof requirements, objection answers, and headline/CTA alternatives.
- Form/signup: field inventory with keep/defer/optional rationale, sequence, labels/help, state copy, authentication handoff/return map, and recovery acceptance criteria.
- Onboarding: activation event and evidence status, minimum path with step dispositions, first-run approach, checklist items, empty-state variants, and time-to-value constraints.
- Lifecycle: draft messages with trigger, timing, eligibility, stop conditions, and exact return destination.
- Experiments: hypotheses and measurement handoff; separate correctness fixes from tests of competing approaches.

End with unresolved evidence or product decisions and a review checklist for the implementation owner. Keep proposed changes distinct from inspected current behavior and from authorized execution.

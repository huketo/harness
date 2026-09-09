# Technical Talks

Use this reference for decks that explain software, APIs, architecture, experiments, benchmarks, or operational cases. It owns technical grounding and evidence discipline, not renderer syntax or general slide styling.

## Ground statements in the system being discussed

Start from the artifacts that define actual behavior:

1. Inspect the local repository, configuration, examples, tests, and executable help when available.
2. Use current primary documentation for external APIs and record the relevant version or retrieval date.
3. Trace a claim to the implementation path, public contract, or observed output that supports it.
4. Reconcile disagreements explicitly: local pinned behavior may differ from the latest documentation.
5. Mark conceptual pseudocode or inferred behavior as such when direct access is unavailable.

For API material, preserve exact names, parameter meaning, return shape, error behavior, lifecycle, and relevant constraints. For local code, cite stable repository-relative paths and symbols rather than machine-specific absolute paths. Avoid screenshots of source when selectable code or a focused diagram communicates the same evidence more clearly.

A diagram or polished code sample does not upgrade an assumption into a fact. If the implementation cannot be inspected, narrow the claim and state the boundary.

**Done when:** each implementation-level claim points to a retrievable API source, local symbol, observed output, or clearly labeled inference.

## Make comparisons answer one fair question

Define the decision before building a comparison:

- the candidates and versions;
- the workload, data shape, and scale;
- hardware, runtime, network, and configuration conditions that materially affect results;
- the metric, unit, direction of improvement, and aggregation method;
- warm-up, sample count, variability, failures, and exclusions when applicable;
- functional differences that make a numeric ranking incomplete.

Compare like with like. Hold relevant conditions constant or explain why they differ. Separate measured findings from vendor claims and from expectations. Show uncertainty when the data supports it; do not imply precision the measurement did not produce.

When no reliable measurement exists, present a qualitative trade-off table tied to documented capabilities, or label a proposed benchmark plan. Never invent numbers to complete a chart. Synthetic data may explain how to read a visualization, but it cannot establish which candidate performs better.

**Done when:** the audience can identify the decision, conditions, metric, source, and limits of every comparison without relying on narration.

## Use code as a short explanation unit

Give each code view one teaching job: introduce an API call, expose a control path, contrast two choices, or connect a symptom to a fix. Include the smallest coherent unit that preserves the behavior being explained.

- Keep identifiers faithful to the real API or local code.
- Include imports, setup, and error paths only when they matter to the point; disclose meaningful omissions.
- Highlight the relevant lines without making non-highlighted lines unreadable.
- Reveal code in logical chunks when the explanation is sequential.
- Put lengthy setup, full listings, and alternatives in a linked source or appendix.
- Pair output with the code when the output is the evidence.
- Treat line count as a layout signal, not a universal limit; split when the audience must scan instead of follow.

Do not retype executable code from memory when the repository can provide it. If a sample is illustrative or intentionally simplified, label it and avoid presenting its output as a completed run.

**Done when:** the shown code is technically faithful, readable at delivery size, and sufficient for the specific explanation without disguising omitted behavior.

## Keep diagrams at one level of abstraction

Choose the diagram's question first: system context, deployment, component responsibility, request sequence, data flow, state transition, or control loop. Keep each diagram primarily at that level. Use a second diagram rather than mixing cloud boundaries, classes, function calls, and packet details in one view.

Establish a small semantic legend:

- use the same term for the same concept in prose, code, diagrams, and notes;
- use stable shapes or colors for stable roles;
- label arrows with the event, data, or control they carry;
- show direction and boundaries where they affect the claim;
- distinguish synchronous, asynchronous, optional, and failure paths only when relevant;
- preserve terminology from the actual system unless the deck explicitly introduces an audience-facing alias.

For repeated architecture views, retain positions and encodings where possible so the audience notices the change rather than relearning the map.

**Done when:** every node and connection serves the diagram's stated question, and equivalent concepts retain one name and one visual meaning across the deck.

## Tell cases as evidence chains

Structure operational and engineering cases as:

1. **Observation:** what was directly seen in logs, traces, behavior, user reports, or measurements.
2. **Interpretation:** the explanation inferred from those observations, including competing hypotheses when relevant.
3. **Action:** what changed and why it tested or addressed the interpretation.
4. **Verification:** what observable result checked the action, plus remaining risk or rollback criteria.

Illustrative pattern — label it as an example, not a real incident:

> Observation: requests stop at a dependency call while upstream work completes.  
> Interpretation: dependency latency is the leading hypothesis; the trace alone does not prove its cause.  
> Action: add a bounded timeout and expose the dependency timing separately.  
> Verification: repeat the controlled failure scenario and confirm the request terminates as designed while the new signal identifies the wait.

Keep these stages distinct on the slide or across a short sequence. Do not rewrite interpretation as observation, or present an implemented action as verified before the check has occurred.

**Done when:** a reviewer can point to the evidence for the observation, the reasoning boundary around the interpretation, and the actual or planned verification of the action.

## Label the evidence class

Use consistent, visible labels wherever provenance could be mistaken:

- **Measured:** captured from the stated real system or experiment under disclosed conditions.
- **Controlled demo:** reproduced in a prepared environment or scripted scenario to demonstrate known behavior.
- **Synthetic:** invented or transformed values used to explain a concept, format, or interaction.

Add **unverified** when an expected result has not been observed. A controlled demo can prove that the scenario works under its controls; it does not automatically prove production prevalence or impact. Synthetic data can teach a pattern; it does not support a performance or business claim.

For screenshots, identify the system, state, and capture context when material. Redact sensitive data without changing the conclusion, and disclose alterations that could affect interpretation. A screenshot proves only what is visible and traceable in that captured state.

**Done when:** every chart, number, screenshot, output block, and demo artifact has an evidence class and enough context to prevent a stronger interpretation than it supports.

## Design demos to fail safely

Decide what the demo must prove, then minimize dependencies unrelated to that proof. Prepare the live path and a truthful static substitute from the same scenario:

- commands or interaction steps and the expected checkpoints;
- known prerequisites, credentials, network needs, and reset state;
- a captured output, recording poster, trace, or ordered screenshots for the critical states;
- a static final state suitable for PDF or other non-interactive delivery;
- a short explanation of what the fallback demonstrates and what it does not;
- a recovery or skip transition that preserves the talk's argument.

Prefer captured real output when it can be shared safely. If policy or access prevents capture, use a clearly labeled controlled or synthetic substitute. Never fabricate a “successful run” screenshot. Do not let a recording poster imply that video playback or a live system was verified.

When interactivity is essential, ensure the static export retains the conclusion, key state changes, and source context rather than a blank frame or play control.

**Done when:** the talk can continue after loss of network, credentials, service, or time without changing the evidence claim, and static recipients still receive the demo's essential conclusion.

## Technical completion gate

Technical talk content is complete only when:

- API and local-code claims are grounded to versions, paths, symbols, or observed output;
- comparisons disclose fair conditions, units, sources, and limitations;
- code views each explain one coherent behavior and label simplification;
- diagrams keep a purposeful abstraction level and consistent terminology;
- cases preserve observation → interpretation → action → verification;
- measured, controlled-demo, synthetic, and unverified material cannot be confused;
- live demos have truthful static fallbacks and export-safe final states;
- no invented metric, result, or screenshot is presented as evidence.

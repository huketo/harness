# Stress testing

Execute only when the user explicitly asks to stress-test a component or flow. This mode renders edge states in an isolated local fixture; it is not a source review, redesign or permission to fix production code.

## Bound the experiment

Identify the requested component, its props/slots, states, context and possible side effects. For several explicitly named components, cover each; resolve an ambiguous target from the task and repository rather than silently choosing a different scope. Record the scenario plan before building.

Use the real component and the project’s existing story, preview or scratch-page mechanism. Preserve its fonts, tokens, global styles and framework/server-client boundaries. A lookalike component or altered theme cannot prove the original works. The fixture may supply labels, container constraints, synthetic props and local event handlers, not restyle the subject to make it pass.

## Select reachable scenarios

Choose content values from [worst-case data](worst-case-data.md): realistic or schema-backed, never random filler. Include values the schema allows but the demo data omits, such as missing optional fields, markup-like text and counts of zero and one. Feed them through the same boundary as the demo data (fixture, props or API stub), not by editing the component's markup or styles.

Keep an axis when the component can actually receive it; record irrelevant axes and why. Combine axes selectively where interaction is plausible, rather than building an exhaustive Cartesian product.

| Cue | Scenarios |
| --- | --- |
| Variable text | Empty, one word, typical text, several sentences, long unbreakable URL/string |
| User or translated content | RTL, mixed direction, combining marks/tall scripts, wide glyphs and multi-codepoint characters; expanded translation text |
| Repeated items | Zero, one, realistic count, bounded high count such as ten times typical |
| Container, always relevant | 320px container, flex/grid sibling pressure, normal and very wide container |
| Stateful component | Reachable loading, error, disabled, selected, empty, success and retry states |
| Interactive component | Keyboard entry and exit, visible focus, hover/active, open/close, rapid reversal or repeated activation where supported |
| Supported environment | Real theme toggle, 200% browser zoom, reduced-motion preference and relevant narrow viewport |

Use [typography](typography.md) for text behavior, [layout](layout.md) for containment, [writing](writing.md) for empty/error guidance, [accessibility](accessibility.md) for input/focus/zoom, [colors](colors.md) for theme/state contrast and [UI polish](ui.md) for visual transitions. Load only owners relevant to the planned or observed behavior.

## Isolate before rendering

Use synthetic data created for the fixture, never copied identities or business content. Local callbacks can change local fixture state but must not call production APIs, submit forms, send messages, charge, delete or mutate user data. Inspect mount effects, imported stores and service clients as well as explicit event handlers. Bind previews locally and isolate network/service access with an existing fixture mechanism. If the real component cannot be safely isolated, report that blocker instead of running it live or substituting a mock and claiming coverage.

Render labeled instances for applicable content, state and container cases. Fixed-width instances help compare containment, but they do not exercise viewport media queries or browser zoom: use actual viewport/zoom controls for those cases. Respect server/client serialization constraints; confirm each instance received its intended props before attributing a failure to the component.

## Observe and report

Launch the local preview with the available supervised process mechanism and confirm readiness. Open it with the available browser, inspect every planned scenario, and exercise relevant interactions. Use captures for visible failures. When motion is involved, inspect normal speed first and slowed playback or interruption when needed. No rendered observation means `Not verified`, not “everything survived.” Investigate fixture failures separately from component failures.

| Scenario and environment | Exact interaction | Observed result | Owning domain / evidence |
| --- | --- | --- | --- |
| The actual input/state/width | Reproduction steps | Concrete break or no observed break | Capture/region and source location if established |

Report broken scenarios first, then covered scenarios, exclusions and unverified checks. For each break, name the cause and propose a fix direction in its owning domain, such as escaping inserted text, a fallback for a missing field or `overflow-wrap` on an unbreakable string; mark choices that are design decisions, such as truncating versus wrapping. “Text escapes the right edge” is evidence; “spacing feels tight” is taste. This mode issues no ship verdict. If fixes were also requested, apply the owning guidance and re-render the failing cases plus their relevant baseline.

## Keep the evidence, not the side effects

Leave the fixture and its worst-case data in place as the reproducible evidence: in the project's existing story, preview or scratch location, or a separate directory outside production paths, never imported by a production entry point or route. Report its location, how to open it and how to remove it. Remove it instead when the user asks for no leftover files, or when the only available location would ship with the product.

Stop the preview processes and browser resources started for this run. Preserve unrelated user work, and keep captures cited as evidence with the report. Report any resource that could not be stopped. A stress page must not silently become shipped UI.

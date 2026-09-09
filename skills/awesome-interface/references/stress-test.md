# Stress testing

Execute only when the user explicitly asks to stress-test a component or flow. This mode renders edge states in a disposable local fixture; it is not a source review, redesign or permission to fix production code.

## Bound the experiment

Identify the requested component, its props/slots, states, context and possible side effects. For several explicitly named components, cover each; resolve an ambiguous target from the task and repository rather than silently choosing a different scope. Record the scenario plan before building.

Use the real component and the project’s existing story, preview or scratch-page mechanism. Preserve its fonts, tokens, global styles and framework/server-client boundaries. A lookalike component or altered theme cannot prove the original works. The fixture may supply labels, container constraints, synthetic props and local event handlers, not restyle the subject to make it pass.

## Select reachable scenarios

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

Report broken scenarios first, then covered scenarios, exclusions and unverified checks. “Text escapes the right edge” is evidence; “spacing feels tight” is taste. This mode issues no ship verdict. If fixes were also requested, apply the owning guidance and re-render the failing cases plus their relevant baseline.

## Cleanup is part of completion

Remove disposable routes and fixture data; stop only preview processes and browser resources created for this run. Preserve unrelated user work and captures cited as evidence, placing those captures with the report outside production paths before cleanup. Keep an executable fixture only when the user explicitly requested a persistent deliverable, state its location/lifecycle and keep it outside production entry points. Report cleanup performed and any resource that could not be removed. A temporary stress page must not silently become shipped UI.

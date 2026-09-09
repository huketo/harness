# Selectable variants

Execute only for an explicit request to build or explore alternatives. An ordinary edit or review does not authorize a picker, extra designs or a replacement of the original. This mode delivers working alternatives and a decision surface, not prose-only suggestions presented as implementations.

## Define the comparison

State the requested UI piece, its job, where it renders and its constraints. Inspect the existing stack, tokens, components, density, voice and surrounding page. Preserve the original implementation and its production entry points until the user selects a replacement. When the request spans several pieces, cover the requested set or state the unresolved scope; do not silently replace it with one preferred component.

Pick one primary axis and name each candidate’s distinct position before coding:

| Axis | Owner | Meaningful difference |
| --- | --- | --- |
| Structure | [Layout](layout.md) | Grouping, order, columns or disclosure |
| Density | [Layout](layout.md) | Information visible at once and spacing, within usable target sizes |
| Emphasis | [Colors](colors.md) | Placement of visual weight, not arbitrary tint swaps |
| Type | [Typography](typography.md) | Hierarchy, scale, weight and measure |
| Voice | [Writing](writing.md) | Tone, explicitness and amount of useful copy |

Use the requested count; otherwise three is a useful default. Give semantic names such as “Compact summary” or “Guided detail.” Secondary choices should support the primary axis so the user can tell why the alternatives differ. Do not spend a candidate on cosmetic randomness or violate accessibility to make it more dramatic.

## Build real candidates in a safe preview

Use an existing local preview/story mechanism, or a disposable preview-only route. Render each candidate full-size with representative synthetic content, realistic item counts, real surrounding chrome, backgrounds and neighbors. Reuse project primitives, styles and tokens; no new styling system or unsolicited palette migration. With no project, use a self-contained local page and explicitly state the neutral fallback styling.

Keep candidate implementations and picker isolated from production routing. The preview may reuse safe production primitives, but production must not depend on the preview. Inspect imported effects and callbacks; interactions update local preview state only, without production writes. Preserve a selectable original baseline as well as the requested new candidates.

### Picker contract

- Use a URL search parameter such as `variant` as the active choice, preserving unrelated parameters and hash. Unknown values select the original baseline; browser back/forward restores selection.
- Render one candidate at a time without shrinking it into a thumbnail. Selection survives resize.
- Provide labeled native buttons or a native select, active-state semantics, visible focus and keyboard operation. If arrow or number shortcuts are added, scope them to the picker and never capture typing in inputs or editable content.
- Switch instantly. Keep picker chrome visibly separate from the product, using neutral styling rather than competing with the alternatives. Position it clear of the component and keep it usable at narrow widths and zoom.
- Keep the baseline and candidate labels stable so a URL identifies a reproducible choice. Add replay only for an entrance being compared.

## Verify and offer the choice

Apply the [review escalation floor](review.md#severity-and-ranking) to every candidate, using [accessibility](accessibility.md) and other relevant owners to establish defects. Repair or withdraw a failing candidate rather than counting it as selectable. Inspect each rendered candidate, its interactions, console/runtime errors, narrow and normal widths, relevant states and reduced motion where applicable. Report exactly which checks ran; inaccessible rendering is `Not verified`, not evidence a candidate is ready.

Present the local preview location, picker controls, judged widths and a concise comparison:

| Variant | Axis position | Useful when | Cost or tradeoff |
| --- | --- | --- | --- |
| Stable semantic name | Distinct design choice | Product/user situation | Space, density, emphasis or interaction cost |

Leave the decision to the user; do not silently promote a favorite. If asked for a recommendation, tie it to task frequency, content and product constraints rather than personal taste. Retain the unselected preview as the requested decision deliverable, state its lifecycle and preserve the original. Stop an owned preview process when it no longer needs to run; retained files still allow reopening.

## After explicit selection

Integrate only the selected direction in the project’s normal implementation, preserving its behavior and contracts. Remove unselected candidates and picker/scaffolding created for this comparison unless the user explicitly asks to retain them. Re-exercise the selected UI in its actual page and relevant states, including consumers of changed shared primitives. If another round is requested instead, retain the original and revise the comparison around the new direction without promotion.

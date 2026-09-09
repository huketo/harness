# Colors

Own palette generation, notation conversion, gamut, semantic color tokens, appearance variants and measurement of rendered contrast. [Accessibility](accessibility.md) owns which contrast requirements apply and non-color cues; [UI](ui.md) owns surface treatment and icon rendering. Use [review](review.md) for ranking and output.

## Preserve the contract before choosing values

1. Identify the requested operation: generate, convert, adjust, measure or review. A review is read-only; a contrast failure does not authorize repainting the interface.
2. Inspect the scoped token definitions and consumers, supported appearances, browser matrix, theme switch and existing color tooling. Include relevant SVG fills/strokes, charts and utility classes, not just CSS literals.
3. Preserve the project's notation, naming, brand constraints and switching mechanism. Hex, RGB and HSL are not defects. Bulk conversion, palette consolidation and a new token architecture are migrations: do them only when explicitly in scope.
4. Produce the requested values or findings with their roles, target gamut and measurement evidence. Recheck affected consumers after an authorized change; one passing button does not prove a shared token safe everywhere.

## Roles before ramps

For a new system, start with neutral, accent and only the status or categorical colors the product uses. Inventory required backgrounds, borders, text, fills and interaction states before choosing how many steps to generate. Do not create unused ramps or insist every product needs twelve steps.

Separate reusable values from roles when the project uses a semantic tier:

```css
:root {
  --neutral-200: #e5e7eb;
  --neutral-700: #374151;
  --color-border-default: var(--neutral-200);
  --color-text-secondary: var(--neutral-700);
}
```

Components consume the role rather than borrowing a same-valued token with another purpose. A separator is not secondary text merely because both are gray. Add a missing role at the existing seam; do not rename the whole system to match this example. Component-specific tokens earn their place only for intentional divergence.

Tailwind-style numeric ramps usually encode lightness; Radix-style scales encode intended roles with separate light/dark values. Preserve that distinction when mapping themes. A step number alone never guarantees contrast. Keep the project's vocabulary consistent; avoid introducing a second meaning of `primary` if it already names emphasis rather than brand.

## Generate a palette

1. Record seed colors and whether each is exact/pinned. Preserve a supplied brand color unless adjustment is authorized. If it cannot support the intended label, use it in a different role and derive a suitable fill or foreground instead of quietly altering the seed.
2. Map consumed roles to steps in each requested appearance. Start with backgrounds, then boundaries, fills and foregrounds; list the pairs those roles will create.
3. Use an available, maintained color library such as Culori, Color.js or chroma.js, after checking its installed version and APIs. Compute in a perceptual space and emit the existing notation. Do not invent hand-derived conversion formulas or claim values calculated by eye. If no computation tool is available, supply a generation method and label numeric output unverified rather than fabricating it.
4. Choose monotonic perceptual lightness and a deliberate hue trajectory. A steady hue is a useful default for a single-hue ramp; preserve an intentional brand trajectory. Allow role-driven spacing, with finer distinctions among pale surfaces and sufficient separation among dark surfaces, rather than requiring uniform numeric intervals.
5. Tune chroma per lightness and hue. Middle steps can carry more color; extremes often need less chroma to remain in gamut. Equal HSL saturation or equal OKLCH chroma across different hues does not imply equal perceived vividness. Inspect related status/accent roles together.
6. Gamut-map and serialize, then reparse the emitted values and check role pairs. Rounding and mapping can merge neighboring steps or change contrast. Deliver role-to-value mappings, pinned seeds, mapping decisions and measured results, not just an attractive swatch strip.

OKLCH is a useful authoring option for a genuinely new system: `L` controls perceptual lightness, `C` chroma, `H` hue angle and slash syntax alpha. It is not a requirement to migrate existing CSS. Interpolation is a starting point, not proof that all generated steps serve their roles.

Pure neutral grays and tinted neutrals are both valid. Preserve the established choice. A brand and status hue may overlap intentionally; assess whether users can distinguish the actual actions and statuses, not whether hue angles exceed a fixed cutoff. Cultural conventions matter for load-bearing categories such as financial gain/loss.

## Convert without redesigning

For an explicit conversion, name source and destination formats, target gamut, precision and alpha handling. Parse with a color-aware tool; preserve keywords (`currentColor`, `inherit`, `transparent`), variable references, comments and configuration values that require a particular format. Convert gradient stops without changing interpolation, stop positions or geometry. Handle embedded SVG and other scoped consumers through their existing syntax rather than indiscriminate textual replacement.

Distinguish exact representation conversion from lossy gamut mapping. Preserve enough precision that reparsing does not introduce a meaningful unintended difference; state any rounding or mapping. Report the actual computed output and tool/version. If asked for a migration, identify all affected consumers and defaults explicitly; do not leave a second notation scattered through unrelated components as incidental cleanup.

## Gamut and browser support

sRGB is a useful baseline when no wider display target is specified. Display P3 contains colors outside sRGB; an OKLCH value can be outside either gamut. CSS syntax support and display gamut are separate questions.

Use the library's documented gamut check and mapping operation. Reducing chroma at fixed lightness/hue is a useful strategy, not a universal formula or guarantee. Record the target and method. Do not simply clamp RGB channels and call the result perceptually unchanged. Inspect adjacent mapped steps for collapsed distinctions.

Where P3 enhancement is wanted, provide a verified sRGB base in the project's notation, then a wider-gamut override under its established `color-gamut: p3` mechanism. Add syntax feature detection only if the browser matrix needs it. A gamut media query does not itself convert or validate a color; lack of a fallback is a concrete compatibility risk, not automatic proof that every modern browser renders nothing.

Preserve gradient interpolation unless the requested design change includes it. OKLab interpolation can give smoother perceptual progression; OKLCH follows a hue path that may introduce unwanted intermediate hues. Select the path deliberately and inspect midpoints, banding and gamut, not only endpoints. A conversion task must not silently change that look.

## Appearances and states

Map semantic roles through the existing theme controller, whether class, attribute, media preference or another mechanism. Do not add a parallel theme source. For `light-dark()`, verify that `color-scheme` follows the effective theme, including a manual override.

Dark appearance is not a mechanical reversal: tune surface separation, foregrounds and chroma against actual backgrounds. Check every shipped appearance and relevant hover, active, selected, focus, disabled, error and loading state. Preserve an established hierarchy that communicates primary action without requiring one filled button per entire screen.

For increased-contrast variants, measure the resulting role pairs rather than adding an arbitrary lightness delta. Resolve `color-mix()`, relative colors and alpha with the active inputs; a statically resolvable expression can be calculated, but a calculation does not prove it is the color rendered in that state.

## Measure rendered WCAG contrast

Use this procedure for a contrast question or after an authorized color edit:

1. Identify the foreground and the surface actually behind it. Follow transparent ancestors, pseudo-elements, overlays and opacity groups; the nearest declared background is not necessarily the final one.
2. Capture the effective theme, state, viewport and computed styles in the running interface. Resolve foreground alpha against the final background and all relevant background layers in their rendering context. For images, gradients or backdrop-filter surfaces, inspect the worst region behind content across relevant positions; an average color or one favorable pixel is insufficient.
3. Measure with a trusted tool implementing the applicable WCAG 2.x relative-luminance contrast ratio. Confirm it handles the resolved color space or explicitly document any conversion to sRGB. Do not treat OKLCH lightness difference, HSL lightness, screenshot antialiasing pixels or APCA Lc as that ratio.
4. Obtain the applicable criterion, content classification and threshold from [accessibility](accessibility.md). Record text size/weight when needed for classification. Label the result with the WCAG version/criterion and target level rather than making a whole-page conformance claim from a pair.
5. Report foreground, final background, measured ratio, required threshold, tool/method and the exact state/location. Compare before rounding for display. A declared-token calculation is useful evidence, but label it as such when the rendered surface was not inspected.
6. If editing is authorized, move foreground or background lightness apart while preserving its role and brand constraints where possible. Adjust chroma if mapping requires it. Remeasure the final serialized values and all affected pairings; do not assume the candidate fix passed.

WCAG 2.x ratios are symmetric for the same two opaque resolved colors. Light and dark themes still need independent checks because their tokens, alpha and backgrounds usually differ. Do not import a polarity-aware algorithm's behavior into a WCAG explanation.

APCA may be additional design guidance when explicitly requested or already used by the project. Name its implementation/version, polarity and font assumptions, and consult its documented interpretation rather than inventing universal Lc floors. Report it separately. APCA is not a substitute for a WCAG 2.x result, and neither a single contrast measurement nor this reference establishes legal compliance.

## Completion evidence

For generation, return values mapped to consumed roles plus gamut and pair checks. For conversion, return computed values and any lossy changes. For review, report concrete role misuse, rendered ambiguity, gamut/support failures or measured contrast failures with the smallest proposed correction. Keep palette consolidation a proposal unless requested.

State which appearances, backgrounds and states were exercised. If the browser, display gamut, content image or computation tool was unavailable, mark that boundary not verified. Never invent a contrast number, call source inspection visual verification or infer whole-system compliance from a sample.

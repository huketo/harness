# UI surfaces, icons and motion

Own surface depth and corners, optical alignment, icon rendering and motion behavior. [Typography](typography.md) owns fonts, text spacing, wrapping and truncation; [layout](layout.md) owns grouping, breakpoints and spatial RTL; [colors](colors.md) owns color tokens and contrast measurement. [Accessibility](accessibility.md) owns hit targets, focus, keyboard interaction, names and reduced-motion requirements. Ranking and report structure belong to [review](review.md).

## Start with the interaction

1. Identify the requested components and states, existing library, styling system, density, surface tokens, icon set and motion mechanism. Read shared components before adding local rules.
2. For generation or authorized implementation, reuse those mechanisms and correct the smallest owning component. A polish review remains read-only. Different radii, timing curves or icon variants are not defects without an observed inconsistency or user impact.
3. Inspect the actual surface at normal speed. For motion, also replay slowly to locate snapping, overlap or delayed state feedback; return to normal speed to judge whether it disrupts use.
4. Exercise entry, exit and interruption, not just the attractive settled state. Record what was rendered and what was only inferred from source.

## Surface structure and depth

For closely nested rounded surfaces with a uniform visible inset, use concentric geometry as a starting point: outer radius equals inner radius plus the inset. For example, an `8px` inset and `12px` inner radius suggest `20px` outside. Include borders in the actual edge-to-edge inset. Keep independent surfaces, widely separated layers, pills and deliberately asymmetric padding on their existing tokens rather than forcing the equation globally.

Distinguish a structural edge from elevation before replacing it. Dividers, table boundaries, input boundaries, selected outlines and focus indicators have jobs that a faint shadow may not preserve. For a surface that genuinely needs elevation, reuse the existing shadow token; layered transparent shadows can combine a close edge with a softer ambient shadow. Dark surfaces may need a visible edge or tonal separation rather than a larger black shadow. Verify against actual backgrounds; transparency does not guarantee suitable contrast.

Where an image edge disappears into its surrounding surface, consider a subtle inset outline without changing its layout dimensions. `outline-offset: -1px` can pull a `1px` outline inside the image. Reuse the project's neutral treatment and notation; black/white at low alpha is one option, not an instruction to add outlines to every image. Check rounded corners, clipping and whether an interactive image already uses the outline for focus.

## Optical alignment

First inspect the SVG viewBox, intrinsic whitespace, flex/grid alignment and text metrics. Correct a malformed local asset or shared icon wrapper before accumulating per-use offsets. When geometric centering still looks unbalanced, make a small optical adjustment and compare at the real size.

A trailing icon may need slightly less padding on its side; about `2px` is a starting experiment, not a universal rule. A play triangle may need a physical rightward nudge because of its mass, independent of text direction. Preserve surrounding layout conventions and let [layout](layout.md) own logical spacing. Confirm the adjustment at each shipped icon size and with longer labels.

## Icon rendering and state

- Use the existing icon set and its native grids. Compare optical weight beside the label rather than mixing libraries for a single attractive glyph. On a 24px outline grid, strokes near `1.5px` beside regular text and `2px` beside semibold are useful comparison points only when the set supports adjustment.
- Render icons at their smallest actual size. Simplify a detailed glyph rather than shrinking it until internal gaps vanish. Inspect fractional scaling and high-density rendering instead of assuming SVG alone guarantees sharpness.
- For monochrome icons, use `currentColor` and the existing semantic color tokens so state changes need no duplicated recolored assets. Preserve intentional multicolor illustrations and logos rather than stripping their fills indiscriminately.
- Where the set and component convention support it, outline/fill variants can distinguish inactive/active state. Keep an established alternative indicator; do not turn every filled default icon into a finding.
- Mirror only glyphs whose meaning follows reading direction, such as navigation arrows. Preserve physical objects, brand marks and conventional media controls. Inspect composite glyphs part by part; an overlay may not mirror with its base. Spatial layout mirroring remains in the layout domain.

Use the accessibility reference for icon-only control names, decorative glyph exposure and persistent non-motion state cues. A correct-looking icon does not prove an operable control.

## Interruptible state changes

Prefer CSS transitions for ordinary hover, toggle and open/close interpolation: they retarget toward the current state when the user changes intent. Use keyframes or the existing motion library for sequences whose timeline matters. These are implementation choices, not claims that every keyframe or library animation is inherently uninterruptible; test the actual state machine.

Name the properties that should transition, such as `opacity` and `transform`, instead of `all`. This prevents an unrelated width, padding or theme change from unexpectedly animating. Check generated utility CSS rather than assuming a framework version's utility expands identically everywhere.

Keep high-frequency actions immediate or brief; a small color/opacity transition around `100`–`150ms` is often enough. A press scale near `0.96` can provide tactile feedback when it matches the product, but static feedback is valid. Preserve the component's existing opt-out mechanism and disabled behavior rather than adding a new prop solely to satisfy a recipe.

## Entrances, exits and icon swaps

For an infrequent entrance where order conveys hierarchy, group semantic chunks rather than animating every character. A stagger around `100ms` between a few chunks is a starting point; check total delay to the last action. Leave frequent tab changes, row hovers and typing unstaggered. Content and controls should not become unusable while waiting for decorative motion.

Keep context-preserving exits quieter than entrances: a small fixed displacement, such as `12px`, and a short fade can be enough. Full travel is appropriate when it communicates a drawer closing or a card returning to a source. Immediate removal is valid when motion adds no information. Integrate exit lifecycle with the existing component mechanism so the node is not removed before its intended exit or left as an invisible interaction blocker afterward.

For a contextual icon swap, first decide whether a direct swap is already clear. If cross-fading improves continuity, keep a stable wrapper and overlap the two glyphs so the button does not resize. With plain CSS, keep one glyph in flow and position the other over it; transition opacity on both. Scope pointer handling and accessibility exposure through the control's established semantics. Opacity alone does not remove an element from focus or hit testing.

Use an already-installed motion package only through its established imports (`motion/react` for Motion, or `framer-motion` where that is the project dependency). An opacity cross-fade does not justify a new dependency. A no-bounce spring around `0.3s`, or a CSS easing such as `cubic-bezier(0.2, 0, 0, 1)`, is an optional starting treatment. Scale and blur are additional effects to justify and measure, not required ingredients.

If stateful icons should not animate on initial render, use the existing presence mechanism's initial-animation control, such as `initial={false}` on `AnimatePresence`. Verify a full refresh and subsequent toggles; do not disable intentional first-entry animation in a parent hierarchy by accident.

## Theme transitions

A theme change can trigger many color, border and shadow transitions at once. If the observed result is an unwanted page-wide smear, use the theme library's existing transition-suppression option first. Do not add a separate theme listener that competes with the effective theme controller.

For a custom controller, suppression must surround the actual theme mutation: apply a temporary transition override, change the theme, flush styles while suppression is active, then remove it after the new theme has painted. Handle repeated toggles and cleanup so a stale callback cannot restore transitions too early or leave them disabled. Include pseudo-elements and relevant scoped roots. Reuse the existing implementation instead of introducing forced reflows without evidence of this defect. Verify both manual override and system changes if the product supports them.

## Motion cost and preferences

Transforms and opacity are often compositor-friendly; filters, especially large blurs, can still be expensive depending on the browser and surface. Profile the changed interaction before claiming improved frame rate. Prefer removing an unnecessary effect over masking its cost with a hint.

Use `will-change` only after observing and diagnosing first-frame stutter. Apply it to the specific moving element and property for the needed lifetime, then release it. Extra layers consume memory; blanket hints or `will-change: all` are not a performance strategy. Check layout/paint work and dropped frames on the target browser rather than guaranteeing GPU acceleration from a property name.

When implementing motion, apply the reduced-motion and persistent-feedback contract from [accessibility](accessibility.md). The final state must remain understandable when the decorative transition does not run. Do not make initial `opacity: 0` depend on an animation that is disabled under that preference.

## Execution checks

For each changed or reviewed component, walk applicable default, hover, focus, press, selected, disabled, loading, success/error and empty states. Check normal and reduced-motion modes through the accessibility procedure, and the relevant light/dark surfaces through colors. Exercise these motion-specific cases:

- Press then release before the transition finishes; toggle again during entry and exit.
- Open, close and reopen rapidly; navigate away during an exit; verify no invisible layer remains over the next interaction.
- Refresh with an already-selected state; verify initial-animation suppression and intentional page entrance independently.
- Compare stable button bounds during icon swaps and loading transitions; inspect the smallest icon size.
- Replay animation slowly where tooling permits, then at normal speed. If performance is the finding, capture the actual trace or timing evidence.

Record the exact component, state, interaction and observed result. Source can show durations, property lists and lifecycle handlers, but not prove optical balance, interruption quality or frame rate. Mark unavailable browser/device and unexercised cases not verified. Propose changes for concrete lost context, unclear state, clipping, jitter or inconsistency; leave taste-only alternatives out of actionable findings.

# Typography

Own font selection and rendering, type hierarchy, line spacing, wrapping, truncation and mixed-direction text. Use [writing](writing.md) for the words, [accessibility](accessibility.md) for semantics and text-resize requirements, [layout](layout.md) for spatial arrangement, and [colors](colors.md) for contrast measurement. Review ranking and output belong to [review](review.md).

## Work from the active type system

1. Identify the requested surface, existing font stack, loaded faces, type tokens and styling mechanism. Read the component and its shared text styles before proposing a local override.
2. Assign each text block a role: display, heading, body, label, caption, code or numeric data. Compare like roles and the hierarchy within each section, not unrelated screens.
3. For generation, use existing role styles. For an authorized edit, correct the smallest owning style or component. A review proposes changes without applying them.
4. Verify with realistic text and the actual fonts. Source inspection can identify declarations, not prove wrapping or readability.

## Fonts and supported features

Preserve the chosen family unless a typeface change is requested. A polish pass does not justify a paid font, an additional font dependency or a replacement brand identity. When choosing a family, check licensing, required scripts, small-size legibility, distinguishable characters and fallback coverage before stylistic pairing. A system stack is a practical option for a new interface; a display face is not automatically suitable for dense labels.

Prefer WOFF2 for web delivery when the project controls the font files. Reuse its loading mechanism. Compare the actual files needed: a variable font is not necessarily smaller than one or two static faces. Declare the supported weight range and load the styles the design uses; inspect the rendered font rather than assuming a successful download means every glyph uses it.

Use high-level CSS properties where available:

| Need | CSS | Check |
| --- | --- | --- |
| Intermediate variable weight | `font-weight: 650` | The loaded face supports the weight; fallback emphasis remains distinct |
| Optical size | `font-optical-sizing: auto` | The font actually has an optical-size axis |
| Stable numeric columns | `font-variant-numeric: tabular-nums` | The active face supplies tabular figures |
| Distinguish zero from O | `font-variant-numeric: slashed-zero` | Appropriate for identifiers, supported by the face |
| Custom axis or stylistic set | `font-variation-settings` or `font-feature-settings` | Read that font's axis ranges or feature documentation first |

Reserve raw four-letter tags for features without a suitable property. A tag such as `ss01` has a font-specific meaning. Keep synthetic emphasis unless the real faces and fallback stack supply every required form; blanket `font-synthesis: none` can erase bold or italic distinctions.

## Hierarchy, measure and spacing

Reuse a small role-based scale that pairs size, weight and line-height. Make subordinate headings visually subordinate within their section, allowing deep levels to share a size when weight or spacing distinguishes them. Choose the semantic element through the accessibility guidance, not for its browser-default size.

For a new scale, body text near `1rem` with unitless `1.5`–`1.6` line-height is a starting point. Short headings can use tighter leading around `1.1`–`1.3`; multiline descriptions need more breathing room, often `1.4` or above. These are tuning inputs, not compliance thresholds. Check ascenders, descenders, diacritics and scripts with taller glyphs before tightening.

Cap long-form Latin text near 60–75 characters per line, then inspect actual lines. `max-inline-size: 65ch` is a useful starting point, not a character counter: `ch` is the width of the font's zero glyph. Dense data, CJK text and short labels need role-specific treatment. Keep container grouping and responsive layout decisions in the layout domain.

Use slight negative tracking on large headings or positive tracking on short uppercase Latin labels only when it improves the actual face. Preserve normal body spacing and language-sensitive shaping. Thin weights that look elegant at display size can disappear in small UI text; verify at the smallest shipped size rather than applying a universal weight floor.

## Wrapping and recovery

| Situation | Smallest useful treatment | Boundary |
| --- | --- | --- |
| Uneven short heading | `text-wrap: balance` | Browser algorithms and line-count limits vary; inspect supported browsers |
| Short description with a stranded final word | `text-wrap: pretty` | Progressive enhancement, not guaranteed word placement |
| URL or long unbroken identifier escapes its box | `overflow-wrap: anywhere` or the project's `break-word` treatment | `anywhere` also affects intrinsic sizing; preserve deliberate code formatting |
| Short badge must remain one line | `white-space: nowrap` | Only when long translations still fit or have an explicit recovery path |
| One-line summary intentionally clipped | Ellipsis recipe below | Full meaningful content remains reachable |
| Multiline preview | Existing line-clamp utility or supported CSS recipe | Verify the fallback and provide expansion when content matters |

Keep ordinary wrapping for long prose and preformatted code unless the task needs another policy. Avoid manual line breaks to repair one viewport; reserve them for authored content where the break is intentional.

```css
.single-line-summary {
  min-inline-size: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
```

The ellipsis needs a constrained available width. In flex or grid content, inspect the shrinking item and its ancestors before adding more clipping. For several lines, reuse the project's clamp implementation; legacy WebKit clamping also needs its companion display and orientation declarations.

Truncation is acceptable only for the intended summary, not as a way to hide an overflow defect. Essential names, errors and values need a full-value view, expansion or another accessible recovery mechanism. A hover-only tooltip or `title` attribute is not a sufficient touch/keyboard recovery plan; its interaction contract belongs to accessibility.

## Numerals, punctuation and language

Apply tabular figures to aligned numeric columns, timers and changing counters, not every number in prose. Equal digit widths do not prevent shifts when the number of digits, sign, decimal separator or currency changes; reserve enough inline space when that movement is disruptive. Inspect transitions such as `99` to `100`, negative values and localized formats.

Store natural case and use presentation CSS where appropriate. Keep exact code, identifiers and user-entered values intact. Use language-appropriate quotation marks and range punctuation in authored prose; a nonbreaking space can hold a number and unit together, and a soft hyphen can mark an allowed word break. Neither should create overflow at narrow widths.

Use correct `lang` and `dir` boundaries for shaping, hyphenation and bidirectional text. Isolate embedded mixed-direction values with `<bdi>` or the established equivalent; let the Unicode bidi algorithm preserve number order. Never manually reverse strings. Spatial mirroring belongs to layout.

## Rendering details

- Prefer font underline metrics (`text-underline-position: from-font`, `text-decoration-thickness: from-font`) when they work for the face; tune offset and `text-decoration-skip-ink` if descenders collide. Link identification requirements belong to accessibility.
- Keep useful text selectable. Restrict `user-select: none` to an observed conflict with dragging or gestures rather than applying it to application chrome.
- Small input text can trigger focus zoom in iOS Safari. Prefer a genuinely readable mobile input size, commonly at least `16px`, and verify on that browser. Do not disable user zoom or shrink a nominal 16px field with a transform to evade the behavior.
- Font smoothing controls are platform-specific aesthetic options, not universal quality fixes. Preserve the project choice; if changing it is in scope, compare the target platform and light/dark rendering. A Linux screenshot does not prove a macOS improvement.
- Treat `text-box` trimming and decorative text effects as progressive enhancements. Verify browser support, diacritics and fallback leading before relying on them for alignment.

## Execution checks

For the requested scope, inspect narrow and wide widths, loaded and fallback fonts, long translations, unbroken identifiers, mixed-direction values and the longest realistic heading or error. Exercise truncation recovery by keyboard and touch where available. Check changing numerals and multiline text inside fixed-height controls. Use the accessibility reference's zoom and spacing scenarios when those requirements are in scope.

Report the component, state, viewport, actual font and observed failure; distinguish declarations inspected from rendered results. A missing optional `pretty` rule or a different scale is not itself a finding. Name the unreadable, clipped, unstable or misleading text and the smallest correction. Mark unsupported platforms and unexercised content cases as not verified.

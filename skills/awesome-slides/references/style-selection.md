# Select a complete theme, then adapt its content

The visual source of truth is the [34-theme catalog](../assets/template-library/index.json), not the three native-engine palette presets. The bundled library contains the actual `template.html`, `design.md`, metadata, and sibling assets of each theme. [Origin](../assets/template-library/ORIGIN.json) pins the upstream snapshot; [LICENSE](../assets/template-library/LICENSE) retains its MIT terms.

## Shortlist from actual designs

Resolve occasion, desired tone, audience, density, and existing brand from the brief. Ask only for unresolved taste decisions through the environment's human-question policy; do not re-ask facts or require a style picker after a user already chose a theme. Match `mood`, `tone`, and `best_for` first, then density and formality. Occasion is a clue, not an industry restriction.

Inspect the full catalog metadata before narrowing. Examples of genuinely different visual systems include:

| Theme slug | Concrete identity |
| --- | --- |
| `soft-editorial` | Warm-paper editorial spreads, Cormorant display serif, sage/blush/lemon regions, ruled matrices and margin details |
| `blue-professional` | Cream/cobalt system, Space Grotesk and Inter, asymmetric cover, numbered process and comparison layouts |
| `broadside` | Dark newspaper-like canvas, fire-orange emphasis, bilingual editorial hierarchy |
| `neo-grid-bold` | Off-white/neon-yellow neo-brutalist grid, heavy display type and strong graphic divisions |
| `pin-and-paper` | Yellow paper, safety-pin illustrations, ink-blue handwriting and paper texture |
| `cobalt-grid` | Cobalt serif, graph-paper canvas and pixel-step decorative geometry |

These are examples, not a six-theme allowlist. Use the complete catalog. Keep upstream slugs: the library's `signal` theme is not the local native-engine `signal.css` palette.

For each shortlisted theme, read `assets/template-library/templates/<slug>/template.html` and `design.md`. Inspect multiple actual slide previews in the [pinned upstream gallery](https://github.com/zarazhangrui/beautiful-html-templates/tree/e5e204fb1f3b06290846e7dcd7aceddabeceec8c). The gallery has cover, middle, and later slides; do not judge a theme by its cover alone. Screenshots are selection evidence, not substitutes for editable source.

## Show real alternatives when needed

When direction is unresolved, clone three meaningfully different templates. Put the same real title/subtitle and a demanding evidence slide into each: six rendered slides total. Preserve claims, numerical values, qualifications, and notes across alternatives. Keep option labels outside the slides. The layouts, type hierarchy, motifs, and evidence arrangements should differ—not only accent colors.

Open each preview in the actual browser, inspect fonts and content, and show the user the files or screenshots through the authorized channel. Honor the requested sample gate before expanding. If a theme or brand is settled, render only that direction's cover and demanding slide before expanding. Unattended runs follow their authority policy rather than inventing approvals.

## Preserve what makes the theme recognizable

Clone the whole folder with `new-deck.mjs html <new-directory> --template <slug>`. Preserve its grids, slide-level classes, font roles, spacing rhythm, illustrations, decorative geometry, and navigation mechanism. Do not strip motifs as “noise,” replace the display face with a generic sans, or turn every layout into the same two-column card slide.

Replace demonstration headlines, text, numbers, names, dates, citations, image placeholders, and authored chrome labels. Demo measurements are not user evidence. Reuse the theme's existing cover, comparison, data, process, quotation, and closing layouts where appropriate; duplicate and reorder by the argument rather than retaining the demo narrative. New layouts inherit that theme's typography, palette, motifs, and geometry. They should visibly belong between two unchanged layouts.

User brand requirements outrank stock colors. Adapt the selected theme deliberately and together—not by arbitrarily changing one color or confusing a palette swap with a new design.

## Typography and language

Keep the original Latin display/body faces. For Korean, add a matching licensed CJK face to the relevant role: serif for serif display, sans for sans substance, appropriate weight and character width. An unsupported Korean glyph falling back to an unrelated system font is not a faithful implementation. Inspect the actual resolved face, not only CSS family names. If required fonts are absent, acquire licensed project-local files and retain their license; do not install host fonts or depend on online loading for offline delivery.

Korean headings break at meaningful phrases, with normal tracking and language-appropriate leading. Adjust the affected text region or split content before shrinking the entire page. Preserve the theme's proportions and emphasis. Code stays exact and preformatted; inspect identifiers and units at actual presentation size.

## Native engines and delivery

Slidev and Reveal remain available when their features or editable source are required. Their bundled starters supply working engine mechanisms and technical components; they are not automatic ports of these 34 themes. Inspect the selected HTML layouts side by side while implementing native layouts/sections. Carry the original typography, grid, motifs, and component grammar across instead of returning to a generic engine theme.

[HTML](html.md) owns local assets, single-file delivery, reading mode, navigation, and export. [Visual design](visual-design.md) owns truthful evidence and accessibility; [Verification](verification.md) owns whole-deck checks. A fixed stage scaled to a phone is not a reading handout, and preserving a template does not excuse inaccessible controls or missing content. Fix the affected mechanism without discarding its visual system.

# Dual-theme contract (opt-in)

One HTML file that renders in light and dark, instead of two files (`template.html` + `template-dark.html`). Use it when the destination switches themes (a docs site, a README `<picture>` pair, a wiki), when the user wants both PNGs from one source, or for logo mode, whose template already uses it. The two-file variants remain the default for everything else.

Start from [`assets/template-dual.html`](../assets/template-dual.html).

Adapted from caru-ini/stack-diagram (MIT, see `LICENSE.stack-diagram`), with markers colored by CSS variables instead of `context-stroke`.

## How it works

- The diagram `<svg>` carries `class="dd"`. Its first children stay `<title>` and `<desc>`; a `<style>` element follows them, before `<defs>`.
- The `<style>` defines the semantic tokens of [style-guide.md](style-guide.md) as custom properties on `svg.dd` (light column), and again for dark (dark column) under three selectors: `prefers-color-scheme: dark` (unless pinned light), `:root[data-theme="dark"]`, and `svg.dd[data-theme="dark"]`.
- Every color comes from a class that reads a token (`.e`, `.name`, `.zone`, `.mask`, `.mk`, …). A hex value in a `fill` or `stroke` attribute does not follow the theme. Exceptions: colors that must not switch (logos, the white tile, the monochrome glyph on that tile, AWS group outlines).
- Arrowhead markers color their polygon with a class (`.mk`, `.mk-accent`, `.mk-link`). Marker content inherits custom properties from the `<svg>`, so all three markers follow the theme. Prefix marker IDs with the diagram slug (`<slug>-arrow`) so two inline diagrams never share one.
- Theme-specific assets come in pairs: `class="lt"` shows in light, `class="dk"` in dark.
- Zone fills are opaque precomputed colors (`--zone`), so a label mask inside a zone uses `.mask.z` and matches its backdrop exactly (SKILL.md §6, "a mask is not a node").

## Choosing the theme

- No `data-theme` anywhere: follows the reader's `prefers-color-scheme`.
- `<html data-theme="light|dark">`: pins the page and the diagram.
- `<svg class="dd" data-theme="light|dark">`: pins just the diagram, which is what an exported SVG carries.

Precedence: the diagram's own `data-theme` beats the page's, which beats the reader's preference. `render_check.py` renders a pinned diagram as authored; `--theme both` overrides the pin to check both themes anyway.

## Export

- **PNG:** `scripts/render_check.py --out <dir>` renders `<file>-light.png` and `<file>-dark.png` in one pass. A requested export still follows [export.md](export.md).
- **SVG:** the exported `<svg>` keeps its `<style>`, so in a browser it still switches with `prefers-color-scheme`; add `data-theme` on the `<svg>` to export one fixed theme. Strict SVG 1.1 importers (PowerPoint, some Illustrator and Figma paths) do not resolve CSS custom properties, so a dual-theme SVG is browser-only: for those destinations deliver the PNG, or redraw from the two-file variants whose colors are presentation attributes.

## Checklist

- [ ] `<svg class="dd">` with `<title>`, `<desc>`, then `<style>`, then `<defs>`?
- [ ] No hex color in a `fill`/`stroke` attribute except the fixed exceptions above?
- [ ] Marker IDs prefixed with the slug and colored by class?
- [ ] Both theme PNGs from `render_check.py` looked at?

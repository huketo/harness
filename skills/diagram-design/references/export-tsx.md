# Export to a React (TSX) component

Load this when the user asks for the diagram as a React component, a `.tsx` file, or "something I can drop into our Next.js/Vite app". Like the other exports it is manual: never emit TSX unprompted.

The HTML stays the source of truth. Build and check the HTML first (SKILL.md §9), then convert it; geometry and content are identical, only the packaging changes.

Adapted from caru-ini/stack-diagram `references/tsx.md` (MIT, see `LICENSE.stack-diagram`).

## Shape

```tsx
// ArchitectureDiagram.tsx: no props, no dependencies beyond React.
// Fonts: load "Geist", "Geist Mono" (and "Noto Sans KR" for Hangul) in the host app to
// match the reference look; the fallbacks in the font stacks render without them.
const LOGOS = {
  hono: "data:image/svg+xml;base64,...",
} as const;

export default function ArchitectureDiagram() {
  return (
    <svg className="dd" viewBox="0 0 1000 520" xmlns="http://www.w3.org/2000/svg"
         role="img" aria-labelledby="stack-logos-title stack-logos-desc"
         style={{ width: "100%", height: "auto", display: "block" }}>
      <title id="stack-logos-title">Web app on Vercel</title>
      <desc id="stack-logos-desc">…</desc>
      <style>{`svg.dd { --paper: #f5f5f5; … }`}</style>
      <defs>…</defs>
      {/* zones, connectors, labels, nodes: same coordinates as the HTML */}
    </svg>
  );
}
```

## Rules

- **Export the `<svg>` only.** The page header, cards, and footer are dropped, as in every export. Keep `role="img"`, `aria-labelledby`, and the first-child `<title>` / `<desc>`.
- **Self-contained.** Logos as data URIs in one `const`, styles in the SVG's own `<style>` element as a template literal (`<style>{`…`}</style>`), no CSS files, no Tailwind assumptions, no imports beyond React. It must compile in any TSX project as-is.
- **JSX attribute names.** `class` → `className`; hyphenated presentation attributes become camelCase (`stroke-width` → `strokeWidth`, `stroke-dasharray` → `strokeDasharray`, `marker-end` → `markerEnd`, `text-anchor` → `textAnchor`, `font-family` → `fontFamily`, `letter-spacing` → `letterSpacing`, `paint-order` → `paintOrder`); `xlink:href` → `href`; a `style="a: b"` string becomes an object (`style={{ stroke: "var(--muted)" }}`). `aria-*` and `data-*` stay hyphenated.
- **Unique IDs.** Keep the slug-prefixed `<title>`, `<desc>`, and marker IDs. If the component may render twice on one page, take an `idPrefix` prop and build every ID from it.
- **Do not embed fonts.** A component lives inside an app with its own font pipeline. Keep the font stacks and say in a leading comment which families restore the reference look.
- **Repeated nodes may become a local component** (`<IconNode cx={504} top={120} logo="hono" name="Hono" sub="api" />`) when that makes later edits easier; keep the coordinates explicit.
- **Theme.** A dual-theme diagram ([theme-dual.md](theme-dual.md)) keeps its `<style>` and follows the host's `prefers-color-scheme` or a `data-theme` attribute on `<html>`. A single-theme diagram is converted as authored.
- **Motion.** Drop the motion controller; deliver the static frame. Motion in React is a separate request.
- Deliver into the user's workspace as `<Name>Diagram.tsx`. It is code for their repository, not a page to publish.

## Verify

1. Type-check or build the file in the user's project (`tsc --noEmit`, the project's build), or at minimum transpile it (`bun build <file> --outdir <tmp>`).
2. Render it with React (`react-dom/server` `renderToStaticMarkup`) into an HTML page and run `scripts/render_check.py` on that page. Compare the PNG with the source HTML's PNG; they should match.

# Logos (primitive, opt-in)

Official brand logos on white tiles, for architecture, deployment, high-level, and DP-integration diagrams whose nodes are named products ("Next.js on Vercel, Postgres on Neon, auth with Clerk"). Readers recognise a real logo faster than a name, and they notice a wrong or redrawn one immediately.

The monochrome set in [primitive-icons.md](primitive-icons.md) stays the default. Use logo mode only when the user names concrete products, asks for logos, or the diagram is a stack overview. Concepts with no brand (user, browser, cron, queue, cache, webhook) keep the monochrome glyphs, inside a tile, even in logo mode. AWS workloads add [vendor-aws.md](vendor-aws.md).

Adapted from caru-ini/stack-diagram (MIT, see `LICENSE.stack-diagram`).

## Workflow

1. **Fetch.** From the skill directory, into a working directory outside any repository:

   ```bash
   python3 scripts/logos.py fetch <logodir> hono nextjs "betterauth:better-auth" "orpc=https://orpc.unnoq.com/logo.webp"
   ```

   Spec forms: `name` (slug = name), `name:slug`, `name=URL` (the official file), `name:aws/<Service>` (AWS's package). Sources, in order: svgl → devicon → gilbarbara/logos. The script writes `<name>.<ext>`, `<name>_dark.<ext>` when the source has a dark-theme variant, and `manifest.json`.
2. **Draft.** Start from [`assets/template-logos.html`](../assets/template-logos.html) (icon nodes on the dual-theme contract). Reference each logo as `href="%%LOGO_<name>%%"` on an SVG `<image>`, and put `%%LOGO_CREDITS%%` in the footer.
3. **Inline.** `python3 scripts/logos.py inline <draft.html> <logodir> <out.html>` embeds every logo as a `data:image/…` URI and fills the credit line. It fails on an unresolved token or an unsafe file.
4. **Check.** Run `scripts/self_check.py` and `scripts/render_check.py` on the output, then look at both theme PNGs (SKILL.md §9).

Requires network access to the logo sources while fetching; nothing is fetched when the diagram is viewed. Offline, fall back to the monochrome set and say so.

## Rules that matter more than the mechanics

- **Never recolor a logo.** Not its fill, not via CSS filters. If a mark is white or too light for a white tile, put it on a dark tile (`.tile.dark`). The manifest's `white_fill` flag is a heuristic: a white inner detail on a colored mark trips it too, so look at the file before switching tiles.
- **Official marks only.** simple-icons is deliberately not a source: its glyphs are monochrome redraws. When every source fails, find the official file in the project's repository (root `logo*.svg`, `docs/`, `assets/`, `public/`) or site (`/logo.svg`, `/favicon.svg`) and pass it as `name=URL`.
- **Embed only through `<image>`.** Never paste a fetched SVG inline. An `<image>` cannot run script or load anything; `logos.py` additionally rejects any SVG carrying script, `foreignObject`, event handlers, external `href`, remote CSS, or entity declarations, and any raster that is not PNG, WebP, or JPEG.
- **Vendor sub-products** (Cloudflare D1/R2/KV) usually have no distinct logo: reuse the vendor logo and let the node name carry the distinction.
- **Square marks only at small sizes.** Group-label icons render at 16px (32px in AWS mode). Wordmarks and wide lockups turn to mud there; fetch the brand's square icon for the label.
- **Light/dark pairs.** Tiles stay white in both themes, so the light variant goes on the tile. On a group label, which sits on the theme's paper, use the `lt`/`dk` pair from the dual-theme contract when `<name>_dark` exists. A dark mark with no dark variant gets a white 20×20 backing rect (`rx=4`) behind its 16px label icon.
- **Coral stays editorial.** Logos bring their own color, so the focal accent goes on the tile stroke (`.tile.focal`), never on the logo. The one continuous primary request path may use accent arrows; it counts as one coral element.
- **Credit the sources.** The footer carries `%%LOGO_CREDITS%%` (for example `logos: svgl / devicon / AWS Architecture Icons. Brand logos are trademarks of their owners.`). It lives in the HTML footer, outside the SVG, so it never enters an exported PNG.
- **Keep logos out of repositories.** Commit the draft with tokens, not the built file or the logo directory, unless the destination's owner has cleared it.

## Node markup

Geometry (box 128×96, 48px tile, 32px logo, anchors, spacing) is owned by [type-architecture.md § Icon nodes](type-architecture.md#icon-nodes).

```svg
<rect class="tile" x="480" y="120" width="48" height="48" rx="8"/>
<image href="%%LOGO_hono%%" x="488" y="128" width="32" height="32"/>
<text class="name halo" x="504" y="188" text-anchor="middle">Hono</text>
<text class="sub halo" x="504" y="204" text-anchor="middle">api</text>
```

A non-brand node keeps the tile and draws a 24px monochrome glyph from `primitive-icons.md` at `(cx-12, top+12)` with class `glyph`. The tile is white in both themes, so the glyph uses a fixed ink, not a theme token.

## Checklist

- [ ] Logo mode actually requested or implied by named products?
- [ ] Every logo from an official source (manifest `source` is svgl, devicon, gilbarbara, aws, or an explicit official URL)?
- [ ] No logo recolored; white marks on `.tile.dark` only after inspection?
- [ ] Group-label icons square, with `lt`/`dk` pairs where a dark variant exists?
- [ ] Footer credit line present; no built file or logo directory committed?

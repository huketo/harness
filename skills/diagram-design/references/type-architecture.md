# Architecture

**Best for:** system overviews, data-flow diagrams, integration maps, infra topology.

## Layout conventions
- Group components by tier or trust boundary (frontend → backend → data; public → private).
- Primary flow runs left→right or top→down. Pick one and hold it.
- Draw arrows before boxes so z-order puts connections behind components.
- 1–2 coral focal nodes: the primary integration point, the primary data store, or the key decision node.
- Dashed boundary rectangles mark regions (VPC, security group, trust zone); labels sit on a paper-colored mask over the boundary line.

## Connector style

**Rounded right-angle (orthogonal) connectors are MANDATORY** for all non-horizontal/vertical connections — diagonal `<line>` between off-axis nodes is a hard fail (see SKILL.md §6 Mandatory connector rules). Two-bend elbow path with `r=8`:

```svg
<!-- right+down: from (x1,y1) to (x2,y2), mid = (x1+x2)/2 -->
<path d="M x1,y1 H mid-8 Q mid,y1 mid,y1+8 V y2-8 Q mid,y2 mid+8,y2 H x2"
      fill="none" stroke="…" stroke-width="1.2" marker-end="url(#arrow)"/>
```

Flip the vertical signs for right+up. Use a plain `<line>` only when endpoints share the same x or y. Arrow labels sit on the vertical segment, centered horizontally on `mid` and vertically between the two corners.

**Port selection — use top/bottom for vertical connectors.** When the destination is noticeably above or below the source, exit the source's top/bottom edge and enter the destination's top/bottom edge. Use a single-bend L-path (horizontal → corner → vertical into the node), not a left/right side port:

```svg
<!-- entering a node from its bottom (destination above source) -->
<path d="M x1,y_src H x2-8 Q x2,y_src x2,y_src-8 V y_dst"
      fill="none" stroke="…" stroke-width="1.2" marker-end="url(#arrow)"/>
```

Reserve left/right ports for connections that travel primarily horizontally. Entering a node from the side on a mainly-vertical path looks like the arrow punctures the node face rather than arriving from above or below.

**Dashed paths — same routing rules.** Optional, return, async, and passive flows use `stroke-dasharray="4,3"` and a lighter stroke weight (`stroke-width="1"`). Apply the **same orthogonal routing, port-selection, and bridge/hop rules** as solid paths — the dash pattern only communicates semantic weight, not a different routing grammar. When a dashed path and a solid path must cross, bridge the dashed one (it is by definition the less important connection).

**Zone label margin.** Leave ≥16px between the bottom of the zone eyebrow label and the top of the first enclosed node. Size the zone rect tall enough to contain this header gap (zone `y` = node_top − 32; label mask `y` = zone_y + 4).

## Crossing arrows — bridge / hop

When two orthogonal arrows must cross, add a small arc (hop/bridge) on the **less important** arrow at the crossing point. The more important arrow is drawn uninterrupted.

```svg
<!-- Horizontal hop over a vertical crossing at x=cx, on a line at y -->
<path d="M x1,y H cx-8 a 8,8 0 0,1 16,0 H x2"
      fill="none" stroke="…" stroke-width="1.2" marker-end="url(#arrow)"/>
```

`a 8,8 0 0,1 16,0` is an SVG arc: rx=ry=8, large-arc=0, sweep=1 (curves visually upward), advancing 16px right — creating an 8px-radius semicircular bump over the crossing. For a vertical hop over a horizontal, use `a 8,8 0 0,0 0,16` on the vertical path.

Decide which arrow to bridge: bridge the one that is less semantically important (passive, secondary, write-back), or the one with lighter stroke weight (dashed, muted). Never bridge both.

## Zone grouping

Group 2+ nodes that serve the same tier or trust boundary with a zone rect — drawn **before** arrows and nodes (z-order: bg → zones → arrows → nodes):

```svg
<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8"
      fill="rgba(45,49,66,0.02)" stroke="rgba(45,49,66,0.10)" stroke-width="0.8"/>
<rect x="{label_x}" y="{y+4}" width="{label_w}" height="12" rx="2" fill="{paper}"/>
<text x="{label_cx}" y="{y+13}" fill="rgba(45,49,66,0.40)" font-size="7"
      font-family="'Geist Mono', monospace" text-anchor="middle" letter-spacing="0.14em">LAYER</text>
```

Rules:
- Leave 12–16px above the first enclosed node — the eyebrow label sits in this margin.
- Zone fill: `rgba(45,49,66,0.02)` (2% ink wash). Any stronger competes with node fills.
- Max 3 zones per diagram. More and it reads like a swimlane (use that type instead).
- Dark mode: swap `rgba(45,49,66,…)` → `rgba(245,245,245,…)` same opacities; label mask fill = `paper` (dark).

## From a stack description

When the user describes a stack in a sentence or a flat list of tools ("Next.js and a Hono API on Vercel, Postgres on Neon, auth with Clerk, GitHub Actions deploys"), infer the content before the §3 plan message:

- **Nodes:** one per technology, named in the brand's own casing, with a short lowercase role as the sublabel (`api`, `postgres`, `ci / deploy`).
- **Zones:** draw one around things that share a runtime, a vendor, or a repository (a cloud account, a monorepo). One nesting level is usually enough.
- **Connectors, three kinds:** the primary request path uses accent arrows as one continuous path (it counts as one coral element); other runtime calls use the default arrow; deploy-time and dev-time relationships (CI, git hooks, IaC) are dashed.
- **Deploy to a platform:** when the target is a zone ("deploys to Vercel"), point the dashed arrow at the most representative node inside it and label it `DEPLOY`.
- **Ask only when it changes the picture.** If a tool could sit in two places and either choice would make the diagram wrong, ask; otherwise infer and list the assumption in the plan message.

When the nodes are named products, consider logo mode ([primitive-logos.md](primitive-logos.md)) and the icon-node geometry below.

## Icon nodes

An icon node is a 48px tile with the name and sublabel **below** it (logo mode, or a monochrome glyph used the same way). The text is part of the node, so the node box is the tile plus its text.

| Part | Geometry (cx, top on the 4px grid) |
|---|---|
| Node box | 128×96, `x = cx-64`, `y = top` to `top+96` |
| Tile | 48×48 at `(cx-24, top)`, `rx=8` |
| Logo | 32×32 at `(cx-16, top+8)`; a 24px glyph at `(cx-12, top+12)` |
| Name | 12px sans 600, baseline `top+68` |
| Sublabel | 9px mono, baseline `top+84` |
| Two-line name | second line baseline `top+84`, sublabel `top+100`, box bottom `top+112` |

Spacing:

- Same row: node centers ≥160px apart (128 box + 32 gap).
- Consecutive rows: tile tops ≥144px apart (96 box + 48 gap); more when zones stack between rows.
- Zone: `x = leftmost cx-88`, right edge `rightmost cx+88` (24px outside the box, not the tile, so every zone has symmetric padding); top `= first tile top-48` for the label band; bottom `≥ last tile top+120`. A nested zone is inset ≥24px on the sides and bottom and starts ≥48px below its parent's top.
- Zone label sits inside the top-left corner (`x+12`, `y+12` for a 16px icon, text baseline `y+25`). Keep connectors out of that corner.

Connector anchors — **never through the text under a tile**:

- **Horizontal** (same row): tile side to tile side at tile mid-height, `y = top+24`, from `cx+28` to `cx'-28`. Nothing sits beside a tile, so this is always clear. Several connectors on one tile side fan along the tile's 48px edge per §6 rule 4 (for two: `top+16` and `top+32`).
- **Vertical** (node above node): from the upper node-box bottom (`top+100`) to the lower tile top (`top'-4`), or the reverse for an upward connector. Never start at the tile bottom (`top+48`): that line runs through the name.
- **Elbow:** run the vertical segment in an x-corridor that crosses no node box, and the horizontal segment in the clear band between rows (`top'-40 … top'-12`). Crossing another connector is normal (bridge it per § Crossing arrows); crossing a node box is not.
- Before drawing, list every vertical and elbow segment and ask which node boxes its corridor passes between y1 and y2. The answer must be none.

Labels keep the opaque mask (§6). Name, sublabel, and edge-label text also carry a paper-colored halo (`paint-order: stroke`, 3px), so a line that must pass close to text disappears behind it instead of striking through. The halo is a second defence, not a replacement for the mask or the anchor rules. A worked example is [`assets/template-logos.html`](../assets/template-logos.html).

Adapted from caru-ini/stack-diagram `references/geometry.md` (MIT, see `LICENSE.stack-diagram`), re-derived for the 4px grid.

## Anti-patterns
- Every box in coral ("this is important too") — hierarchy collapses.
- Bidirectional arrow when one direction is obvious from context.
- Legend floating inside the diagram area.

## Examples
- `assets/example-architecture.html` — minimal light
- `assets/example-architecture-dark.html` — minimal dark
- `assets/example-architecture-full.html` — full editorial

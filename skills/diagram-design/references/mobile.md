# Mobile classification and adaptation

Use this reference for mobile requests and document-embedded diagrams. It overrides conflicting upstream canvas, minimum-width, grid, and typography defaults—not the diagram's semantics. For document palettes, fonts, offline exports, and Word, use [harness-documents.md](harness-documents.md); do not create a second document theme here.

## Contract and status

Status belongs to a **specific artifact at a measured size**, not to a diagram type.

| Status | Meaning |
|---|---|
| `verified` | Browser checks at 360px and 1280px passed: every visible SVG text run is at least 11 rendered CSS px, no page or figure horizontal overflow, no clipped/overlapping labels or truncated connectors; visual review confirms relationships and data. Record the artifact, embedding context, browser, and measurements. |
| `needs-adaptation` | A measured artifact fails the contract and needs reflow, splitting, or a faithful alternative representation. |
| `desktop-only` | An explicit desktop deliverable with a named minimum width. This does not satisfy a mobile request. Supply a usable mobile companion when mobile is required. |
| `unverified` | No qualifying browser evidence exists yet. Source inspection and `self_check.py` alone cannot promote it. |

The pinned upstream baselines are [recorded in mobile-baseline.json](mobile-baseline.json): all 40 are `needs-adaptation`. At 360px, 36 overflow horizontally; the other four (`it-state`, `org-chart`, `waterfall`, `dp-security-matrix`) have text below 11px. This says nothing about other variants or future diagrams of those types. The `high-level` parent's zero-font result was a measurement artifact, so its minimum is deliberately null. Text-bounding-box overlap candidates are not confirmed collisions without visual inspection.

## Size the actual embedded figure

1. Select the host and viewports first. Measure the figure's available width, not just the page width.
2. Compute the text budget. For a uniformly scaled SVG, rendered font = authored font × rendered width / viewBox width. Nested transforms and styled `tspan` runs require their own screen CTM measurements.
3. Reflow only layout that carries no data. Wrap labels and stack topology before shrinking text. Keep reading order, connector endpoints, membership, and edge direction.
4. Split dense content into a linked overview and detail panels. Preserve stable identifiers and every relation across panels; name what each panel excludes. A summary is not an equivalent full diagram.
5. If faithful mobile presentation is still impossible, supply a complete alternative (for example, an accessible data table plus an overview) and label the large diagram `desktop-only`. Do not silently substitute it for the requested mobile deliverable.

The current document shell leaves approximately 309.2px for an SVG at a 360px viewport: `360 − 2×14.4px main padding − 2×(10px figure padding + 1px border)`. Verify this after shell changes. At that width, a 320-unit viewBox with 12-unit text renders at approximately 11.60px; a 960-unit viewBox needs text of at least 34.16 units. These are sizing estimates, not verification.

Declare a viewBox and fluid width; do not use a fixed `min-width`. Keep export-required sizing, fonts, and scoped styles inside the SVG or in presentation attributes. An HTML-head class alone disappears on SVG extraction. Prefix IDs per figure and avoid CSS leaking into the host. Existing document tokens own the palette. See the [bundled gallery](../assets/harness-gallery.html) for four adapted examples and their current status.

## Choose a mobile strategy: all 40 types

The table is design guidance, **not a support badge**. Each canonical baseline's measurements live only in `mobile-baseline.json`. Any reduction in entities, fields, series, or points requires an explicit scope statement and a complete companion; never discard data merely to meet a count target.

| Type | Constraint | Mobile strategy and invariant |
|---|---|---|
| `architecture` | Trust zones and cross-boundary routes | Stack zones; keep ingress/egress, allowed and blocked paths visible. Split by subsystem with shared boundary identifiers. |
| `it-state` | Department × current/target comparison | Stack department cards with paired current/target states; keep status and migration relationships. |
| `flowchart` | Decisions and exception branches | Put the primary path downward; route side branches with explicit conditions and destinations. Preserve every outcome. |
| `sequence` | Actors across, time downward | Keep vertical time and message order. Use narrow actor lanes or numbered linked panels; preserve cross-panel calls, returns, and concurrency. A pairwise subset alone is insufficient. |
| `state` | Cycles, guards, terminal states | Stack the primary lifecycle and route loopbacks at the side. Retain guards and error transitions. |
| `er` | Entities, attributes, cardinality | Stack small entity groups; split by bounded context. A PK/FK overview must link full attributes and retain all cardinalities. |
| `timeline` | Ordered events, sometimes elapsed time | A vertical timeline is valid when time remains monotonic. If distance encodes duration, use one proportional scale or disclose each panel's bounds and scale. |
| `swimlane` | Owner × process phase | Stack phase panels with explicit owner badges. Preserve handoffs and parallel work; a sequential list cannot imply false serialization. |
| `quadrant` | Two independent spatial axes | Keep a compact two-axis plot or split quadrants with coordinates retained. A ranked list is only a companion: quadrant numbering does not establish priority. |
| `radar` | Shared radial scales and series | Use small multiples with the same axes/scales, or an equivalent labeled value table/bar view. Do not drop axes or normalize each panel separately. |
| `polar` | Cyclic angular order and radial magnitude | Keep cyclic order with compact callouts or ordered small multiples. A sorted bar chart loses angular meaning and is not an equivalent replacement. |
| `loop` | Directed reinforcing cycle | Use a vertical racetrack cycle with an explicit return edge. Preserve cycle order and the state being reinforced. |
| `nested` | Containment hierarchy | Use vertically extended nested boxes or an indented containment tree. Keep parent membership and depth explicit. |
| `tree` | Parent-child branching | Use an indented tree or narrow top-down branches with linked subtrees. Preserve every child and its parent. |
| `org-chart` | Reporting hierarchy, possibly dotted lines | Use a vertical reporting chain with indented reports. Distinguish line management from secondary relationships. |
| `layers` | Ordered abstraction stack | Stack full-width slabs with wrapped labels. Keep layer order and any bypass connections. |
| `venn` | Membership and intersections | Keep a compact set diagram with external intersection labels, or a full membership table. Do not drop intersections to reduce circles. |
| `pyramid` | Tier order, possibly magnitude | Use vertical tiers and external labels. If area/width carries a value, keep the quantitative encoding or switch to an explicitly different representation. |
| `bar` | Category values on one scale | Horizontal bars can fit labels; transposition is valid if units, zero baseline, and a common scale survive. Preserve negative values and order. |
| `waterfall` | Signed contributions and running totals | Use narrow panels with repeated shared scale and linked carry totals. A ledger can be a complete alternative, but cards with badges are not the same quantitative chart. |
| `treemap` | Area represents share | Use a compact map and an external value legend. An explicit Other group must name every member and conserve the sum; never resize cells to fit labels. |
| `line` | Continuous coordinates, shared time/value scales | Use small multiples with aligned domains and direct labels. Preserve all series via panels; do not rescale each one silently. |
| `gantt` | Durations, overlaps, dependencies | Split task groups against the same calendar scale, with continuation bounds. A milestone checklist loses duration overlap and is only a companion. |
| `scatter` | Two quantitative coordinates | Keep both axes and every point; use labeled subsets only alongside the full data. If density is unreadable, provide a complete table and a desktop plot rather than hiding points. |
| `high-level` | End-to-end tiers and system boundaries | Stack major tiers and link detailed subdiagrams. Name deferred detail and preserve all inter-tier routes. |
| `process` | Stage order and governance | Stack stages with explicit inputs, outputs, and governance attachments. Keep ownership and parallel branches. |
| `medallion` | Data-quality tiers and gates | Stack Bronze/Silver/Gold with explicit quality gates and failure routes. Do not turn failed validation into forward progress. |
| `data-flow` | Transformations and directed data paths | Stack transformations and route fans explicitly. Bundled connectors must identify which sources reach which destinations. |
| `dp-integration` | Ingestion, platform core, consumption | Stack the three zones and link detail panels. Retain storage/compute distinctions and each external interface. |
| `dp-security-matrix` | Role × component permissions | Use per-role cards listing every component and permission, including denied/unspecified states. Keep a complete matrix/table companion for cross-role comparison. |
| `sankey` | Flow conservation and ribbon widths | Split stages only with explicit continuation labels and consistent flow units/scales. Grouping must conserve totals; no arbitrary narrowing to fit. |
| `fishbone` | Cause categories feeding an effect | A vertical spine or categorized cause cards can work. Preserve category membership and the shared effect; do not imply chronological causation. |
| `wardley` | Value-chain position × evolution | Keep axis meanings and component coordinates. Use linked focused maps or a desktop map plus complete coordinate/dependency table, not a rotated hierarchy. |
| `kanban` | Status columns and WIP | Stack status groups while retaining all cards, owners, and WIP limits. Label the grouping so it does not imply card priority. |
| `journey` | Stages, touchpoints, actions, sentiment | Stack stage cards containing all dimensions. Preserve sentiment scale and chronological stage order. |
| `deployment` | Infrastructure containment and network routes | Stack cloud/VPC/subnet/workload groups; retain ports, replica counts, and network boundaries. Split detailed clusters without losing routes. |
| `dependency` | Directed edges, fan-in, cycles | Layer the graph vertically or use linked subgraphs. Preserve cycles and all cross-panel dependencies; do not invent a critical path without data. |
| `uml-class` | Compartments and typed relationships | Stack focused class groups with typed connectors. Overview omissions must link complete attributes/methods and preserve inheritance/composition distinctions. |
| `story-map` | User activities × release slices | Stack release panels with activity labels and original task order. Preserve both dimensions and identify tasks spanning releases. |
| `db-schema` | Tables and column-level foreign keys | Stack domain groups with linked continuations. A PK/FK-only overview must link the full schema; preserve column endpoints and cardinalities. |

## Verify before promotion

- Run the bundled `scripts/self_check.py` for each authored diagram HTML, then use a real browser. A navigation-only gallery without SVG is not a diagram self-check input.
- At 360px and 1280px, inspect standalone output **and the actual document embedding**. Check `scrollWidth <= clientWidth` for page and figure; do not hide overflow to make the check pass.
- For each visible text run, multiply its computed font size by its screen CTM scale. Inspect styled `tspan` leaves separately; a zero-font parent is not visible zero-size text. Compare actual text/shape bounds and inspect screenshots for overlap, clipping, arrowheads, and font fallback.
- Bind every boxed text run to its actual owning shape (for example, `data-box="<rect-id>"`), then measure containment with the intended padding. Identify free text explicitly. Record total, checked, free, and unresolved counts; an empty selector such as `g.node` is no evidence of containment. Any unresolved ownership leaves the artifact unverified.
- Check text against connector strokes as well as other text. Inspect path geometry, arrowheads, masks, and paint order; enforce the label-to-connector clearance in SKILL.md §6. Putting an opaque mask over an arrow does not satisfy the required visible gap. Match the expected connector/label count to the inspected count before promotion.
- Verify semantic invariants numerically where relevant: timeline tick positions must share one affine time mapping; Sankey quantities conserve flow; paired chart axes share domains. Good-looking geometry is not data evidence.
- For document output, confirm no scripts or external resource requests, no duplicate IDs, and no cross-figure CSS effects. Extracted SVG must retain its styling without the HTML head.
- Record exact evidence before changing `data-mobile-status` or gallery text to `verified`. A caption such as “완벽 대응” is not evidence. Any later content, style, font, or host change invalidates the old status until rechecked.

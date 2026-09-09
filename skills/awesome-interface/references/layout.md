# Layout

Make task structure visible through grouping, shared edges, order and adaptation. Preserve usable project density and platform conventions; fix the smallest structural cause rather than replacing the page with a generic redesign.

This domain owns spatial hierarchy, responsive layout, disclosure and the arrangement of empty/loading/error states. Target boundaries, focus and accessible zoom/reflow requirements belong to [accessibility.md](accessibility.md). Text measure, wrapping and truncation mechanics belong to [typography.md](typography.md); state messages to [writing.md](writing.md); surface depth, optical alignment and motion to [ui.md](ui.md); color emphasis to [colors.md](colors.md). Use [review.md](review.md) for review ranking and reporting.

## Establish the task hierarchy

Before drawing or editing, identify the primary task, the information needed to decide, the main action and the secondary details. Inspect the existing grid, spacing tokens, supported sizes and surrounding screens. Finish this pass with an intended reading order and a clear distinction between essential, supporting and optional content.

Place important information near the top and leading edge for the applicable reading direction. Within a row, let identifying content lead and metadata or actions follow. Keep explanations close to the decision they support. A primary fact buried beneath administrative metadata remains hard to find even when its font is larger.

Favor a clear primary action within each task context, not a rigid count across an entire dashboard. Demote secondary actions without concealing frequent or safety-critical operations. A menu earns its place when a visible list competes with the main task; a particular number of actions is not itself a reason to hide them.

## Group with space and shared edges

Use relatedness to set distances: the gap between groups should read larger than the gaps within each group. Prefer existing spacing steps. A roughly doubled inter-group gap can be a starting experiment where no scale exists, not an exact-value requirement or a substitute for inspecting the result.

Choose the least visual structure that communicates the relationship:

1. Space for ordinary grouping.
2. A background shape when the group must behave or read as a unit, such as a selectable row or draggable card.
3. Separators for dense tables or long lists where spacing alone is insufficient.

Keep necessary separators quiet but perceivable. Preserve borders that communicate structure or state; avoid adding a line, card and large gap to solve the same grouping problem. Do not turn every subsection into nested cards.

Choose a small set of shared alignment edges for headings, rows, content and action bars. Use a consistent project spacing step for each hierarchy indent rather than accumulating arbitrary offsets. Align textual table columns to their reading edge and comparable numeric columns to their trailing edge; numeral shaping belongs to [typography.md](typography.md).

Distinguish interaction from content with an established affordance: an underline, background, border or consistent control zone. A control styled exactly like nearby prose disappears; a static badge shaped like adjacent buttons attracts dead clicks. Borderless controls often need more surrounding space because their target edges are invisible. Resolve hit-area geometry through [accessibility.md](accessibility.md), not by prescribing one gap for all densities.

## Keep visual and source order coherent

Build the meaningful sequence into the DOM. CSS `order`, reversed flex directions and grid placement can create a visual sequence different from reading and focus order. If rearranging at a breakpoint, verify that the source sequence still makes sense; do not repair it with positive tabindex.

Use logical properties for direction-dependent layout: `margin-inline-start`, `padding-inline-end`, `inset-inline-start`, `text-align: start` and logical borders. Retain physical properties for genuinely physical geometry, not merely because the original screen was left-to-right.

Under `dir="rtl"`, inspect progression, step indicators, navigation and manually positioned elements as well as text alignment. Preserve the meaning of rating/progress direction according to the product's locale convention. Avoid double-mirroring a flex/grid sequence already responding to direction. Bidirectional text and digits belong to [typography.md](typography.md); directional icon treatment belongs to [ui.md](ui.md).

## Progressive disclosure without hidden work

Keep the entry view focused on the task, with a visible route to details. Hide optional complexity, not information needed to make the current decision or understand an error.

Every collapsed or off-screen region needs a recognizable affordance:

- A disclosure control names what it reveals and its current state. Its keyboard and semantic behavior belong to [accessibility.md](accessibility.md).
- A horizontal scroller uses the existing scroll indicator, visible navigation or a partial next item. A peek is a cue to inspect, not a mandatory pixel width.
- Truncated content has a practical route to its full value; mechanics belong to [typography.md](typography.md).
- A details view preserves enough context to return to the originating item or task.

Make the cue honest: hide or disable a next affordance when no next content exists, and ensure the final item and its actions are fully reachable. Do not place required form errors only inside a collapsed section without revealing a route to them. Keep persistent guidance outside an empty-state region that disappears after the first item is added.

## Responsive structure follows content

Retain the expanded structure while its content genuinely fits. Collapse when a sidebar, grid cell, label or action row can no longer serve its task, not simply because a familiar device breakpoint was reached. Reuse established breakpoints when they already express that constraint. Prefer container queries for components reused in differently sized regions when the project supports them.

Use the smallest and largest supported sizes to expose failures, then inspect intermediate widths and points immediately around structural changes. Components must work inside a narrow pane on a wide screen, not only at a narrow viewport.

- Let text and controls size from content using padding, flexible tracks and sensible maximum widths. Use `min-height` when a floor is needed rather than a clipping fixed height.
- Let rows wrap or deliberately stack when labels grow. Check flex/grid minimum-size constraints before adding overflow hiding; `min-inline-size: 0` or a flexible track can address an actual shrinking problem.
- Keep long unbroken identifiers from stretching the page while preserving access to their full values.
- Avoid a fixed width chosen for one English label. Short strings often expand proportionally more than paragraphs; use pseudo-localization and a representative long-string locale instead of a universal expansion percentage.
- Treat truncation as an information decision, not a general overflow fix. Critical actions and recovery instructions need room.

```css
/* Illustrative structure; use the project's actual spacing tokens. */
.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-control-gap);
}
.action-row > button {
  max-inline-size: 100%;
  white-space: normal;
}
```

This is a pattern, not a request to introduce a token or restyle working controls. Accessible text-resize and reflow acceptance criteria are owned by [accessibility.md](accessibility.md).

## Edges, safe areas and scrolling

Media and backgrounds may bleed to viewport edges. Text and controls usually stay inside the content margins and device safe areas. Full-width content actions can span the content column without touching the physical screen edges. Preserve deliberate edge-to-edge platform chrome when its role is clear and its safe-area behavior works.

For sticky headers, floating buttons and action bars, account for actual physical safe-area insets such as `env(safe-area-inset-bottom)`. A logical trailing position is not always the physical right side in RTL; map physical notch insets deliberately.

Critical actions must remain reachable when the pane shrinks, content grows or the software keyboard opens. Normal flow is often sufficient. Use a sticky action row or stable chrome only when it solves an observed reachability problem; reserve enough scroll space so it does not cover the final content or focused control. In a scrolling modal, keep the action area reachable without making the body impossible to inspect.

Prefer one understandable scrolling region. Where nested scrolling is needed, make boundaries clear, preserve access to the first and last items and prevent unwanted scroll chaining. Sticky positioning alone does not prove that content remains visible.

## Design every content state

Keep the page's identity, navigation and useful task context recognizable across states. A component is not finished when only its populated state fits.

| State | Spatial decision |
| --- | --- |
| First-use empty | Put orientation and one plausible next action where content will appear; avoid a large decorative treatment that pushes the action out of reach |
| No search/filter results | Keep the query and filters available; put reset or adjustment controls beside the explanation rather than replacing the whole view |
| Initial loading | Preserve the surrounding structure; reserve realistic space for incoming content when useful, without making skeletons look interactive |
| Refreshing existing content | Keep useful content and controls in place where safe; distinguish updating from an empty result and avoid disruptive page replacement |
| Field or section failure | Place recovery at the affected region; preserve unaffected content and entered values |
| Whole-view failure | Retain navigation and a stable recovery location; do not leave the user in an unexplained blank pane |
| Partial data / unusually large data | Show which region is unavailable or overflowing without breaking neighboring structure; keep pagination or expansion reachable |

Message content belongs to [writing.md](writing.md), and announcement/focus behavior to [accessibility.md](accessibility.md). Avoid shifting an action under the pointer when loading ends or an error appears. Reserve space where it stabilizes the task, but allow real content to grow rather than freezing all states to a guessed height.

## Verification evidence

From source, inspect the intended DOM order, existing layout tokens, logical properties, container/media queries, overflow rules and state branches. A stylesheet can suggest a risk but cannot prove visible clipping or hierarchy.

In the rendered interface, inspect the requested states at supported size extremes, intermediate breakpoints and narrow component containers. Resize with long labels, long data, missing data and populated/empty/loading/error states. Inspect the RTL layout where supported and use the resize/reflow checks in [accessibility.md](accessibility.md). Scroll to both ends, open the software keyboard when available and check sticky overlays against final content and primary actions.

Record the exact viewport or container, state and observed obstruction or hierarchy problem. Explain the smallest structural correction and what it preserves. State unavailable rendering, locale, device or zoom checks as unverified; source inspection is not a visual pass. Do not launch a separate stress-test workflow unless that workflow was requested.

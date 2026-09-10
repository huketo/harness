# Signal — cobalt clarity

Use for decisions, comparisons, measured results, and executive or technical briefings. Adopt Blue Professional's exact cream `#fdfae7`, ink `#111111`, and cobalt `#1e2bfa`; preserve its single-accent discipline and split-evidence composition. See [attribution](ATTRIBUTION.md) for adaptations and licensing.

## Working dimensions and roles

Recipes use a 1000 × 562.5 logical stage. Scale coordinates with the native canvas, not with browser viewport units inside a scaled stage. Start with 20px body / 32px leading, 65px cover display, 40px title, 28px region headings, 16px labels/sources, and 17px code / 25.5px leading. Heading weight is 700 and leading 1.25. Use the CJK-first `--as-font` stack for text and `--as-mono` for source. The 5/10/15/20/30/40/60px spacing ladder is expressed as em tokens at body size.

Headlines stay ink. Cobalt identifies the focal value, chosen alternative, or decisive relation; direct labels and position carry the same meaning. Muted text is deliberately darker than upstream tertiary gray. Use `--as-line` for a necessary boundary, and `--as-accent-soft` only behind a named focus. Avoid inheriting opacity for sources or chart labels. Measure actual pairs in the integrated surface before approving contrast.

## Cover: a decisive split

Use 50px outer insets and a 62:38 division of usable width. Put the title at x=50, y≈130, in a measure that allows two meaningful phrase lines. Below, keep 20px to the premise and 40px to authorship. Use the right region for one real headline value with unit/context, or a source-backed before/after visual. Align that evidence's optical center with the title block. A 30 × 2px cobalt rule may mark a real section, but is not a required logo substitute.

Synthetic example: `배포 시간을 줄이려면` / `대기부터 분리해야 한다`. The right side could show a measured waiting-time breakdown only after measurements are supplied. Without data, widen the title rather than invent a giant percentage. Retain cream as the field; a tinted right panel is useful only if it separates a different kind of information.

## Dense comparison: aligned decision rows

Place a 40px assertion title at x=50, y=42. Begin the matrix near y=120, spanning 900px. Allocate 30% to criteria and 35% to each option. Use 18–20px text, 12px row padding, and 20px horizontal cell padding. Separate the header and logical row groups with rules; let ordinary row whitespace do the rest. A cobalt vertical marker and explicit `권장` label may identify the recommendation without coloring every cell.

Synthetic example: compare `빌드 없는 전달` and `발표 기능 확장` against the user's actual constraints. Keep costs, unknowns, and exceptions in the same comparison basis. Reserve about 70px below for the decision condition and source. Split additional criteria into a continuation instead of compressing every row. This is a table, not a collection of equally sized cards.

## Code / evidence: claim beside proof

Give code or a real trace 60% of usable width, leave a 6% gutter, and use 34% for the inference. Title and code share the left edge. Start the explanation beside the decisive line; a 2px cobalt rule on that explanation marks its relationship. Use 20px source padding, 17px code, and 30px between independent interpretations. Show the language/path and exact source range in a 16px caption.

Synthetic title: `캐시 적중은 계산 경로를 건너뛴다`. Show the actual branch with enough context to establish the claim. A tiny one-line result can appear in open space below the source rather than inside a second box. Preserve indentation and exact identifiers; long source lines belong in a readable excerpt or a scrollable reading block, not in silently wrapped stage code.

## Diagram: one emphasized path

Reserve the central 900 × 320px region for the topology. Use ink labels, solid boundary lines, and cobalt on the path discussed by this slide. For a request flow, align `요청`, `캐시`, `계산`, and `응답` according to actual execution; label branching edges `적중` / `미적중` rather than relying on color. Put the key invariant below the figure with a 24px gap. Use a number only for genuine ordering.

If the argument is quantitative, replace topology with aligned bars: the bar lengths derive from the same stated scale, category labels lead, exact values trail, and cobalt singles out the discussed series. Upstream's 28px bar track translates to a starting 14–20px bar on this stage; labels remain 18–20px. Preserve a zero baseline for magnitude comparisons unless a different scale is explicitly justified.

## Conclusion: decision and condition

Use a 58–64px statement in the upper-middle left, starting around y=150; no mandatory eyebrow or card row. After 24px, state the condition under which the recommendation holds. After 40px, add the requested action in 24px type. If that action needs a distinct field, use a cobalt band with `--as-on-accent` text and generous 24px inset, not a fake clickable pill.

Synthetic example: `먼저 관측하고` / `그다음 최적화한다`, then `동일한 부하와 지표로 비교한다`. Add owner and date only from supplied commitments. Keep the figure that supports the decision in the preceding slide, not a miniature dashboard pasted into the ending.

Use [style selection](../../references/style-selection.md) for Korean phrase handling, responsive reading, and the two-slide proof before expansion.

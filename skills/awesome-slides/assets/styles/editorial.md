# Editorial — warm, readable research

Use for explanatory reading, research synthesis, teaching, or a considered proposal. Pair warm paper and ink with serif display and sans-serif substance. The adopted Soft Editorial palette and spacious spread composition are documented in [attribution](ATTRIBUTION.md); these are adaptations, not an exact upstream theme.

## Working dimensions and roles

Compose the following recipes on a 1000 × 562.5 logical stage; multiply coordinates by the actual native canvas width / 1000. These are starting compositions, not fixed content limits. Stage geometry belongs to the engine. For a reading surface, keep source order and stack regions at narrow widths rather than shrinking the stage into a handout.

Start with a 20px body, 32px body leading, 70px cover display, 42.5px slide title, 28px region title, 16px labels/sources, and 17px code at 25.5px leading. Display/title leading is 1.25, weight 600. Use `--as-font-display` for display and titles, `--as-font` for body, and `--as-mono` for exact code. The stylesheet contains these proportional type roles and a 5/10/15/20/30/40/60px spacing ladder at this body size. Apply spacing to body-sized containers so heading em sizes do not inflate it.

Use `--as-fg` on paper, sage, blush, or lemon; reserve dark sage `--as-accent` for links and a focused annotation. `--as-muted` serves secondary prose, not lowered opacity. The pastel fills remain optional semantic regions, not rotating decoration. Keep category meanings stable within a deck. A plain ruled table usually needs no surrounding card.

## Cover: an opening spread

Set a 52px outer inset. Place the title in the left 62% of the usable width, starting near y=132; keep two or three intentional phrase lines. Put the one-sentence premise 24px below it and authorship 48px below that. The right region can carry a real cropped image or a pull-quote from the supplied material, aligned to the title's optical center. If no informative asset exists, keep this region quiet and give the title a wider measure.

Synthetic wording example: `복잡한 운영을 이해하는 방법` / `관찰에서 판단까지`. The slash marks an authored phrase break, not visible punctuation. Keep the title block a little above the canvas midpoint; balance its visible ink against the image, not their bounding boxes. A palette-disc row is unnecessary when it says nothing about the subject.

## Dense comparison: a magazine matrix

Use x=52–948, title at y=46, and a table beginning near y=126. Allocate 28% of table width to criteria and 36% to each alternative. Use 18–20px cell text, 12px vertical cell padding, a solid header rule, and lighter dashed row separators. Leave 28px between the table and an interpretation paragraph. If the rows do not fit with visible qualifications, continue the table on a second slide with repeated column headings.

Synthetic comparison example: title `선택 기준에 따라 답이 달라진다`; rows `편집 가능성`, `오프라인 전달`, `발표자 노트`; alternatives `단일 HTML` and `Slidev`. Populate cells from actual engine evidence rather than assuming equivalence. Highlight a selected column with sage only when there is a stated selection; include its label. Put the recommendation and its limiting condition below the table, not in a floating badge.

## Code / evidence: a margin annotation

Use a 58% source region and 34% explanation region, with an 8% gutter. Align the first explanatory sentence with the relevant code line rather than with the top of an ornamental box. Set code on `--as-code-bg`, with 20px padding and the exact line range in its caption. Keep 10px between a claim and its support, 30px between independent observations. Use a leader line only to identify a precise source location.

Synthetic example: title `재시도는 실패한 단계만 반복한다`; code shows the actual retry branch once available; the margin explains the invariant and the unhandled condition. Until evidence exists, label the example as illustrative. Preserve full source and speaker explanation in native source/notes; a crop must state the omitted scope. Short excerpts may remain directly on paper without an enclosure.

## Diagram: an annotated field

Give the central relationship diagram roughly 70% of the slide's usable height and a side annotation 24% of usable width. Draw only domain objects: for example, `관찰 → 해석 → 결정` for a genuinely sequential explanation. Use ink outlines, text labels, and sage fill on the one current focus. A dashed connector means an explicitly named uncertainty or optional relation, not a weaker-looking aesthetic. Place the figure caption 12px below the diagram and its source another 8px below.

For a cyclic model, use a loop; for containment, use nested boundaries. Retain this paper/ink system while changing the geometry to the relationship. At reading width, place explanation after the diagram and provide a readable textual account of its connections.

## Conclusion: the resolved statement

Place a 58–64px conclusion in a 76%-wide text block around y=155. Follow with a 24px implication after 24px, then the actual next action after 40px. Keep the left edge shared; omit the standard title band. A blush band can contain the next action if it is a distinct commitment, with ink text and 20px padding; otherwise use open space.

Synthetic example: `도구보다 먼저` / `판단 기준을 합의한다`, followed by an owner and next review date only when supplied. A return to the cover's wording closes the argument more clearly than a new decorative motif. Keep caveats visible in reading mode and preserve the final speaking cue in native notes.

For Korean phrase handling, mobile reading, and the cover-plus-dense-slide proof, follow [style selection](../../references/style-selection.md).

# Technical — dark source and systems

Use when exact code, traces, state transitions, and system structure are the primary evidence. Adopt Terminal Green's `#0d1117` field and `#39d353` accent from Frontend Slides; use its dark technical register without scan lines, blinking cursors, or all-monospace prose. See [attribution](ATTRIBUTION.md).

## Working dimensions and roles

Compose on a 1000 × 562.5 logical stage and convert coordinates proportionally to the engine's canvas. Start at 20px body / 32px leading, 60px cover display, 40px title, 28px region headings, 16px labels/sources, and 17px code / 25.5px leading. Headings use weight 700 and 1.25 leading. Sans-serif prose uses `--as-font`; source uses `--as-mono`. The token scale provides 5/10/15/20/30/40/60px spacing at body size.

Use light `--as-fg` and `--as-muted` on the dark field or `--as-surface`. Green marks the active path or relevant source concept, not automatically success. Pair it with a direct label. Use dark `--as-on-accent` text on solid green. Syntax highlighting remains owned by the native engine: choose its dark code theme and check comments, strings, and selected-line backgrounds rather than assuming these palette tokens recolor a highlighter. Borders use `--as-line` only where boundaries convey ownership or state.

## Cover: a system in one sentence

Place a two-line title in the left 66% of the usable width, x=48, y≈140. Follow with a 24px premise after 24px. Place a small actual architecture fragment in the remaining region, aligned with the title's center, or place a one-line real code expression below the premise. Authorship sits 48px below the main group. Keep one dominant text group, not a terminal-window mockup with decorative controls.

Synthetic example: `실패를 격리하면` / `복구 경로가 단순해진다`. An associated fork-and-rejoin symbol is meaningful only when the system really isolates and rejoins work. Prefer an empty region to a fictitious trace or arbitrary circuit texture.

## Dense comparison: observable invariants

Use x=48–952, a 40px title near y=42, and a table beginning near y=120. Allocate 30% to an invariant and 35% each to the two implementations. Set cells in 18–20px sans; set only identifiers in mono. Use 12px vertical row padding and a header rule. Separate unrelated groups with a 24px gap or a group-heading row, not alternating neon backgrounds.

Synthetic example: title `실패 처리의 차이는 경계에서 드러난다`; compare cancellation, partial results, and retry scope. Populate each cell from actual implementation evidence. Use explicit `보장`, `조건부`, or `미확인` text as appropriate; highlight the discussed row with `--as-accent-soft`, retaining light text. A 16px caption states revision and scope. Continue across slides when qualifications would otherwise become unreadable.

## Code / evidence: source first

Allocate about 68% of usable width to code and 26% to explanation, with a 6% gutter. A short title at y=42 leaves the source region beginning around y=114. Set source on `--as-code-bg`, with 20px inset, 17px mono, 1.5 leading. Highlight only the lines necessary to establish the claim using the engine's real code mechanism. Place line-specific annotations at corresponding vertical positions when feasible; otherwise use an ordered explanation below the source.

Synthetic title: `취소는 다음 작업을 시작하지 않는다`. The example requires the real cancellation guard and its caller context, not invented API syntax. State omitted lines and link the full editable source in the caption. At this size roughly a dozen lines may fit with a title and caption; measure the actual block and split at a logical boundary instead of treating that count as a quota. Preserve logs verbatim and label any redactions.

## Diagram: topology with ownership

Give the figure the middle 70% of usable height. Draw bounded processes or stores in `--as-surface` with labels at 18–20px. A boundary means an actual process, trust, or ownership boundary; a connector has an arrow only when direction is meaningful. Use solid edges for actual flow and dashed edges for a stated optional or asynchronous relation. Label green as the currently explained path, and use text or line patterns for alternatives.

Synthetic example: `요청 → 작업 큐 → 실행기`, with an explicit return edge for results if that is the real architecture. Put the invariant 24px below the diagram: for example, a sourced statement about ownership transfer. Wide architectures may become consecutive focused views, each retaining enough context to locate the focus. Reading mode follows the diagram with a textual account of nodes, edges, and the invariant.

## Conclusion: invariant, consequence, next check

Place a 56–60px invariant around x=70, y=150 in a 78%-wide text group. After 24px, state its operational consequence at 24px. After 40px, name the next verification or decision, including the actual owner only when supplied. Leave the remainder quiet. Green may emphasize one exact identifier or relation; the whole heading remains light text.

Synthetic example: `복구의 단위는` / `실패의 경계와 같아야 한다`. Follow with the concrete verification needed, not an unsourced reliability percentage. Keep the caveat visible in the reading version; speaker notes carry the final transition, not the only explanation of the result.

Follow [style selection](../../references/style-selection.md) for mixed Korean/code wrapping, narrow reading, and the cover-plus-dense-slide proof. Dark styling needs actual projector and export inspection where those deliverables matter.

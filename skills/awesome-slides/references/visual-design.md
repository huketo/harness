# Visual design

Use this reference when choosing or applying a deck's visual direction. It owns the visual system for slides; it does not replace the deck's narrative, evidence, build, or delivery workflow.

## Preserve existing authority

Start from the deck or organization's existing brand, engine, theme, and component vocabulary. Preserve deliberate color roles, type choices, logos, spacing, density, illustration style, and motion unless the requested work or an observed failure requires a change.

Map supplied brand guidance onto the current engine rather than creating a second token system. Treat a logo file or one accent color as partial evidence, not permission to invent a full brand. Check whether brand assets may be used in the requested public or internal context.

When `awesome-interface` is available, consult only the relevant accessibility, layout, typography, color, or motion reference for a question that falls in that domain. Apply the rules here without depending on that skill being installed.

## Choose direction with real content

If the visual direction is already decided, apply it and move on. Do not force a style exercise over an approved design.

If it remains open, compare a small set of genuinely different directions using the same real content:

- the actual title slide, with the real title, language, names, and marks;
- the hardest content slide, including its real chart, code, table, diagram, or long mixed-language text;
- any state whose interaction or media treatment materially changes the composition.

A direction succeeds when both the welcoming case and the constrained case retain the intended hierarchy and evidence. Do not select from empty wireframes, placeholder prose, or a title slide alone. Keep the current design intact until a replacement is chosen when the task is a comparison rather than an authorized redesign.

## Establish role-based hierarchy

Assign every visible element a job before styling it:

- **Layout** creates reading order, grouping, alignment, and the relationship between claim and evidence.
- **Type** distinguishes display, slide title, body, label, numeric data, code, and source text.
- **Code** preserves syntax, indentation, identifiers, and the exact fragment needed for the point.
- **Captions** explain what an image, chart, demo, or table proves and carry nearby qualifications or source cues.

Make the message and its evidence easier to find than decoration or navigation chrome. Use shared edges, spacing, scale, weight, and semantic color together; do not ask font size alone to carry the hierarchy. Keep captions and sources readable in the rendered context rather than treating them as ornamental fine print.

Use structure that fits the content: comparison for alternatives, sequence for process, aligned rows for values, a diagram for relationships, and a chart for quantitative patterns. Repeated visual components earn their place when they preserve a repeated meaning, not merely a repeated rectangle.

## Compose with intentional space

Treat empty space as pacing, grouping, and emphasis. A quiet region is valid when it directs attention or gives a speaker room to explain. Rebalance when content has become unintentionally tiny, stranded, or pushed to one edge merely to protect a decorative composition.

Compose the title, evidence, and explanation as a deliberate visual group with room around and within it. Inspect that group's optical position on the canvas. A repeated top-aligned header-and-card scaffold can leave every slide cramped above an empty lower half; distributing equal gaps to fill the screen is not the remedy. Set proximity by meaning, then place the group according to the slide's purpose. A comparison, a code explanation, and a quiet conclusion need not share the same vertical skeleton.

Preserve the chosen template's badges, rules, illustrations, textures, and background motifs: establishing its visual identity is a legitimate compositional role. Do not strip them merely because they are decorative. For new additions, prefer the template's own vocabulary over arbitrary marks or extra containers. Adjust a motif only when it obscures required content or the user asks to change it; retain the overall design rather than flattening it into generic minimalism.

Split or reshape content when the hierarchy no longer reads. Preserve all required information. Never make an overflow defect appear solved by shrinking the entire slide or hiding required content with `overflow: hidden`, a mask, a crop, or a line clamp.

Distinguish that failure from deliberate clipping at the boundary of a fixed 16:9 stage. Background bleeds, decorative off-canvas shapes, and media intended to fill a frame may be clipped when no meaningful information is lost and the result remains correct at the supported stage sizes and exports.

## Design for language and fonts

Use the deck's actual language from the beginning. Exercise Korean and other CJK scripts as first-class content, including punctuation, line breaking, vertical metrics, emphasis, and line spacing. English word-count heuristics do not predict CJK density or reading time.

Render realistic combinations such as a Korean sentence containing an English product name, a version number, and a long API or file identifier. Preserve the exact spelling and case of code and identifiers. Provide a wrapping or layout treatment that keeps the full value available; do not silently abbreviate a load-bearing identifier to make it fit.

For authored headings and short statements, choose line breaks at meaningful phrase boundaries. Keep numbers with their units, avoid stranded particles or one-character final lines, and use script-appropriate wrapping rather than breaking every Korean syllable freely. Adjust wording or measure before compressing tracking or reducing type. Inspect the resulting lines as an image at the actual viewing size; balanced CSS wrapping alone cannot judge meaning.

Choose or retain fonts by role, script coverage, legibility, and delivery constraints:

- verify that the font files cover every language, symbol, weight, and code glyph used;
- define a deliberate fallback stack and inspect the fallback result rather than trusting the declaration;
- avoid depending on synthetic emphasis where it erases the intended distinction;
- confirm the license permits the planned embedding, redistribution, web serving, and exported deliverables;
- keep an offline path free of remote font requests when offline use is required.

A brand font may remain for Latin display text while a compatible CJK face serves Korean or Japanese. Judge the pair by visible weight, scale, baseline, and tone in the actual slide, not by family names.

## Use color semantically

Give color stable roles across the deck: emphasis, categories, states, comparison sides, code concepts, or diagram entities. Reuse a role consistently wherever the same meaning returns. Do not encode a conclusion, status, or selected state by hue alone; pair it with text, shape, position, pattern, or another persistent cue.

Preserve brand seeds where required, then choose readable foreground and surface pairings for the real theme and projector context. Measure applicable contrast on the rendered background when the result is load-bearing; a token name or attractive palette is not evidence.

Avoid decorative color that competes with data. Legends, labels, annotations, and explanatory prose must agree on what each semantic color means.

## Make charts truthful

Select a chart only when its visual encoding answers the slide's question more clearly than direct values or a table. Preserve the source data and comparison basis.

Cross-check the headline, prominent values, and calculations against the same quantity and scenario. Baseline totals are not savings, a mean is not a tail percentile, and the estimated value of freed time is not cash received. Make those distinctions visible where the audience reads the numbers, not only in distant notes.

For every quantitative graphic, make the following observable in the slide or its immediately associated explanation:

- what each axis or encoding represents;
- the exact unit, time range, population, and aggregation that determine interpretation;
- the baseline and scale, including any truncation, log scale, normalization, or dual axis;
- which values are measured, estimated, projected, illustrative, or missing;
- the source and any qualification needed to avoid an unsupported conclusion.

Keep ticks and labels accurate to the plotted values. Do not distort geometry, reorder categories, omit an inconvenient series, or crop an axis merely to strengthen the story. When direct labels are clearer than a legend, use them; when uncertainty matters, show or state it.

## Separate stage and reading surfaces

For a speaker-led presentation, compose for the fixed 16:9 stage and its actual viewing distance. Preserve stable framing as the viewport scales; a narrow browser may show the whole stage at reduced size without becoming a readable mobile document.

For self-contained reading, ensure the delivered reading surface supports comfortable inspection of prose, captions, sources, code, and figures. If mobile reading is required, provide responsive or document-like reading behavior, or a suitable handout derived from the same editable source. Do not claim mobile readability because a miniature 16:9 slide fits within the phone width.

Treat the two contracts separately: stage integrity means the composition remains complete and correctly framed; mobile reading means the content can be read and navigated without impractical zooming or horizontal hunting.

## Keep the deck perceivable and controllable

Maintain a coherent reading order and heading structure. Provide meaningful alternatives for informative images, diagrams, and charts in the form supported by the engine and deliverable. Keep essential text as text where the format permits it.

Ensure controls and linked content have perceivable names, visible focus, and non-color state cues. Motion must support the explanation rather than gate it. Under reduced-motion preference, remove or simplify nonessential movement while preserving the same information, final state, and navigation. Supply captions, transcripts, posters, or static summaries when media carries meaning that would otherwise disappear.

## Completion contract

A visual direction is ready to build when the actual title and hardest content slide demonstrate a consistent system; every required item remains readable and reachable; fonts and fallback cover the content and delivery rights; color and chart encodings retain their meaning; stage and reading requirements are not conflated; and the static or reduced-motion experience communicates the same essential result.

These are observable, purpose-specific outcomes. Do not turn them into arbitrary quotas for words, cards, typefaces, code lines, font sizes, or empty-space ratios.
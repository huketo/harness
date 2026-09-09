# Portable HTML slides

Use plain HTML when the delivery contract calls for one file, no build, or a deliberately small browser deck. Preserve an existing HTML deck's architecture when revising it. This reference defines the necessary behavior rather than prescribing a new reusable slide engine.

## Choose the presentation surface

Separate the authored slide canvas from the surrounding controls. Use the requested aspect ratio, normally 16:9, with uniform scaling when presentation layout must stay fixed. Letterboxing is acceptable; shrinking the entire canvas does not make dense text readable on a phone.

For reading mode, use a self-contained page/slide layout with enough explanatory text. If narrow-screen reading is required, provide an intentional reading view with normal document flow or an equivalent handout. Derive it from the same content rather than duplicating facts in two separately maintained DOM trees. Do not force portrait readers to consume tiny text merely because the deck technically fits.

Recheck intrinsic sizing when a fixed canvas becomes an auto-height reading page. Percentage grid gaps and centered track alignment can create vertical collisions even when the page has no horizontal overflow. Inspect adjacent headings, lists, diagrams, and controls in the actual narrow view; use flow-relative spacing where the container height is indefinite.

Choose a design size and role-based typography consistently. Test its actual scaled size. Keep controls outside the canvas and usable independently of slide scaling. An overflow boundary may protect the stage; it must not hide required content that failed to fit.

## Single-file and offline mean different things

For a promised single-file offline deck, the delivered HTML must contain or avoid every dependency:

- Inline CSS and JavaScript. Do not load a CDN presentation library or a remote chart renderer.
- Use inline SVG, embedded data, or appropriately sized data-URI media. Preserve SVG text and semantics where feasible.
- Use a font stack available on the target platform, or embed licensed fonts covering the required glyphs. Do not silently depend on Google Fonts, Fontshare, or a network-loaded CJK subset.
- Inspect CSS `url()`, `@import`, image/video/source URLs, module imports, workers, and runtime fetches—not just `<script src>` and `<img src>`.
- Distinguish ordinary reference hyperlinks from assets that must load to display the deck. Offline external links can remain visibly identified references, but the content must not require opening them.

A large video may make one-file delivery impractical. If the requested constraints cannot coexist, explain the size/format tradeoff before replacing one with a folder bundle. Do not label `index.html` plus a sidecar asset folder as a self-contained file.

## Navigation and focus

Use semantic sections with meaningful headings and a labelled control region. Implement only the navigation the deck needs, but make the advertised controls real:

- Previous/next buttons and keyboard movement work at the first and last slide without wrapping unexpectedly.
- A reloadable location identifies the current slide when deep links are promised; update the URL on movement and handle back/forward navigation consistently.
- Ignore deck shortcuts while an input, textarea, select, or editable region owns focus, and do not hijack modified browser shortcuts. Keep normal Tab traversal.
- Inactive slides must not expose interactive controls to the tab order or assistive technology. Use native visibility/inert mechanisms compatible with the chosen layout; a transparent slide is not necessarily inactive.
- Ensure focus is not stranded inside a slide that becomes hidden. Keep control focus stable or move it to an appropriate visible target. Announce changes without reading the entire deck on every keypress.
- Support touch if promised, without making it the only way to move or suppressing browser zoom. Avoid wheel interception unless the presentation explicitly requires it and reading/scrollable regions remain usable.

Use animation to explain sequence, with a meaningful reduced-motion state. Decorative motion must not delay reading. If a slide has reveal steps, define how next/previous and export map to those steps rather than scattering unrelated timers.

Do not add an inline editor by default. If editing is requested, define persistence and export behavior explicitly. A localStorage copy is not the user's saved HTML file, and a download must preserve the edited content while excluding transient editor UI.

## Notes and private material

Keep presentation notes associated with each slide in the editable source. Use the existing project's presenter mechanism, or provide a clearly named companion notes artifact when one is requested and compatible with the output contract. Do not promise a presenter console that was not implemented.

HTML comments and hidden elements are delivered to anyone who receives the file. Remove private speaker notes from the shared variant when they are not authorized for publication. Hiding them with CSS is not privacy protection.

## Printing and PDF

Use an intentional print stylesheet and the browser's PDF path where available:

- Print every intended slide in order, normally one slide per page for a presentation export.
- Remove viewport transforms, navigation chrome, and interactive-only overlays in print. Restore all intended slides and the selected reveal state.
- Set a consistent page size/margin and avoid an extra blank final page.
- Replace video or interaction with its meaningful static image and explanation.
- Preserve text as text where the browser supports it. A screenshot assembled into a PDF is raster output; disclose its search/selectability limitations.

Do not infer PDF correctness from a print CSS declaration. Open the generated PDF, inspect rendered pages, count them, and check essential text and glyphs. Browser defaults such as headers, margins, paper size, and background printing can change the result.

## Conversion and completion

For an existing deck, preserve its meaningful text, figures, notes, ordering, and brand. Split an overloaded slide before reducing text below a readable size; keep caveats beside their claims. Reconstruct unsupported source objects honestly rather than silently dropping them.

Apply [Verification](verification.md). For single-file offline delivery, open the actual final file in a fresh browser context with network access disabled, exercise movement and any reading view, and verify required resources. A warm cache or an already loaded page does not prove offline operation. Report the verified browser/platform; system-font availability on another machine remains a separate assumption.

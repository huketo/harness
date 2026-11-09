# Verify

A build that exits 0 proves only that it built. Verification is looking at every state the audience or reader will see, in the files actually delivered.

## deck.html

A reading deck still builds `deck.html` as the input to `check.mjs`; it is not delivered.

```bash
node tools/check.mjs                  # .cache/check/: one PNG per state, index.html contact sheet, report.json
node tools/check.mjs --size 1920x1080 # the projector size, when the brief names one
```

`check.mjs` opens `deck.html` from disk with networking off, walks every slide and click with ArrowRight, and exits 1 when anything besides the file itself tries to load, a load fails, the page throws, or text leaves the slide or is clipped behind `overflow`. Fix each finding at its source, rebuild, and rerun until it exits 0.

Then look, because a clean report is not a good slide:

1. Open every state PNG at full size. For each: the title and evidence the outline promised are there; Korean titles break at phrases; nothing overlaps or hides behind another layer; future click content is hidden and revealed content is fully visible; fonts are the `Deck` families (`report.json` lists each slide's families and each face's load status).
2. Read every title, caption, and takeaway against the values its own chart or table shows: a crossover month, a total, a "faster" or "cheaper" claim. A title that says more than the plotted numbers is a defect even when the chart is right.
3. Open the contact sheet for the deck as a whole: composition varies with the message, density is even, the design reads as one system.
4. Open `deck.html#/presenter/1` and confirm notes belong to their slides and follow `[click]` steps.
5. Check that notes and visible text contain nothing the audience should not receive: internal names, credentials, private figures.

## deck.pdf

Render the pages (`pdftoppm -r 60 -png deck.pdf page` or a browser) and inspect every one:

- page count: one per slide plus one per extra click step on `pdf: steps` slides;
- final states complete: conclusions, code without dimming, chart labels, source lines;
- video slides show the poster and fallback text; stateful components show their print state;
- text is selectable and Korean glyphs are real text, not boxes or images.

## Report

State what was observed: the browser and size used, the number of states checked, the PDF page count, each defect found with its fix and the same-state recheck, and anything not checked (a projector, another browser, a screen reader). Defects stay open until the same slide, click, and page show them fixed.

**Done** when `check.mjs` exits 0, every state and page has been looked at, and the report names what was and was not verified.

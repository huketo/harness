# Package

Two deliverables, both built from the same `slides.md`.

## deck.html

```bash
npm run build:html        # node tools/package.mjs html
```

The script refuses to run while any `⟨…⟩` placeholder remains, inlines each file under `public/` that the deck uses (once for every reference from slides and components; a CSS `url()` reference adds one more copy), subsets the fonts to the characters the deck's sources use, builds with the single-file config, embeds `fonts/LICENSES.txt` as `<script type="text/plain" id="font-licenses">`, and fails if the page still loads a remote script, stylesheet, image, media file, or `url()`.

**Budget: 30 MB.** Past it the script exits with code 2. Compress media first (shorter clip, lower bitrate, smaller poster). If the deck still needs more, ask the person; rerun with `--allow-large` only after they agree.

`deck.html` is the presentation file (built in every mode, delivered when `brief.md` lists it): arrow keys and clicks, `#/<n>` addresses, presenter view at `#/presenter/<n>`. It opens by double-click with no network. A text edit means rebuilding: the font subset follows the text.

## deck.pdf

```bash
npm run build:pdf         # node tools/package.mjs pdf [--executable-path <chromium>]
```

Built when the mode is reading or both, or the person asks. Every slide is one page at its final click state; a slide whose frontmatter says `pdf: steps` becomes one page per click step. The export runs headless Chromium through `playwright-chromium`; on a machine where its browser download is unwanted, install with `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` and pass `--executable-path` to an existing Chromium.

A PDF is static, so interaction has to resolve into something printable:

- clicks: the final state shows everything; mark `pdf: steps` only where the sequence is the point;
- video: the poster and `AsDemoMedia`'s fallback text carry the takeaway;
- stateful components: the state shown under `isPrintMode` (BUILD.md);
- hover, input, and scrolling content: visible in the final state or not essential.

Fonts in the PDF are the full files, subset by Chromium.

**Done** when every deliverable in `brief.md` exists, was built from the current sources, and the commands above exited 0.

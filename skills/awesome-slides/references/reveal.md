# Native Reveal.js deck

Use Reveal when its native fragments, speaker view, HTML authoring or an existing Reveal project is the right fit. This is a six-slide npm/Vite engine starter with synthetic Korean content, not a port of the 34 HTML themes or a standalone-file promise. For a selected visual theme, inspect its actual templates and implement those compositions as native Reveal sections; the starter's palette alone does not reproduce that design.

## Generate, install, run

Requires Node 20.19+ in the 20.x line or Node 22.12+ and npm. Exact direct versions live in the starter's `package.json`: Reveal 5.2.1 and Vite 8.2.2. Vite 8.2.2 was available in the npm registry when selected; this is a reproducible pin, not an instruction to chase latest on each run.

```sh
node <skill>/scripts/new-deck.mjs reveal ./review-flow --style technical
cd review-flow
npm install
npm run dev
```

Open the local address Vite prints. Keep the generated `package-lock.json` with the authored deck; subsequent installs use `npm ci`. No global package is needed. For a production directory:

```sh
npm run build
npm run preview
```

The build uses relative asset paths and writes `dist/`. Share/serve the whole directory, not only `dist/index.html`; modules and styles remain separate. Initial npm installation requires registry access. A built local bundle can run with outbound networking blocked while served over local HTTP, but opening it as `file://` is not the supported delivery path. Retain dependency licenses/notices when distributing the bundle.

## Edit native files

- `index.html`: authoritative slide content, section IDs, HTML fragments and `<aside class="notes">` speaker notes.
- `main.js`: native Reveal initialization and locally imported Notes/Highlight plugins. Plugin files use the **5.2.1** package paths `reveal.js/plugin/notes/notes.esm.js` and `reveal.js/plugin/highlight/highlight.esm.js`; do not replace these with paths from a newer major's documentation.
- `theme.css`: selected shared style copied by the generator. The HTML links it before `deck.css`.
- `deck.css`: maps shared `--as-*` tokens to native `--r-*` roles and implements purposeful list, comparison, flow, sequence, title and closing layouts. Core Reveal CSS is imported by `main.js`; the authored stylesheet is imported afterward so it wins the cascade.

Change content directly rather than adding a framework-independent slide schema. Each `section.page` is authored at 1280×720. Retain `word-break: keep-all` and balanced phrase-level headings; inspect actual Korean wrapping under the chosen font.

```html
<section class="page" id="decision">
  <header><p class="kicker">선택</p><h2>완료 조건을 먼저 맞춥니다</h2></header>
  <p>요청자가 확인할 범위를 제시합니다.</p>
  <p class="fragment" data-fragment-index="0">검토자가 조건에 따라 승인하거나 수정 이유를 남깁니다.</p>
  <aside class="notes">첫 문장을 설명한 뒤 다음 단계로 넘깁니다.</aside>
</section>
```

A fragment should reveal a dependency or sequence, not manufacture suspense around every label. The starter progressively discloses diagnostic causes and experiment steps. Native `hash`, `fragmentInURL` and one-based indices preserve addressable slide/reveal state. Use Reveal's controls, arrows, Space, Home/End and overview rather than a second custom navigation controller. Press `S` for the Notes presenter window and `?` for keyboard help. Allow the local speaker popup when the browser blocks it.

For code, Highlight is already registered. Add real, source-grounded code in ordinary native markup; omit `data-noescape` unless deliberately trusting HTML:

```html
<pre><code class="language-js" data-trim data-line-numbers="1|2-3">
const request = { owner: 'reviewer', scope: 'changed behavior' };
const ready = Boolean(request.owner && request.scope);
console.log(ready);
</code></pre>
```

This is illustrative code, not a claim about a repository API. Preserve its source citation when substituting production code. Style code through the token-mapped `.hljs` rules in `deck.css` rather than a network stylesheet.

## Web, motion and narrow viewing

Reduced motion switches the native transition to `none` and removes fragment animation; information remains available. Presenter notes are source data delivered to recipients, even when invisible on screen.

The starter deliberately disables automatic narrow-screen scroll activation. Reveal's `?view=scroll` remains an optional native scroll view, but it preserves a scaled slide canvas: **it is not proof of readable 390px body text**. For an actual phone handout, use the [HTML reading route](html.md) or an intentionally authored reading document and keep claims synchronized from the maintained source. Do not advertise this Reveal starter as a responsive reading handout.

The flow slide is already a static semantic ordered list with directional arrows and a complete caption. For future animation or video, preserve an adjacent static explanation or print poster. Keep sources and native fragment markup after export.

## Print/export

While the dev or preview server is running, open its root URL with `?print-pdf`. Wait for Reveal layout and fonts to finish, then use Chromium's print dialog: Save as PDF, landscape, no margins, no browser headers/footers, background graphics enabled. Keep CSS page sizing. Native Reveal calculates page dimensions from its configured 1280×720 stage.

`pdfSeparateFragments: false` prints a slide's fragments together in their final visible state. The stock six-slide deck should therefore yield six slide pages. The configuration does not force `pdfMaxPagesPerSlide: 1`, because that could conceal overfull content; correct the layout if extra pages appear.

For a separate-page notes edition, open `?print-pdf&notes`. `main.js` enables native `showNotes: 'separate-page'` only when that explicit query is present. Keep the ordinary presentation PDF separate from this notes edition. Review speaker notes for sharing authority before sending either source or notes PDF.

A browser automation PDF call must navigate to the **print-pdf URL**, wait for the print layout (including `.pdf-page` elements) and fonts, then use `page.pdf({ path: 'deck.pdf', preferCSSPageSize: true, printBackground: true })`. Calling PDF on the ordinary presentation URL is not this export path.

## Verification boundary

Run `npm install`/`npm ci` and `npm run build`, then exercise the served build. Inspect all slides and fragments, direct fragment links, keyboard/focus, overview, `S` notes, code highlighting if used, reduced motion and the actual generated PDF. Count slide pages and inspect glyphs/overflow. A successful bundle does not prove layout or presenter behavior. Network-blocked local HTTP validates absence of CDN dependencies, not standalone-file portability. Use [Verification](verification.md) for the full delivery checks.

## Sources and reuse

The native configuration, section/fragment/notes patterns, CSS-variable mapping and export recipe adapt [content-skills](https://github.com/vstorm-co/content-skills/tree/5138a11b1e3407ea3352d4010cbe33233bdeb01c), `skills/content-presentation/frameworks/reveal-js.md` (MIT, Vstorm). The original CDN option was replaced with pinned local modules, reduced-motion handling and original synthetic layouts/content. Full license: [Reveal asset notice](../assets/reveal/THIRD-PARTY-NOTICES.txt).

Version-grounded paths: [Reveal 5.2.1 package](https://github.com/hakimel/reveal.js/blob/5.2.1/package.json) and [plugin build outputs](https://github.com/hakimel/reveal.js/blob/5.2.1/gulpfile.js). Native behavior references: [initialization](https://revealjs.com/initialization/), [plugins](https://revealjs.com/plugins/), [PDF export](https://revealjs.com/pdf-export/), [scroll view](https://revealjs.com/scroll-view/). Consult the installed version's files before applying newer documentation syntax.

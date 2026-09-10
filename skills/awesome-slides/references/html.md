# HTML: clone a real theme and deliver it

Read [Style selection](style-selection.md), inspect the [catalog](../assets/template-library/index.json), and choose an actual theme. The library is a pinned source dependency: 34 theme-specific HTML/CSS/layout systems, not one runtime recolored 34 ways.

## Generate the editable starting point

```bash
node <skill-directory>/scripts/new-deck.mjs html ./my-deck --template soft-editorial
```

Open `my-deck/template.html` in a real browser. The command copies the selected folder, including its `design.md`, `template.json`, and sibling assets. Where the HTML imports `deck-stage.js` but the folder omits it, the command adds the bundled shared runtime. It preserves the upstream filename and content, refuses an existing destination, and copies the source license and origin record. It does not install tools, fetch fonts, replace demo claims, or certify offline operation.

Read the generated design guide and actual layouts before editing. Replace the demo content; retain the template's hierarchy, grids, motifs, and useful runtime. A single common title/list/comparison scaffold is not an acceptable replacement for the chosen theme. See [Style selection](style-selection.md) for duplication, extension, language, and native-engine ports.

## Inspect the owning runtime

Templates differ: some use the `<deck-stage>` custom element and others use inline navigation or viewport layouts. Inspect the selected template's script, current-slide state, visibility, fragment format, controls, and print CSS. Retain that mechanism rather than layering a second generic controller on top.

Before expanding, exercise:

- next/previous buttons and left/right arrows, including clicking a button and then using arrows without blurring it;
- first/last boundaries, reload with the current fragment, and browser back/forward where supported;
- focus when a slide becomes hidden, visible focus indicators, and native Enter/Space behavior on controls;
- reduced motion without hiding the final content;
- notes and whether they belong in the shared artifact.

Correct unsupported or broken behavior in the selected runtime when the deliverable needs it. Do not claim every upstream template already meets every accessibility, URL, reading, and export contract. Keep text-input editing keys intact. Remove inactive presentation content from keyboard access; restore it in reading/print modes. Preserve visible graph/chart labels and a static final state for reveals.

## Local fonts without losing the design

Many upstream templates load Google Fonts. Keep the named Latin families and add a matching licensed CJK family for Korean; do not silently replace the theme's display face with a system sans because its font request failed.

For an offline artifact:

1. Identify the exact families, styles, and weights used in the selected template.
2. Obtain the font files from their official distribution and retain the font-specific license. Font rights are separate from the template MIT license.
3. Store the required files under the generated deck's own `fonts/` and replace the remote stylesheet with local `@font-face` declarations. No global font installation is implied.
4. Keep original family names where possible. Add the chosen Korean face to the matching serif/sans/mono role; inspect actual mixed-script rendering.
5. Load the deck in a new offline browser context. A warm browser cache is not proof that local fonts work.

A local-face declaration is ordinary CSS, not a second theme system:

```css
@font-face {
  font-family: "Chosen Display";
  src: url("./fonts/chosen-display.woff2") format("woff2");
  font-weight: 500;
  font-style: normal;
  font-display: swap;
}
```

Use the real file, family, weight, and license; this declaration is syntax guidance, not a supplied font.

## Single-file packaging

Keep the editable folder as the source. When the user requires one HTML file, derive it after authoring: inline the selected runtime script, stylesheet rules, licensed font data, and required local image/SVG resources into that HTML. Resolve nested CSS `url()` dependencies too. Preserve copyright and font notices in the distributed file; do not assume a sibling notice travels with a single-file attachment.

No online font stylesheet, script import, external image, CDN icon, or fetched data may remain required for the offline path. Do not replace missing real media with a fake player. Use the user's actual media or an honest static explanation/poster as agreed. Open the final single file in a fresh browser context with networking disabled before navigation and record requests/errors.

This packaging is a delivery step, not a reason to rewrite the selected theme's layouts or maintain a second copy of its claims.

## Reading view

A miniature 16:9 stage is not a readable phone handout. When reading is required, derive normal-flow content from the same slide DOM: release absolute placement at the reading breakpoint, stack related regions in source order, preserve tables/labels/caveats and notes as appropriate, and expose all reveal content. Keep the theme's typography roles, palette, motifs, and grouping while changing geometry.

For complex template-specific positioning, inspect and adapt the affected selectors rather than applying a universal reset that destroys the design. A local horizontal code/table scroller can be appropriate; the entire document must not overflow at the required 390px width. Do not duplicate and separately edit the presentation and reading claims. Reading mode keeps normal scrolling and keyboard semantics.

## PDF from the actual theme

Inspect the template's own print mechanism first. Some runtimes use custom-element/shadow-DOM layout; body-level generic print overrides may not reach it. In print mode, make every intended slide and final reveal visible, disable stage transforms where needed, use the authored page dimensions, and hide navigation and private notes. Preserve the theme's visual composition and vector/text content rather than screenshotting every page.

For a browser page already opened and ready in the environment's browser tool, Puppeteer supports:

```js
await page.evaluate(() => document.fonts.ready)
await page.pdf({ path: outputPath, preferCSSPageSize: true, printBackground: true })
```

The selected template must provide correct page-size/break styles; these options alone do not repair print layout. Use an available browser rather than downloading or globally installing one by default.

Open the resulting PDF. Check page count/order, selectable Korean text, final reveal state, source caveats, font identity, diagrams, cropping, and blank pages. Verify both the authored cover and densest slide, then every remaining page. [Verification](verification.md) owns the full contract.

## Source and adoption boundary

The complete sources are copied from [beautiful-html-templates at e5e204f](https://github.com/zarazhangrui/beautiful-html-templates/tree/e5e204fb1f3b06290846e7dcd7aceddabeceec8c), MIT, copyright 2026 Zara Zhang. [ORIGIN.json](../assets/template-library/ORIGIN.json) records the copied paths and limitations; [LICENSE](../assets/template-library/LICENSE) retains the exact terms. Selection and adaptation guidance here is local integration. The upstream operational guide's unconditional questions and preview gates do not override this environment's authority policy or a user's already settled brief.

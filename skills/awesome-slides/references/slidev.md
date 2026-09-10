# Slidev: generate, author, present, export

Use this recipe for a new Markdown-first deck. For an existing deck, keep its entry, lockfile, commands, layouts, and asset conventions; change only what the request requires.

## Generate a working project

Run from the repository containing this skill; substitute the installed skill path when necessary:

```bash
node skills/awesome-slides/scripts/new-deck.mjs slidev ./my-talk --style editorial
cd my-talk
npm install
npm run dev -- --port 3030
```

The generator copies the native starter and the selected stylesheet to `theme.css`. Choose `editorial`, `signal`, or `technical`; do not copy the engine directory alone and leave its theme import unresolved. The starter pins its three direct runtime/toolchain dependencies. Keep the generated `package-lock.json` with the editable deck; use `npm ci` for subsequent reproduction. `npm install` needs registry access and may run dependency lifecycle scripts.

Start the dev command through the environment's supervised-process mechanism. Observe the ready URL before opening it. This six-slide, six-minute Korean showcase contains synthetic data, not reusable business claims. Replace its assertions, figures, caveats, and notes together.

## Use the native structure

| File | Edit here |
| --- | --- |
| `slides.md` | Narrative, frontmatter, component inputs, notes, click order |
| `layouts/AsCover.vue` | Asymmetric title and decision aside |
| `layouts/AsEvidence.vue` | Header, full-width evidence, source/caveat footer |
| `layouts/AsSplit.vue` | Header, code/table left, interpretation right, footer |
| `components/AsBreakdown.vue` | Comparable duration totals and segment labels |
| `components/AsStageFlow.vue` | Ordered stages, detail, metric, highlighted intervention |
| `components/AsCaseStory.vue` | Observation → interpretation → change → verification |
| `snippets/admission.ts` | Editable code imported into the deck |
| `setup/shiki.ts` | Light/dark syntax palettes |
| `style.css`, `theme.css` | Deck-scoped role styles and selected brand tokens |

Slidev discovers `layouts/`, `components/`, `setup/`, and `style.css` natively. There is no adapter or intermediate slide schema. The `As` prefix avoids collisions with theme layouts and utility classes. Use built-in `default`, `center`, `two-cols`, `image-right`, `quote`, or `section` when their composition fits; the default theme's `cover` is not `AsCover`.

When porting an HTML theme, prefix its layout classes and scope typography under the custom `.slidev-layout` root. Do not carry generic `.cover`, `.code`, or `.timeline` names into frontmatter unchanged: the active Slidev theme or utilities can override their alignment, margins, and opacity. Inspect computed styles on the visible slide, then verify the rendered export at the deck's actual aspect ratio.

A custom layout uses native named slots:

```md
---
layout: AsSplit
---

::header::

# The assertion both columns support

::default::

Evidence or imported code.

::right::

Interpretation, not a duplicate of the evidence.

::footer::

Source, population, and material caveat.

<!--
01:00–02:00 · Explain the evidence, then the interpretation.
-->
```

Keep notes in the final comment block of each slide, after any scoped style. Check the rendered slide count rather than counting `---`: the delimiter also opens YAML. For a title in another language, update `htmlAttrs.lang` and the custom layouts' `lang` attributes.

## Reuse the demonstrated components

### Compare time and its parts

```html
<AsBreakdown
  caption="Synthetic trace examples · same duration scale"
  unit="ms"
  :scenarios="[
    { title: 'Before', segments: [{ name: 'Queue', value: 700 }, { name: 'Work', value: 300 }] },
    { title: 'After', segments: [{ name: 'Queue', value: 200 }, { name: 'Work', value: 300 }] }
  ]"
/>
```

The longest total sets one common scale; totals and labels are derived from the same values. Unlike separately normalized stacks, shorter totals remain visibly shorter. Supply nonnegative finite values in the same unit, unique scenario/segment names, and the same segment order across scenarios. Use two segments here: the first is accented and the remaining segment is muted. A negative/diverging chart or a many-series legend needs a different visual, not misleading input to this component. Zero-length segments retain their text labels. Separate observations are not a distribution, average, or percentile.

### Locate an intervention in a process

```html
<AsStageFlow
  :stages="[
    { id: 'admit', name: '수락 판단', detail: '대기열 여유 확인', metric: 'queue depth' },
    { id: 'work', name: '작업 처리', detail: '수락된 요청 실행', metric: 'service time' },
    { id: 'observe', name: '결과 확인', detail: '재시도까지 추적', metric: 'completion time' }
  ]"
  :highlight="['admit']"
/>
```

Use three or four short stages at the authored canvas size. IDs are unique; highlights identify the intervention without hiding other stages. Arrows encode order, not measured throughput. Branches and loops need an explicit diagram instead of a falsely linear sequence.

### Keep a case's reasoning inspectable

```html
<AsCaseStory
  saw="대기 700 ms, 처리 300 ms를 관찰했다."
  meant="이 요청에서는 대기가 전체의 70%다."
  changed="대기열 한도를 두고 재시도를 안내한다."
  verified="동일 부하에서 완료 시간과 거절률을 비교한다."
  rollback="완료 시간이 악화되면 이전 정책으로 돌아간다."
/>
```

These props are plain text, not HTML. State whether `verified` describes a completed check or a planned experiment; the showcase uses a plan and labels it visibly. Preserve observations separately from causal interpretations. The optional rollback belongs only where the case has a real reversal condition.

These three components adapt actual BaizeAI talks implementations. Keep `NOTICE.txt` and `licenses/` with redistributed sources; the content-skills template adaptation has its own MIT notice there.

## Code, reveal, and brand

Import code from the maintained file rather than duplicating it:

```md
<<< @/snippets/admission.ts {all|4-7|all}

<p v-click class="as-takeaway">Reveal the conclusion after inspecting the evidence.</p>
```

`@` is the project root. The code example starts with all lines, emphasizes the boundary branch, then returns to all lines. Update line ranges when the source changes. The breakdown slide has one conclusion reveal. Inspect those initial, intermediate, and final states using real navigation; do not force hidden classes visible. Default PDF export disables click animations and includes the complete static content.

`setup/shiki.ts` configures GitHub light/dark palettes through `defineShikiSetup` from `@slidev/types`. Keep syntax colors paired with their code background. The scoped code rule preserves readable dimmed context. If code is too wide, restructure the actual snippet or use full-width evidence; shrinking all text to fit is not a layout fix.

Edit `theme.css` for brand roles: `--as-bg`, `--as-fg`, `--as-muted`, `--as-accent`, `--as-line`, `--as-font`, `--as-mono`. `style.css` imports it and scopes slide typography under `.slidev-layout`, leaving presenter controls alone. Headings also use the optional `--as-font-display` and `--as-heading-weight` roles. The generator sets `colorSchema: dark` for Technical; if you change the brand background later, match `colorSchema` in `slides.md` so Shiki selects the appropriate palette. Set background, foreground, and accent together and inspect contrast in the actual render.

The starter disables remote font injection with `fonts.provider: none`. Use a Korean-capable local font stack; embed licensed fonts under `public/` and add `@font-face` only when delivery needs a stable face. Intentional title breaks belong at phrase boundaries; body copy uses Korean `keep-all` wrapping. Asset URLs under `public/` are rooted at `/`; check built URLs under any requested non-root base path. Use local text/SVG for diagrams; inspect computed SVG font sizes if UnoCSS interprets presentation attributes as utilities.

## Present and produce the deliverables

1. Open the ready dev URL and use next/previous through all six slides and their clicks. Open presenter mode from Slidev's toolbar; verify notes, timing, and click markers. `presenter: dev` keeps that UI development-only. Review all notes and metadata before sharing source.
2. Build the web bundle:

   ```bash
   npm run build
   # For a requested subpath:
   npm run build -- --base /my-talk/
   ```

   Serve `dist/` with an available local static server and check navigation and every local asset again. A dev-server success does not prove the build. This is a web application, not single-file HTML and not a readable 390px handout merely because its canvas scales down. A requested mobile reading deliverable needs a reading layout/output.
3. Export using a project-local browser dependency, after checking the installed CLI options:

   ```bash
   npx slidev export --help
   npm install --save-dev --save-exact playwright-chromium
   npm run export -- --output queue-decision.pdf
   ```

   The export dependency can download Chromium. If a compatible browser is already available, install with `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` and pass `--executable-path /path/to/chromium` to the export command. Record the resulting dependency and lockfile. Use the actual browser path, never a path copied from another workstation.
4. Inspect the actual PDF: six pages for this starter, complete conclusion on slide 2, full code/context on slide 4, Korean glyphs, chart totals, table caveats, and no clipping. Check selectable text rather than assuming text preservation. For click-step pages, invoke `npx slidev export slides.md --with-clicks --output click-steps.pdf` separately and count the result.
5. If PPTX is requested, `npx slidev export slides.md --format pptx --with-clicks false` produces slide images with presenter notes, **not editable text, shapes, or charts**. Route native PowerPoint editing requirements to a native authoring tool. PNG export is for thumbnails or explicit raster delivery, not a substitute for editable source.

For video, supply a print poster and static explanation using the installed version's video component API. Interactive charts need a visible static conclusion. Diagnose missing fonts/assets or readiness before adding waits; a successful export exit is not a visual pass.

Apply [Verification](verification.md) to the actual runtime and requested outputs. Deliver editable source, lockfile, license notices, requested exports, and exact verification scope. Exclude `node_modules`, browser caches, credentials, and workstation paths. Publication and persistent hosting require separate authority.

## Official Slidev integration

If the official `slidev` skill is installed, read its router and the branch reference needed by the feature. Its absence is not a blocker and does not authorize global installation. Use this precise fallback sequence against the installed version:

- For separators, notes, or configuration: [syntax](https://sli.dev/guide/syntax) and [official headmatter reference](https://github.com/slidevjs/slidev/blob/main/skills/slidev/references/core-headmatter.md); keep notes last and set language/fonts in headmatter.
- For components or layouts: [directory conventions](https://sli.dev/custom/directory-structure) and [writing layouts](https://sli.dev/guide/write-layout); create native Vue files and named slots as shown above.
- For code/reveals: [snippet imports](https://sli.dev/features/import-snippet), [Shiki setup](https://sli.dev/custom/config-highlighter), and [animations](https://sli.dev/guide/animations); exercise the specified click sequence.
- For an output change: [exporting](https://sli.dev/guide/exporting) or [hosting](https://sli.dev/guide/hosting), then the installed CLI's help; choose click and base-path policy explicitly.

The [official skill router](https://github.com/slidevjs/slidev/blob/main/skills/slidev/SKILL.md) indexes additional native features. Read the exact feature reference when adding one; current upstream examples may target a newer version than this pinned starter. If a URL resolves to unrelated content, locate the feature through the official navigation rather than treating a homepage as API evidence.

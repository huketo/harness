# Build

Write the whole deck in Slidev from `outline.md`, in the system `DESIGN.md` fixed.

## Starter

Preview with `npm run dev`, started through the environment's supervised-process mechanism; wait for its ready URL.

| Path | Role |
| --- | --- |
| `slides.md` | Headmatter and slides; every `⟨…⟩` is a placeholder that `build:html` refuses to ship |
| `theme.css` | Design tokens (`--as-*`) from DESIGN.md |
| `style.css` | Slide typography and role classes, scoped under `.slidev-layout` |
| `layouts/As*.vue` | `AsCover` (claim + aside), `AsEvidence` (header, evidence, source footer), `AsSplit` (evidence left, interpretation right) |
| `components/AsDemoMedia.vue` | Video with required poster, caption, and static fallback text |
| `setup/shiki.ts` | Code colors for light and dark |
| `snippets/` | Source files imported into code slides |
| `tools/` | `fonts.py`, `package.mjs`, `check.mjs`, `variants.mjs` |
| `vite.config.ts` | Single-file build and the `@deckfont` font path; leave as is |

Headmatter keeps `routerMode: hash`, `preloadImages: false`, `monaco: false`, `fonts.provider: none`, and the data-URI `favicon`: they make the single file work offline.

## Slides

- One slide per outline entry, in order; the title is the outline's assertion.
- Layouts: built-in `section`, `quote`, `center`, `two-cols`, `image-right`, or the `As*` layouts with named slots (`::header::`, `::right::`, `::footer::`). A purpose with no fitting layout gets a new `layouts/As<Name>.vue` in DESIGN.md's grammar; vary composition with the message rather than repeating one arrangement.
- Notes go in the final `<!-- -->` comment of each slide: the first sentence to say, the explanation, caveats, the transition. `[click]` markers keep notes in step with clicks. Reading decks put the explanation on the slide itself.
- Korean text: phrase-level line breaks in titles (`<br>` where the phrase ends), `word-break: keep-all` for body text, numbers kept with their units. When text does not fit, split the slide or reword; shrinking the type is not the fix.
- Slide-level `pdf: steps` in frontmatter marks the slides the outline exports as one PDF page per click.
- Claims, values, and labels come from `outline.md` exactly; synthetic and unverified material keeps its visible label.

## Motion and clicks

A click earns its place by answering the next question; items read together appear together. In the PDF every slide is rendered at its final click state unless marked `pdf: steps`, so:

- the conclusion is visible in the final state; `v-click.hide` and early `v-switch` slots disappear from it;
- a highlight sequence ends on `all` (`{all|4-7|all}`) so the final state is undimmed;
- one `v-mark` focal point per slide at most;
- transitions stay one style unless a structural break calls for another.

Syntax lives in the bundled official reference: [slidev-official/INDEX.md](slidev-official/INDEX.md) (animations, layouts, code, components, headmatter, exporting).

## Code, diagrams, media

- Code colors belong to the design: set `setup/shiki.ts` to themes, or token colors, that match DESIGN.md's palette rather than leaving the default GitHub themes on a designed deck.
- Import code from the real source (`<<< @/snippets/file.ts {all|2-3|all}`) instead of retyping it. Lines fit the column at presentation size; restructure the snippet or give it the full width.
- Magic Move (` ````md magic-move `) for code that changes across steps; keep shared tokens between steps.
- Diagrams: hand-written SVG or a small Vue component in DESIGN.md's style render offline and in PDF and stay small. ` ```mermaid ` and KaTeX (`$$…$$`) also work in the offline single file, but Mermaid adds about 6.5 MB to `deck.html` and draws in its own default style unless themed to DESIGN.md. PlantUML fetches from a server and is out.
- Monaco and live code execution are out: they do not survive the single file.
- Images and media: files under `public/` (subfolders allowed), referenced by root path: `<img src="/charts/a.svg" alt="…">`, `image: /photo.jpg` in frontmatter, `![…](/a.png)`. `build:html` inlines every file there; base64 makes each a third larger inside `deck.html`.
- Video: `<AsDemoMedia src="/clip.mp4" poster="/clip.jpg" caption="…" fallback="…" />`. Its video appears on a click, which the outline's `Clicks` counts. Keep clips short and compressed.
- Interactive components: any component with its own state renders its essential state when printed. Read `useNav().isPrintMode` from `@slidev/client` and show the final or summary state there.

**Done** when every outline entry is a slide with its notes, no `⟨…⟩` remains, and `npm run build:html` passes.

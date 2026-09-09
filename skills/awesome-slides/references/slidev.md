# Slidev authoring and delivery

Use this path for a new Markdown-first deck or an existing Slidev project. This reference owns generator and output boundaries, not a cached copy of every Slidev API.

## Establish the project

Inspect `package.json`, the lockfile, entry Markdown, theme, custom layouts, styles, and asset conventions. Run the project's commands rather than scaffolding over it. For a new deck, use a small project with an entry Markdown, the styles it needs, a package manifest, and local assets. Choose compatible package versions from the current official requirements and retain a lockfile. Install locally; do not install another skill or rewrite global tooling as an implicit prerequisite.

Keep dependencies that the deck actually uses. A theme, custom Vue component, icon collection, or drawing package is not mandatory simply because another example used it. Use the installed CLI's help for current arguments and its normal development/build/export commands.

Consult official references when a feature is needed:

- [Syntax](https://sli.dev/guide/syntax): slide separators, frontmatter, notes, code, diagrams, scoped styles.
- [Configuration](https://sli.dev/custom/): deck and per-slide options.
- [Animation](https://sli.dev/guide/animations): reveal steps and animation semantics.
- [Export](https://sli.dev/guide/exporting): format limitations and output options.
- [Hosting](https://sli.dev/guide/hosting): static builds and base paths.

If a URL returns a homepage or unrelated content, locate the corresponding section through the official navigation; do not treat the fallback page as feature documentation. An installed official Slidev skill can help, but its absence is not a reason to stop.

## Authoring boundaries

- A slide separator and the beginning of a slide's YAML frontmatter can both use `---`. Inspect the resulting slide count and layouts in the runtime instead of estimating by delimiter count.
- Place presentation notes in the final comment block of their slide, as specified by the syntax guide. Keep notes after slide-specific style or other content that would otherwise displace them. Check presenter view and exported notes if required.
- Use native code blocks with syntax highlighting and relevant-line emphasis. Code screenshots lose selectable text and should solve an actual delivery constraint rather than become the default.
- Use built-in diagrams or local SVG when they express the concept clearly. Inspect labels and arrows at the actual authored size; a syntactically valid diagram can still be illegible.
- Inspect computed SVG typography: utility-CSS engines can reinterpret presentation attributes such as `font-size="14"` as utilities. Use scoped CSS or inline styles when the rendered size disagrees with the SVG. Check syntax colors and dimmed code lines against the actual theme background; emphasis must not make context unreadable.
- Use reveal steps for explanatory order. Check the initial, intermediate, and final state; changing classes to force everything visible is not verification of the interaction.
- Keep shared role styles in the existing style/theme mechanism. Prefer a reusable layout to repeated arbitrary `zoom` values or absolute offsets that compensate for overstuffed slides.
- Set the deck language and choose fonts covering that language. Check how the installed version loads fonts; remote font injection can contradict offline requirements. A system fallback must still render the intended script legibly.
- Follow the framework's public-asset conventions. Check both development URLs and built assets under the intended non-root base path when one is required. Do not encode a workstation filesystem path in the deck.

## Output contracts

| Output | Required handling |
| --- | --- |
| Development preview | Start through the environment's supervised-process mechanism, choose an available port, and observe readiness. Deliver the actual URL. |
| Static web build | Run the build, serve the built directory locally, and check navigation and assets. A working dev server does not prove a portable production bundle. |
| PDF | Use the framework's exporter and inspect the actual PDF for page count, final state, text, glyphs, charts, and media substitutes. Prefer text-preserving output where available. |
| PPTX | Official Slidev export places slide images in PowerPoint and carries presenter notes. Tell the user this is not editable text/shapes. Route native editing requirements elsewhere. |
| PNG | Use for thumbnails or a requested raster deliverable, not as a silent replacement for an editable source or text-preserving PDF. |

At the time this reference was authored, the official CLI documents `slidev export`, `--format pptx`, and `--with-clicks`. Check the installed version's help before invoking. PDF defaults to one page per slide; the PPTX path enables click-step export by default. Set the desired policy deliberately and count the resulting pages instead of assuming output page count equals source slide count.

CLI export uses a browser dependency. Check for a compatible installed executable and the documented executable-path option before downloading another browser. Use project-local export dependencies and report unavailable codecs or fonts accurately. Wait for actual fonts, images, diagrams, and reveal completion; repeated blind sleep increases are not a fix for broken assets.

For videos, provide a representative poster and a concise static explanation, using the installed version's print-poster mechanism where supported. Confirm the static output contains them. For interactive charts and demos, provide the conclusion and the evidence necessary to understand it without interaction.

## Revision and conversion

Keep the existing entry and package scripts. Update relevant slides and any dependent note, reference, or summary that the changed claim affects. If a slide must split, preserve the user's intended ordering and cross-references. Avoid changing the theme or engine just to make an isolated layout easier.

When converting into Slidev, compare the rendered result to the original and inventory unsupported objects. A chart image can preserve appearance but not native chart editing or underlying data; state that distinction when it affects the requested deliverable.

## Completion

Apply [Verification](verification.md) to the actual runtime and each requested export. Deliver source and lockfile alongside exports when a project is required. Exclude `node_modules`, credentials, browser caches, and local absolute paths from the handoff. Explain whether the preview needs its local server; do not call a build directory a single-file offline HTML deck.

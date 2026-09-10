---
name: awesome-slides
description: "Create, improve, and convert presentation slide decks: technical talks, decision or proposal decks, teaching slides, and self-contained reading decks. Use for slide narrative, visual design, speaker notes, and requested web/PDF/PowerPoint deliverables. Not for ordinary web pages, non-slide documents, or isolated presentation-library syntax questions."
license: MIT
---

# Awesome slides

Start from a complete theme-specific template, not a generic deck recolored with tokens. This skill bundles 34 actual HTML themes with their original layouts, typography, motifs, metadata, and design guides. Choose one, clone its source, and replace its demonstration content with the user's evidence. Native engine components help implement the chosen design; they do not replace it.

## 1. Establish the brief and boundary

Identify creation, revision, or conversion. Inspect supplied materials and, for existing decks, their engine, styles, assets, notes, and export commands before choosing a path. Preserve existing user work and meaningful content; a restyle is not authority to change claims or discard inconvenient data.

Resolve audience, intended understanding or decision, duration, language, available evidence, brand, and delivery requirements from the request and source. Ask only for unresolved human-owned choices, together where related, through the environment's question policy. A missing brand folder does not block creation. Do not add routine approval gates when the user has already specified the work; honor requested outline or sample approval before dependent work.

Choose the delivery mode:

| Mode | Content contract |
| --- | --- |
| **Presentation** | Speaker-led. The slide supplies the main message and evidence; notes supply explanation, pacing, and transitions. |
| **Reading** | Self-contained. The reader can understand the context, figures, caveats, sources, and conclusion without hearing the speaker. |
| **Both** | Derive the presentation and reading material from one maintained content source. Do not maintain two independently edited versions of the same claims. |

Record the brief compactly in the project's existing working format. Avoid a new manifest or duplicated research file unless the task needs it. **Done:** the audience, mode, essential content, and required deliverables are known.

## 2. Choose the least complex suitable engine

| Situation | Route |
| --- | --- |
| Existing deck | Keep its engine and design system. Inspect its own documentation and commands; migrate only when requested or necessary for an agreed deliverable. |
| New deck without an engine requirement | **HTML theme library**: read [HTML](references/html.md), select a complete theme, and clone it. |
| Technical deck requiring native code reveals, motion, embedded demo media, presenter tooling, or an explicitly requested Slidev source | Read [Slidev](references/slidev.md). Preserve the selected theme's compositions when implementing native layouts. |
| One file or offline delivery | Use the selected HTML template, then localize/embed its fonts, runtime, and assets as described in [HTML](references/html.md). A copied upstream template is not yet an offline deliverable. |
| Reveal.js requested or already used | Read [Reveal.js](references/reveal.md); preserve the existing project or port the selected theme into native sections. |
| PowerPoint with editable text, shapes, or charts | Read [Native PPTX](references/officecli.md) and use `officecli`'s actual schema. Slidev's image-based PPTX export does not meet this requirement. |

For a theme-based deck, run `node <skill-directory>/scripts/new-deck.mjs html <new-directory> --template <catalog-slug>`. This clones the complete theme folder and any missing shared runtime; it refuses an existing destination and carries the source license. Native engine scaffolds remain available as `new-deck.mjs <slidev|reveal> <new-directory> --style <editorial|signal|technical>`, but those palette presets are not the HTML themes and do not constitute a finished visual design. Neither route installs dependencies or starts services.

For Slidev, the official feature documentation is bundled at `references/slidev-official/` (pinned to Slidev 52.19.1); the Slidev recipe routes to it. Read the exact feature reference instead of guessing syntax, and do not install a separate Slidev skill or global package. Presentation judgment and engine syntax are separate responsibilities. Do not rely on a theme name alone to supply the design. Existing Spectacle and other engines remain valid revision targets; do not migrate merely to use a bundled starter.

## 3. Ground and storyboard the content

Read [Narrative](references/narrative.md). For code, architecture, benchmarks, or demos, also read [Technical talks](references/technical-talks.md).

Use supplied material first. Research the uncertain factual claims at their primary sources; source-ground a library/API explanation in the relevant version or local code. Distinguish reported data, observed measurements, controlled demos, illustrative synthetic data, and unknowns. An attractive chart or screenshot is not evidence by itself.

Plan each slide's role, main message or assertion title, supporting evidence, visual form, note intent, and time allocation where applicable. Follow the audience's next question rather than a fixed sales formula. Cover, section, exercise, and discussion slides need not assert conclusions. Make the sequence readable by its titles, and budget demos, pauses, and questions as well as spoken content.

**Done:** all required claims and materials have a place, the sequence supports the intended outcome, and unresolved evidence is explicit rather than fabricated.

## 4. Establish the visual direction

Read [Style selection](references/style-selection.md), shortlist from `assets/template-library/index.json`, then inspect each candidate's actual `template.html`, `design.md`, and multi-slide previews. A theme is its concrete layout system, typography, decorations, and runtime—not a palette or written description.

If the visual direction is unresolved, build genuinely distinct previews with the same user content. Include a cover and a demanding evidence/code/data slide. Use an existing approved brand directly rather than forcing a style picker. Preview labels and design rationale belong in review UI, never on the slides.

Before expanding the deck, render the cover, densest content slide, and technical visual where relevant. Fix the starter/layout/component that fails, then continue from that source. Once selected, extend the same system across the deck. Change composition with the message; do not repeat one container arrangement on every page.

**Done:** representative slides have been visually compared, the system carries difficult content, and any user-requested sample gate is satisfied. A beautiful cover alone is insufficient.

## 5. Build the complete deck

Clone the chosen theme's complete source folder. Replace its demo copy, statistics, names, dates, and placeholders; retain the layout classes, type hierarchy, visual motifs, spacing rhythm, and useful native behavior. Select and duplicate the theme's existing layouts by slide purpose. Extend missing layouts in that same visual language. For a required Slidev or Reveal port, recreate those compositions in native layouts/sections; reuse technical components only where they fit and restyle them to belong. Prefer native text/code/vector content to screenshots of text; preserve a static explanation for animation, video, and interaction.

Create speaker notes alongside presentation slides. Reading slides carry the explanation they need visibly. Keep assets local or embedded as the delivery contract requires, with their origin and reuse conditions. Do not substitute invented real-world photos, product screenshots, statistics, citations, or placeholder assets for missing evidence.

For conversions, inventory text, tables, charts, images, ordering, and notes against the original. Distinguish extraction from faithful reconstruction. Resolve unsupported objects explicitly and inspect the rendered conversion; never promise lossless arbitrary PPTX conversion from a text/image extractor.

**Done:** the entire deck contains the required content and real assets and opens in the selected runtime. Requested output generation remains part of the task, not an optional instruction handed back to the user.

## 6. Verify and deliver

Read [Verification](references/verification.md). Exercise the actual presentation and requested export files. Inspect every slide and meaningful reveal state for legibility, missing material, overflow, and overlap; check the required navigation and notes. Render at the intended display and a narrow viewing size where relevant. A fixed-ratio mobile preview is not proof of a readable mobile handout.

Choose the browser by verification purpose. In WSL, read `windows-chrome` for an actual visible Windows browser or user-assisted review; built-in/headless browsers remain valid for automated rendering and checks. Do not use a WSLg GUI browser as development or compatibility evidence merely because it opens. Honor an explicit browser request and record the real host/mode; the verification reference covers CDP tab ownership and Windows-readable paths.

Fix observed failures at their source and recheck the affected state. A build success, source audit, or screenshot of the cover alone cannot approve the whole deck. State any missing runtime or unresolved required asset instead of claiming a finished result.

When evaluating this skill itself, preserve the fresh worker's initial output before corrections. Record interventions separately. A polished final deck after extensive orchestrator edits is not evidence that the skill reliably produces that quality on its first pass.

Deliver the editable source, requested files or local preview, revision/run instructions, evidence locations, and exact verification scope. Include known format losses such as image-based PPTX, static animation, or unavailable video playback. Inspect notes and metadata as well as visible slides before sharing private material. Publishing, installing global tools, changing host configuration, or leaving a persistent service requires the applicable task authority; none follows automatically from making slides.

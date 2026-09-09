---
name: awesome-slides
description: "Create, improve, and convert presentation slide decks: technical talks, decision or proposal decks, teaching slides, and self-contained reading decks. Use for slide narrative, visual design, speaker notes, and requested web/PDF/PowerPoint deliverables. Not for ordinary web pages, non-slide documents, or isolated presentation-library syntax questions."
license: MIT
---

# Awesome slides

Make a deck that communicates a grounded message in its actual delivery setting. Own the content, visual direction, editable source, and requested outputs—not just plausible slide markup.

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
| New deck without a stronger requirement | **Slidev**: read [Slidev](references/slidev.md). |
| One file, no build, or a portable offline deck | **HTML**: read [HTML](references/html.md). Offline also requires fonts, media, and scripts to be available without external requests. |
| PowerPoint with editable text, shapes, or charts | Use a native PPTX authoring tool. If available, consult `officecli`; otherwise use the available Office tooling and document the limitation. Slidev's image-based PPTX export does not meet this requirement. |

Existing Reveal.js, Spectacle, and other engines remain valid revision targets. Do not introduce a second renderer or a framework-agnostic adapter layer for a single deck. Other skills are optional collaborators, never installation prerequisites; use available tools and official documentation when they are absent.

## 3. Ground and storyboard the content

Read [Narrative](references/narrative.md). For code, architecture, benchmarks, or demos, also read [Technical talks](references/technical-talks.md).

Use supplied material first. Research the uncertain factual claims at their primary sources; source-ground a library/API explanation in the relevant version or local code. Distinguish reported data, observed measurements, controlled demos, illustrative synthetic data, and unknowns. An attractive chart or screenshot is not evidence by itself.

Plan each slide's role, main message or assertion title, supporting evidence, visual form, note intent, and time allocation where applicable. Follow the audience's next question rather than a fixed sales formula. Cover, section, exercise, and discussion slides need not assert conclusions. Make the sequence readable by its titles, and budget demos, pauses, and questions as well as spoken content.

**Done:** all required claims and materials have a place, the sequence supports the intended outcome, and unresolved evidence is explicit rather than fabricated.

## 4. Establish the visual direction

Read [Visual design](references/visual-design.md). Use existing brand and role tokens. When style is undecided, compare a small set of genuinely distinct directions using the same real content: a cover and a demanding evidence/code/data slide. A named style or approved brand does not need a compulsory alternative picker.

Treat preview labels and design rationale as review UI, not slide content. After selection, extend the same type, spacing, color, and layout system throughout the deck. Templates guide composition; their demo text, facts, logos, and numerical examples are not user content.

**Done:** the selected system works for the hardest content, not only the title slide.

## 5. Build the complete deck

Use the engine's existing code, notes, chart, diagram, and export mechanisms. Keep the editable content source authoritative. Extract a component only when a repeated meaning or interaction earns it. Prefer native text/code/vector content to screenshots of text; preserve a static explanation for animation, video, and interaction.

Create speaker notes alongside presentation slides. Reading slides carry the explanation they need visibly. Keep assets local or embedded as the delivery contract requires, with their origin and reuse conditions. Do not substitute invented real-world photos, product screenshots, statistics, citations, or placeholder assets for missing evidence.

For conversions, inventory text, tables, charts, images, ordering, and notes against the original. Distinguish extraction from faithful reconstruction. Resolve unsupported objects explicitly and inspect the rendered conversion; never promise lossless arbitrary PPTX conversion from a text/image extractor.

**Done:** the entire deck contains the required content and real assets and opens in the selected runtime. Requested output generation remains part of the task, not an optional instruction handed back to the user.

## 6. Verify and deliver

Read [Verification](references/verification.md). Exercise the actual presentation and requested export files. Inspect every slide and meaningful reveal state for legibility, missing material, overflow, and overlap; check the required navigation and notes. Render at the intended display and a narrow viewing size where relevant. A fixed-ratio mobile preview is not proof of a readable mobile handout.

Fix observed failures at their source and recheck the affected state. A build success, source audit, or screenshot of the cover alone cannot approve the whole deck. State any missing runtime or unresolved required asset instead of claiming a finished result.

Deliver the editable source, requested files or local preview, revision/run instructions, evidence locations, and exact verification scope. Include known format losses such as image-based PPTX, static animation, or unavailable video playback. Inspect notes and metadata as well as visible slides before sharing private material. Publishing, installing global tools, changing host configuration, or leaving a persistent service requires the applicable task authority; none follows automatically from making slides.

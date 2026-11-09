---
name: awesome-slides
description: "Create, revise, or convert presentation slide decks as Slidev source packaged into one offline HTML file, with PDF on request: technical talks, decision or proposal decks, teaching slides, and reading decks. Use for slide narrative, visual design, speaker notes, and deck deliverables. Not for ordinary web pages, non-slide documents, or editable PowerPoint (officecli)."
license: MIT
---

# Awesome slides

One engine, one pipeline: a Slidev deck in its own directory, designed with the person, packaged into `deck.html` (one file that opens offline) and `deck.pdf` when asked. The deck directory is the state: each phase writes one artifact, and the first artifact that is missing or not settled is where work resumes.

## Phases

| Phase | Artifact in the deck directory | Guide | Gate |
| --- | --- | --- | --- |
| 1. Brief | `brief.md` | [BRIEF.md](BRIEF.md) | Every field settled |
| 2. Outline | `outline.md` | [OUTLINE.md](OUTLINE.md) | **Stop** until the person approves |
| 3. Design | `DESIGN.md`, `theme.css` | [VISUAL.md](VISUAL.md) | **Stop** until the person approves |
| 4. Build | `slides.md`, layouts, components, notes | [BUILD.md](BUILD.md) | `npm run build:html` passes |
| 5. Package | `deck.html`, `deck.pdf` if required | [PACKAGE.md](PACKAGE.md) | Every required file exists |
| 6. Verify | report in the final response | [VERIFY.md](VERIFY.md) | Every state and page inspected |

`brief.md`, `outline.md`, and `DESIGN.md` begin with a `status:` line: `draft`, `approved` (the person said so in this thread; for the brief, every field came from the request, the material, or the person's answers), or `assumed` (decided without the person; reasons recorded beside it). Phases 1–3 are settled when their file is `approved` or `assumed`; phases 4–6 by their gate. Read the guide for a phase when you enter it, not before.

**Run style.** By default work stops at the two gates. When the person asked for the whole deck without further questions, or the run is unattended, mark gated artifacts `assumed`, record why each choice fits the brief, and continue. Questions and approvals follow the environment's human-in-the-loop policy.

**Fonts.** Korean typography uses the pinned OFL fonts in the starter's `tools/fonts.json`; [FONTS.md](FONTS.md) covers choosing, swapping, and licensing.

## Scope

- **New deck:** `node <skill-directory>/scripts/new-deck.mjs <deck-directory>` copies the starter into a new directory, or into one holding only phase artifacts; it refuses to overwrite anything. Then phase 1.
- **Starter ready before phase 3:** design rounds render the deck itself, so by then the directory needs the starter, `npm ci` (npm registry access), and `npm run fonts` (needs `uv` and PyPI access for fonttools, then downloads the pinned fonts). Run whichever is missing when entering phase 3 or later.
- **Existing Slidev deck:** keep its files and conventions; enter at the first unsettled phase, writing any missing artifact from what the deck already shows.
- **Existing deck in another engine** (Reveal.js, plain HTML, PPTX, Keynote): a wording or number fix happens in place as ordinary work, outside this pipeline; PPTX edits go to the `officecli` skill. A change to structure or design moves the content into a new Slidev deck, using the old deck as the design reference in phase 3. When the size of the change is unclear, ask.
- **Editable PowerPoint output** belongs to `officecli`; Slidev's PPTX export is slide images.

## Finish

Deliver the deck directory, the deliverables `brief.md` lists (a reading deck ships `deck.pdf` alone), the commands to rebuild them, and the verification report. Publishing, global installs, and long-running services each need their own authority.

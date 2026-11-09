# Design

The design is settled on the deck's own slides, with the person reacting to pictures rather than describing taste in design vocabulary. Two paths lead to an approved `DESIGN.md`:

- **Reference path** — the brief lists references, a brand, an existing deck, or a DESIGN.md.
- **Twenty questions** — no design input; the person's preference is found by pairwise choices.

Both use the outline's real content. Pick the **probe slides** first: the cover, the hardest content slide (densest table, longest code, real chart), and one section or transition slide. Lay out `slides.md` with one slide per outline entry so slide numbers match the outline; give the probe slides their full real content and every other slide only its outline title. Phase 4 writes the rest. Starter placeholder text is never shown to the person.

## Rendering

A variant is a directory `design/variants/<name>/` holding the files that differ: usually `theme.css`, often `style.css` or a layout under `layouts/`, and `variant.json` for headmatter such as `{"colorSchema": "dark"}`. The deck itself stays untouched until a direction is chosen.

```bash
node tools/variants.mjs --slides 1,4,2 --out design/round-01.png <left> <right>
node tools/variants.mjs --slides 1,4,2 --out design/final.png        # the deck as it now is
```

Rows follow the `--slides` order. A variant that carries its own `tools/fonts.json` fetches those fonts for its render, so two sans or two display families can be compared side by side. Open every image yourself before showing it: fonts loaded, nothing clipped, both sides showing the same content.

## Reference path

1. Read each reference for what it can establish. A DESIGN.md or brand guide gives values; an image or site gives arrangement, relative emphasis, and mood, so values taken from it are estimates and are labelled so.
2. Fill what the reference leaves open (usually data, code, and dense slides) in the same visual language.
3. Write `DESIGN.md`, apply it to `theme.css`, `style.css`, and layouts, and render the three probe slides.
4. Show the image and ask: **이대로 진행 / 아직 아님**. "아직 아님" starts twenty questions with this direction as the first left-hand side.

## Twenty questions

Each **round** shows the same probe slides in two variants, left and right, and asks one question with four answers:

- **왼쪽** / **오른쪽** — keep the chosen side as the new baseline.
- **둘 다 별로** — record both as directions to avoid; the next round moves to a region not yet shown.
- **둘 다 괜찮음** — the difference does not matter to the person; stop probing that element.

The person never explains a choice and never needs design words. Interpreting the answers is your job: keep a round log in `design/rounds.md` (round, what differed, answer, what it implies).

**Coarse to fine.** Early rounds compare whole directions that are far apart: quiet editorial against loud poster, light paper against dark stage, serif display against heavy sans. Once a direction holds, each round changes one element of the baseline:

- composition and grid: alignment, asymmetry, where the claim sits against the evidence
- type: display face (from FONTS.md), title scale, weight contrast
- graphic motifs: rules, blocks, numbering, frames, or none
- color and surface: background, accent count, how emphasis is marked
- evidence treatment: how tables, charts, code, and diagrams are framed
- density and rhythm: space per slide, how much composition varies between slides

Choose the next pair where the answer would change the design most, and before asking, write in the round log what the next round will compare after each of the four answers. Six to ten rounds usually settle it; stop early when two rounds in a row change nothing.

**Ask.** Put the round image in the reply where the person can see it (embed the PNG path), then ask with the environment's question tool, the four answers as options. Without a question tool, end the turn with the question. A reference the person offers at any point switches to the reference path from the current baseline.

**Converge.** Apply the baseline to the deck, write `DESIGN.md`, render the three probe slides as `design/final.png`, and ask **이대로 진행 / 아직 아님**. "아직 아님" resumes rounds at the element the log is least sure of.

## DESIGN.md

```markdown
status: draft | approved | assumed

# Design
## Direction
Two or three plain sentences: what the deck looks like and why it fits the audience.
## Sources
References and what each contributed; or a one-line summary per twenty-questions round.
## Color
Token (theme.css) → value → role. One accent role used the same way everywhere.
## Type
Role → fonts.json family and weights → title / body / caption / code sizes.
## Layout
Margins and grid; which layout serves which slide purpose.
## Motifs
Each graphic element and where it appears.
## Motion
Transition and what earns a click.
## PDF
Final state by default; slides marked `pdf: steps` and why.
## Avoid
Rejected directions and the round that rejected them.
```

`theme.css` and the layouts are the runtime owners; `DESIGN.md` states intent and points at them, without copying token tables twice.

**Done** when `DESIGN.md` is `approved` (the person chose 이대로 진행) or `assumed` (unattended or finish-without-questions: the direction derived from the brief and references, reasons recorded), and the probe slides render correctly in it.

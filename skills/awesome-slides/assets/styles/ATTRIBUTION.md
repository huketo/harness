# Style asset attribution

## Adopted source and license

These style assets adapt material from [Zara Zhang's Frontend Slides](https://github.com/zarazhangrui/frontend-slides) at commit [`9906a34d640d2111f724544cbc50f7f130569ae1`](https://github.com/zarazhangrui/frontend-slides/tree/9906a34d640d2111f724544cbc50f7f130569ae1), distributed under the MIT License, copyright (c) 2025 Zara Zhang. The complete original license is retained in [LICENSE.frontend-slides.txt](LICENSE.frontend-slides.txt) and in each CSS file so the notice travels with a copied or embedded theme. Preserve it in generated distributions.

This attribution covers only the native-engine token assets and local composition recipes in this directory, originally adapted from Frontend Slides' bundled design guides. The complete HTML themes are a separate direct adoption under `assets/template-library/ORIGIN.json` and its MIT license; they include upstream demonstration content that must be replaced for a user's deck. These palette assets are not ports of those themes.

## Exact adoption map

All upstream paths below are relative to the pinned Frontend Slides repository.

| Local asset | Source file / section | Reused material | Local changes |
| --- | --- | --- | --- |
| `editorial.css`, `editorial.md` | `bold-template-pack/templates/soft-editorial/design.md`: colors, typography roles, spacing, matrix/source-line patterns, depth and CJK sections | Exact paper `#F2EEDF`, alternate paper `#ECE6D2`, ink `#2A241B`, soft ink `#5C5345`, sage `#B7C7A8`, blush `#E8C9B6`, lemon `#D6DD63`; serif display / sans substance; open magazine-spread margins, ink-on-pastel regions, restrained ruled matrices and source annotations | Dark sage text accent and opaque boundary; local Korean serif/sans stacks; larger body-to-display ratio and CJK leading; a compact spacing ladder; five purpose-specific recipes on a 1000px logical canvas; code support; optional rather than universal cards; no mandatory swatch discs, drop caps, italic Korean, or chrome |
| `signal.css`, `signal.md` | `bold-template-pack/templates/blue-professional/design.md`: colors, split-highlight-block, bar-track/fill, cover split, typography and layout | Exact cream `#fdfae7`, ink `#111111`, cobalt `#1e2bfa`; single-accent emphasis, near-black headlines, labeled cobalt numerical evidence, asymmetric cover/evidence split, highlighted margin interpretation, direct-value bar composition | Darker muted text and opaque line/surface roles; local Korean-capable stack; readable CJK-first scale; optional evidence fields instead of compulsory header/tag/card grid; no decorative dots/circles or fading future-step labels |
| `technical.css`, `technical.md` | `STYLE_PRESETS.md`: Terminal Green | Exact dark field `#0d1117` and terminal green `#39d353`; dark technical palette and mono source role | Light foreground/muted/boundary/surface roles; sans prose with CJK-aware mono fallback; source-first, invariant-comparison and topology recipes; no scan lines, blinking cursor, remote font loading, or prescribed syntax engine |

The additional type ratios, spacing tokens, Korean examples, readable-source treatments, and five-layout recipe organization are local adaptations for Awesome Slides. Example phrases are synthetic composition demonstrations, not external quotations, measurements, API implementations, or factual results. The selected systems are adaptations with different names, not claims of pixel-identical reproductions of the upstream templates.

## Deliberate adoption boundaries

Upstream implementation is reusable; its integration assumptions differ. These assets retain concrete tokens and composition mechanisms while leaving fixed-stage scaling, navigation, notes, export, syntax highlighting, and responsive reading to the actual deck engine. They introduce no runtime dependency and no remote font request. The source's fixed 1920 × 1080 geometry informs proportions, not a replacement renderer. Local Korean font stacks replace upstream CDN-only Latin/Chinese font loading; no font license is implied by naming an installed family.

The accompanying MIT notice applies to the adopted material; it does not assert a blanket license over an enclosing repository or unrelated deck content. Retain source-specific permissions for any additional fonts, media, code excerpts, and evidence used in a deck.

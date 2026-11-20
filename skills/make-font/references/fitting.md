# Fitting the base

`fit_font.py` turns one variable font into one static per weight. It reads the base and `targets.json`, and
nothing else.

## Before the fit

The script starts from `base.json`. The base font and its `OFL.txt` must still have the sha256 recorded when the
person approved them, and the font given on the command line must be that file, byte for byte: a subset or a
copy made elsewhere is refused. The base must be a TrueType variable font (glyf, fvar, gvar) in a plain `.ttf`
file: `chain.read_base` checks it again here, as at the approval step.

It then subsets the verified base itself, to the characters of the targets' scripts (`fontlib.COVERAGE`, and
`fontlib.COVERAGE_REPORTED` for `korean`: every modern syllable and the compatibility jamo beyond the KS X 1001
syllables the check gates) plus ASCII, Latin-1 and common punctuation, keeping every layout feature and glyph name. The subset goes to
`build/subset/base.subset.ttf`, and `fit-log.json` records it under `subset`: the base's sha256, the file, its
sha256, the pyftsubset arguments in order and the fontTools version. `chain.build_subset` makes it, always with
fontTools' own GSUB and GPOS serializer (HarfBuzz's repacker, used whenever uharfbuzz is installed, gives other
bytes, and each script has its own environment). The same base, arguments and fontTools give the same bytes, so
`package.py` and `check_font.py` make it again from the base and compare the sha256 instead of reading the file. Everything below runs on that subset, and the check
compares the output's glyph order and character map with it. Every font the fit writes is a plain TrueType file. `fit-log.json` also carries the chain: `base.json`'s sha256, the
base as the only input, every fitted font as an output, and `targets.json`.

## Why x and y come from different places

Every location of one variable font has the same points in the same order. So a glyph can take its x
coordinates from one location and its y coordinates from another, and still be a valid outline.

That matters because width and contrast often live at opposite ends of an axis. A typical text serif is wide
and low in contrast at small optical sizes, narrow and high in contrast at large ones. A reference that is wide
and high in contrast sits at neither end. Taking x from the small size and y from the large one gets both. Bars,
hairlines and the x-height are horizontal strokes and vertical positions, so they follow y. Stems and curved sides
follow x.

## The steps

1. **y instance.** For each optical size tried (nine across the axis, unless `--loc` fixes it), solve the weight
   axis so the n stem meets the target (without a Latin n stem, the Hangul stem: see [Hangul](#hangul)), then
   measure contrast, bar to stem and x-height to cap. Each wght tried reads its n stem at cap 700 against the cap
   height that wght draws, since the cap can grow with the weight. Keep, among the sizes where the wght axis reaches the stem,
   the one with the smallest error; when none reaches it, the size whose axis end comes nearest, and `fit-log.json`
   records the miss (`weight_missed_pct`). With `--no-contrast` the opsz scan is skipped.
2. **x instance per class.** For each width class: on a width axis, bisect wdth so the class's mean advance meets
   its target. At every wdth tried, solve wght again so the class's stem (n for lowercase, H for capitals and
   figures) meets its target, because width changes stems. Without a width axis, or where it runs out, scale the
   class horizontally by a factor, capped at `--max-stretch` (3 %), and solve the weight for `stem / factor` so
   the stem lands on target after the stretch.
3. **Assemble.** Each glyph takes x from its class instance times the factor, y from the y instance, and its
   advance from the class instance times the factor. Accented letters and alternates follow their base letter
   (by Unicode decomposition and name suffix). Composites made of one class join it, and their marks stay centred.
   Mark-to-base anchors take x from the class instance and y from the y instance. Everything else (punctuation,
   symbols, small capitals, figures variants) keeps the y instance's own x.
4. **Iterate.** Assemble the measuring subset (the letters, figures and space, every class mean and side needs)
   the same way, set the class sides, measure it, correct each factor by the class's error, assemble again. Stop
   when every class is within `--tol` (0.3 % by default) or six passes have run. Rounding and overlap removal move
   means a little, which is why one pass is not enough. Then the whole font is assembled once, with the factors
   found: it has the class means the last pass measured. On Noto Sans KR (11,879 glyphs) a weight takes about 25 s
   this way, against about 39 s when every pass assembled the whole font; `fit-log.json` records each style's
   `seconds`.
5. **Finish.** Remove overlaps (skia-pathops), scale the em so cap height per 1000 em matches the reference file,
   set the line box from the reference's vertical metrics when a file gave them, make the win metrics cover
   every glyph, and drop the variation tables.

## Limits, and what to do at them

- **Stretch.** Past 3 % a glyph reads as stretched: its curved strokes get heavier than its stems and its curves
  flatten. If a class needs more, say so, keep the cap, and offer a base with a width axis. For capitals at 8 to
  10 % with a strong reason, a person may choose it. Above 10 % the base is wrong.
- **Bare stems.** i, l and I are one stem. A stem-compensated stretch leaves their ink unchanged, so the narrow
  classes move mostly through their sidebearings. That is correct.
- **Kerning from an extreme location.** Some variable fonts extrapolate pair kerning badly at the ends of an axis
  (a curved letter followed by a descender opened by 90 units). Kerning comes through the y instance's location. If
  the kerning reads wrong in a word set at 18 px, rebuild with a y location nearer the axis default, and let the
  collision guard handle the tails.
- **Kinks.** Mixing x from one location with y from another can kink a curve where the two drawings differ a lot.
  Render S & @ W Q g a e and y at 200 px and look. If one kinks, take x and y from one location and solve widths
  with factors alone.
- **What fitting cannot change.** Serif thickness and bracket shape, terminal shape, stress angle, one or two
  storeys. A serif that is too thin needs point classification the base does not carry. Report these as known
  gaps, never as fitted.
- **Weight colour.** Matching the n stem does not match colour. If the reference's curved strokes or serifs are
  heavier relative to the stem, the fitted font reads lighter. Compare o side and serif tip in the check table and
  report the gap.

## Several weights

The first style's stem comes from the measurement. Other styles take an explicit stem (`--style Medium:500:88`),
solved like the first, or the first style's y location, its optical size included, with the wght moved by the
weight-class difference (Bold 700 after Regular 400: +300) and clamped to the axis: no optical size of their own,
so the weights stay as far apart on the axis as their classes and keep the base's own stem ratio between them.
Each style gets its own class instances. All styles share the vertical metrics, so they can mix in one line.

## Hangul

When `targets.json` has a `hangul` object (`references/measuring.md`, its last table), the targets' scripts
must have `korean`, so the subset keeps the base's Hangul. The fit moves every Hangul glyph by one transform per
class, fitted only to the targets a reference measured. It cannot change what the base drew: square or open
syllable shapes, the jamo's shapes, serifs or none, stroke endings. Report those as differences, never as fitted.

**Weight.** A style with an n stem, or after a first style with one, solves the Latin weight from the n stem as
above. Without a Latin n stem, the first style's wght comes from the Hangul stem (ㅣ in 이 니 미), taken in this
order, and the Latin takes the same wght, which keeps the base's own balance between the two:

1. `stem` at `cap700` (a reference with a Latin H): the base's stem times 700 over its cap height meets it.
2. `stem` at `em1000` (a font file without an H): the base's stem per 1000 of the finished em meets it, the em
   being the cap height over `cap_em` when the targets have one, else the base's em.
3. `stem_h1` (a screenshot of Hangul alone): the base's stem over its H1 mean face height meets the ratio.

With both an n stem and a Hangul stem, the Hangul solves a wght of its own at the y location's other axes (its
optical size included), and the check compares the two stems with the reference's ratio. The wght is one for the
whole Hangul: the stem is read on H1 syllables only, so no class has a weight target of its own. It is solved for
the stem over the transform's scale (below), because the transform scales the stem too: a stem length over the H1
x scale, `stem_h1` times the H1 y scale over its x scale. The scale depends on the face sizes the wght draws, so
the two are solved in turn on the measuring syllables until the wght moves less than half a unit.

The cap height and the face height move a little with the weight, so each try reads them and the stem at the same
wght. The wght is solved at every optical size the y instance is chosen from (step 1). At some sizes the wght axis
may not reach the stem: it is thicker than the boldest the axis draws there, or thinner than the lightest. The scan
keeps a size where the axis reaches it, the one nearest the contrast, bar and x-height targets among those. When no
size reaches it, the scan keeps the size whose axis end comes nearest, and `fit-log.json` records the miss
(`weight_missed_pct`, and a line in the style's log).

Each later style takes the first style's Hangul location, with the wght moved by the weight-class difference and
clamped to the axis, and the first style's transform. The Bold so keeps the base's own Bold drawing, faces and
centres included, moved the way the Regular moved.

**Transform.** Every number is in the units of the base's instance at the Hangul location, before `finish()`:

1. One scale for the whole Hangul: the geometric mean, over every class's face width and height that a reference
   gave as a length, of target over base, within ±6 %. Without a length (a screenshot of Hangul alone) it is 1,
   so the base's Hangul scale, centre heights and advances stay.
2. Each class's final x and y scale: that scale times the class's own, which is target over base over the one
   scale on each axis, within ±3 %, and the larger axis within 3 % of the smaller too. A ratio past it moves both
   toward their geometric mean. A class without a target takes the one scale. Every scale is logged, and applied,
   at five decimals, each rounded to the nearest five-decimal value inside its limits (`fit_font.class_axes`), so
   rounding never carries one past a limit.
3. The ink of each glyph is scaled about the centre of its points' box, then moved up or down by the class's
   shift, the target face centre height (`cy`) minus the base's class mean.
4. The advance is the base's times the one scale, plus what makes the class mean (or the font-wide advance of a
   fixed-width Hangul) meet `adv` when a reference gave one. Half the change goes to each side, so the glyph's own
   optical asymmetry stays; only a class's mean centre moves, to `cx` when a reference gave it.
5. The compatibility jamo (U+3131 to U+318E) take the one scale on both axes, no shift and no advance target.
6. A composite glyph is decomposed into its own points first, so a component another glyph shares never moves twice.

The limits apply to the final per-axis transform, not to each step. `fontlib.hangul_transform_over` is the one
check of them: `fit_font.py` runs it before it logs a transform, and `check_font.py` on the transform in the log,
then checks every glyph against it point by point (`references/checks.md`, provenance). The fit reads and moves the measuring syllables while it solves, and moves the
whole Hangul once, when the wght has settled.

**Units, before `finish()`.** Every Hangul target is stated in the units of the Hangul location, beside the base's
value there, and only then does `finish()` scale the em, once, at the end:

- `cap700`: value × the y instance's cap height / 700.
- `em1000`: value × the finished font's em / 1000. That em is the y instance's cap height over `cap_em` when a
  file gave one, else the base's em.
- `ratio`: never turned into a cap length. `face_h_h1` multiplies the base's own H1 face height, `aspect` that
  height, `stem_h1` the same H1 height. A screenshot of Hangul alone so keeps the base's Hangul scale, centre
  heights and advances, and gives shapes and the weight only.

A key with a length uses `cap700` first, then `em1000`; the ratios fill in where no length was measured.
`finish()` scales x and y alike, so a ratio to the cap height survives it (checked by measuring the fitted font).
The saved font rounds every point to a whole unit, so a stem lands up to a unit from the solve: about 1 % of an
80-unit stem at 1000 units per em.

`fit-log.json` records this under each style's `hangul`. Beside it, the style's `em_scale` is the factor `finish()`
multiplied every length by (1000 over the em it scaled from), and `overlaps_removed` says whether `finish()`
removed overlaps; the check makes the Hangul again from both:

| Field | Value |
|-|-|
| `weight_from` | what the Hangul wght came from: `stem cap700`, `stem em1000` or `stem_h1` when the Hangul stem set it (alone, or beside a Latin n stem that set the y), else `n_stem` (the Hangul follows the y instance); after the first style, with ", stepped from the first style's Hangul location" |
| `stepped_from` | after the first style, when the Hangul location was stepped: `{"style", "location"}`, the first style's Hangul location |
| `weight_missed_pct` | only when no optical size tried lets the wght axis reach the Hangul stem: the stem the base draws at the chosen location over the target, minus 1, in percent |
| `location` | the base location the Hangul outlines come from |
| `units` | font units of that instance per `cap700` and per `em1000` unit |
| `classes.Hn.<key>` | `{"target", "base", "from", "fitted"}` in those font units, for `face_w`, `face_h`, `cx`, `cy`, `side`, `side_asym` and `adv`; `from` is the unit the target came in, `fitted` what the moved glyphs measure |
| `stem`, `adv` | the same, font-wide (`adv` for fixed-width Hangul) |
| `stem_h1` | `{"target", "got", "fitted"}`: the ratio aimed at, the base's at the chosen wght, the fitted font's |
| `transform` | `scale` and `scale_wanted`; `classes.Hn` with `sx`, `sy`, `dx`, `dy`, `adv_add` and, where a limit held a class back, `wanted`; `jamo` |
| `glyphs_moved`, `composites_decomposed` | how many Hangul glyphs the transform moved, and how many were composites in the base |

For a later style the targets are the first style's: a Bold's `stem.target` is the Regular's, not a target missed.

**Limits.** The one scale stays within ±6 % of the base's, and each class within ±3 % of it on each axis and between
its axes. They were set by comparing the unchanged Noto Sans KR at wght 400 with transforms at and past them, on the
held-out syllables (`HANGUL_HELD_OUT`) and a mixed Korean and Latin line:

- The fixed candidates differ by less than that: Pretendard's mean face is 4.0 % smaller than Noto Sans KR's per
  1000 em and 0.4 % at cap height 700; Noto Serif KR's is 6.1 % larger per em. A sans reference lands inside the
  ±6 %; a serif one does not, and its class shapes differ well past 3 % (its H2 is 13 % wider over its height).
- Spacing holds at the limits. The tightest gap between two syllables of 가나다라마바사 is 64 units in the base, 69
  at one scale 1.06 with the advances scaled with it, 15 with the advances kept, and 40 at a 3 % stretch of one
  axis. Past them the syllables touch: at 1.12 with the advances kept the gap is −35 units and seven of the
  held-out syllables leave their advance; at a one-axis stretch of 8 % it is −2, and the H1 stem is 7 % heavier
  while the horizontal strokes stay, which shifts the contrast.
- Nothing is clipped: at 1.06 the held-out syllables reach 870 and −111 units, inside the line box of 1160 and −288.

A face that grows to its limits while a reference keeps the advance narrow can still run into the next syllable:
at the one scale 1.06 and a class 1.03 with the advance held, an H1 face is about 68 units wider, more than the 64
units between two syllables of the base. The check reports how many Hangul glyphs leave their advance, fitted and
base (**hangul** group); look at a Korean line before handing the font over.

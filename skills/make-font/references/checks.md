# Checks

`check_font.py` first checks the chain, then gates each style, and exits 1 on any failure. Each gate is PASS,
FAIL, INFO or NOT RUN. Its tolerances come from `targets.json`, set by use:

| Gate | text | display | ui |
|-|-|-|-|
| n stem, units | 3 | 3 | 2 |
| class mean width | 1.5 % | 1.0 % | 1.5 % |
| shaped paragraph | 1.5 % | 1.0 % | 1.5 % |
| contrast | 0.05 | 0.04 | 0.05 |
| x-height, units | 6 | 4 | 5 |
| side means, units | 4 | 3 | 4 |
| smallest ink gap in a kerned pair | 6 | 4 | 8 |

Units are cap-normalised (cap 700). The width gates are the fit's own objective, so they pass nearly by
construction. The paragraph gate is the independent one: it has spaces, punctuation, figures and kerning, which
the fit never saw. Read it as the real test of width. It only runs when the targets came from a font file.

## The chain

It takes `--base-json`, `--fit-log`, every `--space-log` and `--package-log` (`dist/package-log.json`), and
refuses to go on when a link is broken. `chain.verify_build` is the same check `package.py` ran: the base or its
`OFL.txt` fails `chain.read_base` or no longer has the recorded sha256; a log was made from another `base.json`;
`fit_font.py` read anything but the approved base and this `targets.json`; the subset made again from the base
with the arguments `fit-log.json` records does not have the recorded sha256 (the subset file is never read);
`space_font.py` read anything but fitted fonts and this `targets.json`. Then the package log: it must record
this `targets.json` and exactly the fit and space logs given (by sha256), have taken only spaced fonts, list
every font checked here as an output, and find every output it lists (each TTF and WOFF2) in its own folder with
the recorded sha256. Each input is read once, so the gates run on the bytes the chain checked. When every link
holds, the **chain** group lists them as PASS. That
structure is the provenance guarantee: the steps that draw the font never opened a reference. It cannot rule
out one agent hand-writing the fonts and every log consistently (`licensing.md`).

`checks/check-report.json` holds `base` (the base's file name, full sha256, source, and its licence's id, file
name, sha256, name ID 13 and Reserved Font Names), `approval` (question, answer, decision and time, verbatim from
`base.json`), `package.outputs` (the TTF and WOFF2 files verified above, by name inside the package and sha256)
and `gates`, one row per gate. The font book reads it and shows only fonts it lists. A report or render path
that leads to an input, through a link or not, is refused.

## The groups

- **metrics**: stem, x-height, contrast gated. Ascender, descender, bar, serif and overshoot printed for
  information, because the fit does not aim at them.
- **widths** and **spacing**: every class mean, the paragraph, the four side means.
- **kerning**: every pair of letters, figures and punctuation, shaped, f on the left skipped. Fails if any gap is
  more than a unit under `min_gap`.
- **coverage**: the characters each script needs (`COVERAGE` in `fontlib.py`: latin, latin-ext, vietnamese,
  cyrillic, greek, and korean, the 2,350 syllables of KS X 1001). Add a list there before claiming a script that is
  not in it; the fit subsets to it too. For korean the fit also keeps every modern syllable and the compatibility
  jamo (`COVERAGE_REPORTED`), which the check counts as INFO rows (`korean, modern syllables`: "n of 11172") and
  does not gate.
- **provenance**: glyph order and character map equal the subset `fit_font.py` recorded. Every glyph is compared
  with the subset's glyph at the fit's y location, at the same cap height: its ink must be within 3 % as tall
  (all y coordinates come from there) and within 40 % as wide (x comes from the width classes). The Hangul a fit
  moved is checked against its own record instead: the transform in `fit-log.json` must lie within the limits
  (one scale within ±6 %, each class's x, y and x over y within ±3 % of it, the jamo at it), and every Hangul glyph
  must be a simple glyph whose ink box and advance are where that transform, the style's `em_scale` and the
  space log's track put the subset's glyph at the fit's Hangul location, within 2 units. So the class scales the
  log records are the allowance, and any other outline change, a composite left or made included, fails. With
  `--reference` files there is one diagnostic, INFO only: our outlines that have a curve or at least 16 points
  are compared with the reference's, and any that share point structure and lie within 2 % in
  bounding-box-normalised shape are listed. Simpler shapes are left out, since a straight bar matches every
  straight bar. A match is a reason to look, not a verdict: the chain already shows the build never opened the
  reference, and a reference built on the same open base matches by design. A CFF reference cannot be compared
  with TrueType outlines, so the comparison is NOT RUN, and the report and the font book say so.
- **hangul** (a fit with Hangul targets), per weight. The first two are the weight harmony, and both are NOT RUN
  when no reference measured Latin (a screenshot of Hangul alone):
  - `Hangul stem / Latin n stem`: the fitted font's ratio within ±0.05 of `hangul.stem_n`, the ratio a reference
    measured with its own Latin n. NOT RUN also when no one reference measured both.
  - `Hangul face centre heights`: every class's mean face centre within ±15 units at cap 700 of its `cy` target.
    NOT RUN also without one (only a font file gives it).
  - `vertical strokes across the classes` (INFO): each class's vertical strokes, read on its measuring syllables
    (`fontlib.hangul_class_strokes`), fitted against the base at the fit's Hangul location, and how far apart the
    classes are in each. The fit promises no stem balance between classes: their x scales may differ by 6 %.
  - `Hangul ink inside the advance` (INFO): how many Hangul glyphs leave their advance, fitted and base, and the
    smallest side.
  The two tolerances are provisional. Without a Latin reference the Latin follows the wght the Hangul chose and
  only the measured Hangul targets apply.
- **validity**: a ttx dump-and-reload (dump, compile, dump, compare), win ascent and descent covering every glyph,
  no variation tables left, and `fontbakery check-universal` when it is installed. Not installed is NOT RUN.
- **licence**: see `licensing.md`.

## Renders

With a reference font file, `overlay-<style>-text.png` and `-display.png` set the same words in both fonts at the
same cap height: reference red, ours blue, both black, with that legend drawn above the words. Black shapes
with thin coloured fringes mean a close match.
A coloured shadow along one side of every letter means a width or spacing drift. With a screenshot,
`stacked-<style>.png` puts the screenshot above our render of the same lines at the same cap height.

Look at every render yourself. A gate passes on numbers. A letter that reads wrong only shows in a render.

## Kill criteria

Stop and go back a step when:
- a class needs more than 10 % stretch: the base is wrong (step 4);
- the guard opens more than 150 pairs: the spacing is too tight (step 6);
- a curve kinks in the x and y mix: take both from one location (step 5);
- the paragraph is off by more than twice its tolerance while every class passes: a class is missing, or the
  space or punctuation is far off, so compare `space` and the figure class.

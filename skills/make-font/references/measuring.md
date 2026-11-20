# Measuring a reference

Every Latin number is in cap-normalised units: the font is scaled so its cap height is 700. A screenshot has no
em size, so this is the only scale a screenshot and a file share. `cap_em` keeps a file's real cap height per 1000
em, and the build uses it to set the em of the output. A screenshot-only build keeps the base's cap-to-em ratio.
Hangul numbers carry their unit with them, since a screenshot of Hangul alone has no cap height: see
[Hangul](#hangul).

## What is measured, and where

All lengths come from straight cuts through the outline (or the pixels): a line crosses the ink, and the run
between entering and leaving is the measure. Runs use nonzero winding, so overlapping contours in a variable
font instance read as one shape.

| Number | Where |
|-|-|
| x-height | top of x |
| cap height | top of H |
| ascender | mean top of b d h k l |
| descender | mean bottom of p q |
| curved overshoot | top of o minus x-height, top of O minus cap height |
| n stem | first run across n at half the x-height |
| n counter | white between the two runs of n at the same height |
| H stem | first run across H at 30 % of the cap height |
| H bar | vertical run at the middle of H, between its stems |
| o side, o thin | run across o at mid height, and the thinnest vertical run at its centre |
| contrast | o thin over o side |
| serif reach | how far the foot of H, 1 % above the baseline, reaches past the stem, mean of both sides |
| serif tip | vertical thickness of the foot 30 % of the way in from its tip |
| class widths | mean advance of each class in `fontlib.CLASSES` |
| sidebearings | mean side of each class in `fontlib.SIDE_CLASSES` (straight and curved, lowercase and caps) |
| rhythm | twice the straight side over the n counter. It carries spacing from a screenshot to a font |
| paragraph | the fixed paragraph in `fontlib.PARA`, shaped by HarfBuzz with kerning and ligatures |

A serif counts as present when its reach is more than 12 % of the stem. Below that the font is treated as sans
and both serif numbers are 0.

The classes are set by how a letter is built, before any measurement, and never tuned per letter:
straight (h m n u), bowl (a b d g p q), curved (c e o s), diagonal (k v w x y z), narrow (f i j l r t), and for
capitals straight (B D H N P R U), curved (C G O Q S), diagonal (A K V X Y Z), wide (M W), narrow (E F I J L T),
plus figures. One mean per class is a target. A single letter's advance is never a target: that would copy the
reference glyph by glyph.

## From a font file

`uv run scripts/measure_font.py file --out m.json`. It reads TTF, OTF and WOFF2. For a variable font, `--loc`
picks a location and `--stem 76` solves the weight axis so the n stem is 76 first, which is how candidates are
compared at equal colour. Confidence is high for everything.

## From a screenshot

`uv run scripts/measure_image.py shot.png --text "line one|line two" --out m.json`.

The image is split into lines at blank rows, and each line into letters by connected ink. A dot or accent joins
the letter under it. A letter drawn in two parts (a k whose arm does not touch the stem) is joined to its
neighbour when the count is one too many, choosing the join that keeps repeated letters the same width. If the
count still disagrees with `--text`, the script stops. Crop tighter or set the text larger.

Edges are read with sub-pixel precision from the anti-aliasing: the partial coverage of an edge pixel is the
fraction of it that is ink. A run's thickness is the sum of the coverage across it, which is exact for a
vertical edge.

Advances need context. In `n X n`, the distance from the first n's left edge to the last n's left edge is
`advance(n) + advance(X)`, whatever the sidebearings, and `advance(n)` comes from a run of n. The same holds for
`H X H`. Sides come from the gap between two n (twice the n side) and from each letter's gap to its n. That is
why `SAMPLE_LINES` exist. A screenshot of ordinary text gives vertical proportions, stems and contrast, and no
widths.

### Confidence

- high: vertical lines when the cap is 60 px or more, a stroke 6 px or thicker.
- medium: advances and sides (kerning against n or H can bias them), strokes 3 to 6 px.
- low: strokes under 3 px, serif tips, anything with a cap under 30 px.

Report every low number to the person, and give low numbers less weight (`make_targets.py` does).

### What to expect

`--selftest` renders the sample lines from any open font, measures the pixels and the file, and prints the
error. On a text serif at a 98 px cap height the class widths came within 1.2 %, stems within 1.5 units, the
x-height exact. At a 34 px cap the stems drifted 3 units, the thin strokes went low confidence, and widths
stayed within 1.5 %. The straight lowercase side read about 4 units low at both sizes, because the n of that
font is not quite symmetric. Run the selftest at the screenshot's own size before trusting a number.

Things a screenshot cannot give: the em size, vertical metrics, kerning tables, and anything hinting or a
renderer's stem darkening has moved. Subpixel (coloured) anti-aliasing breaks the coverage reading: ask for a
greyscale capture or a large size.

## Hangul

### Classes

A syllable's class is computed from its initial, medial vowel and final (`fontlib.hangul_class`), before anything
is measured: where the vowel stands against the initial, and whether a final sits under them.

| Class | Structure | Measured on (`fontlib.HANGUL_CLASSES`) |
|-|-|-|
| H1 | vowel beside the initial (ㅏ ㅐ ㅑ ㅒ ㅓ ㅔ ㅕ ㅖ ㅣ), no final | 가나머서저이니미 |
| H2 | vowel under it (ㅗ ㅛ ㅜ ㅠ ㅡ), no final | 고노도무수그느오 |
| H3 | mixed vowel (ㅘ ㅙ ㅚ ㅝ ㅞ ㅟ ㅢ), no final | 과귀뇌뭐쉬의와위 |
| H4 | vowel beside, final | 각난달맘선일진형 |
| H5 | vowel under, final | 공눈돌몸손울큰흥 |
| H6 | mixed vowel, final | 광권뒷원괜윙휠쾅 |

The lists are fixed for every font, and one mean per class is a target; a single syllable never is.
`HANGUL_HELD_OUT` holds four other syllables per class. A font file's measurement reports their mean face over
the list's (`held_out`), which shows how well the list stands for its class in that font. In Noto Sans KR and
Pretendard at wght 400 every class came within 4.5 %, except the H2 height: held-out ×1.08, because ㅜ and ㅠ
drop a leg below ㅡ and the held-out set has more of them. A class mean depends on its vowels.

### Units

Each Hangul value is tagged: `{"value": 0.0887, "unit": "ratio", "confidence": "high"}`.

- `cap700`: a length at Latin cap height 700, as every Latin number. Only when an H was measured with the
  Hangul: a font file with Latin, or a screenshot with a Latin H in it at the same size.
- `em1000`: a length per 1000 em (`value × 1000 / upm`). Font files only.
- `ratio`: a ratio of two lengths of the same source. Every source gives these, a screenshot of Hangul alone
  nothing else.

A key holds lengths (one entry per length unit the source has) or one ratio, never both. A ratio key's suffix
names its denominator: `_cap` the Latin cap height, `_h1` the H1 class's mean face (height, or width for
`face_w_h1`). `make_targets.py` merges values of one unit only; a value in another unit stays beside them as a
target of its own, and a unit outside the three is refused.

### What is measured

The face is the ink box of a syllable. Cuts are straight lines through the outline or the pixels, as for Latin.

| Key | How | From |
|-|-|-|
| `face_w`, `face_h` | mean ink box width and height of the class | file, screenshot with H |
| `face_w_cap`, `face_h_cap` | the same over the Latin cap height | file or screenshot with H |
| `face_w_h1`, `face_h_h1` | the same over the H1 class's mean | file, any screenshot |
| `aspect` | mean face width over mean face height | file, any screenshot |
| `cx`, `cy` | mean face centre from the glyph origin and the baseline | file |
| `side`, `side_asym` | mean of the two sidebearings, and mean right minus left | file |
| `center_adv` | mean face centre over the advance | file |
| `adv`, `adv_cap` | mean advance, per class when the Hangul is proportional, once when it is fixed-width | file |
| `stem`, `stem_h1` | the last vertical run (ㅣ) across 이 니 미 at mid face height, median of the three; over the H1 mean face height | file, any screenshot (`stem` with H) |
| `report.overshoot` | top of 오 minus top of 고 | report only |
| `report.hstroke` | the lowest run (ㅡ) at the face centre of 으 그 느, median | report only |
| `report.contrast` | ㅇ of 으: top and bottom thickness over side thickness | report only |
| `report.pitch` | screenshot: one 으's left edge to the next, around each syllable of the class | report only |

Sides and advances come from files only: in a screenshot the gap in `으 X 으` holds the anchor's sides and the
pair's kerning, so a screenshot leaves the base's spacing, and its anchor distances (`pitch`) are reported, never
used. A screenshot has no baseline under a Hangul line, so face centres come from files too. `overshoot` in a
Korean font is mostly ㅇ drawn taller than ㄱ, not a round overshoot.

### From a screenshot

Ask for the six lines of `fontlib.SAMPLE_LINES_KO`: one line per class, each syllable between two 으 (anchors).
Add the Latin `SAMPLE_LINES` to the same screenshot, at the same size, when the font has Latin: their H gives the
Hangul lengths at cap height 700. Then `uv run scripts/measure_image.py shot.png --text "<every line, split by |>"`.

A line with Hangul in it is cut by columns, since a syllable is drawn in parts: ink whose columns overlap or touch
is one group. In the `으 X 으` form the first group is an anchor, every group drawn like it (same box, same column
and row profile) is one, and all the ink between two anchors is one syllable. 으 has no blank column inside it in
Noto Sans KR, Pretendard and Noto Serif KR at wght 100, 400 and 900 (outlines, and pixels at 40, 100 and 200 px
per em), and its sides differ by at most 0.5 % of the advance. Without anchors, or when the anchors found do not
fit the text, the line is cut at its N − 1 widest gaps (N characters), and only when the narrowest of those is at
least 1.5 times, and 2 px more than, the widest gap left inside a syllable. Otherwise the script stops, because
the gap between ㅇ and ㅣ in 이 can be as wide as the gap between two syllables. `cut_at` records which way each
line was cut. A line whose syllables all have blank rows at one height (a final under the vowel) reads as two
bands of ink; bands are joined across the narrowest gaps when those stand as far apart from the line gaps.

Confidence: a face is high from 60 px tall, medium from 30 px; strokes as for Latin; the overshoot is low under a
120 px face.

What to expect, measured on static wght 400 instances: `--selftest` (the skill's own rasteriser, no hinting) put
every class value of Noto Sans KR, Pretendard and Noto Serif KR within 0.25 % of the file at 120 px per em and
within 0.55 % at 60 px; the stem within 0.4 % at 120 px and 2.5 % at 60 px; the overshoot was off by up to 69 %
at 60 px. A Chromium screenshot of Pretendard at 120 px, read without an H, gave every class ratio and the stem
ratio within 0.35 % of the file.

### The `hangul` object (targets.json)

`make_targets.py` writes one `hangul` object in `targets.json` when `--scripts` has `korean`; later steps read
only this table's fields. A *tagged list* is a list of tagged values, at most one per unit.

| Path | Value | Units | Use |
|-|-|-|-|
| `classes` | object with keys `H1` to `H6`, each a class some reference measured | | |
| `classes.Hn.syllables` | the measuring syllables the first reference had | | names only |
| `classes.Hn.face_w`, `face_h` | tagged list | `cap700`, `em1000` | target |
| `classes.Hn.face_w_cap`, `face_h_cap` | tagged list | `ratio` | target |
| `classes.Hn.face_w_h1`, `face_h_h1` | tagged list | `ratio` | target |
| `classes.Hn.aspect` | tagged list | `ratio` | target |
| `classes.Hn.cx`, `cy` | tagged list | `cap700`, `em1000` | target |
| `classes.Hn.side`, `side_asym` | tagged list | `cap700`, `em1000` | target |
| `classes.Hn.center_adv` | tagged list | `ratio` | target |
| `classes.Hn.adv` | tagged list, proportional Hangul only | `cap700`, `em1000` | target |
| `classes.Hn.adv_cap` | tagged list, proportional Hangul only | `ratio` | target |
| `stem` | tagged list | `cap700`, `em1000` | target |
| `stem_h1` | tagged list | `ratio` | target: the weight without a Latin stem |
| `fixed_width` | true when every measured syllable has one advance (within 0.5 %), the commoner answer of the files | | |
| `adv` | tagged list, fixed-width Hangul only | `cap700`, `em1000` | target |
| `adv_cap` | tagged list, fixed-width Hangul only | `ratio` | target |
| `report.overshoot`, `report.hstroke` | tagged list | `cap700`, `em1000` | report only |
| `report.overshoot_h1`, `report.hstroke_h1`, `report.contrast` | tagged list | `ratio` | report only |
| `report.pitch.Hn` | tagged list | `cap700` | report only |
| `report.pitch_h1.Hn` | tagged list | `ratio` | report only |
| `spread` | `{"<path>": {"<unit>": [values]}}` where references of one unit differ by more than 4 %; `{"fixed_width": [answers]}` when files disagree | | ask the person |

A tagged value's `confidence` is the highest of the values merged into it. Every key is optional: a target exists
only when a reference measured it, so a screenshot of Hangul alone gives the ratio keys, `stem_h1` and the ratio
report. Neither `make_targets.py` nor `fit_font.py` needs a Latin field. A measurement file's `hangul` object has
the same keys, plus three that describe how that reference was read and are not merged: `units` (the units it
gives), `held_out.Hn.face_w` and `face_h` (font files, `ratio`) and `cut_at` (screenshots).


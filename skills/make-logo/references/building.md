# Building

A direction is a recipe: a JSON file `build_logo.py` turns into the mark, the wordmark and two lockups. The recipe
names shapes on a grid, OFL glyphs, and traces made by `trace_ref.py`. The full format is in
`uv run scripts/build_logo.py --help`.

## A direction

```json
{"name": "Fieldnote", "title": "Survey ring", "idea": "A level's sighting ring, one quarter left open.",
 "grid": 48,
 "mark": [
  {"shape": "ring", "cx": 24, "cy": 24, "r": 20, "width": 7},
  {"op": "cut", "shape": "rect", "x": 24, "y": 0, "w": 24, "h": 24},
  {"shape": "rect", "x": 27, "y": 4, "w": 17, "h": 17, "r": 2}
 ],
 "wordmark": {"text": "FIELDNOTE", "font": "Space Grotesk", "weight": 500, "tracking": 60},
 "lockup": {"mark_scale": 1.9, "gap": 0.8},
 "palette": {"ink": "#0f3d2e", "paper": "#f2f3ee", "accent": "#c4ea3f", "neutral": "#8fa39a", "tint": "#dfe7e1"}}
```

- **Shapes**: `rect` (with `r` for rounded corners), `circle`, `ring`, `arc` (a band from `start` to `end` degrees),
  `polygon`, `glyph` (letters from an OFL font, outlined), `trace` (see Tracing). `op` is add, cut, keep or xor,
  applied in order. Any shape takes `rotate`, `mirror` and `repeat` (`count` with `rotate`, or `step` for a row).
- **Coordinates on the grid, not free curves.** Agents place shapes well and draw curves badly. Keep every number a
  whole or half grid unit; the construction page draws those lines.
- **Wordmark**: any OFL family on Google Fonts, fetched with its OFL.txt, shaped with HarfBuzz and outlined, with
  `tracking` in thousandths of the em. The build copies each font's OFL.txt into its own `LICENSES/`. If the name
  matches a Reserved Font Name the build warns; those names come only from the OFL's copyright lines
  (`fonts.reserved_font_names`).
- **Lockup**: `mark_scale` is the mark's height over the wordmark's cap height; `gap` is the space between, in cap
  heights. A stacked lockup is written too.
- **Palette**: ink, paper, accent, neutral, tint. The book and the package use these five.

## Directions that differ

Lead with abstract marks that make one move with two or three primitives: two squares overlapped and xor'd with one
tilted ("a sketch snapping to the grid"), a disc cut once, one shape repeated and turned. These read as confident and
hold at 16 px. Literal pictograms (a bell, a chat bubble, a moon) read as stock icons; use them last.

Six directions, each a different answer to the idea, not six versions of one shape. Mix the kinds: idea marks built
from shapes, typographic marks, and traced marks when the person gave you a drawing of their own. At least half carry
the idea as a picture (a hand, a ripple, a ring of voices), not as the first letter. A set of shape-built directions
that works:

- a monogram: the first letter built from the product's own shapes;
- a negative-space letter: the letter carved out of a solid disc, square or tile;
- a stencil mark: one shape split by a clean gap where the idea turns;
- a symbol for the idea: an object or motion from the product's world;
- a pure wordmark with one drawn detail (a cut terminal, a joined pair);
- a construction: a grid, a stack, a fold, a repeat.

Take these moves from the references you measured: open the measured sheet and name, for each direction, the
reference move it borrows. The marks that work are close in spirit to great logos and clearly not copies of any; the
marks that fail are the ones built from nothing (a plain chat bubble, a plain waveform). Prefer crisp, square
terminals; curve an end only when the curve is the idea. When the distance check fails a direction, the silhouette
is too close: change the outline itself (split it, cut it, extend it), not a detail inside it.

Give each its own wordmark face and palette, so the person compares directions, not colours.

## Tracing

A drawing the person made, or their existing brand, has a hand in it that grid shapes can't reach. Trace it and
change it. Only their own material: reference logos, Are.na images and stock photos set proportions and are never
traced, and the scripts refuse them by hash and by likeness.

1. Get the person's answer first (SKILL.md step 6). `brief.json` `trace_sources` holds the file, its sha256, the kind
   of right (`own-drawing`, `own-brand`, `licensed`), the question you showed and their answer, both verbatim.
2. `uv run scripts/trace_ref.py sketches/l.png --brief brief.json --refs <refs> --calibration calibration.json
   --crop x,y,w,h --out trace/<n>.svg` (crop in fractions, around the mark only; `--threshold` and `--invert` for a
   light mark on dark). It refuses a file not in `trace_sources`, a file whose sha256 is in any collection manifest,
   and a crop whose mask, or whose traced path, scores at or over the limit against a collected image or a `--refs`
   logo. Every image whose ink can be told from its ground counts, even one `measure_logo.py` skips (a logo cut close
   out of a screenshot); one it can't read as a mark is printed as "not checked" and listed in the record's
   `gate.not_checked`. The person's own sketch in `--refs` (its sha256 is in `trace_sources`) is left out of that
   comparison.
   potrace draws the curves and drops specks; check for stray type in the crop and cut it.
3. Place it: `{"shape": "trace", "file": "trace/<n>.svg", "x": 2, "y": 2, "size": 44}`, with `rotate` and `mirror` as
   usual. The path is found from the working folder first, then from the recipe's folder. Then change one thing with
   the usual shapes so the mark says the idea: fill a centre, turn it level, add a tail, cut a part away.
4. Build with `--brief brief.json --refs <refs> --calibration calibration.json`. The build reads
   `trace/<n>.svg.provenance.json`, refuses an SVG that changed since it was traced, a source the brief no longer
   vouches for, or a record whose raster arguments no longer give the mask it recorded (an edited crop, say), traces
   the source again behind the same gates, and writes the result and its record into the build.
   Leave `traced_from` out of the recipe: the build refuses it and writes the trace's record into `build.json`
   `traces` itself.
5. Look at it beside the original. A change nobody would notice isn't a change; one that breaks the drawing is too
   much.

The book shows where a traced mark came from, the kind of right, the person's answer and the score against the
source; the trademark sheet says the same in words.

## Type

For a typographic direction, pick a display face with character from Google Fonts' OFL families, not a quiet sans:
Bagel Fat One, Abril Fatface, Fraunces at heavy weights, Syne, Bricolage Grotesque, Instrument Serif, Unbounded.
Pull the first letter out as the mark with a `glyph` shape and set the name in the same face.

## Parts it may also use

- Icons as a starting part: Lucide (ISC), Phosphor, Tabler, Heroicons, Iconoir (MIT), Material Symbols (Apache 2.0),
  as `polygon` points; to trace one, record it in `trace_sources` as `licensed` with the person's answer, like any
  source. Change it until the distance check passes against the icon too: an icon anyone can ship is a weak mark.
  Never Remix Icon, whose licence bans logos even modified, and never a brand-icon set.
- No image model draws final paths.

## Checks

`check_logo.py` renders each mark with resvg and fails a direction on any of:

| Check | Pass |
|-|-|
| Stroke at 16 px | 1.5 px or more (median stroke at 512, scaled) |
| Counters at 16 px | every hole at 512 px still open |
| Ink on paper | 4.5:1 or more |
| Accent against paper or ink | 3:1 or more |
| Nearest reference | under the calibrated limit, against every reference but a traced direction's own source |

On the test brief (three directions for a site-inspection app), all three passed: strokes 2.7 to 4.4 px at 16 px,
nearest reference 0.15, 0.36 and 0.73 against a limit of 0.81.

A traced direction's score against its own source goes into `check.json` `source_scores` and the book, never into a
pass or a fail: a source the person holds rights in may be used unchanged. The references are the trace gates' own:
every `--refs` image whose ink can be told from its ground. The ones it can't read are printed as "not checked" and
listed in `check.json` `refs_not_checked`, beside `refs_compared` and the `limit`. Before checking, `check_logo.py`
confirms every file `build.json` lists still has its sha256 and that the list holds the mark, its grid and, with a
wordmark, the wordmark and both lockups; it renders the mark from those verified bytes. It refuses a traced direction
whose trace was gated against other `--refs` images, another calibration or other collections than the check's
(`trace-gate-stale`), and removes its old `check.json`: build it again. `check.json` then records the sha256 of
`build.json`, of the `--refs` images and of the calibration.

## Package

`package_logo.py` writes, for the chosen direction, into a new folder:

- `svg/`: mark, wordmark, lockup and stacked lockup, each in ink, reversed, accent and black;
- `png/`: the mark from 16 to 1024 px on a transparent square, and the lockup at 1600 wide; `favicon.ico`;
- `LICENSES/`: each font's OFL.txt;
- `trademark-search.md`: where to search the name and the design codes of the shapes the recipe uses (build.json
  `shapes`; KIPRIS for Korea), that it is not a clearance, what the distance check compared (how many references,
  the ones it could not read, the nearest score, the limit and which calibration set it), and, for a traced mark, its
  source, the kind of right, the person's question and answer verbatim, and the other shapes the recipe combines the
  trace with, or that it has none; in the brief's language;
- `brand.json`: the palette, the fonts and any trace's source and statement.

It reads only the verified bytes of the files `build.json` lists, so a part an earlier build left in the folder never
ships, and it refuses a build whose `check.json` is missing, failed, or no longer matches `build.json`, its files, the
`--refs` images or the calibration.

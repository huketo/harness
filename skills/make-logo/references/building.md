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
   logo. Every image counts, even one `measure_logo.py` skips (a logo cut close out of a screenshot): an SVG is
   rasterised with resvg, a raster too small to split (a 16 px favicon) is enlarged, an image with transparency is
   seen on white and on black (a sheet may hold a dark logo and a light one), and one with an EXIF orientation (a
   camera's JPEG stored on its side) as stored and as shown, its highest score counting. While an
   image still can't be read as one mark, the trace is refused (`not-comparable`, naming it): take it out of the
   folder, or out of its collection, or replace it with one mark cropped out of it on a plain ground. That includes a
   sheet whose mask, on white or on black, keeps under 90% of the ink seen there: a second mark, or a favicon beside a
   large logo that the split drops as a speck, would never be compared. A `--refs` folder or file that is not there,
   a folder in them that can't be listed, or an image that is a broken link, is refused by name (`refs-missing`). A
   collection that is or holds a symbolic link (`collection-linked`), one that holds a file its manifest does not
   list (`collection-unlisted`: a pull that stopped, or a file put there by hand), or a
   collected file that is gone or no longer has the sha256 its manifest lists (`collection-changed`), is refused too;
   `node scripts/collection.mjs <name>` clears what a stopped pull left and lists what the collection holds now. Last,
   the file and the part `--crop` takes are compared as pictures with every collected image, whatever
   `trace_sources` lists, and one that is the same picture saved again, resized, cut a little, made lighter or darker,
   or partly made clear is refused (`collected-copy`; see Same picture). The person's own sketch in `--refs` (its
   sha256 is in `trace_sources`) is left out of the mask and path comparisons; a collected file never is.
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

### Same picture

The mask and path gates compare marks: the source cut at `--threshold`, each reference split from its ground. A
photo (a 3D mockup, a sign on a wall) has no one mark to split, so the two masks can cover different parts of the
same picture: in a real run a re-saved or slightly cut copy of a collected photo scored 0.37 to 0.45 against a limit
of 0.795. `same_picture.py` compares the pictures themselves, at every step (trace, check, package, book), with
every collected image whatever `trace_sources` lists, and with no `--refs` image. Each image is seen in grey,
squeezed into a square (a crop changes the aspect), on white and, with transparency, on black and as its colour
channels alone (what potrace gets of a source). One with clear pixels is also seen on black with its alpha, and one
with an EXIF orientation both as stored and as shown. One is compared with every window of the other that leaves out
up to an eighth of each side, at 32 px, both ways round, and the best window is refined to 1/128 of a side at 64 px.
Each view is compared less its blur (sigma an eighth of its side), so light falling across a wall counts for
nothing, and the score is the correlation of the pixels, 1 for the same picture at any brightness and contrast.
Where either picture has clear pixels, only what both show counts: each pixel counts as much as both show of it, and
each view is less a plane fitted around each pixel to what both show, so the colour under a clear pixel, which a
copy can set to anything, reaches no pixel that shows. A window where both show under a tenth of it (`MIN_SHOWN`)
scores 0, and so does one where what both show holds under a quarter of either picture's own detail (`MIN_HELD`),
measured at 32 px for the refined windows too: one edge of a mark, or one side of a ball, matches a window of other
pictures as well. A pixel of the square averages what a copy shows with what it hides, so where its clear pixels are
finer than that (stripes a pixel or two wide), each pixel of the other picture's square holds what the copy hides:
copies of a test photo crossed by threads a pixel wide, with stripes of 1 to 6 px made clear, scored 0.65 to 0.89.
So two views, one or both with clear pixels, whose search reaches `FLOOR` (0.5) are compared again at their own
size: the one with clear pixels is laid on the other where the 64 px search put it, each way round, and moved to
within an eighth of its own pixel by its fine detail where it shows (each pixel less the mean of the 5 px square
around it), no further than 1/128 of a side; then each 64 px cell averages only its own pixels that show and the
other's resampled onto them. The searches at 32 and 64 px only find where: on a photo of pixel-wide lines, a mask
laid 1 px off scored 0.20 to 0.87 where laid true it scored 1.00. Moved by all of what shows rather than its fine
detail, a copy of one test photo with its centre clear rose from 0.81 to 0.94 against another photo staged alike,
and to 0.90 within the bound; moved by its fine detail, 0.83. Two views without clear pixels score as before, bit
for bit. The gate refuses at `LIMIT` = 0.85 and over.

Measured with the committed `same_picture.py` on the 150 collected images of a real run (Are.na pulls and stock
photos; 74 flat marks, 76 photos, scenes and sheets) and the test fixtures' 8 photos (a box, a ball and a printed
word on a lit wall, staged alike):

| Pairs | n | Score |
|-|-|-|
| Each image against its copies: saved again as PNG, JPEG q75 or WebP; 2 to 10% cut off every side, one side or at random; 50% and 200% size; 10% darker or lighter; cut, halved and saved as JPEG at once; a plain ground made clear, its colour kept or zeroed; a JPEG stored turned or mirrored with the EXIF orientation (2 to 8) that shows it, and the shown pixels of such a JPEG against it | 4,740 | lowest 0.8590 (a photo keyed to 6% of itself, colour zeroed) |
| Each image against its partly clear copies that hold a quarter of its detail: 65, 40 or 20% shown with the centre, the edges or patches of 1/80 of the long side made clear, or 50 or 62.5% shown in stripes (1 of every 2, 2 of 4, 5 of 8 or 20 of 32 columns or rows of the image at 1,024 px at most, the first three mostly finer than a pixel of the square); then saved as WebP, cut 4% each side or 10% on one, or halved, and the stripes also as they are. Each copy twice, the colour under its clear pixels zeroed and noise | 9,845 copies (19,690 scores) | lowest 0.8525, but 21 of the 9,845 copies (42 of the 19,690 scores) under 0.85: below |
| Each image saved again, cut, resized, made lighter or darker, or turned with EXIF, before any part is made clear | 1,422 | lowest 0.9429 |
| Every pair of different images | 11,175 | highest 0.7197 (two white-on-black wordmarks from one studio, checked by eye: different marks); 99.9th percentile 0.5889 |
| A clear copy of each image (the centre or the edges made clear, 12 to 65% shown; 1 of every 2 or 5 of 8 columns, 2 of 4 or 20 of 32 rows; a plain ground made clear) against other images, sampled (below) | 32,146 | highest 0.8087, but 1 at 0.89: below |
| The test fixtures' own marks (also on a clear ground), photos and their cut-outs against each image | 3,750 | highest 0.6302 |
| The fixture photos against each other | 28 | highest 0.8375 |
| A fixture photo's cut-out, or a copy of it with part made clear (stripes too), against the other photos | 1,176 | highest 0.9412; 12 at 0.85 or over |

0.85 sits between every edited copy and every pair of different images. Among clear copies it does not, and these
are measured:

- A one-colour mark on a clear ground, partly made clear, can pass (17 copies of one black wordmark, 4 of them in
  stripes of 20 of 32 and cut: 0.67 to 0.84). Where it shows it is one colour, so the view with alpha finds no
  detail; the flattened views compare it, and in them the clear part reads as ground.
- A copy whose clear part takes most of the detail and that is also cut can pass (40% shown with the centre clear,
  cut 4% each side: 0.40 and 0.83): what shows holds 0.18 and 0.24 of the image's detail at the window that undoes
  the cut, under `MIN_HELD`.
- An image shown only as a thin band can pass (a wordmark 20% shown with the centre clear, saved as WebP or halved:
  0.59 and 0.59, where its band holds a third of its detail).
- A copy that shows only a thin band can be refused against an image whose border looks alike (1 of 32,146 sampled
  pairs, 20% shown with the centre clear: 0.89).
- A cut-out, or a copy showing 12 to 40%, of a photo staged like a collected one can be refused (the fixture photos:
  12 of 1,176, up to 0.94); the whole photo passes (0.84 at most).
- A copy made clear in stripes finer than its pixels and then resized keeps no record of which pixels it hid:
  halved, a copy with every other column clear shows each pixel half (alpha 0.50, give or take 0.01), so it is
  compared whole. Of the threaded test photo it scores 0.84 (every other row: 0.75), and 1.00 against the photo's
  own shown columns halved alike: what it lacks is the threads it hid. Every collected image so copied and halved
  scored 0.86 or more.
- Only a pairing whose 32 px search reaches `FLOOR` is compared at its own size, and that search averages what a
  copy hides: striped copies of a photo dense with lines a pixel wide, cut 2 to 7% a side, scored 0.57 there at the
  lowest.

Raising `MIN_SHOWN` to a quarter keeps 12 of those 13 different pairs under 0.85 (a copy showing 40% is untouched:
0.85), but passes a keyed copy that shows 14% of a collected logo (0.81) and 430 of the 504 copies above that show
20%. Comparing only what shows is what refuses that keyed copy: it scores 1.00, and 0.81 with the flattened views
alone. Measuring what a refined window holds at 32 px is what refuses a fixture photo with its centre clear (65%
shown, holding 0.26 to 0.28 of its detail) once it is also cut 2 to 5% each side: 0.97 to 0.98, where at 64 px it
held 0.23 to 0.25 and scored 0.40 to 0.82; letting the refinement leave `MIN_HELD` behind instead raised a copy of
one fixture photo against another to 0.95.

The partly clear copies and the clear copies against other images were cut as below; with the stripes added, each in
every cell of its own (eight stripes, both colours, the four edits and none), the run took 137 minutes on 18
processes. A pilot on 10 of the collected images and the fixture photos scored every cell (90, 65, 40, 20 and 12%
shown; five shapes, single pixels and patches of 1/20 included; colour kept, zeroed or noise; nine edits) and every
clear copy against every other image. The run keeps the values whose lowest copy in a first pilot scored under 0.95,
leaves out the kept colour (never more than 0.016 under zeroed for the same copy) and, among the clear copies
against other images, the patch copies (0.47 at most, against 0.79); it compares each clear copy with the images in
the 100 highest pairs with it, its own 2 highest partners, the 8 images the pilot's clear copies scored highest
against, and 6 more drawn with a fixed seed. On the pilot the reduced grid's lowest copy was the full grid's for
every image (0.9191 at the lowest), and the sample's highest pair was the full set's (0.7941), also with the 8
images taken from the other half of the pilot. None of the images behind the 21 copies and the pair above was in the
pilot. Against 150 images the gate reads each one once more (2.6 seconds), then takes 0.2 to 0.4 seconds for an
opaque source or a cut copy (the first source about a second more) and 10 to 14 for a source with clear pixels;
about 20 for one that reaches `FLOOR` against many of them (a keyed mark: 15 of 150), as each of those pairings is
compared again at its own size, each way round.

It does not see a copy turned (other than by its EXIF orientation) or mirrored, cut by more than an eighth on a
side, shown as a small part of a larger picture, keyed until under a tenth of it shows (the views without alpha
still compare it: the copy keyed to 6% scored 0.8590), with its tones inverted, or the partly clear copies above, a
resized one made clear finer than its pixels among them; the mask and path gates still compare its mark. A copy of a
`--refs` image that no collection lists is left to the mask and path gates, which can miss a photo. Those gates, and
the check's distance check, see a reference with an EXIF orientation both as stored and as shown, so a mark drawn
again from what such a file shows is compared too. They read a source as stored, as potrace traces it: one that its
EXIF orientation turns is compared as the turned mark it holds, and they can miss a mark turned a quarter.

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
every `--refs` image, SVGs included, read the same way, and the check refuses to run while one can't be read as a
mark (`not-comparable`), removing the builds' old `check.json`. `check.json` records `refs_compared` and the `limit`.
Before checking, `check_logo.py` confirms every file `build.json` lists still has its sha256 and that the list holds
the mark, its grid and, with a wordmark, the wordmark and both lockups; it renders the mark from those verified
bytes. For a traced direction it first runs the same-picture gate again on the source, against the collections as they
are now: a source a collection now lists (`collected`), or a copy of a collected image (`collected-copy`), is
refused, so a copy collected after the trace, or a trace made before this gate, goes no further. It refuses a traced direction whose trace was gated
against other `--refs` images, another calibration or other collections than the check's (`trace-gate-stale`), or
while a collected file is gone or changed (`collection-changed`), and removes its old `check.json`: build it again,
or, for a copy, drop the direction. `check.json` then records the sha256 of
`build.json`, of the `--refs` images, of the calibration and, for a traced direction, of the collections
(`collected_sha256`; `null` for one with no trace).

## Package

`package_logo.py` writes, for the chosen direction, into a new folder:

- `svg/`: mark, wordmark, lockup and stacked lockup, each in ink, reversed, accent and black;
- `png/`: the mark from 16 to 1024 px on a transparent square, and the lockup at 1600 wide; `favicon.ico`;
- `LICENSES/`: each font's OFL.txt;
- `trademark-search.md`: where to search the name and the design codes of the shapes the recipe uses (build.json
  `shapes`; KIPRIS for Korea), that it is not a clearance, what the distance check compared (how many references,
  the nearest score, the limit and which calibration set it), and, for a traced mark, its source, the kind of right,
  the person's question and answer verbatim, and the other shapes the recipe combines the trace with, or that it has
  none (never that the trace kept its shape: `rotate` and `mirror` change it too); in the brief's language;
- `brand.json`: the palette, the fonts and any trace's source and statement.

It reads only the verified bytes of the files `build.json` lists, so a part an earlier build left in the folder
never ships, and it refuses a build whose `check.json` is missing, failed, or no longer matches `build.json`, its
files, the `--refs` images or the calibration, or, for a traced direction, its source or the collections
(`collections-changed`); a traced source must also pass the same-picture gate again (`collected`, `collected-copy`),
judged before the `--refs` images, so a copy that a pull brings into a collection that is also a `--refs` folder is
named as one. It verifies all of that before it creates the output folder.

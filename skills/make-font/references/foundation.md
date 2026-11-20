# Finding the foundation

The base decides most of what the font looks like. Fitting moves widths, weight and spacing. It cannot change
a terminal, a serif's shape, a two-storey g into a one-storey g, or the angle of stress. So the search ranks
on the numbers fitting cannot fix as heavily as on the ones it can.

## Where candidates come from

- The Fontsource catalogue, `https://api.fontsource.org/v1/fonts`, one request: every Google Fonts family with
  its category, licence, scripts, weights and whether it is variable.
- The google/fonts GitHub tree, one request: every file path. Variable fonts carry their axes in the file name,
  `Family[opsz,wght].ttf`, so the axes are known before a download.
- Font files from `raw.githubusercontent.com/google/fonts/main/ofl/...`, with the family's `OFL.txt`.
- Any `--local` folder of fonts the person already has. A local font without the OFL notice in name ID 13 is
  skipped. Put its `OFL.txt` beside it: the approval step records that file.

Kept: the SIL Open Font License 1.1 only, a TrueType variable font in `ofl/`, the asked category (from
`targets.json`'s category: sans-serif, serif or monospace; `--category` for display or handwriting), every asked
script in its subsets, a main script that is one of them, an upright style, and no math, symbol or icon family.
An Apache-2.0 family is not a base, even when named with `--families`.

GitHub limits requests without a token to 60 an hour. With `GITHUB_TOKEN` set, the script sends it to
`api.github.com` and `raw.githubusercontent.com` only (to curl through its standard input, never on the command
line) and never prints it. A 403 or 429 stops the search with the requests left, the reset time and the way on:
a token, waiting, or `--offline`. `--offline` downloads nothing: it reads the catalogue, the tree and the font
files from `--cache` and skips what is not there.

## Two passes

1. Coarse. A small Latin WOFF2 of each family near weight 400 from the jsDelivr Fontsource mirror, measured and
   scored without the stem (weights differ). A few hundred files, a few minutes the first time, cached after.
2. Fine. The best `--shortlist` families, whole. On a weight axis the n stem is solved to the target. On an
   optical-size axis three sizes are tried, chosen by use: text leans small, display leans large.

## The score

Distance is the root of the weighted sum of squared, scaled gaps (`fontlib.DISTANCE`):

| Number | One unit of distance | Weight |
|-|-|-|
| x-height to cap | 0.015 | 3 |
| contrast | 0.06 | 2 |
| serif reach | 12 | 1.5 |
| ascender, descender | 15 | 1 |
| bar to stem, rhythm | 0.08 | 1 |
| serif tip | 10 | 1 |
| each class width | 2.5 % | 0.5, or 0.125 when the width axis can move toward the target |

A serif against a sans adds 50: never fit one into the other. A width axis helps only in the direction it can
move from the measured location: an axis from 75 to 100 that sits at 100 can narrow a class, not widen it. So a
class that is too narrow keeps its full weight on such a font, and the shortlist shows each axis as `narrow`,
`widen`, both or `fixed`. The score adds a penalty for axes the fit needs: 0 with width and weight, 0.5 to 0.75
with weight alone. A width axis that cannot move the way a class beyond the 3 % stretch limit needs counts as
missing.

## Choosing

Show three to five rows with their deltas, axes, licence and Reserved Font Names. Then look. Render each at
display size beside a reference, with cap heights matched. A candidate that wins on numbers but has the wrong
skeleton (an oldstyle against a transitional, angled stress against vertical, a ball terminal against a sharp
one) is the wrong base. Say why in one line per candidate and recommend one.

Prefer, in order: the right skeleton, a weight axis, a width axis that moves the right way, an optical-size axis
(it holds contrast), coverage of the scripts, then the score.

Wait for the person's answer before fitting, and record it with `record_base.py` (SKILL.md step 5): the
question you asked and their answer, verbatim, bound to the base's and its `OFL.txt`'s sha256 in `base.json`.
Keep the shortlist JSON: the approval step reads the chosen row from it.

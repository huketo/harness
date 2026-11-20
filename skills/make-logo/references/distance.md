# Distance

`distance.py` says how close a variant is to each reference and fails it when the nearest is too close. It is a
guardrail against a near copy of these references, never a legal clearance.

## The measures

Both marks are fitted into the same 128 px box, so size, position and ground colour don't count. The variant is tried
as is, mirrored, and turned up to 6° either way; every measure is taken at its closest pose.

- `overlap`: intersection over union of the silhouettes.
- `edges`: mean nearest distance between the outlines, both ways, in thousandths of the box.
- `hash`: matching bits of a 63-bit DCT hash.
- `negative`: intersection over union of the negative space, what the ink leaves empty inside its convex hull
  (counters, notches, a carved letter); 1 when neither has any.
- `skeleton`: mean nearest distance between the skeletons, both ways, in thousandths of the box.
- `thickness`: earth mover's distance between the local thicknesses along the skeletons, in thousandths of the box.

`score`, 0 to 1, is a logistic model on the features the calibration file lists, fitted by `calibrate.py`
(`--features`, by default the shipped file's). The shipped file lists `overlap`, `edges` and `hash`; the other three
are measured and printed, and stay out of it ("The shape measures" below). With no reference showing a mark,
`distance.py` prints "not checked" and exits 2: nothing was compared, so nothing is clear.

## Calibration

`calibrate.py` fits the model and sets the limit from the references themselves:

- different pairs: every pair of distinct references (a pair overlapping over 0.9 is the same logo uploaded twice and
  is set aside);
- near copies: each reference against edited copies of itself, the edits a trace-and-change makes: turned 4°,
  thickened, thinned, stretched 10%, a part cut away, a part added, mirrored, and three at once.

The limit is where 10% of references reach it against their nearest other reference. That's the number that matters:
a variant is checked against all of them, so a per-pair limit would trip on almost every original mark (at 2% per
pair, about 86% of marks against 98 references).

On 98 Are.na references (2026-11-15). The held-out column fits the model on half of them and tests on the other 49
(limit 0.64 there); the second column fits and tests on all 98 (limit 0.81, the shipped default), so it flatters a
little:

| Edit | Held-out half | All 98 |
|-|-|-|
| turned 4° | 100% | 97% |
| thicker | 98% | 92% |
| thinner | 94% | 92% |
| stretched 10% | 98% | 97% |
| mirrored | 100% | 98% |
| part cut away | 100% | 94% |
| part added | 100% | 97% |
| three at once | 94% | 81% |

The limit grows with the number of references, because more of them means a closer nearest one; the catch rate falls
with it. With the person's own 30 or more, recalibrate on them.

## The shape measures

`negative`, `skeleton` and `thickness` are there for marks whose silhouettes meet: a coin with an L carved through it
scores 0.90 against a ring-shaped reference (0.94 under a calibration fitted on 77 references). They do set such
pairs apart: across eight of them `negative` is 0.26 to 0.42 and `skeleton` over 27, where the median edited copy is
over 0.5 and under 15. Fitted with `calibrate.py`, they still leave those pairs over the limit. On 73 Are.na
references (2026-11-20), every combination caught held-out copies at the three's rate, within half a point, or
better (`negative`: three at once 82% to 97%). But the fit took the new measures as more evidence of a copy, the
limit fell with them, and seven of the eight pairs stayed over it in every combination; the coin went under only with
`skeleton` and without `negative` (0.67 against 0.75). The references hold almost no different marks with one
silhouette (2 of 2628 pairs overlap over 0.6), so the fit never learns what such a pair looks like. The shipped
model keeps the three silhouette measures.

## What it misses

- The near copies come from these edits, not from real remixes. A remix that redraws a mark in a new style can keep
  its idea and still score low. The look in step 8 is the backstop.
- Silhouettes stop telling dense, heavy marks apart: a row of rounded bars drawn from nothing scored 0.84 against a
  heavy wordmark. About 1 original mark in 10 is flagged; that's the cost of the limit, and it's why a flag means
  "look at the three nearest", then build another variant.
- Marks that share only a silhouette score as copies: a disc with a letter carved through it against a ring, a tile
  with an L against a tile with a round hole, 0.89 to 0.98 under the shipped calibration. `negative` and `skeleton` in
  the output show the difference; the score doesn't.
- It compares shapes, not ideas or names. Trademark risk comes from looking alike in a market, which needs the search
  sheet and, before filing, a clearance search.
- Next, if the cheap measures miss real lookalikes: an image embedding (DINOv2 or DreamSim) as a fourth feature.

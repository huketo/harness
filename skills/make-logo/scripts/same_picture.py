# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "resvg-py"]
# ///
"""The same-picture gate (references/building.md, "Same picture"): is a file to be traced a collected image saved
again, resized, cut a little at the edges, made lighter or darker, or with part of it made clear?

The distance gates compare marks: the source cut at a fixed grey level, each reference split from its ground. A
photo has no one mark to split, so those two masks can cover different parts of the same picture, and a re-saved or
cropped copy of a collected photo passes them. This compares the pictures themselves, with every collected image
(never with a --refs image: the distance gates compare those):

1. Each image is seen in grey, squeezed into a SQUARE x SQUARE square (a crop changes the aspect, so it is dropped):
   flattened on white and, when it has transparency, on black and as its colour channels alone, which is what
   trace_ref.raster_mask() gives potrace. One with clear pixels is also seen on black with its alpha, so that only
   what it shows counts (step 5). One with an EXIF orientation is seen both as stored and as shown. A source is also
   seen as the part --crop takes.
2. One square is compared with every window of the other that leaves out up to CUT of each side, on a STEP grid, at
   COARSE x COARSE px, both ways round: the one a crop of the other, or the other with a border.
3. The best window of each pairing whose score reaches FLOOR there is refined to 1/128 of a side, at FINE x FINE px.
4. Each view is compared less its blur (a Gaussian, sigma an eighth of its side), so light falling across a wall
   counts for nothing, and the score is the correlation of the pixels (Pearson's r): 1 for the same picture whatever
   its brightness and contrast.
5. Where either view has alpha, only what both show counts, so the colour under a clear pixel, which a copy may set
   to anything, counts for nothing: each pixel's colour is its value on black over its alpha, it counts as much as
   both show of it, and each view is less a plane fitted around each pixel to what both show (_Plane) rather than
   its blur, which would carry the hidden colour, or the ground a copy is flattened on, into the pixels that show. A
   window scores 0 where both show under MIN_SHOWN of it, or where that part holds under MIN_HELD of either view's
   own detail where it shows: one edge of a mark, or one side of a ball, matches some window of other pictures too.
   What a window holds is measured at COARSE px in the refinement too: at FINE px a picture's sharpest edges weigh
   more, so a copy whose clear part takes them would hold less of its detail at the window that undoes its cut.

A pairing's score is its refined score, or its coarse score under FLOOR; two images score the highest of their
pairings. The gate refuses at LIMIT and over. It does not see a picture turned (but by its EXIF orientation),
mirrored, cut by more than CUT on a side, reduced to a small part of a larger one, or a copy that shows under
MIN_SHOWN of it or holds under MIN_HELD of its detail at COARSE px.
"""
from __future__ import annotations

import os
import sys
from functools import cache
from typing import NamedTuple

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logolib as L  # noqa: E402
import rights as R  # noqa: E402

# Measured on 150 collected images (references/building.md, "Same picture"): their edited copies scored 0.8590 or more,
# every pair of different images, a clear-ground copy against another image included, 0.7246 or less; every copy
# reached FLOOR before refining. At MIN_SHOWN 0.05 a clear-ground copy scored 0.7636 against another image.
LIMIT = 0.85
FLOOR = 0.5
MIN_SHOWN = 0.1
MIN_HELD = 0.25
SQUARE, COARSE, FINE = 128, 32, 64
CUT, STEP = 1 / 8, 1 / 32
WHOLE = (0.0, 0.0, 1.0, 1.0)
WHITE, BLACK = (255, 255, 255), (0, 0, 0)


def _square(grey: Image.Image) -> np.ndarray:
    return np.asarray(grey.resize((SQUARE, SQUARE), Image.BOX), dtype=np.float32) / 255


def _grounds(im: Image.Image) -> list[tuple[np.ndarray, np.ndarray | None]]:
    """(grey, alpha or None) squares of `im`: on white and, with transparency, on black and as its colour channels
    alone; with clear pixels, on black again with the alpha that says how much of each pixel shows (on black, a pixel
    is its colour times that alpha)."""
    if not L.transparent(im):
        return [(_square(im.convert("L")), None)]
    rgba = im.convert("RGBA")
    on = {g: _square(Image.alpha_composite(Image.new("RGBA", im.size, (*g, 255)), rgba).convert("L"))
          for g in (WHITE, BLACK)}
    out = [(on[WHITE], None), (on[BLACK], None), (_square(rgba.convert("L")), None)]  # last: as raster_mask() reads it
    alpha = _square(rgba.getchannel("A"))
    if alpha.min() < 1:
        out.append((on[BLACK], alpha))
    return out


def views(im: Image.Image, crop=WHOLE) -> list[tuple[np.ndarray, np.ndarray | None]]:
    """The (grey, alpha or None) squares `im` is compared as, of the part `crop` (x, y, w, h in fractions) takes:
    _grounds() of it as stored and, with an EXIF orientation, as shown (logolib.orientations). Floats 0-1."""
    x, y, w, h = (float(v) for v in crop)
    W, H = im.size
    part = im.crop((round(x * W), round(y * H), round((x + w) * W), round((y + h) * H)))
    return [v for p in L.orientations(part) for v in _grounds(p)]


def _resample(m: int, n: int, a: float, b: float) -> np.ndarray:
    """n x m: row j averages the m pixels of a side under the j-th of n equal parts of [a, b] (fractions of the side),
    each pixel weighted by how much of it lies there."""
    edges = (a + (b - a) * np.arange(n + 1) / n) * m
    k = np.arange(m)[None, :]
    w = np.clip(np.minimum(edges[1:, None], k + 1) - np.maximum(edges[:-1, None], k), 0, None)
    return (w / w.sum(1, keepdims=True)).astype(np.float32)


def _blur(n: int) -> np.ndarray:
    """n x n: a Gaussian blur of a side of n pixels, sigma n / 8, each row summing to 1."""
    i = np.arange(n)
    g = np.exp(-0.5 * ((i[:, None] - i[None, :]) / (n / 8)) ** 2)
    return (g / g.sum(1, keepdims=True)).astype(np.float32)


class _Spans:
    """Windows along one side of m pixels, each named by what it leaves out of the two ends, resampled to n pixels:
    `take` stacks their n x m resampling matrices, `blurred` the same then blurred. Every window of a square, and its
    blur, is then two matrix products."""

    def __init__(self, m: int, n: int, spans: list[tuple[float, float]]):
        self.n, self.spans = n, spans
        take = [_resample(m, n, a, 1 - b) for a, b in spans]
        g = _blur(n)
        self.take, self.blurred = np.concatenate(take), np.concatenate([g @ t for t in take])


def _by_window(down: _Spans, across: _Spans, v: np.ndarray) -> np.ndarray:
    """(windows down, windows across, n * n) from the stacked products of down's and across's matrices."""
    n = down.n
    v = v.reshape(len(down.spans), n, len(across.spans), n).transpose(0, 2, 1, 3)
    return v.reshape(len(down.spans), len(across.spans), n * n)


def _details(down: _Spans, across: _Spans, square: np.ndarray) -> np.ndarray:
    """(windows down, windows across, n * n): the window of `square` each pair of spans takes, less its blur, as a
    vector of mean 0 and length 1; one with no detail left (under a thousandth, in 0-1 grey) is all zeros."""
    v = _by_window(down, across, down.take @ square @ across.take.T - down.blurred @ square @ across.blurred.T)
    v = v - v.mean(-1, keepdims=True)
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    return np.where(norm > 1e-3, v / np.maximum(norm, 1e-12), 0).astype(np.float32)


def _windows(down: _Spans, across: _Spans, square: np.ndarray) -> np.ndarray:
    """(windows down, windows across, n * n): the window of `square` (grey or alpha) each pair of spans takes."""
    return _by_window(down, across, down.take @ square @ across.take.T)


@cache
def _plane_blurs(n: int) -> list[np.ndarray]:
    """n x n: _blur(n)'s Gaussian times the offset from each pixel (in sigmas) to the power 0, 1 and 2."""
    i = np.arange(n)
    d = (i[None, :] - i[:, None]) / (n / 8)
    g = np.exp(-0.5 * d ** 2)
    return [g * d ** k for k in range(3)]


class _Plane:
    """A plane fitted around each pixel of each row of `w`'s n x n squares: least squares weighted by the Gaussian of
    _blur(n) and by `w`, how much of each pixel counts. A local mean would leave the slope of light falling across a
    wall at every edge of what shows, and two lit walls would agree there; a plane takes it away. A small ridge on the
    slope makes a pixel whose neighbours lie on one line less their mean."""

    def __init__(self, w: np.ndarray):
        self.w, self.n = w, round(np.sqrt(w.shape[1]))
        s00, s10, s01, s20, s11, s02 = (self._moment(w, p, q) for p, q in ((0, 0), (1, 0), (0, 1), (2, 0), (1, 1),
                                                                          (0, 2)))
        s20, s02 = s20 + 1e-3 * s00, s02 + 1e-3 * s00
        det = s00 * (s20 * s02 - s11 * s11) - s10 * (s10 * s02 - s11 * s01) + s01 * (s10 * s11 - s20 * s01)
        det = np.where(det > 1e-12, det, np.inf)
        self.of = [(s20 * s02 - s11 * s11) / det, (s11 * s01 - s10 * s02) / det, (s10 * s11 - s20 * s01) / det]

    def _moment(self, v: np.ndarray, p: int, q: int) -> np.ndarray:
        blurs, n = _plane_blurs(self.n), self.n
        return (blurs[p] @ v.reshape(-1, n, n) @ blurs[q].T).reshape(len(v), n * n)

    def less(self, v: np.ndarray) -> np.ndarray:
        """Each row of `v` (or its one row against each of w's) less the plane fitted to it."""
        vw = v * self.w
        return v - sum(self._moment(vw, p, q) * c for (p, q), c in zip(((0, 0), (1, 0), (0, 1)), self.of))


class _Shown(NamedTuple):
    """A view's rows (n x n squares) ready for _shown_scores()."""
    colour: np.ndarray  # a view with alpha is on black: each pixel's value over its alpha, whatever the rows averaged
    alpha: np.ndarray | None
    held: np.ndarray  # where its detail lies: its detail squared where it shows, each row summing to 1 (0: no detail)
    plane: _Plane | None  # fitted over its alpha
    detail: np.ndarray | None  # its colour less that plane


def _shown(v: np.ndarray, alpha: np.ndarray | None, details: np.ndarray | None = None) -> _Shown:
    """`v`'s rows as _Shown, with `alpha`'s; a view without alpha passes its details() for where its detail lies."""
    v = v.astype(np.float64)
    if alpha is None:
        return _Shown(v, None, details.astype(np.float64) ** 2, None, None)
    alpha = alpha.astype(np.float64)
    v = np.divide(v, alpha, out=np.zeros_like(v), where=alpha > 0)
    plane = _Plane(alpha)
    detail = plane.less(v)
    held = alpha * (detail - (alpha * detail).sum(1, keepdims=True) / np.maximum(alpha.sum(1, keepdims=True),
                                                                                1e-12)) ** 2
    total = held.sum(1, keepdims=True)
    return _Shown(v, alpha, np.where(total > 1e-6, held / np.maximum(total, 1e-12), 0), plane, detail)


def _held(x: _Shown, y: _Shown) -> np.ndarray:
    """For each row of `x` against `y` (one row): the lower of the two views' shares of their own detail where both
    show."""
    if x.alpha is not None and y.alpha is not None:
        w = x.alpha * y.alpha
    else:
        w = x.alpha if x.alpha is not None else y.alpha
    return np.minimum((w * x.held).sum(1), (w * y.held).sum(1))


def _shown_scores(x: _Shown, y: _Shown, held: np.ndarray) -> np.ndarray:
    """The score of each row of `x` against `y` (one row), one or both with alpha, where both show: Pearson's r of
    their colours less a plane, each pixel weighted by how much both show of it, the plane fitted to that weight too
    (_Plane), so what a clear pixel hides, or the ground a copy is flattened on, reaches no pixel that shows. 0 for a
    window where they show under MIN_SHOWN of it, where `held` (each row's _held(), at COARSE px) is under MIN_HELD
    (one edge of a mark, one side of a ball: some window of other pictures matches it as well), or where either has no
    detail left (under a thousandth, in 0-1 grey)."""
    if x.alpha is not None and y.alpha is not None:
        plane = _Plane(x.alpha * y.alpha)
        w, dx, dy = plane.w, plane.less(x.colour), plane.less(y.colour)
    elif x.alpha is not None:  # what both show is what x shows: x's own plane
        w, dx, dy = x.alpha, x.detail, x.plane.less(y.colour)
    else:
        w, dx, dy = y.alpha, y.plane.less(x.colour), y.detail
    n = w.shape[1]
    s = w.sum(1)
    dx = dx - (w * dx).sum(1, keepdims=True) / np.maximum(s, 1e-12)[:, None]
    dy = dy - (w * dy).sum(1, keepdims=True) / np.maximum(s, 1e-12)[:, None]
    vx, vy = (w * dx * dx).sum(1), (w * dy * dy).sum(1)
    ok = (s >= MIN_SHOWN * n) & (held >= MIN_HELD) & (vx > 1e-6) & (vy > 1e-6)
    return np.where(ok, (w * dx * dy).sum(1) / np.sqrt(np.where(ok, vx * vy, 1)), 0.0)


SPANS = [(a, b) for a in np.arange(0, CUT + 1e-9, STEP) for b in np.arange(0, CUT + 1e-9, STEP)]  # off the two ends
_COARSE = _Spans(2 * COARSE, COARSE, SPANS)
_COARSE_WHOLE = _Spans(2 * COARSE, COARSE, [(0, 0)])
_FINE_WHOLE = _Spans(SQUARE, FINE, [(0, 0)])


def _halve(square: np.ndarray) -> np.ndarray:
    return square.reshape(2 * COARSE, SQUARE // (2 * COARSE), 2 * COARSE, -1).mean((1, 3))


def _whole(spans: _Spans, square: np.ndarray, alpha: np.ndarray | None, details: np.ndarray) -> _Shown:
    """A view whole, as _shown() gives it, at the size `spans` (one window, none left out) resamples to."""
    return _shown(_windows(spans, spans, square)[0], None if alpha is None else _windows(spans, spans, alpha)[0],
                  details[None])


class Picture:
    """An image's views, ready to compare: each whole at both sizes, as detail and as _shown() gives it, and its coarse
    windows when first asked for."""

    def __init__(self, views: list[tuple[np.ndarray, np.ndarray | None]]):
        self.squares = [s for s, _ in views]
        self.alphas = [a for _, a in views]
        self.halves = [_halve(s) for s in self.squares]
        self.coarse = [_details(_COARSE_WHOLE, _COARSE_WHOLE, h)[0, 0] for h in self.halves]
        self.fine = [_details(_FINE_WHOLE, _FINE_WHOLE, s)[0, 0] for s in self.squares]
        self.coarse_shown = [_whole(_COARSE_WHOLE, h, None if a is None else _halve(a), d)
                             for h, a, d in zip(self.halves, self.alphas, self.coarse)]
        self.fine_shown = [_whole(_FINE_WHOLE, s, a, d) for s, a, d in zip(self.squares, self.alphas, self.fine)]
        self._details = self._shown = None

    def details(self) -> list[np.ndarray]:
        """Each view's coarse windows less their blur, as _details() gives them, (len(SPANS) ** 2, COARSE ** 2): row i
        leaves out SPANS[i // len(SPANS)] down and SPANS[i % len(SPANS)] across."""
        if self._details is None:
            self._details = [_details(_COARSE, _COARSE, h).reshape(len(SPANS) ** 2, -1) for h in self.halves]
        return self._details

    def shown(self, i: int) -> _Shown:
        """View i's coarse windows as _shown() gives them, rows as in details(). Kept only for a view with alpha, whose
        detail takes a while to find: one without is cheap to take again, and a trace compares every collected image."""
        k, a = len(SPANS) ** 2, self.alphas[i]
        if a is None:
            return _shown(_windows(_COARSE, _COARSE, self.halves[i]).reshape(k, -1), None, self.details()[i])
        if self._shown is None:
            self._shown = [None] * len(self.squares)
        if self._shown[i] is None:
            self._shown[i] = _shown(_windows(_COARSE, _COARSE, self.halves[i]).reshape(k, -1),
                                    _windows(_COARSE, _COARSE, _halve(a)).reshape(k, -1))
        return self._shown[i]


def picture(data: bytes, crops=(WHOLE,)) -> Picture:
    """The image in `data` seen whole, or as each part `crops` takes. One neither Pillow nor resvg can read has no
    views and scores 0: the distance gates refuse it ("not-comparable") where they compare it."""
    try:
        im = L.open_image(data)
    except Exception:
        return Picture([])
    return Picture([v for c in crops for v in views(im, c)])


def source(data: bytes, crop=WHOLE) -> Picture:
    """A file to be traced: seen whole and as the part --crop takes."""
    crop = tuple(float(v) for v in crop)
    return picture(data, (WHOLE,) if crop == WHOLE else (WHOLE, crop))


_CACHE: dict[str, Picture] = {}  # sha256 -> Picture: a build traces again and checks; the bytes behind a hash don't change


def cached(sha: str, data: bytes) -> Picture:
    if sha not in _CACHE:
        _CACHE[sha] = picture(data)
    return _CACHE[sha]


def _coarse_scores(big: Picture, i: int, small: Picture, j: int) -> np.ndarray:
    """The score of each coarse window of `big`'s view i against `small`'s view j whole: where neither has alpha, the
    dot product of their details, which is Pearson's r; else _shown_scores()."""
    if big.alphas[i] is None and small.alphas[j] is None:
        return big.details()[i] @ small.coarse[j]
    x, y = big.shown(i), small.coarse_shown[j]
    return _shown_scores(x, y, _held(x, y))


def _coarse_held(big: Picture, i: int, small: Picture, j: int, down: _Spans, across: _Spans) -> np.ndarray:
    """_held() of each window `down` and `across` take of `big`'s view i against `small`'s view j whole, both at
    COARSE px, as the coarse search measures it."""
    d, a = _Spans(2 * COARSE, COARSE, down.spans), _Spans(2 * COARSE, COARSE, across.spans)
    half, alpha, k = big.halves[i], big.alphas[i], len(down.spans) * len(across.spans)
    shown = None if alpha is None else _windows(d, a, _halve(alpha)).reshape(k, -1)
    details = None if alpha is not None else _details(d, a, half).reshape(k, -1)
    x = _shown(_windows(d, a, half).reshape(k, -1), shown, details)
    return _held(x, small.coarse_shown[j])


def _refine(big: Picture, i: int, small: Picture, j: int, cut: tuple[float, float, float, float]) -> float:
    """The best score of `small`'s view j whole, at FINE, against windows of `big`'s view i near `cut` (left, top,
    right, bottom left out), moving each side a step of 1/64, then of 1/128."""
    square, alpha = big.squares[i], big.alphas[i]
    best = -1.0
    for step in (1 / 64, 1 / 128):
        l, t, r, b = cut
        across = _Spans(SQUARE, FINE, [(l + p * step, r + q * step) for p in (-1, 0, 1) for q in (-1, 0, 1)
                                       if l + p * step >= 0 and r + q * step >= 0])
        down = _Spans(SQUARE, FINE, [(t + p * step, b + q * step) for p in (-1, 0, 1) for q in (-1, 0, 1)
                                     if t + p * step >= 0 and b + q * step >= 0])
        shape = (len(down.spans), len(across.spans))
        details = None if alpha is not None else _details(down, across, square).reshape(-1, FINE * FINE)
        if alpha is None and small.alphas[j] is None:
            s = details @ small.fine[j]
        else:
            s = _shown_scores(_shown(_windows(down, across, square).reshape(-1, FINE * FINE),
                                     None if alpha is None else _windows(down, across, alpha).reshape(-1, FINE * FINE),
                                     details), small.fine_shown[j], _coarse_held(big, i, small, j, down, across))
        s = s.reshape(shape)
        y, x = np.unravel_index(int(s.argmax()), shape)
        if s[y, x] > best:
            best = float(s[y, x])
            (t, b), (l, r) = down.spans[y], across.spans[x]
            cut = (l, t, r, b)
    return best


def score(a: Picture, b: Picture) -> float:
    """How much `a` and `b` are the same picture, 0 to 1: the highest over their views, each way round."""
    best = 0.0
    k = len(SPANS)
    for big, small in ((b, a), (a, b)):
        for i in range(len(big.squares) if small.squares else 0):
            for j in range(len(small.squares)):
                s = _coarse_scores(big, i, small, j)
                w = int(s.argmax())
                if s[w] >= FLOOR:
                    (t, bt), (l, r) = SPANS[w // k], SPANS[w % k]
                    best = max(best, _refine(big, i, small, j, (l, t, r, bt)))
                else:
                    best = max(best, float(s[w]))
    return best


def nearest(src: Picture, images: list[tuple[str, str, Picture]]) -> dict:
    best = {"score": 0.0, "ref": None}
    for f, _, pic in images:
        s = score(src, pic)
        if s > best["score"]:
            best = {"score": s, "ref": f}
    return best


def gate(source_file: str, src: Picture, collected: list[tuple[str, str, Picture]], **detail) -> dict:
    """{"score", "ref"} of the collected image `src` is nearest to as a picture, or a refusal ("collected-copy") at
    LIMIT and over. `detail` goes into the refusal."""
    near = nearest(src, collected)
    found = {"score": round(near["score"], 4), "ref": near["ref"]}
    if near["score"] < LIMIT:
        return found
    raise R.Refused("collected-copy", f"{source_file} is the same picture as {near['ref']}: they score "
                                      f"{near['score']:.3f} as pictures (limit {LIMIT}), so it is that image saved "
                                      "again, resized, cut at the edges, made lighter or darker, or partly made clear. "
                                      "That image was collected for measuring. Collected and reference logos set "
                                      "proportions; they are never traced.", copy_nearest=found, **detail)


def recheck(traces: list[dict], collected: list[tuple[str, str, bytes]]) -> None:
    """The trace gate's own check of each verified trace (rights.traces()) against the collections as they are now, so
    a copy collected after the trace, or a trace made before this gate, goes no further: refuses ("collected") a
    source whose sha256 a collection lists, then ("collected-copy") one that is the same picture as any collected
    image. `collected` is rights.collected_files()."""
    for t in traces:
        hit = next((f for f, sha, _ in collected if sha == t["trace"]["source_sha256"]), None)
        if hit:
            raise R.Refused("collected", f"the traced source {t['provenance']['source']['file']} has the same sha256 as "
                                         f"{hit}, collected since it was traced. Collected and reference logos set "
                                         "proportions; they are never traced. Drop that direction or trace another file.")
    images = list({sha: (f, sha, cached(sha, data)) for f, sha, data in collected}.values())
    for t in traces:
        gate(t["provenance"]["source"]["file"], source(t["source"], t["provenance"]["raster"]["crop"]), images)

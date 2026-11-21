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
6. Two views, one or both with alpha, that reach FLOOR are then compared at their own size (_native): a pixel of a
   square averages what a copy shows with what it hides, so where the clear pixels are finer than that (stripes a
   pixel or two wide), each pixel of the other image's square holds what the copy hides. The view with alpha is laid
   on the other where the refinement put it, the way round it scored higher, and moved to within an eighth of its
   own pixel by the fine detail of what it shows (_register); then each FINE px averages only its pixels that show
   and the other's resampled onto them, each weighted by how much both show (_cells), and scores as in step 5. The
   searches only find where: a mask laid a pixel off picks what it hides as surely as no mask.

A pairing's score is its refined score (with alpha, its score at their own size), or its coarse score under FLOOR;
two images score the highest of their pairings. The gate refuses at LIMIT and over. It does not see a picture turned
(but by its EXIF orientation), mirrored, cut by more than CUT on a side, reduced to a small part of a larger one, or a
copy that shows under MIN_SHOWN of it or holds under MIN_HELD of its detail at COARSE px.
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

# Measured on 150 collected images and the test fixtures' photos (references/building.md, "Same picture"): edited
# copies scored 0.8590 or more and every pair of different images 0.7197 or less. Partly clear copies scored 0.8576 or
# more but for 17 of 3,605 (0.40 to 0.84: a one-colour mark on a clear ground, two holding under MIN_HELD once cut, a
# thin band); a clear copy against another image 0.8490 or less but for 2 of 22,282 thin bands (0.88, 0.90), and the
# fixture photos, staged alike, up to 0.93 (14 of 952 at LIMIT or over). MIN_SHOWN 0.25 would pass those 16 pairs, and
# a keyed copy of a logo (0.81).
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


def _grounds(im: Image.Image) -> list[tuple[Image.Image, Image.Image | None]]:
    """(grey, alpha or None) of `im` at its own size, as "L" images: on white and, with transparency, on black and as
    its colour channels alone; with clear pixels, on black again with the alpha that says how much of each pixel shows
    (on black, a pixel is its colour times that alpha)."""
    if not L.transparent(im):
        return [(im.convert("L"), None)]
    rgba = im.convert("RGBA")
    on = {g: Image.alpha_composite(Image.new("RGBA", im.size, (*g, 255)), rgba).convert("L") for g in (WHITE, BLACK)}
    out = [(on[WHITE], None), (on[BLACK], None), (rgba.convert("L"), None)]  # last: as raster_mask() reads it
    alpha = rgba.getchannel("A")
    if _square(alpha).min() < 1:
        out.append((on[BLACK], alpha))
    return out


def views(im: Image.Image, crop=WHOLE) -> list[tuple[Image.Image, Image.Image | None]]:
    """The (grey, alpha or None) "L" images `im` is compared as, of the part `crop` (x, y, w, h in fractions) takes:
    _grounds() of it as stored and, with an EXIF orientation, as shown (logolib.orientations)."""
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
    """An image's views, ready to compare: each whole at both sizes, as detail and as _shown() gives it, its coarse
    windows when first asked for, and each view at its own size (native()) when a pairing with alpha needs it."""

    def __init__(self, views: list[tuple[Image.Image, Image.Image | None]], remake=None):
        """`views` as views() gives them; `remake()` gives them again for native(), so a collected image, of which a
        trace compares every one, keeps only its squares. Without `remake` the views are kept."""
        self.squares = [_square(g) for g, _ in views]
        self.alphas = [None if a is None else _square(a) for _, a in views]
        self.halves = [_halve(s) for s in self.squares]
        self.coarse = [_details(_COARSE_WHOLE, _COARSE_WHOLE, h)[0, 0] for h in self.halves]
        self.fine = [_details(_FINE_WHOLE, _FINE_WHOLE, s)[0, 0] for s in self.squares]
        self.coarse_shown = [_whole(_COARSE_WHOLE, h, None if a is None else _halve(a), d)
                             for h, a, d in zip(self.halves, self.alphas, self.coarse)]
        self.fine_shown = [_whole(_FINE_WHOLE, s, a, d) for s, a, d in zip(self.squares, self.alphas, self.fine)]
        self._details = self._shown = self._native = None
        self._remake = remake or (lambda: views)
        self._samples: dict[int, _Samples] = {}

    def native(self, i: int) -> tuple[np.ndarray, np.ndarray | None]:
        """View i at its own size: (grey, alpha or None), each 0-255 in uint8."""
        if self._native is None:
            self._native = [(np.asarray(g), None if a is None else np.asarray(a)) for g, a in self._remake()]
        return self._native[i]

    def samples(self, i: int) -> "_Samples":
        """View i's _Samples, for _register() where it is the frame."""
        if i not in self._samples:
            self._samples[i] = _samples(*self.native(i))
        return self._samples[i]

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
    def remake():
        im = L.open_image(data)
        return [v for c in crops for v in views(im, c)]

    try:
        return Picture(remake(), remake)
    except Exception:
        return Picture([])


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


def _refine(big: Picture, i: int, small: Picture, j: int,
            cut: tuple[float, float, float, float]) -> tuple[float, tuple[float, float, float, float]]:
    """(the best score, its window) of `small`'s view j whole, at FINE, against windows of `big`'s view i near `cut`
    (left, top, right, bottom left out), moving each side a step of 1/64, then of 1/128."""
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
    return best, cut


SAMPLES = 1 << 15  # the most pixels that show _register() compares, drawn once with a fixed seed
REACH = 1 / 128  # how far _register() moves an end, of the other's side: _refine()'s last step
DETAIL = 2  # _register() takes each px less the mean of a square of 2 * DETAIL + 1 frame px around it


def _along(v: np.ndarray, axis: int, n: int, a: float, c: float, area: bool) -> np.ndarray:
    """`v` resampled along `axis` to n px, px i taking what lies at a * i + c in v (its px centred on whole numbers):
    with `area`, the mean of v over [a * i + c - a / 2, a * i + c + a / 2], each px weighted by how much of it lies
    there; else v linearly interpolated at that point. Clamped at the ends."""
    v = np.moveaxis(np.asarray(v, dtype=np.float32), axis, 0)
    m, shape = v.shape[0], (-1,) + (1,) * (v.ndim - 1)
    at = a * np.arange(n) + c
    if area:
        s = np.concatenate([np.zeros((1, *v.shape[1:])), np.cumsum(v, 0, dtype=np.float64)])

        def upto(x):  # the sum of v over [0, x), x on its px edges (px k spans [k, k + 1))
            x = np.clip(x, 0, m)
            k = np.minimum(np.floor(x).astype(int), m - 1)
            return s[k] + (x - k).reshape(shape) * v[k]

        lo, hi = at - a / 2 + 0.5, at + a / 2 + 0.5
        out = (upto(hi) - upto(lo)) / np.maximum(np.clip(hi, 0, m) - np.clip(lo, 0, m), 1e-12).reshape(shape)
    else:
        p = np.clip(at, 0, m - 1)
        k = np.minimum(np.floor(p).astype(int), max(m - 2, 0))
        f = (p - k).reshape(shape)
        out = v[k] * (1 - f) + v[np.minimum(k + 1, m - 1)] * f
    return np.moveaxis(out, 0, axis)


def _ends(big: tuple[int, int], small: tuple[int, int], cut, small_is_frame: bool) -> list[list[float]]:
    """Down and across, where the window `cut` (left, top, right, bottom left out of `big`, shapes (rows, columns))
    puts the first and the last px of the frame, the view with alpha (`small`, or `big`), in the other's px (each
    centred on a whole number)."""
    l, t, r, b = cut
    out = []
    for nb, ns, lo, hi in ((big[0], small[0], t, b), (big[1], small[1], l, r)):
        kept = 1 - lo - hi
        if small_is_frame:  # small px x is big px nb * (lo + kept * (x + 0.5) / ns) - 0.5
            px, n = (lambda x: nb * (lo + kept * (x + 0.5) / ns) - 0.5), ns
        else:  # big px x is small px ((x + 0.5) / nb - lo) * ns / kept - 0.5
            px, n = (lambda x: ((x + 0.5) / nb - lo) * ns / kept - 0.5), nb
        out.append([px(0), px(n - 1)])
    return out


def _line(ends: list[float], n: int) -> tuple[float, float]:
    """(a, c): px x of a side of n px lies at a * x + c in the other's px, from where its first and last px lie."""
    return (ends[1] - ends[0]) / max(n - 1, 1), ends[0]


class _Samples(NamedTuple):
    """Up to SAMPLES px of a view with alpha that show at least half: where they are, how much each shows, and its
    colour less the mean of what shows around it (in a square of 2 * DETAIL + 1 px)."""
    ys: np.ndarray
    xs: np.ndarray
    weight: np.ndarray
    detail: np.ndarray


def _samples(grey: np.ndarray, alpha: np.ndarray) -> _Samples:
    from scipy.ndimage import uniform_filter

    shows = alpha.astype(np.float32) / 255
    lit = grey.astype(np.float32) / 255  # on black: colour times alpha
    ys, xs = np.nonzero(alpha >= 128)
    pick = np.random.default_rng(0).permutation(len(ys))[:SAMPLES]
    ys, xs = ys[pick], xs[pick]
    side = 2 * DETAIL + 1
    near = uniform_filter(lit, side)[ys, xs] / np.maximum(uniform_filter(shows, side)[ys, xs], 1e-6)
    return _Samples(ys, xs, shows[ys, xs].astype(np.float64), (lit[ys, xs] / shows[ys, xs] - near).astype(np.float64))


def _register(frame: _Samples, shape: tuple[int, int], other: tuple[np.ndarray, np.ndarray | None],
              ends: list[list[float]]) -> list[list[float]]:
    """`ends` (_ends()) moved to where the fine detail of the frame's px that show (`frame`, of a view of `shape`)
    agrees best with the other view's, linearly interpolated there: Pearson's r of the two, each px less the mean of
    what shows around it (in a square of 2 * DETAIL + 1 frame px; where a frame px covers more than one of the
    other's, theirs averaged first), and weighted by how much both show of it. Each end moves alone, up to 2 steps
    either way and no further than REACH of the other's side from where it was, the step starting at 1/512 of that
    side and halving down to an eighth of a frame px. A mask finer than the alignment the search finds at 128 px
    picks the other's px it is laid on: a px off, these two compare what the copy shows with what it hides. Only the
    fine detail counts, as only a copy shares it: the lit walls of two photos staged alike, in all, agree better
    once moved a few px."""
    from scipy.ndimage import uniform_filter, uniform_filter1d

    og, oa = other
    scale = [abs(_line(e, n)[0]) for e, n in zip(ends, shape)]
    planes = [og.astype(np.float32) / 255] + ([] if oa is None else [oa.astype(np.float32) / 255])
    for axis, a in enumerate(scale):
        if a > 1.5:
            planes = [uniform_filter1d(p, max(1, round(a)), axis=axis, mode="nearest") for p in planes]
    side = [2 * max(1, round(DETAIL * a)) + 1 for a in scale]
    if oa is None:
        planes = [planes[0] - uniform_filter(planes[0], side, mode="nearest")]
    else:  # on black over alpha, less what shows around it
        planes = [np.divide(planes[0], planes[1], out=np.zeros_like(planes[0]), where=planes[1] > 1e-3)
                  - uniform_filter(planes[0], side, mode="nearest")
                  / np.maximum(uniform_filter(planes[1], side, mode="nearest"), 1e-6), planes[1]]
    H, W = og.shape
    flat = [p.ravel() for p in planes]

    def at(p: np.ndarray, y: np.ndarray, x: np.ndarray) -> np.ndarray:
        y, x = np.clip(y, 0, H - 1), np.clip(x, 0, W - 1)
        y0, x0 = np.minimum(y.astype(np.int64), max(H - 2, 0)), np.minimum(x.astype(np.int64), max(W - 2, 0))
        fy, fx = y - y0, x - x0
        k = y0 * W + x0
        dy, dx = (H > 1) * W, int(W > 1)
        top = p[k] * (1 - fx) + p[k + dx] * fx
        return top * (1 - fy) + (p[k + dy] * (1 - fx) + p[k + dy + dx] * fx) * fy

    def agree(e: list[list[float]]) -> float:
        (ay, cy), (ax, cx) = (_line(v, n) for v, n in zip(e, shape))
        y, x = ay * frame.ys + cy, ax * frame.xs + cx
        w = frame.weight * ((y >= -0.5) & (y <= H - 0.5) & (x >= -0.5) & (x <= W - 0.5))
        v = at(flat[0], y, x)
        if oa is not None:
            w = w * at(flat[1], y, x)
        total = w.sum()
        if total < 100:
            return -1.0
        dc, dv = frame.detail - (w * frame.detail).sum() / total, v - (w * v).sum() / total
        vc, vv = (w * dc * dc).sum(), (w * dv * dv).sum()
        return float((w * dc * dv).sum() / np.sqrt(vc * vv)) if vc > 1e-12 and vv > 1e-12 else -1.0

    start, ends = ends, [list(e) for e in ends]
    best = agree(ends)
    steps = [max(og.shape[k] / 512, a / 8) for k, a in enumerate(scale)]
    floors = [a / 8 for a in scale]
    while any(st >= f for st, f in zip(steps, floors)):
        for _ in range(2):
            moved = False
            for axis in (k for k in range(2) if steps[k] >= floors[k]):
                for end in range(2):
                    here, keep = ends[axis][end], ends[axis][end]
                    for k in (-2, -1, 1, 2):
                        ends[axis][end] = here + k * steps[axis]
                        if abs(ends[axis][end] - start[axis][end]) > REACH * og.shape[axis]:
                            continue
                        v = agree(ends)
                        if v > best:
                            best, keep, moved = v, ends[axis][end], True
                    ends[axis][end] = keep
            if not moved:
                break
        steps = [st / 2 for st in steps]
    return ends


def _cells(frame: tuple[np.ndarray, np.ndarray], other: tuple[np.ndarray, np.ndarray | None],
           ends: list[list[float]], held: float) -> float:
    """The score of the frame against the other view where `ends` lay it, at FINE px over the frame's px that land on
    the other: each FINE px averages the frame's px, and the other resampled onto them (averaged where a frame px
    covers more than one of its px, else linearly interpolated), each weighted by how much both show of it, so no px
    either hides counts. Then as _shown_scores(), with `held` (at COARSE px, as the search measured it)."""
    (fg, fa), (og, oa) = frame, other
    lines = [_line(e, n) for e, n in zip(ends, fg.shape)]
    span = []
    for (a, c), n, m in zip(lines, fg.shape, og.shape):
        x = np.arange(n)
        on = np.nonzero((a * x + c >= -0.5) & (a * x + c <= m - 0.5))[0]
        span.append((int(on[0]), int(on[-1]) + 1) if len(on) >= 4 else None)
    if None in span:
        return 0.0
    (y0, y1), (x0, x1) = span
    (ay, cy), (ax, cx) = lines

    def onto(p: np.ndarray) -> np.ndarray:  # the axis that shrinks it most first
        steps = [(0, y1 - y0, ay, cy + ay * y0), (1, x1 - x0, ax, cx + ax * x0)]
        for axis, n, a, c in sorted(steps, key=lambda st: st[1] / p.shape[st[0]]):
            p = _along(p, axis, n, a, c, abs(a) > 1)
        return p

    shows = fa[y0:y1, x0:x1] / 255.0
    lit = fg[y0:y1, x0:x1] / 255.0  # on black: the frame's colour times its alpha
    seen = onto(og) / 255  # the other's grey, or on black its colour times its alpha
    if oa is None:
        w, mine, theirs = shows, lit, shows * seen
    else:
        both = onto(oa) / 255
        w, mine, theirs = shows * both, lit * both, shows * seen

    def fine(p: np.ndarray) -> np.ndarray:
        p = _along(p, 0, FINE, p.shape[0] / FINE, p.shape[0] / FINE / 2 - 0.5, True)
        return _along(p, 1, FINE, p.shape[1] / FINE, p.shape[1] / FINE / 2 - 0.5, True).reshape(1, -1)

    w, mine, theirs = fine(w), fine(mine), fine(theirs)
    x = _shown(mine, w)
    y = _Shown(np.divide(theirs, w, out=np.zeros_like(theirs), where=w > 0), None, None, None, None)
    return float(_shown_scores(x, y, np.asarray([held]))[0])


def _native(big: Picture, i: int, small: Picture, j: int, cut: tuple[float, float, float, float]) -> float:
    """The score of `small`'s view j against `big`'s view i, one or both with alpha, at their own size: the view with
    alpha (the frame; small's when both have) laid on the other where _refine() put it (`cut`), _register()ed, and
    compared by _cells(). The searches at 32 and 64 px only find where: a px of theirs holds what the frame hides
    wherever its clear px are finer than a px of the 128 px squares."""
    frame_is_small = small.alphas[j] is not None
    (f, fi), (o, oi) = ((small, j), (big, i)) if frame_is_small else ((big, i), (small, j))
    frame, other = f.native(fi), o.native(oi)
    ends = _register(f.samples(fi), frame[0].shape, other,
                     _ends(big.native(i)[0].shape, small.native(j)[0].shape, cut, frame_is_small))
    l, t, r, b = cut
    held = _coarse_held(big, i, small, j, _Spans(2 * COARSE, COARSE, [(t, b)]), _Spans(2 * COARSE, COARSE, [(l, r)]))
    return _cells(frame, other, ends, float(held[0]))


def score(a: Picture, b: Picture) -> float:
    """How much `a` and `b` are the same picture, 0 to 1: the highest over their views, each way round. Two views one
    or both with alpha whose coarse search reaches FLOOR either way round score as _native() gives it, laid the way
    round _refine() scored higher."""
    best = 0.0
    k = len(SPANS)
    laid = {}  # (a's view, b's view) with alpha -> (refined score, big, i, small, j, window)
    for big, small in ((b, a), (a, b)):
        for i in range(len(big.squares) if small.squares else 0):
            for j in range(len(small.squares)):
                s = _coarse_scores(big, i, small, j)
                w = int(s.argmax())
                if s[w] < FLOOR:
                    best = max(best, float(s[w]))
                    continue
                (t, bt), (l, r) = SPANS[w // k], SPANS[w % k]
                fine, cut = _refine(big, i, small, j, (l, t, r, bt))
                if big.alphas[i] is None and small.alphas[j] is None:
                    best = max(best, fine)
                    continue
                pair = (i, j) if big is a else (j, i)
                if pair not in laid or fine > laid[pair][0]:
                    laid[pair] = (fine, big, i, small, j, cut)
    for _, big, i, small, j, cut in laid.values():
        best = max(best, _native(big, i, small, j, cut))
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

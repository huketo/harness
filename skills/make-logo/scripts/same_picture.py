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
   trace_ref.raster_mask() gives potrace. One with clear pixels is also seen on white and on black with its alpha,
   so that only what it shows counts (step 4). One with an EXIF orientation is seen both as stored and as shown. A
   source is also seen as the part --crop takes.
2. One square is compared with every window of the other that leaves out up to CUT of each side, on a STEP grid, at
   COARSE x COARSE px, both ways round: the one a crop of the other, or the other with a border.
3. The best window of each pairing whose score reaches FLOOR there is refined to 1/128 of a side, at FINE x FINE px.
4. Each view is compared less its blur (a Gaussian, sigma an eighth of its side), so light falling across a wall
   counts for nothing, and the score is the correlation of the pixels (Pearson's r): 1 for the same picture whatever
   its brightness and contrast. With alpha, each pixel counts as much as both pictures show of it, and a window
   where they show under MIN_SHOWN of it scores 0: the colour under a clear pixel, which a copy may set to anything,
   counts for nothing.

A pairing's score is its refined score, or its coarse score under FLOOR; two images score the highest of their
pairings. The gate refuses at LIMIT and over. It does not see a picture turned (but by its EXIF orientation),
mirrored, cut by more than CUT on a side, reduced to a small part of a larger one, or showing under MIN_SHOWN of it.
"""
from __future__ import annotations

import os
import sys

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
SQUARE, COARSE, FINE = 128, 32, 64
CUT, STEP = 1 / 8, 1 / 32
WHOLE = (0.0, 0.0, 1.0, 1.0)
WHITE, BLACK = (255, 255, 255), (0, 0, 0)


def _square(grey: Image.Image) -> np.ndarray:
    return np.asarray(grey.resize((SQUARE, SQUARE), Image.BOX), dtype=np.float32) / 255


def _grounds(im: Image.Image) -> list[tuple[np.ndarray, np.ndarray | None]]:
    """(grey, alpha or None) squares of `im`: on white and, with transparency, on black and as its colour channels
    alone; with clear pixels, on white and on black again with the alpha that says how much of each pixel shows."""
    if not L.transparent(im):
        return [(_square(im.convert("L")), None)]
    rgba = im.convert("RGBA")
    on = {g: _square(Image.alpha_composite(Image.new("RGBA", im.size, (*g, 255)), rgba).convert("L"))
          for g in (WHITE, BLACK)}
    out = [(on[WHITE], None), (on[BLACK], None), (_square(rgba.convert("L")), None)]  # last: as raster_mask() reads it
    alpha = _square(rgba.getchannel("A"))
    if alpha.min() < 1:
        out += [(on[WHITE], alpha), (on[BLACK], alpha)]
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


def _shown(down: _Spans, across: _Spans, alpha: np.ndarray | None) -> np.ndarray | None:
    """The alpha of each window _details() takes, the same shape, or None for none."""
    return None if alpha is None else _by_window(down, across, down.take @ alpha @ across.take.T)


SPANS = [(a, b) for a in np.arange(0, CUT + 1e-9, STEP) for b in np.arange(0, CUT + 1e-9, STEP)]  # off the two ends
_COARSE = _Spans(2 * COARSE, COARSE, SPANS)
_COARSE_WHOLE = _Spans(2 * COARSE, COARSE, [(0, 0)])
_FINE_WHOLE = _Spans(SQUARE, FINE, [(0, 0)])


def _halve(square: np.ndarray) -> np.ndarray:
    return square.reshape(2 * COARSE, SQUARE // (2 * COARSE), 2 * COARSE, -1).mean((1, 3))


class Picture:
    """An image's views, ready to compare: each whole at both sizes with its alpha, and its coarse windows when first
    asked for."""

    def __init__(self, views: list[tuple[np.ndarray, np.ndarray | None]]):
        self.squares = [s for s, _ in views]
        self.alphas = [a for _, a in views]
        self.halves = [_halve(s) for s in self.squares]
        self.coarse = [_details(_COARSE_WHOLE, _COARSE_WHOLE, h)[0, 0] for h in self.halves]
        self.fine = [_details(_FINE_WHOLE, _FINE_WHOLE, s)[0, 0] for s in self.squares]
        self.coarse_alpha = [None if a is None else _shown(_COARSE_WHOLE, _COARSE_WHOLE, _halve(a))[0, 0]
                             for a in self.alphas]
        self.fine_alpha = [None if a is None else _shown(_FINE_WHOLE, _FINE_WHOLE, a)[0, 0] for a in self.alphas]
        self._windows = None

    def windows(self) -> list[tuple[np.ndarray, np.ndarray | None]]:
        """Each view's coarse windows and their alpha, (len(SPANS) ** 2, COARSE ** 2): row i leaves out
        SPANS[i // len(SPANS)] down and SPANS[i % len(SPANS)] across."""
        if self._windows is None:
            k = len(SPANS) ** 2
            self._windows = [(_details(_COARSE, _COARSE, h).reshape(k, -1),
                              None if a is None else _shown(_COARSE, _COARSE, _halve(a)).reshape(k, -1))
                             for h, a in zip(self.halves, self.alphas)]
        return self._windows


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


def _scores(x: np.ndarray, x_alpha: np.ndarray | None, y: np.ndarray, y_alpha: np.ndarray | None) -> np.ndarray:
    """The score of each row of `x` (windows, as _details() gives them) against `y`: their dot product, which is
    Pearson's r. With alpha on either side, r with each pixel weighted by how much both show of it, and 0 for a
    window where they show under MIN_SHOWN of it or it has no detail there."""
    if x_alpha is None and y_alpha is None:
        return x @ y
    x, y = x.astype(np.float64), y.astype(np.float64)  # sums of squares less squared sums: float32 loses them
    a = np.ones_like(y) if y_alpha is None else y_alpha.astype(np.float64)
    u = np.stack([a, a * y, a * y * y], 1)
    if x_alpha is None:  # each window shown in full: sums over y alone
        s, sy, syy = u.sum(0)
        sx, sxy = (x @ u[:, :2]).T
        sxx = (x * x) @ a
    else:
        ax = x_alpha.astype(np.float64)
        s, sy, syy = (ax @ u).T
        ax = ax * x
        sx, sxy = (ax @ u[:, :2]).T
        sxx = (ax * x) @ a
    var = (s * sxx - sx * sx) * (s * syy - sy * sy)
    ok = (s >= MIN_SHOWN * len(y)) & (var > 1e-12)
    return np.where(ok, (s * sxy - sx * sy) / np.sqrt(np.where(ok, var, 1)), 0.0)


def _refine(square: np.ndarray, alpha: np.ndarray | None, small: np.ndarray, small_alpha: np.ndarray | None,
            cut: tuple[float, float, float, float]) -> float:
    """The best score of `small` (a FINE view) against windows of `square` near `cut` (left, top, right, bottom left
    out), moving each side a step of 1/64, then of 1/128."""
    best = -1.0
    for step in (1 / 64, 1 / 128):
        l, t, r, b = cut
        across = _Spans(SQUARE, FINE, [(l + i * step, r + j * step) for i in (-1, 0, 1) for j in (-1, 0, 1)
                                       if l + i * step >= 0 and r + j * step >= 0])
        down = _Spans(SQUARE, FINE, [(t + i * step, b + j * step) for i in (-1, 0, 1) for j in (-1, 0, 1)
                                     if t + i * step >= 0 and b + j * step >= 0])
        shape = (len(down.spans), len(across.spans))
        shown = _shown(down, across, alpha)
        s = _scores(_details(down, across, square).reshape(-1, FINE * FINE),
                    None if shown is None else shown.reshape(-1, FINE * FINE), small, small_alpha).reshape(shape)
        i, j = np.unravel_index(int(s.argmax()), shape)
        if s[i, j] > best:
            best = float(s[i, j])
            (t, b), (l, r) = down.spans[i], across.spans[j]
            cut = (l, t, r, b)
    return best


def score(a: Picture, b: Picture) -> float:
    """How much `a` and `b` are the same picture, 0 to 1: the highest over their views, each way round."""
    best = 0.0
    k = len(SPANS)
    for big, small in ((b, a), (a, b)):
        for (windows, shown), square, alpha in zip(big.windows() if small.coarse else [], big.squares, big.alphas):
            for whole, whole_alpha, fine, fine_alpha in zip(small.coarse, small.coarse_alpha, small.fine,
                                                            small.fine_alpha):
                s = _scores(windows, shown, whole, whole_alpha)
                i = int(s.argmax())
                if s[i] >= FLOOR:
                    (t, bt), (l, r) = SPANS[i // k], SPANS[i % k]
                    best = max(best, _refine(square, alpha, fine, fine_alpha, (l, t, r, bt)))
                else:
                    best = max(best, float(s[i]))
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

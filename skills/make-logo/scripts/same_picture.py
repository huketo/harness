# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "resvg-py"]
# ///
"""The same-picture gate (references/building.md, "Same picture"): is a file to be traced a collected or reference
image saved again, resized, cut a little at the edges, or made lighter or darker?

The distance gates compare marks: the source cut at a fixed grey level, each reference split from its ground. A
photo has no one mark to split, so those two masks can cover different parts of the same picture, and a re-saved or
cropped copy of a collected photo passes them. This compares the pictures themselves:

1. Each image is seen in grey, squeezed into a SQUARE x SQUARE square (a crop changes the aspect, so it is dropped):
   flattened on white and, when it has transparency, on black and as its colour channels alone, which is what
   trace_ref.raster_mask() gives potrace. A source is also seen as the part --crop takes.
2. One square is compared with every window of the other that leaves out up to CUT of each side, on a STEP grid, at
   COARSE x COARSE px, both ways round: the one a crop of the other, or the other with a border.
3. The best window of each pairing whose score reaches FLOOR there is refined to 1/128 of a side, at FINE x FINE px.
4. Each view is compared less its blur (a Gaussian, sigma an eighth of its side), so light falling across a wall
   counts for nothing, and the score is the correlation of the pixels (Pearson's r): 1 for the same picture whatever
   its brightness and contrast.

A pairing's score is its refined score, or its coarse score under FLOOR; two images score the highest of their
pairings. The gate refuses at LIMIT and over. It does not see a picture turned, mirrored, cut by more than CUT on a
side, or reduced to a small part of a larger one.
"""
from __future__ import annotations

import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logolib as L  # noqa: E402
import rights as R  # noqa: E402

# Measured on 150 collected images (references/building.md, "Same picture"): their edited copies scored 0.9076 or more
# (but a photo whose ground was keyed out with its colour zeroed, 0.8111), every pair of different images 0.7197 or
# less. FLOOR: every edited copy scored 0.7447 or more before refining.
LIMIT = 0.85
FLOOR = 0.5
SQUARE, COARSE, FINE = 128, 32, 64
CUT, STEP = 1 / 8, 1 / 32
WHOLE = (0.0, 0.0, 1.0, 1.0)


def views(im: Image.Image, crop=WHOLE) -> list[np.ndarray]:
    """The grey squares `im` is compared as, of the part `crop` (x, y, w, h in fractions) takes: on white and, with
    transparency, on black and as its colour channels alone. Floats 0-1."""
    out = []
    clear = im.mode == "P" or L.transparent(im)
    for ground in [(255, 255, 255)] + ([(0, 0, 0), None] if L.transparent(im) else []):
        if ground is None:  # the colour channels alone, as raster_mask() reads a source
            grey = im.convert("RGBA").convert("L")
        elif clear:
            grey = Image.alpha_composite(Image.new("RGBA", im.size, (*ground, 255)), im.convert("RGBA")).convert("L")
        else:
            grey = im.convert("L")
        x, y, w, h = (float(v) for v in crop)
        W, H = grey.size
        grey = grey.crop((round(x * W), round(y * H), round((x + w) * W), round((y + h) * H)))
        out.append(np.asarray(grey.resize((SQUARE, SQUARE), Image.BOX), dtype=np.float32) / 255)
    return out


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


def _details(down: _Spans, across: _Spans, square: np.ndarray) -> np.ndarray:
    """(windows down, windows across, n * n): the window of `square` each pair of spans takes, less its blur, as a
    vector of mean 0 and length 1; one with no detail left (under a thousandth, in 0-1 grey) is all zeros."""
    n = down.n
    v = down.take @ square @ across.take.T - down.blurred @ square @ across.blurred.T
    v = v.reshape(len(down.spans), n, len(across.spans), n).transpose(0, 2, 1, 3)
    v = v.reshape(len(down.spans), len(across.spans), n * n)
    v = v - v.mean(-1, keepdims=True)
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    return np.where(norm > 1e-3, v / np.maximum(norm, 1e-12), 0).astype(np.float32)


SPANS = [(a, b) for a in np.arange(0, CUT + 1e-9, STEP) for b in np.arange(0, CUT + 1e-9, STEP)]  # off the two ends
_COARSE = _Spans(2 * COARSE, COARSE, SPANS)
_COARSE_WHOLE = _Spans(2 * COARSE, COARSE, [(0, 0)])
_FINE_WHOLE = _Spans(SQUARE, FINE, [(0, 0)])


class Picture:
    """An image's views, ready to compare: each whole at both sizes, and its coarse windows when first asked for."""

    def __init__(self, squares: list[np.ndarray]):
        self.squares = squares
        self.halves = [s.reshape(2 * COARSE, SQUARE // (2 * COARSE), 2 * COARSE, -1).mean((1, 3)) for s in squares]
        self.coarse = [_details(_COARSE_WHOLE, _COARSE_WHOLE, h)[0, 0] for h in self.halves]
        self.fine = [_details(_FINE_WHOLE, _FINE_WHOLE, s)[0, 0] for s in squares]
        self._windows = None

    def windows(self) -> list[np.ndarray]:
        """Each view's coarse windows, (len(SPANS) ** 2, COARSE ** 2): row i leaves out SPANS[i // len(SPANS)] down
        and SPANS[i % len(SPANS)] across."""
        if self._windows is None:
            k = len(SPANS)
            self._windows = [_details(_COARSE, _COARSE, h).reshape(k * k, COARSE * COARSE) for h in self.halves]
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


def _refine(square: np.ndarray, small: np.ndarray, cut: tuple[float, float, float, float]) -> float:
    """The best score of `small` (a FINE view) against windows of `square` near `cut` (left, top, right, bottom left
    out), moving each side a step of 1/64, then of 1/128."""
    best = -1.0
    for step in (1 / 64, 1 / 128):
        l, t, r, b = cut
        across = _Spans(SQUARE, FINE, [(l + i * step, r + j * step) for i in (-1, 0, 1) for j in (-1, 0, 1)
                                       if l + i * step >= 0 and r + j * step >= 0])
        down = _Spans(SQUARE, FINE, [(t + i * step, b + j * step) for i in (-1, 0, 1) for j in (-1, 0, 1)
                                     if t + i * step >= 0 and b + j * step >= 0])
        s = _details(down, across, square) @ small
        i, j = np.unravel_index(int(s.argmax()), s.shape)
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
        for windows, square in zip(big.windows() if small.coarse else [], big.squares):
            for whole, fine in zip(small.coarse, small.fine):
                s = windows @ whole
                i = int(s.argmax())
                if s[i] >= FLOOR:
                    (t, bt), (l, r) = SPANS[i // k], SPANS[i % k]
                    best = max(best, _refine(square, fine, (l, t, r, bt)))
                else:
                    best = max(best, float(s[i]))
    return best


def nearest(src: Picture, images: list[tuple[str, str, Picture]]) -> dict:
    best = {"score": 0.0, "ref": None, "sha256": None}
    for f, sha, pic in images:
        s = score(src, pic)
        if s > best["score"]:
            best = {"score": s, "ref": f, "sha256": sha}
    return best


def gate(source_file: str, src: Picture, images: list[tuple[str, str, Picture]], collected: set[str], **detail) -> dict:
    """{"score", "ref"} of the image `src` is nearest to as a picture, or a refusal at LIMIT and over:
    ("collected-copy") when a collection lists that image, else ("reference-copy"). `detail` goes into the refusal."""
    near = nearest(src, images)
    found = {"score": round(near["score"], 4), "ref": near["ref"]}
    if near["score"] < LIMIT:
        return found
    said = (f"{source_file} is the same picture as {near['ref']}: they score {near['score']:.3f} as pictures (limit "
            f"{LIMIT}), so it is that image saved again, resized, cut at the edges or made lighter or darker.")
    if near["sha256"] in collected:
        raise R.Refused("collected-copy", f"{said} That image was collected for measuring. Collected and reference "
                                          "logos set proportions; they are never traced.", copy_nearest=found, **detail)
    raise R.Refused("reference-copy", f"{said} That image is a --refs reference, which sets proportions and is never "
                                      "traced, unless the person said it is theirs: then it is in trace_sources too, and "
                                      "left out of this comparison.", copy_nearest=found, **detail)


def recheck(traces: list[dict], refs: list[tuple[str, str, Picture]], collected: list[tuple[str, str, bytes]]) -> None:
    """The trace gate's own check of each verified trace (rights.traces()) against the collections and --refs images
    as they are now, so a copy collected after the trace, or a trace made before this gate, goes no further: refuses
    ("collected") a source whose sha256 a collection lists, then ("collected-copy", "reference-copy") one that is the
    same picture as any of them but the build's own sources. `collected` is rights.collected_files()."""
    for t in traces:
        hit = next((f for f, sha, _ in collected if sha == t["trace"]["source_sha256"]), None)
        if hit:
            raise R.Refused("collected", f"the traced source {t['provenance']['source']['file']} has the same sha256 as "
                                         f"{hit}, collected since it was traced. Collected and reference logos set "
                                         "proportions; they are never traced. Drop that direction or trace another file.")
    own = {t["trace"]["source_sha256"] for t in traces}
    images, seen = [], set(own)
    for f, sha, pic in [(f, sha, None) for f, sha, _ in collected] + list(refs):
        if sha not in seen:
            seen.add(sha)
            images.append((f, sha, pic))
    data = {sha: d for _, sha, d in collected}
    images = [(f, sha, pic if pic is not None else cached(sha, data[sha])) for f, sha, pic in images]
    shas = set(data)
    for t in traces:
        gate(t["provenance"]["source"]["file"], source(t["source"], t["provenance"]["raster"]["crop"]), images, shas)

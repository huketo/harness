# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "resvg-py"]
# ///
"""Shared image handling for make-logo: load a reference, find its ink on any ground, and normalise it.

A reference is a raster (a screenshot, a photo of a sign, a sheet of marks) or an SVG, which is rasterised with resvg
first. Nothing here keeps an outline. The mask lives in memory long enough to be measured or compared, then it's gone
(references/measuring.md).
"""
from __future__ import annotations

import io
import os

import numpy as np
from PIL import ExifTags, Image, ImageOps, ImageSequence, UnidentifiedImageError
from scipy import ndimage as ndi
from skimage import color, filters, measure, morphology, transform

WORK = 1024  # long side, in pixels, that every reference is measured at
CANON = 256  # side of the square a mark is normalised into for comparing


def open_image(src) -> Image.Image:
    """The picture in a path, bytes or open file: a raster's first frame, or an SVG rasterised by resvg to WORK on its
    long side, transparent around its ink, with a margin of an eighth of WORK each side (an SVG's box is often its
    ink's, and the ground is read from the border)."""
    if isinstance(src, (bytes, bytearray)):
        data = bytes(src)
    elif hasattr(src, "read"):
        data = src.read()
    else:
        with open(src, "rb") as f:
            data = f.read()
    try:
        im = next(ImageSequence.Iterator(Image.open(io.BytesIO(data))))
        im.load()
        return im
    except UnidentifiedImageError:
        if b"<svg" not in data:
            raise
    import resvg_py  # only an SVG needs it

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    im = Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=text, width=WORK))))
    if im.height > WORK:  # a tall mark: fit its height instead
        im = Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=text, height=WORK))))
    pad = WORK // 8
    out = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    out.paste(im.convert("RGBA"), (pad, pad))
    return out


def orientations(im: Image.Image) -> list[Image.Image]:
    """`im` as stored and, when its EXIF orientation (2 to 8) turns or mirrors it, as shown: a camera often stores a
    JPEG on its side with the tag that shows it upright. open_image() and load() give it as stored."""
    if im.getexif().get(ExifTags.Base.Orientation, 1) in range(2, 9):
        return [im, ImageOps.exif_transpose(im)]
    return [im]


def transparent(im: Image.Image) -> bool:
    return im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info


def flatten(im: Image.Image, ground: tuple[int, int, int] = (255, 255, 255), side: int | None = None) -> np.ndarray:
    """RGB floats 0-1 with any transparency flattened onto `ground`, the long side brought down to WORK, or, given
    `side`, resized to it either way."""
    if im.mode == "P" or transparent(im):
        im = Image.alpha_composite(Image.new("RGBA", im.size, (*ground, 255)), im.convert("RGBA"))
    im = im.convert("RGB")
    s = (side or WORK) / max(im.size)
    if s < 1 or (side and s != 1):
        im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    return np.asarray(im, dtype=np.float64) / 255


def load(path) -> np.ndarray:
    """RGB floats 0-1, long side at most WORK, first frame of an animation, transparency flattened onto white; an SVG
    rasterised first (open_image)."""
    return flatten(open_image(path))


def segment(rgb: np.ndarray) -> dict:
    """Split ink from ground. The ground is the colour of the image's border; ink is whatever is far from it in Lab.

    Returns the ink mask cropped to its box, plus how much to trust it:
    - `separation`: Otsu's effectiveness on the distance image, 0 to 1. A flat mark on a plain ground is over 0.9; a
      photo is well under.
    - `ground_share`: the share of border pixels close to the ground colour. Low means the mark runs off the edge or
      the ground isn't plain.
    - `kept`: the share of the ink seen above the threshold that the mask keeps once specks are dropped, also when
      none is kept ("no ink found"). Under 1 when something was too small to keep: dust, or a small mark beside a
      larger one.
    """
    lab = color.rgb2lab(rgb)
    b = np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    ground = np.median(b, axis=0)
    dist = np.linalg.norm(lab - ground, axis=2)
    ground_share = float(np.mean(np.linalg.norm(b - ground, axis=1) < 8))
    flat = dist.ravel()
    if flat.max() - flat.min() < 1e-6:
        return {"ok": False, "why": "blank image"}
    t = filters.threshold_otsu(dist)
    lo, hi = flat[flat <= t], flat[flat > t]
    between = lo.size * hi.size / flat.size**2 * (lo.mean() - hi.mean()) ** 2 if lo.size and hi.size else 0.0
    separation = float(between / flat.var())
    ink = dist > max(t, 12)  # under 12 Lab units the eye barely tells ink from ground
    seen = int(ink.sum())
    speck = max(16, int(ink.size * 2e-4))
    try:  # scikit-image 0.26 renamed min_size to max_size; older releases only know min_size.
        ink = morphology.remove_small_objects(ink, max_size=speck)
    except TypeError:
        ink = morphology.remove_small_objects(ink, min_size=speck + 1)
    kept = float(ink.sum() / seen) if seen else 1.0
    if ink.sum() < 64:
        return {"ok": False, "why": "no ink found", "kept": kept}
    rows, cols = np.where(ink)
    r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
    ink_rgb = rgb[ink]
    return {
        "ok": True,
        "mask": ink[r0:r1, c0:c1],
        "box": [int(r0), int(c0), int(r1), int(c1)],
        "image_size": [int(rgb.shape[0]), int(rgb.shape[1])],
        "separation": separation,
        "ground_share": ground_share,
        "kept": kept,
        "ground_lab": [round(float(v), 1) for v in ground],
        "ink_colours": colour_count(ink_rgb),
        "reversed": bool(ground[0] < 50),
    }


def colour_count(pixels: np.ndarray, share: float = 0.9) -> int:
    """How many colours make up `share` of the ink, after merging colours closer than about 10 Lab units."""
    if len(pixels) > 40000:
        pixels = pixels[np.random.default_rng(0).choice(len(pixels), 40000, replace=False)]
    q = np.round(color.rgb2lab(pixels.reshape(-1, 1, 3)).reshape(-1, 3) / 10).astype(int)
    _, counts = np.unique(q, axis=0, return_counts=True)
    counts = np.sort(counts)[::-1]
    return int(np.searchsorted(np.cumsum(counts) / counts.sum(), share) + 1)


def usable(seg: dict) -> tuple[bool, str]:
    """Whether a reference is a flat mark we can measure. Photos, scenes and marks bleeding off the edge are not."""
    if not seg["ok"]:
        return False, seg["why"]
    if seg["separation"] < 0.8:
        return False, f"not flat (separation {seg['separation']:.2f})"
    if seg["ground_share"] < 0.85:
        return False, f"ground not plain or mark touches the edge ({seg['ground_share']:.2f})"
    if seg["ink_colours"] > 6:
        return False, f"too many colours ({seg['ink_colours']}), likely a photo"
    h, w = seg["mask"].shape
    H, W = seg["image_size"]
    if h * w > 0.97 * H * W:
        return False, "ink fills the frame"
    return True, ""


def canonical(mask: np.ndarray, size: int = CANON, pad: float = 0.06) -> np.ndarray:
    """The mask fitted, aspect kept, into a size x size square with a margin, centred on its box. Floats 0-1."""
    h, w = mask.shape
    inner = size * (1 - 2 * pad)
    s = inner / max(h, w)
    nh, nw = max(1, round(h * s)), max(1, round(w * s))
    small = transform.resize(mask.astype(float), (nh, nw), order=1, anti_aliasing=True)
    out = np.zeros((size, size))
    r, c = (size - nh) // 2, (size - nw) // 2
    out[r:r + nh, c:c + nw] = small
    return out


def components(mask: np.ndarray, min_share: float = 0.002) -> int:
    lab = measure.label(mask, connectivity=2)
    if lab.max() == 0:
        return 0
    sizes = np.bincount(lab.ravel())[1:]
    return int(np.sum(sizes >= min_share * mask.sum()))


def holes(mask: np.ndarray, min_share: float = 0.002) -> list[float]:
    """Each enclosed counter's area as a share of the mark's ink, largest first. Specks are ignored."""
    filled = ndi.binary_fill_holes(mask)
    gaps = measure.label(filled & ~mask, connectivity=1)
    if gaps.max() == 0:
        return []
    sizes = np.bincount(gaps.ravel())[1:] / max(1, mask.sum())
    return sorted([round(float(s), 4) for s in sizes if s >= min_share], reverse=True)


IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".svg"}


def images(paths: list[str], onerror=None) -> list[str]:
    """Every image under the given files and folders, at any depth, sorted. fetch_arena.mjs writes one folder per
    channel, so refs/arena/ holds images a level down. A folder that can't be listed is passed over unless `onerror`
    is given: os.walk() calls it with the OSError."""
    out = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, names in os.walk(p, onerror=onerror):
                dirs.sort()
                out += [os.path.join(root, n) for n in sorted(names) if os.path.splitext(n)[1].lower() in IMAGE_EXT]
        elif os.path.splitext(p)[1].lower() in IMAGE_EXT:
            out.append(p)
    return out

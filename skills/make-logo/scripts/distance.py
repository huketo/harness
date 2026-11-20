# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "resvg-py"]
# ///
"""How close a logo is to each reference (references/distance.md). Used to keep every variant far from every reference.

    uv run distance.py <candidate.png|svg-render.png> <reference image or folder> [...] [--json out.json]

Exits 0 when the nearest reference is clear, 1 when it is too close, and 2 when no reference showed a mark.

Measures on the marks' silhouettes, each normalised so that size, position and the ground's colour don't count, all
taken at the candidate's closest pose (as is, mirrored, or turned a few degrees either way, picked by `similarity`):
- `overlap`: intersection over union of the silhouettes. 1 is the same silhouette.
- `edges`: how far the outlines sit from each other, as the mean nearest distance both ways, in thousandths of the
  box. 0 is the same outline.
- `hash`: matching bits of a 63-bit perceptual hash, as a share. 1 is the same picture at low frequency.
- `negative`: intersection over union of the negative space, the part of each mark's convex hull its ink leaves
  empty (counters, notches, carved letters). 1 is the same negative space, or none in either.
- `skeleton`: the mean nearest distance between the marks' skeletons, both ways, in thousandths of the box.
- `thickness`: how far apart the marks' local thicknesses are (twice the distance to the outline along the skeleton,
  each point weighted by its thickness), as the earth mover's distance in thousandths of the box.

`score` folds the features a calibration file lists into one number, 0 to 1, with weights `calibrate.py` fits on
edited copies against pairs of different references, and it sets where "too close" starts. With no reference showing
a mark, nothing was compared and the check is "not checked", never "clear". This is a guardrail against copying, not
a legal clearance.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi
from scipy.fft import dctn
from scipy.stats import wasserstein_distance
from skimage import morphology, transform

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logolib as L  # noqa: E402

SIDE = 128
TURNS = (-6, -3, 0, 3, 6)


def _features(c: np.ndarray) -> dict:
    """Silhouette, outline, distance to the outline, hash, negative space, skeleton and local thickness for one pose
    of a mark (floats 0-1, SIDE square)."""
    b = c > 0.5
    edge = b ^ ndi.binary_erosion(b)
    small = transform.resize(c, (32, 32), anti_aliasing=True)
    d = dctn(small, norm="ortho")[:8, :8].ravel()[1:]
    skel = morphology.skeletonize(b)
    return {"mask": b, "edge": edge, "edt": ndi.distance_transform_edt(~edge), "hash": d > np.median(d),
            "gaps": morphology.convex_hull_image(b) & ~b if b.any() else b,
            "skeleton": skel, "skeleton_edt": ndi.distance_transform_edt(~skel),
            "thickness": 2 * ndi.distance_transform_edt(b)[skel] / SIDE}


def prepare(mask: np.ndarray, poses: bool = True) -> dict:
    """Everything a comparison needs, computed once per mark. A candidate gets poses: as is, mirrored, and turned a
    few degrees, each re-fitted to its box. A reference needs only itself."""
    c = L.canonical(mask, SIDE)
    out = {"self": _features(c), "poses": []}
    if not poses:
        return out
    for flip in (False, True):
        base = c[:, ::-1] if flip else c
        for deg in TURNS:
            r = transform.rotate(base, deg, order=1, mode="constant") if deg else base
            rb = r > 0.5
            if not rb.any():
                continue
            rows, cols = np.nonzero(rb)
            out["poses"].append(_features(L.canonical(r[rows.min():rows.max() + 1, cols.min():cols.max() + 1], SIDE)))
    return out


def _measure(a: dict, b: dict) -> dict:
    u = np.logical_or(a["mask"], b["mask"]).sum()
    overlap = float(np.logical_and(a["mask"], b["mask"]).sum() / u) if u else 0.0
    ea, eb = a["edge"], b["edge"]
    near = (b["edt"][ea].mean() + a["edt"][eb].mean()) / 2 if ea.any() and eb.any() else SIDE
    edges = 1000 * near / SIDE
    hash_match = float(np.mean(a["hash"] == b["hash"]))
    # Each measure mapped to 0..1 where 1 is identical; the strongest wins, since a copy only has to show in one.
    similarity = max(overlap, max(0.0, 1 - edges / 60), max(0.0, (hash_match - 0.5) / 0.5) * 0.9)
    return {"overlap": round(overlap, 3), "edges": round(float(edges), 1), "hash": round(hash_match, 3), "similarity": round(float(similarity), 3)}


def _shape(a: dict, b: dict) -> dict:
    """The measures that can tell apart two marks whose silhouettes meet: what the ink leaves empty, and the lines and
    thicknesses it is drawn with."""
    u = np.logical_or(a["gaps"], b["gaps"]).sum()
    negative = float(np.logical_and(a["gaps"], b["gaps"]).sum() / u) if u else 1.0
    sa, sb = a["skeleton"], b["skeleton"]
    near = (b["skeleton_edt"][sa].mean() + a["skeleton_edt"][sb].mean()) / 2 if sa.any() and sb.any() else SIDE
    ta, tb = a["thickness"], b["thickness"]
    thick = wasserstein_distance(ta, tb, ta, tb) if len(ta) and len(tb) else 1.0
    return {"negative": round(negative, 3), "skeleton": round(float(1000 * near / SIDE), 1),
            "thickness": round(float(1000 * thick), 1)}


def compare(a: dict, b: dict) -> dict:
    """a is the candidate, b the reference. Every measure is taken at the candidate's closest pose, so a mirrored or
    turned copy is judged as the copy it is."""
    poses = a["poses"] or [a["self"]]
    d, pose = max(((_measure(p, b["self"]), p) for p in poses), key=lambda t: t[0]["similarity"])
    return {**d, **_shape(pose, b["self"])}


HERE = os.path.dirname(os.path.abspath(__file__))


# What a calibration file may name in "features": the compare() key each reads and the number it is divided by.
FEATURES = {"overlap": ("overlap", 1), "edges/100": ("edges", 100), "hash": ("hash", 1), "negative": ("negative", 1),
            "skeleton/100": ("skeleton", 100), "thickness/100": ("thickness", 100)}


def known_features(names: list[str], source: str) -> list[str]:
    unknown = [n for n in names if n not in FEATURES]
    if unknown:
        raise SystemExit(f"{source} names features distance.py doesn't measure: {', '.join(unknown)}. "
                         f"It measures {', '.join(FEATURES)}.")
    return list(names)


def load_calibration(path: str | None = None) -> dict:
    """The fused score's features, weights and limit: from calibrate.py on the person's references when there are
    enough of them (30 or more), otherwise the defaults shipped here, fitted on 98 references."""
    path = path or os.path.join(HERE, "calibration.json")
    with open(path) as f:
        cal = json.load(f)["fused"]
    names = known_features(cal["features"], path)
    if len(cal["weights"]) != len(names) + 1:
        raise SystemExit(f"{path} has {len(cal['weights'])} weights for {len(names)} features; a fitted model has "
                         "one per feature and a constant. Run calibrate.py again.")
    return {"features": names, "weights": cal["weights"], "limit": cal["limit"]}


def fused(d: dict, cal: dict) -> float:
    """0 to 1: how likely this pair is a copy rather than two different logos, by the fitted model, on the features
    the calibration lists and no others."""
    w = cal["weights"]
    z = 0.0
    for wi, name in zip(w, cal["features"]):
        key, scale = FEATURES[name]
        z += wi * d[key] / scale
    z += w[-1]
    return round(float(1 / (1 + np.exp(-z))), 4)


def from_file(path: str, candidate: bool = False) -> dict | None:
    seg = L.segment(L.load(path))
    return prepare(seg["mask"], poses=candidate) if seg["ok"] else None


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("candidate")
    ap.add_argument("refs", nargs="+")
    ap.add_argument("--limit", type=float, default=None, help="score at which a variant fails; default from the calibration")
    ap.add_argument("--calibration", help="calibration.json from calibrate.py; default the one shipped beside this script")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    cand = from_file(a.candidate, candidate=True)
    if cand is None:
        sys.exit("No mark found in the candidate")
    rows = []
    for f in L.images(a.refs):
        ref = from_file(f)
        if ref is not None:
            rows.append({"ref": f, **compare(cand, ref)})
    cal = load_calibration(a.calibration)
    for r in rows:
        r["score"] = fused(r, cal)
    rows.sort(key=lambda r: -r["score"])
    limit = a.limit if a.limit is not None else cal["limit"]
    for r in rows[:5]:
        print(f"{r['score']:.3f}  overlap {r['overlap']:.3f}  edges {r['edges']:5.1f}  hash {r['hash']:.3f}  "
              f"negative {r['negative']:.3f}  skeleton {r['skeleton']:5.1f}  thickness {r['thickness']:5.1f}  "
              f"{r['ref']}")
    if not rows:
        verdict = "not checked"
        print("No reference image showed a mark to compare with, so the distance was not checked.")
    else:
        verdict = "too close" if rows[0]["score"] >= limit else "clear"
        print(f"nearest {rows[0]['score']:.3f} against a limit of {limit:.3f}: {verdict}")
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"limit": limit, "verdict": verdict, "nearest": rows[:10]}, f, indent=1)
    sys.exit({"too close": 1, "clear": 0, "not checked": 2}[verdict])


if __name__ == "__main__":
    main()

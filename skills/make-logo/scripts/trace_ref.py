# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "skia-pathops", "fonttools", "resvg-py"]
# ///
"""Trace a file the person holds rights in into a path the recipe can use (references/building.md, "Tracing").

    uv run trace_ref.py <image> --brief brief.json --refs <ref folder> [...] --out trace/<name>.svg
        [--crop x,y,w,h] [--threshold 0.5] [--invert] [--calibration calibration.json]

--crop is in fractions of the image (0 to 1), around the one mark to take. Dark ink on a light ground is traced as is;
pass --invert for a light mark on a dark ground. potrace draws the curves; the path is fitted to a 48 x 48 box,
centred, so the recipe places it with {"shape": "trace", "file": ..., "x", "y", "size"} and then changes it with the
usual add, cut and xor shapes.

trace() is the only way to trace, and build_logo.py runs it again for every trace shape. It refuses:
1. a file that is not in brief.json `trace_sources` (by sha256);
2. a file whose sha256 is in any collection manifest under the cache (fetch_arena.mjs, fetch_photos.mjs);
3. a mask, the exact pixels passed to potrace after the crop, threshold and invert, that scores at or over the
   calibrated limit against any collected image or --refs logo;
4. potrace's path, rendered, that does the same (potrace drops specks, so a small mark beside dust can pass 3).
In 3 and 4 a reference whose sha256 is a trace_sources entry (the person's own sketch on the moodboard) is left out.
Beside the SVG it writes <svg>.provenance.json: the source and its sha256, the person's statement, the brief's
sha256, every raster and potrace argument, the scores, the potrace binary, and the SVG's sha256.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
import pathops
import resvg_py
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import distance as D  # noqa: E402
import logolib as L  # noqa: E402
import potrace_bin as P  # noqa: E402
import rights as R  # noqa: E402

SCHEMA = "make-logo/trace@1"
LONG_SIDE = 1200  # potrace gets about this many pixels on the long side, so it has edges to fit
POTRACE_ARGS = ["-s", "--flat", "--turdsize", "60", "--opttolerance", "0.4", "-o", "out.svg", "in.pbm"]


def raster_mask(source: str, crop=(0, 0, 1, 1), threshold: float = 0.5, invert: bool = False,
                long_side: int = LONG_SIDE) -> np.ndarray:
    """The ink potrace is given: the crop, resized to `long_side`, thresholded (True is ink)."""
    x, y, w, h = (float(v) for v in crop)
    if not (0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1 - x + 1e-9 and 0 < h <= 1 - y + 1e-9):
        raise SystemExit(f"--crop {x},{y},{w},{h} is not inside the image (fractions 0 to 1)")
    with Image.open(source) as im:
        im = im.convert("L")
    W, H = im.size
    im = im.crop((round(x * W), round(y * H), round((x + w) * W), round((y + h) * H)))
    k = long_side / max(im.size)
    im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    g = np.asarray(im, dtype=np.float32) / 255
    return g > threshold if invert else g < threshold


def ink_box(mask: np.ndarray) -> np.ndarray | None:
    """The mask cropped to its ink, as the references are, or None when there is none."""
    rows, cols = np.nonzero(mask)
    if not rows.size:
        return None
    return mask[rows.min():rows.max() + 1, cols.min():cols.max() + 1]


def pbm(mask: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(np.where(mask, 0, 255).astype(np.uint8)).convert("1").save(buf, "PPM")
    return buf.getvalue()


def svg_text(d: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><path d="{d}"/></svg>\n'


def render_mask(svg: str, px: int = 512) -> np.ndarray:
    png = bytes(resvg_py.svg_to_bytes(svg_string=svg, width=px, background="#ffffff"))
    return np.asarray(Image.open(io.BytesIO(png)).convert("L"), dtype=float) / 255 < 0.5


def run_potrace(mask_pbm: bytes, potrace: str) -> str:
    """potrace's outline of the mask, fitted to a 48 box and centred, as SVG path data."""
    with tempfile.TemporaryDirectory() as t:
        R.write_bytes(os.path.join(t, "in.pbm"), mask_pbm)
        subprocess.run([potrace, *POTRACE_ARGS], cwd=t, check=True)
        src = R.read_bytes(os.path.join(t, "out.svg")).decode()
    # potrace writes paths in its own units under translate(0,H) scale(sx,-sy); undo that, then fit to 48.
    tr = re.search(r'translate\(([-\d.]+),([-\d.]+)\)\s*scale\(([-\d.]+),([-\d.]+)\)', src)
    tx, ty, sx, sy = (float(v) for v in tr.groups())
    path = pathops.Path()
    path.fillType = pathops.FillType.EVEN_ODD
    for dd in re.findall(r'<path[^>]* d="([^"]+)"', src):
        parse_path(dd, TransformPen(path.getPen(), (sx, 0, 0, sy, tx, ty)))
    path = pathops.simplify(path)
    if path.bounds == (0, 0, 0, 0):
        raise SystemExit("potrace found nothing to trace in the crop")
    x0, y0, x1, y1 = path.bounds
    sc = 44 / max(x1 - x0, y1 - y0)
    ox, oy = 24 - (x0 + x1) / 2 * sc, 24 - (y0 + y1) / 2 * sc
    out = pathops.Path()
    path.draw(TransformPen(out.getPen(), (sc, 0, 0, sc, ox, oy)))
    pen = SVGPathPen(None, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
    out.draw(pen)
    return pen.getCommands()


_PREPARED: dict[str, dict | None] = {}  # sha256 -> the reference's prepared features, or None when it isn't a flat mark


def references(refs: list[str], collected: list[tuple[str, str]], skip: set[str]) -> list[tuple[str, str, dict]]:
    """(file, sha256, features) of every flat mark among the --refs images and the collected files, once each by
    sha256, leaving out the shas in `skip`."""
    out, seen = [], set()
    for f in L.images(refs) + [f for f, _ in collected if os.path.isfile(f)]:
        sha = R.sha256_file(f)
        if sha in seen or sha in skip:
            continue
        seen.add(sha)
        if sha not in _PREPARED:
            try:
                seg = L.segment(L.load(f))
                _PREPARED[sha] = D.prepare(seg["mask"], poses=False) if L.usable(seg)[0] else None
            except Exception:  # an unreadable file is not a reference, as in measure_logo.py
                _PREPARED[sha] = None
        if _PREPARED[sha] is not None:
            out.append((f, sha, _PREPARED[sha]))
    return out


def nearest(mask: np.ndarray, refs: list[tuple[str, str, dict]], cal: dict) -> dict:
    cand = D.prepare(mask, poses=True)
    best = {"score": 0.0, "ref": None}
    for f, _, feat in refs:
        s = D.fused(D.compare(cand, feat), cal)
        if s > best["score"]:
            best = {"score": s, "ref": f}
    return best


def trace(source: str, *, brief: str, refs: list[str], out: str, calibration: str | None = None,
          crop=(0, 0, 1, 1), threshold: float = 0.5, invert: bool = False, long_side: int = LONG_SIDE) -> dict:
    """Trace `source` into `out` behind every gate; returns {"provenance", "d", "svg", "record"}. Raises
    rights.Refused, with the scores in `.detail`, instead of writing anything."""
    source = os.path.abspath(source)
    b = R.load_brief(brief)
    src_sha = R.sha256_file(source)
    entry = R.trace_source(b, source, src_sha)
    collected = R.collected()
    hit = next((f for f, sha in collected if sha == src_sha), None)
    if hit:
        raise R.Refused("collected", f"{source} has the same sha256 as {hit}, collected for measuring. Collected and "
                                     "reference logos set proportions; they are never traced.")
    cal_path = R.calibration_file(calibration)
    cal = D.load_calibration(cal_path)
    crop = [float(v) for v in crop]
    mask = raster_mask(source, crop, threshold, invert, long_side)
    mask_pbm = pbm(mask)
    tight = ink_box(mask)
    if tight is None:
        raise SystemExit(f"no ink in {source} at --crop {crop} and --threshold {threshold}{' with --invert' if invert else ''}")
    refset = references(refs, collected, {e["sha256"] for e in b["trace_sources"]})
    mask_near = nearest(tight, refset, cal)
    if mask_near["score"] >= cal["limit"]:
        raise R.Refused("mask-too-close", f"the mask potrace would get scores {mask_near['score']:.3f} against "
                                          f"{mask_near['ref']} (limit {cal['limit']:.3f}). That is another logo, "
                                          "however the file was named, saved or cropped.", mask_nearest=mask_near)
    potrace = P.resolve()
    d = run_potrace(mask_pbm, potrace["path"])
    svg = svg_text(d)
    vector = ink_box(render_mask(svg))
    vector_near = nearest(vector, refset, cal) if vector is not None else {"score": 0.0, "ref": None}
    if vector_near["score"] >= cal["limit"]:
        raise R.Refused("vector-too-close", f"potrace's path scores {vector_near['score']:.3f} against "
                                            f"{vector_near['ref']} (limit {cal['limit']:.3f}; the mask scored "
                                            f"{mask_near['score']:.3f}, the specks potrace dropped hid it).",
                        mask_nearest=mask_near, vector_nearest=vector_near)

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    data = svg.encode()
    R.write_bytes(out, data)
    prov = {
        "schema": SCHEMA,
        "source": {"file": source, "sha256": src_sha},
        "trace_source": entry,
        "brief_sha256": b["sha256"],
        "raster": {"crop": crop, "threshold": threshold, "invert": bool(invert), "long_side": long_side,
                   "potrace_args": list(POTRACE_ARGS)},
        "mask_sha256": R.sha256_bytes(mask_pbm),
        "gate": {"calibration_sha256": R.sha256_file(cal_path), "limit": cal["limit"], "refs_sha256": R.refs_sha256(refs),
                 "collected_sha256": R.digest(sha for _, sha in collected), "mask_nearest": mask_near,
                 "vector_nearest": vector_near},
        "potrace": potrace,
        "svg_sha256": R.sha256_bytes(data),
    }
    record = out + ".provenance.json"
    R.write_bytes(record, json.dumps(prov, indent=1, ensure_ascii=False).encode())
    return {"provenance": prov, "d": d, "svg": out, "record": record}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--brief", required=True, help="brief.json with the person's trace_sources answer for this file")
    ap.add_argument("--refs", nargs="+", required=True, help="every reference folder, as check_logo.py gets them")
    ap.add_argument("--out", required=True)
    ap.add_argument("--crop", default="0,0,1,1")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--invert", action="store_true")
    ap.add_argument("--calibration", help="calibration.json from calibrate.py; default the one shipped here")
    a = ap.parse_args(argv)
    r = trace(a.image, brief=a.brief, refs=a.refs, out=a.out, calibration=a.calibration,
              crop=a.crop.split(","), threshold=a.threshold, invert=a.invert)
    g = r["provenance"]["gate"]
    print(f"traced {os.path.basename(a.image)} into {a.out} ({r['provenance']['trace_source']['rights']}): nearest "
          f"reference {g['mask_nearest']['score']:.3f} as a mask, {g['vector_nearest']['score']:.3f} as a path, "
          f"limit {g['limit']:.3f}; provenance in {r['record']}")


if __name__ == "__main__":
    main()

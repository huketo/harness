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
In 3 and 4 a --refs image whose sha256 is a trace_sources entry (the person's own sketch on the moodboard) is left
out, unless a collection manifest lists that sha256: a collected file is always compared. Every image is compared,
fit to measure or not: an SVG rasterised, a raster too small to split enlarged, and one with transparency split on
white and on black, its highest score counting (a sheet may hold a dark logo and a light one). It also refuses while
any of them still can't be read as a mark, or its mask leaves out a tenth of the ink seen (a sheet of several marks)
("not-comparable": take it out, or replace it with one mark cropped out of it), while a --refs folder or file named
is not there, a folder in them can't be listed, or an image is a broken link ("refs-missing"), while a collection is
or holds a symbolic link ("collection-linked"), while a collection holds a file its manifest does not list
("collection-unlisted": a pull that stopped, or a file put there by hand), and while a collected file is gone or no
longer has the sha256 its manifest lists ("collection-changed"). Each file, the source, every reference and the
calibration, is read once, and the hashes recorded are of the bytes judged.
Beside the SVG it writes <svg>.provenance.json: the source and its sha256, the person's statement, the brief's
sha256, every raster and potrace argument, the scores, the potrace binary, and the SVG's sha256.
"""
from __future__ import annotations

import argparse
import io
import json
import math
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


def raster_mask(data: bytes, crop=(0, 0, 1, 1), threshold: float = 0.5, invert: bool = False,
                long_side: int = LONG_SIDE) -> np.ndarray:
    """The ink potrace is given, from the source file's bytes: the crop, resized to `long_side`, thresholded (True is
    ink)."""
    x, y, w, h = (float(v) for v in crop)
    if not (0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1 - x + 1e-9 and 0 < h <= 1 - y + 1e-9):
        raise SystemExit(f"--crop {x},{y},{w},{h} is not inside the image (fractions 0 to 1)")
    with Image.open(io.BytesIO(data)) as im:
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


_SEGMENT_WHY = {"blank image": "blank", "no ink found": "no-ink"}
_PREPARED: dict[str, tuple[list[dict], str]] = {}  # sha256 -> (features of each mask, "") or ([], why)
# On each ground a reference's mask must keep this share of the ink logolib.segment() sees there before it drops
# specks. On one flat mark the specks are dust, a few percent at most; of the 156 collected and reference images of a
# real run, the three under 90% (86 to 88%) were two photos and a menu.
KEEP = 0.9


def gate_masks(data: bytes) -> tuple[list[np.ndarray], str]:
    """A reference's ink for the distance gates, one mask for each ground it is seen on, or ([], why) with why the
    words for the refusal (rights.UNCOMPARABLE). An opaque image is split as logolib.load() gives it, as measuring
    sees it. One with transparency is split on white and on black, and both masks are kept: a sheet with a dark logo
    and a light one shows one on each. On each ground, while no ink is found, or the mask keeps under KEEP of the ink
    seen, the image is enlarged to logolib.WORK when it is smaller (a favicon). A ground on which every size tried
    keeps under KEEP ("partial") means more than one mark, or a mark too small to keep beside a larger one: the gates
    would compare with part of the image only, so it is not comparable until it is cropped to one mark. The best size
    counts, as enlarging blurs a mark that is not there on that ground into specks."""
    try:
        im = L.open_image(data)
    except Exception:  # neither Pillow nor resvg can read it
        return [], R.UNCOMPARABLE["unreadable"]
    masks, why, short = [], "", []
    for name, ground in [("white", (255, 255, 255))] + ([("black", (0, 0, 0))] if L.transparent(im) else []):
        best = 0.0
        for side in (None, L.WORK) if max(im.size) < L.WORK else (None,):
            seg = L.segment(L.flatten(im, ground, side))
            if seg["ok"] and seg["kept"] >= KEEP:
                masks.append(seg["mask"])
                break
            best = max(best, seg.get("kept", 1.0))
            why = why or seg.get("why", "")
        else:
            if best < KEEP:
                short.append(f"{math.floor(best * 1000) / 10:g}% of the ink on {name}")
    if short:
        return [], R.UNCOMPARABLE["partial"].format(kept=" and ".join(short), need=f"{KEEP:.0%}")
    return masks, "" if masks else R.UNCOMPARABLE.get(_SEGMENT_WHY.get(why, why), why)


def _prepared(sha: str, data: bytes) -> tuple[list[dict], str]:
    if sha not in _PREPARED:
        masks, why = gate_masks(data)
        _PREPARED[sha] = ([D.prepare(m, poses=False) for m in masks], why)
    return _PREPARED[sha]


def _read(path: str) -> bytes | None:
    try:
        return R.read_bytes(path) if os.path.isfile(path) else None
    except OSError:  # gone since it was listed
        return None


def reference_set(refs: list[str], collected: list[tuple[str, str]] = ()) -> dict:
    """What the distance checks compare with: every image in the --refs folders and files and every collected file,
    each read once, so a sha256 recorded is of the bytes judged. Returns {"marks": [(file, sha256, [features of each
    mask])], once per sha256, "refs_sha256": the --refs images' digest, as rights.refs_sha256() computes it}.

    Refuses ("refs-missing") while a --refs path named is not there or an image is a link to nothing,
    ("collection-changed") while a collected file is gone or its bytes no longer have the sha256 its manifest lists,
    and ("not-comparable") while any image can't be read as a mark even by gate_masks()'s fallbacks: the gates say
    nothing about a picture they could not compare."""
    marks, uncomparable, changed, missing, seen, ref_shas, read = [], [], [], [], set(), [], {}
    for f, listed in [(f, None) for f in R.ref_images(refs)] + list(collected):
        if f not in read:
            data = _read(f)
            read[f] = (data, R.sha256_bytes(data) if data is not None else None)
        data, sha = read[f]
        if listed is None:
            if data is None:  # gone between the listing and the read
                missing.append(f)
                continue
            ref_shas.append(sha)
        elif sha != listed:
            changed.append(f"{f} ({'gone' if data is None else 'changed'})")
            continue
        if sha in seen:
            continue
        seen.add(sha)
        feats, why = _prepared(sha, data)
        if feats:
            marks.append((f, sha, feats))
        else:
            uncomparable.append(f"{f} ({why})")
    if missing:
        raise R.Refused("refs-missing", f"these --refs images could not be read: {'; '.join(missing)}. Put them back "
                                        "or take them out of the --refs folders, then run this again.")
    if changed:
        raise R.Refused("collection-changed", "these collected files are gone or changed since their manifest listed "
                                              f"them: {'; '.join(changed)}. Fetch the collection again, or list what "
                                              "is in it now with `node scripts/collection.mjs <name>`, then run this "
                                              "again.")
    if uncomparable:
        raise R.Refused("not-comparable", "the distance gates can't read a mark in "
                                          f"{'; '.join(uncomparable)}, so they can't say the result is far from it. "
                                          "Take each one out of the --refs folder (or out of its collection, then "
                                          "`node scripts/collection.mjs <name>`), or replace it with a copy that "
                                          "shows one mark on a plain ground, then run this again.")
    return {"marks": marks, "refs_sha256": R.digest(ref_shas)}


def calibration_snapshot(path: str | None) -> tuple[dict, str]:
    """The calibration's model and the sha256 of the bytes it came from, read once. distance.load_calibration() takes
    a path, so it reads a private copy of those bytes, not the file, which may change once it has been hashed."""
    raw = R.read_bytes(R.calibration_file(path))
    with tempfile.TemporaryDirectory() as t:
        copy = os.path.join(t, "calibration.json")
        R.write_bytes(copy, raw)
        return D.load_calibration(copy), R.sha256_bytes(raw)


def score(cand: dict, feats: list[dict], cal: dict) -> float:
    """A candidate's score against one reference image: the highest over the masks the image was seen as."""
    return max(D.fused(D.compare(cand, f), cal) for f in feats)


def nearest(mask: np.ndarray, refs: list[tuple[str, str, list[dict]]], cal: dict) -> dict:
    cand = D.prepare(mask, poses=True)
    best = {"score": 0.0, "ref": None}
    for f, _, feats in refs:
        s = score(cand, feats, cal)
        if s > best["score"]:
            best = {"score": s, "ref": f}
    return best


def trace(source: str, *, brief: str, refs: list[str], out: str, calibration: str | None = None,
          crop=(0, 0, 1, 1), threshold: float = 0.5, invert: bool = False, long_side: int = LONG_SIDE,
          reproduce: dict | None = None) -> dict:
    """Trace `source` into `out` behind every gate; returns {"provenance", "d", "svg", "record"}. Raises
    rights.Refused, with the scores in `.detail`, instead of writing anything.

    With `reproduce`, a provenance record (build_logo.py), it also refuses unless the source, the person's statement,
    potrace's arguments and the mask are the ones that record holds, so the record's raster arguments must give back
    the very mask it was traced from."""
    source = os.path.abspath(source)
    b = R.load_brief(brief)
    if reproduce and not os.path.isfile(source):
        raise R.Refused("source-changed", f"the source {source} recorded for this trace is gone. Trace again.")
    data = R.read_bytes(source)
    src_sha = R.sha256_bytes(data)
    if reproduce and src_sha != reproduce["source"]["sha256"]:
        raise R.Refused("source-changed", f"the source {source} changed after it was traced. Trace again.")
    entry = R.trace_source(b, source, src_sha)
    if reproduce and entry != reproduce.get("trace_source"):
        raise R.Refused("brief-changed", f"the person's statement for {source} in {brief} differs from the one in the "
                                         "trace's record. Trace again so the record holds what they said.")
    if reproduce and reproduce["raster"].get("potrace_args") != POTRACE_ARGS:
        raise R.Refused("record-changed", f"the record says potrace ran with {reproduce['raster'].get('potrace_args')}, "
                                          f"and trace_ref.py runs it with {POTRACE_ARGS}. Trace again with trace_ref.py.")
    collected = R.collected()
    hit = next((f for f, sha in collected if sha == src_sha), None)
    if hit:
        raise R.Refused("collected", f"{source} has the same sha256 as {hit}, collected for measuring. Collected and "
                                     "reference logos set proportions; they are never traced.")
    cal, cal_sha = calibration_snapshot(calibration)
    crop = [float(v) for v in crop]
    mask = raster_mask(data, crop, threshold, invert, long_side)
    mask_pbm = pbm(mask)
    mask_sha = R.sha256_bytes(mask_pbm)
    if reproduce and mask_sha != reproduce.get("mask_sha256"):
        raise R.Refused("record-changed", f"the record's raster arguments (crop {crop}, threshold {threshold}, invert "
                                          f"{bool(invert)}, long side {long_side}) give another mask than the one it "
                                          "records, so it was edited. Trace again with trace_ref.py.")
    tight = ink_box(mask)
    if tight is None:
        raise SystemExit(f"no ink in {source} at --crop {crop} and --threshold {threshold}{' with --invert' if invert else ''}")
    refset = reference_set(refs, collected)
    # The person's own sketches on the moodboard are left out; a collected file never is, whatever the brief says.
    own = {e["sha256"] for e in b["trace_sources"]} - {sha for _, sha in collected}
    marks = [m for m in refset["marks"] if m[1] not in own]
    mask_near = nearest(tight, marks, cal)
    if mask_near["score"] >= cal["limit"]:
        raise R.Refused("mask-too-close", f"the mask potrace would get scores {mask_near['score']:.3f} against "
                                          f"{mask_near['ref']} (limit {cal['limit']:.3f}). That is another logo, "
                                          "however the file was named, saved or cropped.", mask_nearest=mask_near)
    potrace = P.resolve()
    d = run_potrace(mask_pbm, potrace["path"])
    svg = svg_text(d)
    vector = ink_box(render_mask(svg))
    vector_near = nearest(vector, marks, cal) if vector is not None else {"score": 0.0, "ref": None}
    if vector_near["score"] >= cal["limit"]:
        raise R.Refused("vector-too-close", f"potrace's path scores {vector_near['score']:.3f} against "
                                            f"{vector_near['ref']} (limit {cal['limit']:.3f}; the mask scored "
                                            f"{mask_near['score']:.3f}, the specks potrace dropped hid it).",
                        mask_nearest=mask_near, vector_nearest=vector_near)

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    svg_bytes = svg.encode()
    R.write_bytes(out, svg_bytes)
    prov = {
        "schema": SCHEMA,
        "source": {"file": source, "sha256": src_sha},
        "trace_source": entry,
        "brief_sha256": b["sha256"],
        "raster": {"crop": crop, "threshold": threshold, "invert": bool(invert), "long_side": long_side,
                   "potrace_args": list(POTRACE_ARGS)},
        "mask_sha256": mask_sha,
        "gate": {"calibration_sha256": cal_sha, "limit": cal["limit"], "refs_sha256": refset["refs_sha256"],
                 "collected_sha256": R.digest(sha for _, sha in collected), "compared": len(marks),
                 "mask_nearest": mask_near, "vector_nearest": vector_near},
        "potrace": potrace,
        "svg_sha256": R.sha256_bytes(svg_bytes),
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
    print(f"traced {os.path.basename(a.image)} into {a.out} ({r['provenance']['trace_source']['rights']}): nearest of "
          f"{g['compared']} images compared {g['mask_nearest']['score']:.3f} as a mask, {g['vector_nearest']['score']:.3f} "
          f"as a path, limit {g['limit']:.3f}; provenance in {r['record']}")


if __name__ == "__main__":
    main()

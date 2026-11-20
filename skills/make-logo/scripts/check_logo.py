# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "skia-pathops", "fonttools", "resvg-py"]
# ///
"""Check a built direction before anyone sees it (references/building.md, "Checks").

    uv run check_logo.py <build dir> [...] --refs <ref folder> [...] [--calibration calibration.json]

For each direction: the mark rendered at 16, 32, 64 and 512 px; its stroke at 16 px; its counters at 16 px against
512 px; its palette's contrast; and its distance to every reference. Writes check.json into each build dir and exits 1
if any direction fails. A failure goes back to the recipe.

Every file build.json lists must still have its sha256, and the list must hold every part the build writes; the
mark is read from those verified bytes. The references are every --refs image whose ink can be told from its ground,
fit to measure or not, each read once; one that can't be read as a mark is printed as "not checked" and listed in
check.json `refs_not_checked`. A traced direction (build.json `traces`, verified against its provenance) leaves out
only its own source, by sha256: every other reference keeps the usual limit. Its score against that source is
recorded in `source_scores` for the book to show and fails nothing; a source the person holds rights in may be used
unchanged. A trace whose gates saw other --refs images, another calibration or other collections than this check is
refused, and the build's old check.json removed: build it again so the trace is gated against what the check sees.
check.json also records the sha256 of build.json, of the --refs images and of the calibration, which package_logo.py
and logo_book.py recompute before they go on.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

import numpy as np
import resvg_py
from PIL import Image
from scipy import ndimage as ndi
from skimage import morphology

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import distance as D  # noqa: E402
import logolib as L  # noqa: E402
import rights as R  # noqa: E402
import trace_ref as T  # noqa: E402

SIZES = (16, 32, 64, 512)


def render(svg: str, px: int) -> np.ndarray:
    """The mark's ink at `px` on its long side, as floats 0-1 (1 is ink)."""
    png = bytes(resvg_py.svg_to_bytes(svg_string=svg, width=px, background="#ffffff"))
    im = np.asarray(Image.open(io.BytesIO(png)).convert("L"), dtype=float) / 255
    if im.shape[0] > px:  # a tall mark: refit on height
        png = bytes(resvg_py.svg_to_bytes(svg_string=svg, height=px, background="#ffffff"))
        im = np.asarray(Image.open(io.BytesIO(png)).convert("L"), dtype=float) / 255
    return 1 - im


def luminance(hex_: str) -> float:
    h = hex_.lstrip("#")
    h = "".join(ch * 2 for ch in h) if len(h) == 3 else h  # #999 is #999999
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a: str, b: str) -> float:
    x, y = sorted([luminance(a), luminance(b)], reverse=True)
    return (x + 0.05) / (y + 0.05)


GATE_INPUTS = {"refs_sha256": "--refs images", "calibration_sha256": "calibration", "collected_sha256": "collections"}


def check(build: str, refset: dict, cal: dict, calibration_sha256: str) -> dict:
    """Check one build against trace_ref.reference_set() and the calibration and write its check.json. A build this
    refuses keeps no check.json, so nothing after it can go on from an earlier one."""
    try:
        return _check(build, refset, cal, calibration_sha256)
    except R.Refused:
        if os.path.exists(os.path.join(build, "check.json")):
            os.remove(os.path.join(build, "check.json"))
        raise


def _check(build: str, refset: dict, cal: dict, calibration_sha256: str) -> dict:
    raw = R.read_bytes(os.path.join(build, "build.json"))
    info = json.loads(raw)
    files = R.verified_files(build, info)
    traces = R.traces(build, info, files)
    if traces:
        now = {"refs_sha256": refset["refs_sha256"], "calibration_sha256": calibration_sha256,
               "collected_sha256": R.collected_sha256()}
        for t in traces:
            stale = [GATE_INPUTS[k] for k, v in now.items() if t["provenance"]["gate"].get(k) != v]
            if stale:
                raise R.Refused("trace-gate-stale", f"{build}/{t['svg']} was traced behind gates that saw other "
                                                    f"{' and '.join(stale)} than this check. Build it again with the "
                                                    "same --refs and --calibration, so its trace is gated against "
                                                    "them, then check it.")
    own = {t["trace"]["source_sha256"] for t in traces}
    mark = files["mark.svg"].decode()
    big = render(mark, 512) > 0.5
    small = render(mark, 16)
    rows = []

    # Stroke at 16 px: the median stroke at 512, scaled. Under 1.5 px a stroke breaks up on a favicon.
    edt = ndi.distance_transform_edt(big)
    skel = morphology.skeletonize(big)
    w512 = float(np.median(2 * edt[skel])) if skel.any() else 0.0
    stroke16 = w512 * 16 / max(big.shape)
    rows.append(("stroke at 16 px", f"{stroke16:.2f} px", ">= 1.5 px", stroke16 >= 1.5))

    # Counters: holes that exist at 512 px must still be open at 16 px, and no new ones may appear. A new hole means
    # a gap pinched shut at 16 px and closed into a ring.
    h512 = len(L.holes(big, min_share=0.004))
    h16 = len(L.holes(small > 0.5, min_share=0.004))
    rows.append(("counters at 16 px", f"{h16} of {h512}", "same as at 512 px", h16 == h512))

    pal = info.get("palette", {})
    if {"ink", "paper"} <= pal.keys():
        c = contrast(pal["ink"], pal["paper"])
        rows.append(("ink on paper", f"{c:.2f}:1", ">= 4.5:1", c >= 4.5))
    if {"accent", "paper"} <= pal.keys():
        c = max(contrast(pal["accent"], pal["paper"]), contrast(pal["accent"], pal.get("ink", "#000000")))
        rows.append(("accent against paper or ink", f"{c:.2f}:1", ">= 3:1", c >= 3))

    # Distance: the mark against every reference but its own verified source, scored with the calibrated model.
    cand = D.prepare(big, poses=True)
    marks = [m for m in refset["marks"] if m[1] not in own]
    near = sorted(((D.fused(D.compare(cand, r), cal), f) for f, _, r in marks), reverse=True)[:3]
    top = near[0][0] if near else 0.0
    rows.append(("nearest reference", f"{top:.3f}", f"< {cal['limit']:.3f}", top < cal["limit"]))
    # Against the source it was traced from: shown in the book, never a failure.
    source_scores = []
    for t in traces:
        r = t["provenance"]["raster"]
        src = T.ink_box(T.raster_mask(t["source"], r["crop"], r["threshold"], r["invert"], r["long_side"]))
        score = D.fused(D.compare(cand, D.prepare(src, poses=False)), cal) if src is not None else 0.0
        source_scores.append({"source_sha256": t["trace"]["source_sha256"], "score": score})

    sizes = {}
    for px in SIZES:
        a = render(mark, px)
        sizes[px] = round(float(a.mean()), 4)
    report = {"direction": info.get("title", os.path.basename(build)), "checks": [
        {"check": n, "value": v, "pass_at": p, "ok": bool(ok)} for n, v, p, ok in rows],
        "nearest": [{"score": s, "ref": f} for s, f in near], "ink_share_by_size": sizes,
        "source_scores": source_scores, "refs_compared": len(marks), "refs_not_checked": refset["not_checked"],
        "limit": cal["limit"],
        # A detailed trace may close up at 16 px (SKILL.md step 8): those rows are reported, and the build still passes.
        "ok": all(r[3] for r in rows if not (traces and r[0].endswith("at 16 px"))),
        "build_sha256": R.sha256_bytes(raw), "refs_sha256": refset["refs_sha256"], "calibration_sha256": calibration_sha256}
    R.write_bytes(os.path.join(build, "check.json"), json.dumps(report, indent=1, ensure_ascii=False).encode())
    return report


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("builds", nargs="+")
    ap.add_argument("--refs", nargs="+", required=True)
    ap.add_argument("--calibration")
    a = ap.parse_args(argv)
    cal, cal_sha = T.calibration_snapshot(a.calibration)
    refset = T.reference_set(a.refs)
    print(f"{len(refset['marks'])} references to check against, limit {cal['limit']:.3f}")
    for line in T.not_checked_lines(refset["not_checked"]):
        print(line)
    ok = True
    for b in a.builds:
        rep = check(b, refset, cal, cal_sha)
        ok &= rep["ok"]
        print(f"\n{rep['direction']}: {'pass' if rep['ok'] else 'FAIL'}")
        for c in rep["checks"]:
            print(f"  {'ok  ' if c['ok'] else 'FAIL'} {c['check']:28s} {c['value']:>12s}   {c['pass_at']}")
        for sc in rep["source_scores"]:
            print(f"  info score against its own traced source {sc['source_sha256'][:12]}: {sc['score']:.3f} (shown, not checked)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

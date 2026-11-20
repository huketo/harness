# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "brotli", "uharfbuzz"]
# ///
"""Measure a font file: proportions, stems, contrast, serifs, class-mean widths and sidebearings.

  uv run measure_font.py <font.ttf|otf|woff2> [--loc wght=400,opsz=14] [--stem 76] [--out m.json]

--loc     a location in a variable font (defaults to its default instance).
--stem    solve the weight axis so the n stem, at cap 700, equals this value first. Use it to compare a
          variable font with a reference at the same colour.
Lengths are in cap-normalised units (cap height 700). The JSON also keeps cap_em, the real cap height per
1000 em, and the font's vertical metrics. Every number is a font-wide value or a class mean.

A font with Hangul syllables also gets a `hangul` object: per structural class (H1 to H6) the face size, centre,
sides and advance, the vertical stem and the report-only numbers, each value tagged with its unit (cap700 when the
font has a Latin H, em1000 always, ratio). A font without the Latin letters gets the Hangul numbers alone; an H
among them still sets the Hangul's cap700 lengths.
"""
import argparse
import json
import os
import sys

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontTools.ttLib import TTFont  # noqa: E402

import fontlib as L  # noqa: E402

LATIN_NEEDED = "Hxno"  # measure_face's scale and core cuts; a font without them is measured for Hangul only


def parse_loc(s):
    if not s:
        return {}
    return {k.strip(): float(v) for k, v in (p.split("=") for p in s.split(",") if p.strip())}


def measure_path(path, loc=None, stem=None):
    f = TTFont(path)
    axes = L.axes_of(f)
    loc = dict(loc or {})
    cmap = f.getBestCmap()
    latin = all(ord(c) in cmap for c in LATIN_NEEDED)
    if stem and not latin:
        raise SystemExit(f"--stem solves the Latin n stem, and {path} has no {LATIN_NEEDED}")
    if stem and "wght" in axes:
        lo, hi = axes["wght"][0], axes["wght"][2]
        quick = L.subset_font(f, "nHx", layout=False)
        w, got = L.solve_axis(lambda v: L.Face(quick, {**loc, "wght": v}), L.stem_cap700, stem, lo, hi)
        loc["wght"] = round(w, 1)
    if latin:
        m = L.measure_face(L.Face(L.subset_font(f, L.MEASURE_TEXT), loc if axes else None))
    else:
        m = {"source": "file", "cap_em": None, "vmetrics": L.vmetrics(f), "confidence": {}}
    if any(ord(c) in cmap for c in L.HANGUL_TEXT):
        hface = L.Face(L.subset_font(f, L.HANGUL_TEXT + "H", layout=False), loc if axes else None)
        # The Hangul's cap is the H alone, whatever other Latin the font has.
        cap = hface.bounds("H")[3] if hface.has("H") and hface.bounds("H") else None
        lengths = {"cap700": L.CAP / cap} if cap else {}
        lengths["em1000"] = 1000 / hface.upm
        geo = L.hangul_geometry(hface)
        if geo["classes"]:
            m["hangul"] = L.hangul_measurement(geo, lengths)
        else:
            print(f"Hangul left out: no class has {L.CLASS_MIN} syllables of its list (fontlib.HANGUL_CLASSES) "
                  "in this font", file=sys.stderr)
    m["file"] = os.path.basename(path)
    m["loc"] = loc
    m["axes"] = axes
    m["family"] = f["name"].getDebugName(16) or f["name"].getDebugName(1)
    m["glyphs"] = len(f.getGlyphOrder())
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("font")
    ap.add_argument("--loc", default="")
    ap.add_argument("--stem", type=float)
    ap.add_argument("--out")
    a = ap.parse_args()
    m = measure_path(a.font, parse_loc(a.loc), a.stem)
    if a.out:
        L.save_json(m, a.out)
    keys = ["cap_em", "xh", "xh_cap", "asc", "desc", "overshoot_lc", "n_stem", "H_stem", "H_bar", "o_side", "o_thin",
            "contrast", "bar_stem", "serif", "serif_ext", "serif_tip", "n_counter", "rhythm", "lc_avg", "uc_avg", "space", "para"]
    print(f"{m['file']}  loc {m['loc'] or 'default'}")
    if "widths" in m:
        for k in keys:
            print(f"  {k:13s} {m.get(k)}")
        print("  widths       ", json.dumps(m["widths"]))
        print("  sides        ", json.dumps(m["sides"]))
    else:
        print("  no Latin H, x, n and o: Latin not measured")
    if "hangul" in m:
        print("\n".join(L.hangul_summary(m["hangul"])))


if __name__ == "__main__":
    main()

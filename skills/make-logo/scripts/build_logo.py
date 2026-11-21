# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "skia-pathops", "fonttools", "uharfbuzz", "resvg-py"]
# ///
"""Build a logo from a recipe of grid shapes and an OFL wordmark (references/building.md).

    uv run build_logo.py <direction.json> --out <dir> [--fonts <cache dir>]
        [--brief brief.json --refs <ref folder> [...] [--calibration calibration.json]]

The recipe (units are grid squares, y down, on a `grid` x `grid` canvas):

    {"name": "Northlight", "title": "Two lights", "idea": "one sentence",
     "grid": 48,
     "mark": [
       {"shape": "circle", "cx": 24, "cy": 24, "r": 20},
       {"op": "cut", "shape": "rect", "x": 22, "y": 0, "w": 4, "h": 48},
       {"shape": "ring", "cx": 24, "cy": 24, "r": 10, "width": 4, "rotate": 30},
       {"shape": "arc", "cx": 24, "cy": 24, "r": 18, "width": 5, "start": 200, "end": 340},
       {"shape": "polygon", "points": [[4, 44], [24, 4], [44, 44]]},
       {"shape": "rect", "x": 4, "y": 4, "w": 12, "h": 12, "r": 3, "repeat": {"count": 4, "rotate": 90, "about": [24, 24]}},
       {"shape": "glyph", "text": "N", "font": "Inter Tight", "weight": 700, "x": 10, "y": 40, "cap": 30},
       {"shape": "trace", "file": "trace/bell.svg", "x": 2, "y": 2, "size": 44}
     ],
     "wordmark": {"text": "Northlight", "font": "Inter Tight", "weight": 500, "tracking": -10},
     "lockup": {"mark_scale": 1.6, "gap": 0.7},
     "palette": {"ink": "#151515", "paper": "#f7f5f1", "accent": "#e8562a", "neutral": "#9b9187", "tint": "#e7e2da"}}

`op` is add (default), cut, keep (intersect) or xor, applied in order. Any shape takes `rotate` (degrees about its
own centre or `about`), `mirror` ("x" or "y" across the grid's centre) and `repeat`.

A `trace` file is an SVG trace_ref.py wrote, found from the working folder first, then from the recipe's folder. Its
SVG is never used: the build checks its .provenance.json against the SVG's sha256, then traces the source again with
trace_ref.trace() and every gate, against --refs and the collections as they are now, and uses that path. That trace
goes on only while the source, the person's statement in --brief, potrace's arguments and the mask the recorded
raster arguments give are the ones the record holds. A recipe that says `traced_from` is refused: whether and from
what a mark was traced comes from the verified record only.

Writes mark.svg (tight), mark-grid.svg (on its grid, for the construction page), wordmark.svg, lockup.svg,
lockup-stacked.svg, trace/<n>.svg with its provenance, LICENSES/ (each font's OFL.txt) and build.json: boxes, guides,
the fonts, `shapes` (each recipe shape and its op, in order), `traces` (the verified record of each trace) and `files`
(every file this build wrote, with its sha256; package_logo.py and logo_book.py use only those).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys

import pathops
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.svgLib.path import parse_path
from fontTools.pens.transformPen import TransformPen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fonts as F  # noqa: E402
import rights as R  # noqa: E402

K = 0.5522847498  # cubic handle length for a quarter circle


def affine(m, p):
    a, b, c, d, e, f = m
    x, y = p
    return (a * x + c * y + e, b * x + d * y + f)


def mul(m, n):
    """m then n."""
    a, b, c, d, e, f = n
    return (a * m[0] + c * m[1], b * m[0] + d * m[1], a * m[2] + c * m[3], b * m[2] + d * m[3], a * m[4] + c * m[5] + e, b * m[4] + d * m[5] + f)


def rot(deg, cx, cy):
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    return (c, s, -s, c, cx - c * cx + s * cy, cy - s * cx - c * cy)


class Draw:
    """Draws into a pathops Path through an affine transform."""

    def __init__(self, m):
        self.path = pathops.Path()
        self.pen = self.path.getPen()
        self.m = m

    def move(self, p):
        self.pen.moveTo(affine(self.m, p))

    def line(self, p):
        self.pen.lineTo(affine(self.m, p))

    def curve(self, a, b, p):
        self.pen.curveTo(affine(self.m, a), affine(self.m, b), affine(self.m, p))

    def close(self):
        self.pen.closePath()


def arc_points(d: Draw, cx, cy, r, a0, a1, first=True):
    """An arc from a0 to a1 degrees (clockwise on screen, 0 at 3 o'clock), as cubics of at most 90 degrees."""
    n = max(1, math.ceil(abs(a1 - a0) / 90))
    step = (a1 - a0) / n
    pt = lambda a: (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
    if first:
        d.move(pt(a0))
    for i in range(n):
        s, e = a0 + i * step, a0 + (i + 1) * step
        h = 4 / 3 * math.tan(math.radians(e - s) / 4) * r
        ps, pe = pt(s), pt(e)
        ts = (-math.sin(math.radians(s)), math.cos(math.radians(s)))
        te = (-math.sin(math.radians(e)), math.cos(math.radians(e)))
        d.curve((ps[0] + h * ts[0], ps[1] + h * ts[1]), (pe[0] - h * te[0], pe[1] - h * te[1]), pe)


def circle(d, cx, cy, r, reverse=False):
    if reverse:
        arc_points(d, cx, cy, r, 360, 0)
    else:
        arc_points(d, cx, cy, r, 0, 360)
    d.close()


def rect(d, x, y, w, h, r=0):
    r = max(0, min(r, w / 2, h / 2))
    if r == 0:
        d.move((x, y)); d.line((x + w, y)); d.line((x + w, y + h)); d.line((x, y + h)); d.close()
        return
    k = r * K
    d.move((x + r, y)); d.line((x + w - r, y))
    d.curve((x + w - r + k, y), (x + w, y + r - k), (x + w, y + r)); d.line((x + w, y + h - r))
    d.curve((x + w, y + h - r + k), (x + w - r + k, y + h), (x + w - r, y + h)); d.line((x + r, y + h))
    d.curve((x + r - k, y + h), (x, y + h - r + k), (x, y + h - r)); d.line((x, y + r))
    d.curve((x, y + r - k), (x + r - k, y), (x + r, y)); d.close()


def centre_of(s) -> tuple[float, float]:
    k = s["shape"]
    if k == "trace":
        h = s.get("size", 48) / 2
        return s.get("x", 0) + h, s.get("y", 0) + h
    if k in ("circle", "ring", "arc"):
        return s["cx"], s["cy"]
    if k == "rect":
        return s["x"] + s["w"] / 2, s["y"] + s["h"] / 2
    if k == "polygon":
        xs, ys = zip(*s["points"])
        return sum(xs) / len(xs), sum(ys) / len(ys)
    return s.get("x", 0), s.get("y", 0)


def shape_path(s: dict, grid: float, fonts_dir: str, m=(1, 0, 0, 1, 0, 0), traced: str | None = None) -> pathops.Path:
    if "rotate" in s:
        cx, cy = s.get("about") or centre_of(s)
        m = mul(rot(s["rotate"], cx, cy), m)
    if s.get("mirror") == "x":
        m = mul((-1, 0, 0, 1, grid, 0), m)
    elif s.get("mirror") == "y":
        m = mul((1, 0, 0, -1, 0, grid), m)
    d = Draw(m)
    k = s["shape"]
    if k == "rect":
        rect(d, s["x"], s["y"], s["w"], s["h"], s.get("r", 0))
    elif k == "circle":
        circle(d, s["cx"], s["cy"], s["r"])
    elif k == "ring":
        circle(d, s["cx"], s["cy"], s["r"])
        inner = Draw(m)
        circle(inner, s["cx"], s["cy"], s["r"] - s["width"])
        return pathops.op(d.path, inner.path, pathops.PathOp.DIFFERENCE)
    elif k == "arc":
        r0, r1 = s["r"] - s["width"], s["r"]
        arc_points(d, s["cx"], s["cy"], r1, s["start"], s["end"])
        a = math.radians(s["end"])
        d.line((s["cx"] + r0 * math.cos(a), s["cy"] + r0 * math.sin(a)))
        arc_points(d, s["cx"], s["cy"], r0, s["end"], s["start"], first=False)
        d.close()
    elif k == "polygon":
        pts = s["points"]
        d.move(tuple(pts[0]))
        for p in pts[1:]:
            d.line(tuple(p))
        d.close()
    elif k == "glyph":
        info = F.fetch(s["font"], fonts_dir)
        t = F.set_text(F.load(info, s.get("weight", 400)), s["text"], s.get("tracking", 0))
        sc = s["cap"] / t["cap"]
        # Font units are y up from the baseline; the grid is y down. Place the baseline at (x, y).
        gm = mul((sc, 0, 0, -sc, s["x"], s["y"]), m)
        t["pen"].replay(TransformPen(d.pen, gm))
    elif k == "trace":
        # The path trace_ref.trace() just made for this shape: one path in a 48 x 48 box, placed at (x, y), scaled to `size`.
        sc = s.get("size", 48) / 48
        parse_path(traced, TransformPen(d.pen, mul((sc, 0, 0, sc, s.get("x", 0), s.get("y", 0)), m)))
    else:
        raise SystemExit(f"unknown shape {k!r}")
    return d.path


OPS = {"add": pathops.PathOp.UNION, "cut": pathops.PathOp.DIFFERENCE, "keep": pathops.PathOp.INTERSECTION, "xor": pathops.PathOp.XOR}


def build_mark(spec: dict, fonts_dir: str, traced: dict[int, str] | None = None) -> pathops.Path:
    grid = spec.get("grid", 48)
    acc = pathops.Path()
    for i, s in enumerate(spec["mark"]):
        rep = s.get("repeat")
        copies = [(1, 0, 0, 1, 0, 0)]
        if rep:
            cx, cy = rep.get("about", (grid / 2, grid / 2))
            copies = [rot(rep.get("rotate", 360 / rep["count"]) * i, cx, cy) for i in range(rep["count"])]
            if "step" in rep:
                copies = [(1, 0, 0, 1, rep["step"][0] * i, rep["step"][1] * i) for i in range(rep["count"])]
        piece = pathops.Path()
        for m in copies:
            piece = pathops.op(piece, shape_path(s, grid, fonts_dir, m, (traced or {}).get(i)), pathops.PathOp.UNION)
        acc = pathops.op(acc, piece, OPS[s.get("op", "add")])
    return pathops.simplify(acc)


def guides(spec: dict) -> dict:
    """The construction lines for the book: every edge and centre the recipe names, on the grid."""
    xs, ys = set(), set()
    for s in spec["mark"]:
        if s["shape"] == "rect":
            xs |= {s["x"], s["x"] + s["w"]}; ys |= {s["y"], s["y"] + s["h"]}
        elif s["shape"] in ("circle", "ring", "arc"):
            xs |= {s["cx"] - s["r"], s["cx"], s["cx"] + s["r"]}; ys |= {s["cy"] - s["r"], s["cy"], s["cy"] + s["r"]}
        elif s["shape"] == "polygon":
            for x, y in s["points"]:
                xs.add(x); ys.add(y)
    g = spec.get("grid", 48)
    keep = lambda v: sorted(round(float(x), 3) for x in v if 0 <= x <= g)
    return {"x": keep(xs), "y": keep(ys)}


def d_of(path: pathops.Path) -> str:
    pen = SVGPathPen(None, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
    path.draw(pen)
    return pen.getCommands()


def bounds(path: pathops.Path):
    return path.bounds  # (xMin, yMin, xMax, yMax)


def svg(d: str, box, fill="#151515", pad=0.0) -> str:
    x0, y0, x1, y1 = box
    w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0 - pad:.2f} {y0 - pad:.2f} {w:.2f} {h:.2f}" '
            f'width="{w:.2f}" height="{h:.2f}"><path fill="{fill}" fill-rule="nonzero" d="{d}"/></svg>\n')


def says_traced_from(v) -> bool:
    if isinstance(v, dict):
        return "traced_from" in v or any(says_traced_from(x) for x in v.values())
    return isinstance(v, list) and any(says_traced_from(x) for x in v)


def trace_file(f: str, recipe_dir: str) -> str:
    """A recipe's trace path: from the working folder, else from the recipe's folder."""
    if os.path.isabs(f) or os.path.exists(f):
        return os.path.abspath(f)
    return os.path.join(recipe_dir, f)


def admit_traces(spec: dict, out: str, recipe_dir: str, brief: str | None, refs: list[str] | None,
                 calibration: str | None) -> tuple[dict[int, str], list[dict], list[str]]:
    """Check each trace shape's record, trace its source again behind every gate, and return the new paths by shape
    index, the build.json `traces` entries, and the files written."""
    import trace_ref as T

    traced, entries, written = {}, [], []
    for i, s in enumerate(spec["mark"]):
        if s.get("shape") != "trace":
            continue
        if not brief or not refs:
            raise SystemExit("a recipe with a trace shape needs --brief and --refs: the build traces it again and checks it")
        svg = trace_file(s["file"], recipe_dir)
        if not os.path.isfile(svg):
            raise SystemExit(f"no trace file {s['file']} (looked in the working folder and beside the recipe)")
        rec = svg + ".provenance.json"
        if not os.path.isfile(rec):
            raise R.Refused("no-provenance", f"{svg} has no {os.path.basename(rec)}. Trace it with trace_ref.py; an SVG "
                                             "from anywhere else can't go into a build.")
        prov = R.read_json(rec)
        if prov.get("schema") != T.SCHEMA:
            raise R.Refused("no-provenance", f"{rec} is not a {T.SCHEMA} record. Trace again with trace_ref.py.")
        if R.sha256_file(svg) != prov.get("svg_sha256"):
            raise R.Refused("svg-changed", f"{svg} changed after trace_ref.py wrote it. Trace again; change the mark "
                                           "with recipe shapes, not by editing the SVG.")
        raster = prov["raster"]
        rel = f"trace/{i}.svg"
        r = T.trace(prov["source"]["file"], brief=brief, refs=refs, out=os.path.join(out, rel), calibration=calibration,
                    crop=raster["crop"], threshold=raster["threshold"], invert=raster["invert"],
                    long_side=raster["long_side"], reproduce=prov)
        traced[i] = r["d"]
        p = r["provenance"]
        entries.append({"source_sha256": p["source"]["sha256"], "rights": p["trace_source"]["rights"],
                        "answer": p["trace_source"]["answer"], "provenance_sha256": R.sha256_file(r["record"]),
                        "svg_sha256": p["svg_sha256"]})
        written += [rel, rel + ".provenance.json"]
    return traced, entries, written


def build(spec: dict, out: str, fonts_dir: str, recipe_dir: str = ".", brief: str | None = None,
          refs: list[str] | None = None, calibration: str | None = None) -> dict:
    if says_traced_from(spec):
        raise R.Refused("traced-from", "the recipe says traced_from. Leave it out: the build writes where a trace came "
                                       "from, from the record trace_ref.py made.")
    os.makedirs(out, exist_ok=True)
    traced, traces, written = admit_traces(spec, out, recipe_dir, brief, refs, calibration)

    def put(rel: str, text: str) -> None:
        R.write_bytes(os.path.join(out, rel), text.encode())
        written.append(rel)

    mark = build_mark(spec, fonts_dir, traced)
    if mark.bounds == (0, 0, 0, 0):
        raise SystemExit("The mark is empty")
    g = spec.get("grid", 48)
    md = d_of(mark)
    put("mark.svg", svg(md, bounds(mark)))
    put("mark-grid.svg", svg(md, (0, 0, g, g)))
    result = {"name": spec["name"], "grid": g, "mark_box": [round(v, 3) for v in bounds(mark)], "guides": guides(spec),
              "shapes": [{"shape": s["shape"], "op": s.get("op", "add")} for s in spec["mark"]]}

    fonts = {}

    def licence(family: str, info: dict) -> str:
        rel = f"LICENSES/{re.sub(r'[^A-Za-z0-9]+', '-', family)}-OFL.txt"
        if rel not in written:
            os.makedirs(os.path.join(out, "LICENSES"), exist_ok=True)
            R.write_bytes(os.path.join(out, rel), R.read_bytes(info["licence"]))
            written.append(rel)
        fonts[family] = rel
        return rel

    wm = spec.get("wordmark")
    if wm:
        info = F.fetch(wm["font"], fonts_dir)
        t = F.set_text(F.load(info, wm.get("weight", 500)), wm["text"], wm.get("tracking", 0))
        wpath = pathops.Path()
        t["pen"].replay(TransformPen(wpath.getPen(), (1, 0, 0, -1, 0, 0)))  # y down, baseline at 0
        wpath = pathops.simplify(wpath)
        put("wordmark.svg", svg(d_of(wpath), bounds(wpath)))
        cap = t["cap"]
        lk = spec.get("lockup", {})
        mx0, my0, mx1, my1 = bounds(mark)
        mh = lk.get("mark_scale", 1.6) * cap
        sc = mh / (my1 - my0)
        gap = lk.get("gap", 0.7) * cap
        # Horizontal: the mark's middle on the cap height's middle.
        mid = -cap / 2
        hm = (sc, 0, 0, sc, -mx0 * sc - (mx1 - mx0) * sc - gap, mid - (my0 + (my1 - my0) / 2) * sc)
        lock = pathops.Path()
        mark.draw(TransformPen(lock.getPen(), hm))
        lock = pathops.op(lock, wpath, pathops.PathOp.UNION)
        put("lockup.svg", svg(d_of(lock), bounds(lock)))
        # Stacked: the mark centred above the wordmark.
        wx0, wy0, wx1, wy1 = bounds(wpath)
        sm_h = 2.2 * cap
        ss = sm_h / (my1 - my0)
        sm = (ss, 0, 0, ss, (wx0 + wx1) / 2 - (mx0 + mx1) / 2 * ss, -cap - 1.0 * cap - my1 * ss)
        stack = pathops.Path()
        mark.draw(TransformPen(stack.getPen(), sm))
        stack = pathops.op(stack, wpath, pathops.PathOp.UNION)
        put("lockup-stacked.svg", svg(d_of(stack), bounds(stack)))
        result["wordmark"] = {"text": wm["text"], "font": wm["font"], "weight": wm.get("weight", 500), "cap": cap,
                              "licence": licence(wm["font"], info), "reserved_names": info["reserved_names"]}
        if any(n.lower() in wm["text"].lower() for n in info["reserved_names"]):
            print(f"warning: the wordmark uses the font's Reserved Font Name {info['reserved_names']}")
    for part in spec["mark"]:
        if part["shape"] == "glyph":
            licence(part["font"], F.fetch(part["font"], fonts_dir))
    if fonts:
        result["fonts"] = fonts
    result.update({k: spec[k] for k in ("title", "idea", "palette") if k in spec})
    result["traces"] = traces
    result["files"] = {rel: R.sha256_file(os.path.join(out, rel)) for rel in written}
    R.write_bytes(os.path.join(out, "build.json"), json.dumps(result, indent=1, ensure_ascii=False).encode())
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recipe")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fonts", default=None, help="font cache; default ${XDG_CACHE_HOME:-~/.cache}/hstack/make-logo/fonts")
    ap.add_argument("--brief", help="brief.json with trace_sources; needed when the recipe has a trace shape")
    ap.add_argument("--refs", nargs="+", help="every reference folder, as check_logo.py gets them; needed with a trace shape")
    ap.add_argument("--calibration", help="calibration.json from calibrate.py; default the one shipped here")
    a = ap.parse_args(argv)
    fonts_dir = a.fonts or os.path.join(R.cache_root(), "fonts")
    r = build(R.read_json(a.recipe), a.out, fonts_dir, os.path.dirname(os.path.abspath(a.recipe)), a.brief, a.refs, a.calibration)
    traced = f", traced from {len(r['traces'])} checked source(s)" if r["traces"] else ""
    print(f"built {r['name']}: mark box {r['mark_box']}, {len(r['guides']['x'])} x and {len(r['guides']['y'])} y guides{traced}")


if __name__ == "__main__":
    main()

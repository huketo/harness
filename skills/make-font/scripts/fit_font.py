# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "uharfbuzz", "skia-pathops"]
# ///
"""Bend the approved OFL variable font to targets.json: one static TTF per style.

  uv run fit_font.py <base-vf.ttf> targets.json --base-json base.json --out-dir DIR [--loc opsz=14]
      [--style Regular] [--max-stretch 0.03] [--tol 0.3] [--no-contrast]

This script opens the base font and targets.json. It never opens a reference font: the references reach it
only as the numbers in targets.json.

Before anything else it checks base.json (record_base.py wrote it when the person approved the base): the font
and OFL text must still have the sha256 recorded there, and <base-vf.ttf> must be that font, byte for byte. A
subset made elsewhere is refused. With korean in the targets' scripts, the base must be a pinned manifest entry's
files too (chain.require_pinned_base): base.json records that entry, and bases.json still pins both sha256 values. The script subsets the verified base itself, to the characters of the
targets' scripts (fontlib.COVERAGE and COVERAGE_REPORTED, plus ASCII, Latin-1 and common punctuation), writes
<DIR>/subset/base.subset.ttf, and fits from that subset. fit-log.json records the subset (source sha256, file,
sha256, pyftsubset arguments) and the chain: base.json's sha256, the base as input, every font written as output.
Each input is read once (chain.Files), so the base it subsets is the base it checked, and each sha256 it logs is
of the bytes it wrote. An output path that leads to an input (base.json, the base, its licence, targets.json),
through a link or not, is refused before anything is written.

For each style:
1. The y instance. The weight axis is solved so the n stem meets the target. If the base has an optical-size
   axis and --loc does not fix it, opsz is scanned too, for the o contrast and the H bar closest to the
   targets, among the sizes where the wght axis reaches the stem (else the nearest, with the miss in
   fit-log.json). Every y coordinate comes from this instance, so x-height, bars and thin strokes come from it.
   A later style without a stem of its own takes the first style's location with the wght moved by the
   weight-class difference, and scans no optical size of its own.
2. One x instance per width class. On a width axis, wdth is solved so the class's mean advance meets its
   target, and wght is solved again at that width so the class's stem stays on target. Where the axis runs
   out, the class is scaled horizontally by at most --max-stretch (3 % by default), with the weight solved for
   the stem the stretch will produce. Accented letters and alternates follow their base letter's class.
   Glyphs in no class take the y instance's own x.
3. Assembly. Every location of one variable font has the same points, so each glyph takes x from its class
   instance and y from the y instance. Advances, components and mark anchors follow.
4. Iteration. The class sidebearings are set (space_font.respace), because an advance is ink plus sides.
   Then the assembled font is measured and each class's factor corrected, until every class mean is
   within --tol percent of its target (or the stretch limit is reached, which the log reports).
5. Overlaps are removed (needs skia-pathops), the font is scaled so its cap height per em matches the target
   (or the base's), and the variation tables are dropped.

Hangul (targets.json's `hangul` object, when the targets' scripts have korean). Every Hangul target is stated in
the units of the base's instance at the Hangul location beside what the base draws there: a length at cap 700
against the y instance's cap height, a length per 1000 em against the finished font's em, a ratio by the base's own
H1 face. From them, one transform (hangul_transform): one scale for the whole Hangul, within ±6 %
(fontlib.HANGUL_SCALE_LIMIT), 1 without a length; per class a final x and y scale within ±3 % of it and of each
other (HANGUL_CLASS_LIMIT), a vertical shift to the class's centre height, and an advance that splits its change
evenly between the two sides and moves only the class's mean centre; the compatibility jamo at the one scale alone.
Composites are decomposed first. The weight is one for the whole Hangul, solved from the Hangul stem (a length at
cap 700, else per 1000 em, else the ratio stem_h1) over the transform's H1 scale, the two solved in turn on the
measuring syllables. Without a Latin n stem it sets the y instance, at every location step 1 tries, and the Latin
follows it; with one, the Hangul takes a wght of its own at the y location's other axes. Without a Hangul stem the
Hangul follows the y instance. A later style steps the first style's Hangul location like its y location and keeps
the first style's transform. The whole Hangul moves once, after the Latin is assembled and before step 5, from the
full instance at the Hangul location. fit-log.json records the targets, what the base and the fitted font draw, the
transform and the location under each style's `hangul`, and the style's em_scale.

Output: <DIR>/<Family>-<Style>.fit.ttf and fit-log.json. The fonts still carry the base's names: package.py
renames them. Run space_font.py next.
"""
import argparse
import copy
import io
import math
import os
import statistics as st
import sys
import unicodedata

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontTools.ttLib import TTFont  # noqa: E402
from fontTools.ttLib.scaleUpem import scale_upem  # noqa: E402
from fontTools.varLib import instancer  # noqa: E402

import chain as C  # noqa: E402
import fontlib as L  # noqa: E402
import space_font  # noqa: E402

STEM_CHAR = {"lc": "n", "uc": "H", "figures": "H"}


def parse_loc(s):
    return {k.strip(): float(v) for k, v in (p.split("=") for p in s.split(",") if p.strip())} if s else {}


def subset_path(out_dir):
    # A folder of its own, so a glob over the build folder (build/*.ttf) never picks the subset up as a style.
    return os.path.join(out_dir, "subset", "base.subset.ttf")


def make_subset(files, base, scripts, out_dir):
    """Subset the verified base (its bytes, as read) to the scripts' characters, with its layout closure
    (chain.build_subset, which package.py and check_font.py run again to check it). Returns the subset, from the
    bytes written, and the record fit-log.json keeps of it."""
    import fontTools
    args = C.subset_args(L.charset_unicodes(scripts))
    data = C.build_subset(base.data, args)
    wrote = files.write(subset_path(out_dir), data)
    rec = {"source_sha256": base.sha256, "file": wrote["file"], "sha256": wrote["sha256"], "args": args,
           "fonttools": fontTools.version}
    return TTFont(io.BytesIO(data)), rec


class Base:
    """The variable font (the subset of the approved base), a smaller subset of it for fast solving, and a cache
    of full instances."""

    def __init__(self, font):
        self.vf = font
        self.axes = L.axes_of(self.vf)
        self.small = L.subset_font(self.vf, L.SOLVE_TEXT, layout=False)
        self.cache, self.subsets, self.hangul_small = {}, {}, None

    def clamp(self, loc):
        """Every axis pinned: the ones not given sit at their default, so no variation data survives."""
        return {k: min(max(loc.get(k, de), lo), hi) for k, (lo, de, hi) in self.axes.items()}

    def tiny(self, loc, text=None):
        """A fast instance: only the glyphs `text` needs (all letters and figures by default), no layout."""
        if text is None:
            return L.Face(self.small, self.clamp(loc))
        if text not in self.subsets:
            self.subsets[text] = L.subset_font(self.small, text, layout=False)
        return L.Face(self.subsets[text], self.clamp(loc))

    def hangul(self, loc):
        """A fast instance of the Hangul syllables fontlib measures, with H for the cap height."""
        if self.hangul_small is None:
            self.hangul_small = L.subset_font(self.vf, L.HANGUL_TEXT + "H", layout=False)
        return L.Face(self.hangul_small, self.clamp(loc))

    def full(self, loc):
        key = tuple(sorted((k, round(v, 2)) for k, v in self.clamp(loc).items()))
        if key not in self.cache:
            self.cache[key] = instancer.instantiateVariableFont(copy.deepcopy(self.vf), dict(key), updateFontNames=False)
        return self.cache[key]


def raw_stem(face, ch):
    xh = face.bounds("x")[3]
    cap = face.bounds("H")[3]
    y = xh * 0.5 if ch == "n" else cap * 0.3
    r = face.hspans(ch, y)[0]
    return r[1] - r[0]


def solve_wght(B, loc, ch, target_raw):
    if "wght" not in B.axes:
        return loc
    lo, _, hi = B.axes["wght"]
    w, _ = L.solve_axis(lambda v: B.tiny({**loc, "wght": v}, "nHx"), lambda f: raw_stem(f, ch), target_raw, lo, hi, iters=10)
    return {**loc, "wght": round(w, 2)}


def reach_wght(B, loc, face, measure, target, iters=12):
    """loc with the wght where measure(face(loc at that wght)) meets target, and how far what the base draws there
    misses it: 0 where the wght axis reaches the target at loc, else the wght is the nearer axis end and the miss is
    what is drawn there over the target, minus 1."""
    lo, _, hi = B.axes["wght"]
    thinnest, boldest = (measure(face({**loc, "wght": v})) for v in (lo, hi))
    if target < thinnest:
        return {**loc, "wght": lo}, thinnest / target - 1
    if target > boldest:
        return {**loc, "wght": hi}, boldest / target - 1
    w, _ = L.solve_axis(lambda v: face({**loc, "wght": v}), measure, target, lo, hi, iters=iters)
    return {**loc, "wght": round(w, 2)}, 0.0


def latin_weigh(B, stem_t):
    """weigh(loc) for pick_y: the wght where the n stem meets stem_t (at cap 700, over the location's cap height), and
    the miss where the wght axis does not reach it there."""
    def weigh(loc):
        raw = stem_t * B.tiny(loc, "nHx").bounds("H")[3] / L.CAP
        return reach_wght(B, loc, lambda at: B.tiny(at, "nHx"), lambda f: raw_stem(f, "n"), raw, iters=10)
    return weigh


HANGUL_STEM_LENGTHS = ("cap700", "em1000")  # the units a Hangul stem length is aimed at in, first found first


def hangul_weight_aim(T, cap=None):
    """What the Hangul weight is solved from: (name, target, measure(face)). The stem as a length when a reference
    gave one (at cap 700, else per 1000 em), else the stem over the H1 face height. measure reads the base's stem in
    that unit, and the H1 face it needs, from the same face, so both come from the wght tried. The cap height a length
    is over is the face's own, or `cap` when given: the y instance's, when the Latin has a wght of its own."""
    h = T.get("hangul") or {}
    for unit in HANGUL_STEM_LENGTHS:
        target = L.tagged_value(h.get("stem"), unit)
        if target is None:
            continue
        if not target > 0:
            raise SystemExit(f"targets.json: the Hangul stem {unit} is {target}; a stem length must be above 0. "
                             "Measure the references again.")
        if unit == "cap700":
            def measure(face):
                return L.hangul_stem(face) * L.CAP / (cap or face.bounds("H")[3])
        elif T.get("cap_em"):
            def measure(face):  # the finished em is the cap height over cap_em
                return L.hangul_stem(face) * T["cap_em"] / (cap or face.bounds("H")[3])
        else:
            def measure(face):  # the finished em is the base's
                return L.hangul_stem(face) * 1000 / face.upm
        return f"stem {unit}", target, measure
    ratio = L.tagged_value(h.get("stem_h1"), "ratio")
    if ratio is not None and not ratio > 0:
        raise SystemExit(f"targets.json: the Hangul stem_h1 is {ratio}; it must be above 0. Measure the references again.")
    return ("stem_h1", ratio, L.hangul_stem_h1) if ratio else None


def y_tries(B, fixed, args, tg):
    """The locations the y instance is chosen from: nine optical sizes across the axis when the base has one, --loc
    leaves it free and the targets have a contrast, else the --loc location alone."""
    if "opsz" in B.axes and "opsz" not in fixed and not args.no_contrast and tg.get("contrast"):
        lo, de, hi = B.axes["opsz"]
        return [{**fixed, "opsz": round(lo + (hi - lo) * i / 8, 2)} for i in range(9)]
    return [dict(fixed)]


def pick_y(B, tries, weigh, tg):
    """The y instance. Each location tried takes its wght from weigh(loc), which also returns how far the stem it
    aims at stays from what the base draws there (0 where the wght axis reaches it). The locations that reach it come
    first, and of them the one whose contrast, bar to stem and x-height to cap come closest to the targets wins; when
    none reaches it, the nearest. Returns (location, its measurements, its miss)."""
    best = None
    for loc in tries:
        loc, miss = weigh(loc)
        m = L.measure_face(B.tiny(loc))
        err = sum(((m.get(k) or 0) - tg[k]) ** 2 / s ** 2 for k, s in (("contrast", 0.04), ("bar_stem", 0.06), ("xh_cap", 0.01))
                  if tg.get(k) is not None)
        if best is None or (abs(miss), err) < best[0]:
            best = ((abs(miss), err), loc, m, miss)
    return best[1:]


HANGUL_LENGTHS = ("face_w", "face_h", "cx", "cy", "side", "side_asym", "adv")


def resolve_hangul(B, hloc, T, cap=None):
    """The Hangul targets in the units of the base's instance at hloc, beside what the base draws there, and that
    geometry. A length at cap 700 resolves against `cap`, the y instance's cap height (the face's own when not given),
    and a length per 1000 em against the finished font's em (that cap height over cap_em, or the base's em); finish()
    scales the em uniformly, so both stay true. A ratio never becomes a cap length: a size ratio multiplies the base's
    own H1 face, which keeps the base's Hangul scale."""
    want = T["hangul"]
    face = B.hangul(hloc)
    geo = L.hangul_geometry(face)
    h1 = geo["classes"]["H1"]
    cap = cap or face.bounds("H")[3]
    em = 1000 * cap / T["cap_em"] if T.get("cap_em") else face.upm
    per = {"cap700": cap / L.CAP, "em1000": em / 1000}

    def length(entries, base):
        unit = next((u for u in per if L.tagged_value(entries, u) is not None), None)
        if unit and base is not None:
            return {"target": round(L.tagged_value(entries, unit) * per[unit], 1), "base": round(base, 1), "from": unit}
    out = {"units": {u: round(k, 4) for u, k in per.items()}, "classes": {}}
    for cls, w in want.get("classes", {}).items():
        base = geo["classes"].get(cls)
        if base is None:
            continue
        row = {k: r for k in HANGUL_LENGTHS if (r := length(w.get(k), base.get(k, geo.get(k))))}
        if "face_h" not in row and (r := L.tagged_value(w.get("face_h_h1"), "ratio")):
            row["face_h"] = {"target": round(r * h1["face_h"], 1), "base": round(base["face_h"], 1), "from": "ratio"}
        if "face_w" not in row and "face_h" in row and (r := L.tagged_value(w.get("aspect"), "ratio")):
            row["face_w"] = {"target": round(r * row["face_h"]["target"], 1), "base": round(base["face_w"], 1),
                             "from": "ratio"}
        out["classes"][cls] = row
    for key in ("stem", "adv"):
        if r := length(want.get(key), geo.get(key)):
            out[key] = r
    ratio = L.tagged_value(want.get("stem_h1"), "ratio")
    if ratio and geo["stem"]:
        out["stem_h1"] = {"target": ratio, "got": round(geo["stem"] / h1["face_h"], 4)}
        out.setdefault("stem", {"target": round(ratio * h1["face_h"], 1), "base": round(geo["stem"], 1),
                                "from": "ratio"})
    return out, geo


def class_scales(kx, ky, limit=L.HANGUL_CLASS_LIMIT):
    """A class's x and y scale over the Hangul's one scale, each within 1 ± limit, and x over y within 1 + limit
    either way: a ratio past it moves both toward their geometric mean."""
    kx, ky = (min(max(k, 1 - limit), 1 + limit) for k in (kx, ky))
    if not 1 / (1 + limit) <= kx / ky <= 1 + limit:
        mid, r = (kx * ky) ** 0.5, (1 + limit) ** (0.5 if kx > ky else -0.5)
        kx, ky = (min(max(k, 1 - limit), 1 + limit) for k in (mid * r, mid / r))
    return kx, ky


TRANSFORM_STEP = 10 ** 5  # the transform's scales are logged, and applied, at five decimals


def step_within(v, lo, hi):
    """v at five decimals, the nearest such value within [lo, hi]: rounding never carries it past a limit."""
    lo_q, hi_q = math.ceil(lo * TRANSFORM_STEP) / TRANSFORM_STEP, math.floor(hi * TRANSFORM_STEP) / TRANSFORM_STEP
    return min(max(round(v, 5), lo_q), hi_q)


def class_axes(s, kx, ky, limit=L.HANGUL_CLASS_LIMIT):
    """A class's final x and y scale at five decimals, from its scales over the one scale s (class_scales): each
    within 1 ± limit of s, and the larger within 1 + limit of the smaller."""
    sx = step_within(s * kx, s * (1 - limit), s * (1 + limit))
    sy = step_within(s * ky, max(s * (1 - limit), sx / (1 + limit)), min(s * (1 + limit), sx * (1 + limit)))
    return sx, sy


def hangul_transform(rows, geo):
    """The Hangul's final transform, from the targets resolve_hangul states. One scale for the whole Hangul: the
    geometric mean of target over base of every class's face width and height given as a length, within
    L.HANGUL_SCALE_LIMIT, and 1 when no length was measured. Then per class the final x and y scale (that scale times
    class_scales, at five decimals within the limits: class_axes), the vertical shift that puts the class's mean face
    centre at its target height (cy), what is added to every advance after the scale (adv, per class or font-wide),
    and the horizontal shift that puts the class's mean face centre at its target (cx). A class without a target
    takes the one scale and the font-wide advance. The compatibility jamo take the one scale alone. Every number is
    rounded as logged, the fit applies the logged numbers, and a transform fontlib.hangul_transform_over finds past a
    limit is never logged."""
    sizes = [r[k]["target"] / r[k]["base"] for r in rows["classes"].values() for k in ("face_w", "face_h")
             if k in r and r[k]["from"] != "ratio"]
    wanted = math.exp(st.mean(math.log(v) for v in sizes)) if sizes else 1.0
    s = step_within(wanted, 1 - L.HANGUL_SCALE_LIMIT, 1 + L.HANGUL_SCALE_LIMIT)
    wide = rows["adv"]["target"] - s * rows["adv"]["base"] if "adv" in rows else 0.0
    out = {"scale": s, "scale_wanted": round(wanted, 5), "classes": {},
           "jamo": {"sx": s, "sy": s, "dx": 0.0, "dy": 0.0, "adv_add": 0.0}}
    for cls in L.HANGUL_CLASSES:
        r, g = rows["classes"].get(cls, {}), geo["classes"].get(cls)
        want = [r[k]["target"] / r[k]["base"] / s if k in r else 1.0 for k in ("face_w", "face_h")]
        kx, ky = class_scales(*want)
        sx, sy = class_axes(s, kx, ky)
        add = r["adv"]["target"] - s * r["adv"]["base"] if "adv" in r else wide
        t = {"sx": sx, "sy": sy, "dy": round(r["cy"]["target"] - g["cy"], 2) if "cy" in r else 0.0,
             "adv_add": round(add, 2)}
        if "cx" in r:
            t["dx"] = round(r["cx"]["target"] - g["cx"] - ((s - 1) * g.get("adv", geo.get("adv")) + add) / 2, 2)
        else:
            t["dx"] = 0.0
        if (kx, ky) != tuple(want):
            t["wanted"] = {"sx": round(s * want[0], 5), "sy": round(s * want[1], 5)}
        out["classes"][cls] = t
    if over := L.hangul_transform_over(out):
        raise SystemExit(f"the Hangul transform lies past its limits ({'; '.join(over)}), which fit_font.py never "
                         "writes: this is a bug in hangul_transform")
    return out


def h1_stem_factor(aim, xf):
    """How much the transform multiplies what the aim measures: the H1 x scale for a stem length (ㅣ of 이 니 미 is
    an H1 stroke), the H1 x scale over its y scale for the stem over the H1 face height."""
    h1 = xf["classes"]["H1"]
    return h1["sx"] if aim[0].startswith("stem ") else h1["sx"] / h1["sy"]


def solve_hangul(B, loc, T, aim, cap=None):
    """The Hangul at loc: the targets beside the base there and the transform, and with an aim, the wght solved so
    the stem the transform makes meets it. The transform depends on the face sizes the wght draws and the wght on the
    transform's H1 scales, so the two are solved in turn on the measuring syllables until the wght settles.
    Returns (loc, miss, rows, geo, transform)."""
    rows, geo = resolve_hangul(B, loc, T, cap)
    xf = hangul_transform(rows, geo)
    if aim is None or "wght" not in B.axes:
        return loc, 0.0, rows, geo, xf
    got, miss, last = loc, 0.0, None
    for _ in range(6):
        got, miss = reach_wght(B, loc, B.hangul, aim[2], aim[1] / h1_stem_factor(aim, xf))
        rows, geo = resolve_hangul(B, got, T, cap)
        xf = hangul_transform(rows, geo)
        if last is not None and abs(got["wght"] - last) < 0.5:
            break
        last = got["wght"]
    return got, miss, rows, geo, xf


def class_mean(face, chars):
    have = [c for c in chars if face.has(c)]
    return st.mean(face.adv(c) for c in have) if have else None


def case_of(cls):
    return "figures" if cls == "figures" else cls[:2]


# ------------------------------------------------------------------ glyph membership
def class_map(f):
    """glyph name -> width class, for basic letters, their accented forms and suffixed alternates."""
    letter_class = {c: cls for cls, chars in L.CLASSES.items() for c in chars}
    cmap = f.getBestCmap()
    rev = {}
    for cp, n in sorted(cmap.items(), reverse=True):
        rev[n] = cp
    out = {}
    for name in f.getGlyphOrder():
        stem, _, suf = name.partition(".")
        cp = rev.get(name) or rev.get(stem)
        if cp is None:
            continue
        if suf and any(t in suf for t in ("sc", "c2sc", "sups", "subs", "sinf", "numr", "dnom", "tf", "osf", "case")):
            continue
        ch = chr(cp)
        base = unicodedata.normalize("NFD", ch)[0]
        if base in letter_class:
            out[name] = letter_class[base]
    # Composites built only from members of one class join it.
    glyf = f["glyf"]
    for _ in range(3):
        for name in f.getGlyphOrder():
            g = glyf[name]
            if name not in out and g.isComposite():
                cls = {out.get(c.glyphName) for c in g.components} - {None}
                if len(cls) == 1 and all(out.get(c.glyphName) in cls or _is_mark(f, c.glyphName) for c in g.components):
                    out[name] = cls.pop()
    return out


def _is_mark(f, name):
    gdef = f["GDEF"].table if "GDEF" in f else None
    cd = gdef.GlyphClassDef.classDefs if gdef and gdef.GlyphClassDef else {}
    return cd.get(name) == 3


# ------------------------------------------------------------------ assembly
def glyph_bounds(f, name):
    from fontTools.pens.boundsPen import BoundsPen
    gs = f.getGlyphSet()
    p = BoundsPen(gs)
    gs[name].draw(p)
    return p.bounds


def mix(fy, src, cmap_cls, factor, log):
    """x from each glyph's class instance times the class factor, y from fy. fy's copy is the result."""
    f = copy.deepcopy(fy)
    glyf, hm = f["glyf"], f["hmtx"].metrics
    gy = fy["glyf"]
    from fontTools.pens.boundsPen import BoundsPen
    gs = fy.getGlyphSet()
    centers = {}
    for name in f.getGlyphOrder():
        p = BoundsPen(gs)
        gs[name].draw(p)
        centers[name] = (p.bounds[0] + p.bounds[2]) / 2 if p.bounds else 0
    for name in f.getGlyphOrder():
        cls = cmap_cls.get(name)
        if cls is None:
            continue
        k = factor[cls]
        xs = src[cls]
        gx, g, b = xs["glyf"][name], glyf[name], gy[name]
        if g.isComposite():
            for c, cx, cb in zip(g.components, gx.components, b.components):
                kc = factor.get(cmap_cls.get(c.glyphName), 1.0) if cmap_cls.get(c.glyphName) else 1.0
                c.x = round(cx.x * k + centers[c.glyphName] * (k - kc))
                c.y = cb.y
        elif g.numberOfContours > 0:
            if len(gx.coordinates) != len(b.coordinates):
                raise SystemExit(f"{name}: instances are not point-compatible")
            g.coordinates = type(g.coordinates)([(round(px[0] * k), py[1]) for px, py in zip(gx.coordinates, b.coordinates)])
        hm[name] = (round(xs["hmtx"].metrics[name][0] * k), hm[name][1])
    # Mark-to-base and mark-to-ligature anchors on moved glyphs: x from their class instance, times the factor.
    n = 0
    if "GPOS" in f:
        for cls, xs in src.items():
            k = factor[cls]
            for lk, lks in zip(f["GPOS"].table.LookupList.Lookup, xs["GPOS"].table.LookupList.Lookup):
                for s1, s2 in zip(lk.SubTable, lks.SubTable):
                    a = s1.ExtSubTable if lk.LookupType == 9 else s1
                    b = s2.ExtSubTable if lk.LookupType == 9 else s2
                    kind = type(a).__name__
                    if kind == "MarkBasePos":
                        for gname, rec, recs in zip(a.BaseCoverage.glyphs, a.BaseArray.BaseRecord, b.BaseArray.BaseRecord):
                            if cmap_cls.get(gname) == cls:
                                for an, ans in zip(rec.BaseAnchor, recs.BaseAnchor):
                                    if an is not None and ans is not None:
                                        an.XCoordinate = round(ans.XCoordinate * k)
                                        n += 1
                    elif kind == "MarkLigPos":
                        for gname, lig, ligs in zip(a.LigatureCoverage.glyphs, a.LigatureArray.LigatureAttach,
                                                    b.LigatureArray.LigatureAttach):
                            if cmap_cls.get(gname) == cls:
                                for comp, comps in zip(lig.ComponentRecord, ligs.ComponentRecord):
                                    for an, ans in zip(comp.LigatureAnchor, comps.LigatureAnchor):
                                        if an is not None and ans is not None:
                                            an.XCoordinate = round(ans.XCoordinate * k)
                                            n += 1
    log.append(f"assembled: {len(cmap_cls)} glyphs in width classes, {n} base anchors moved with them")
    return f


def fix_lsb(f):
    glyf, hm = f["glyf"], f["hmtx"].metrics
    for name in f.getGlyphOrder():
        g = glyf[name]
        g.recalcBounds(glyf)
        hm[name] = (hm[name][0], g.xMin if g.numberOfContours != 0 else 0)


def finish(f, cap_em, vm_target):
    """Remove overlaps, scale to the target cap height per em, set vertical metrics, drop variation tables. Returns
    the notes, the factor the em scale multiplied every length by, and whether the overlaps were removed."""
    notes, removed = [], False
    try:
        from fontTools.ttLib.removeOverlaps import removeOverlaps
        removeOverlaps(f)
        notes.append("overlaps removed")
        removed = True
    except ImportError:
        notes.append("skia-pathops missing: overlaps kept (the OVERLAP_SIMPLE flag still makes them render)")
    cap = glyph_bounds(f, f.getBestCmap()[ord("H")])[3]
    if cap_em:
        f["head"].unitsPerEm = round(1000 * cap / cap_em)
    em_scale = 1000 / f["head"].unitsPerEm
    scale_upem(f, 1000)
    notes.append(f"scaled to 1000 upm, cap height {round(glyph_bounds(f, f.getBestCmap()[ord('H')])[3], 1)}")
    for t in ("STAT", "MVAR", "HVAR", "VVAR", "avar", "fvar", "gvar", "cvar", "DSIG"):
        if t in f:
            del f[t]
    fix_lsb(f)
    os2, hh = f["OS/2"], f["hhea"]
    glyf = f["glyf"]
    ymax = max((glyf[n].yMax for n in f.getGlyphOrder() if glyf[n].numberOfContours != 0), default=0)
    ymin = min((glyf[n].yMin for n in f.getGlyphOrder() if glyf[n].numberOfContours != 0), default=0)
    if vm_target:
        k = 1000 / vm_target["upm"]
        a, d, g = (round(v * k) for v in vm_target["typo"])
        hh.ascent, hh.descent, hh.lineGap = a, d, g
        os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = a, d, g
        os2.fsSelection |= 1 << 7
        notes.append(f"line box from the reference: {a} / {d} / {g}")
    os2.usWinAscent = max(os2.usWinAscent, ymax, hh.ascent)
    os2.usWinDescent = max(os2.usWinDescent, -ymin, -hh.descent)
    hh.numberOfHMetrics = len(f["hmtx"].metrics)
    os2.recalcAvgCharWidth(f)
    cm = f.getBestCmap()
    os2.sxHeight = round(glyph_bounds(f, cm[ord("x")])[3])
    os2.sCapHeight = round(glyph_bounds(f, cm[ord("H")])[3])
    return notes, em_scale, removed


def locate_first(B, T, args):
    """Where the first style sits; every later style steps from it. The first style's n stem, when it has one, sets
    the wght at each location the y instance is chosen from; else the Hangul stem does, after the Hangul transform,
    and the Latin takes that wght. With both, the Hangul solves a wght of its own at the y location's other axes.
    Without a Hangul stem the Hangul follows the y location. Returns the y location, its measurements and miss, what
    the weight came from, and with Hangul targets the Hangul location, its miss and the transform."""
    tg, first = T["targets"], T["styles"][0]
    tries = y_tries(B, parse_loc(args.loc), args, tg)
    aim = hangul_weight_aim(T)
    if "wght" not in B.axes:
        at = dict(zip(("y", "ym", "miss"), pick_y(B, tries, lambda loc: (loc, 0.0), tg)),
                  weight_from="the base, which has no weight axis")
    elif first.get("n_stem"):
        at = dict(zip(("y", "ym", "miss"), pick_y(B, tries, latin_weigh(B, first["n_stem"]), tg)), weight_from="n_stem")
    elif aim:
        at = dict(zip(("y", "ym", "miss"), pick_y(B, tries, lambda loc: solve_hangul(B, loc, T, aim)[:2], tg)),
                  weight_from=aim[0])
    else:
        raise SystemExit(f"{first['name']}: targets.json has neither a Latin n stem nor a Hangul stem (stem or "
                         "stem_h1) to solve the weight from. Measure a reference with n, or with 이, 니 and 미.")
    at["aim"] = aim
    if T.get("hangul"):
        cap = B.tiny(at["y"], "nHx").bounds("H")[3]
        if aim and at["weight_from"] == "n_stem":
            rest = {k: v for k, v in at["y"].items() if k != "wght"}
            at["hangul"], at["hangul_miss"], _, _, at["transform"] = solve_hangul(B, rest, T, hangul_weight_aim(T, cap),
                                                                                  cap)
            at["hangul_weight_from"] = aim[0]
        else:
            at["hangul"], at["hangul_miss"] = at["y"], at["miss"] if aim and at["weight_from"] == aim[0] else 0.0
            at["transform"] = hangul_transform(*resolve_hangul(B, at["y"], T, cap))
            at["hangul_weight_from"] = at["weight_from"]
    return at


def stepped(B, loc, step):
    """loc with its wght moved by step and clamped to the axis."""
    if "wght" not in B.axes:
        return dict(loc)
    lo, _, hi = B.axes["wght"]
    return {**loc, "wght": round(min(max(loc["wght"] + step, lo), hi), 2)}


def locate(B, T, args, style, first_at, log):
    """This style's y location, its measurements, its miss, the n stem the Latin is fitted to there, what the weight
    came from, and with Hangul targets where the Hangul sits: {"location", "weight_from"}, and "stepped_from" for a
    later style. The first style takes locate_first's. A later style with an n stem of its own (--style
    Medium:500:88) is solved like the first; any other takes the first style's y location, its optical size
    included, with the wght moved by the weight-class difference (Bold 700 after Regular 400: +300), and scans no
    optical size of its own, so the weights stay as far apart on the axis as their classes. The Hangul location
    steps from the first style's Hangul location the same way, unless the Hangul follows the y instance (no Hangul
    stem target), and then its weight comes from wherever the y's did."""
    tg, first, name = T["targets"], T["styles"][0], style["name"]
    step = style["weight"] - first["weight"]
    aim = first_at["aim"]
    what = "n stem" if first_at["weight_from"] == "n_stem" else f"Hangul {aim[0]} {aim[1]:.4g}" if aim else "base"
    stem_t, weight_from = style.get("n_stem"), first_at["weight_from"]
    if style is first:
        yloc, ym, miss = first_at["y"], first_at["ym"], first_at["miss"]
        stem_t = first.get("n_stem")
        if aim and weight_from == aim[0]:
            log.append(f"{name}: wght solved from the {what}, after the Hangul transform, at each location the y "
                       "instance is chosen from")
        if miss:
            drawn = (stem_t or aim[1]) * (1 + miss)
            log.append(f"{name}: the wght axis reaches the {what if stem_t is None else f'n stem {stem_t:.1f}'} at no "
                       f"location tried; the nearest, {yloc}, draws {drawn:.4g} ({miss * 100:+.1f} %)")
    elif stem_t is not None and "wght" in B.axes:
        yloc, ym, miss = pick_y(B, y_tries(B, parse_loc(args.loc), args, tg), latin_weigh(B, stem_t), tg)
        weight_from = "n_stem"
        if miss:
            log.append(f"{name}: the wght axis reaches the n stem {stem_t:.1f} at no location tried; the nearest, "
                       f"{yloc}, draws {stem_t * (1 + miss):.4g} ({miss * 100:+.1f} %)")
    else:
        yloc, miss = stepped(B, first_at["y"], step), 0.0
        ym = L.measure_face(B.tiny(yloc))
        weight_from += ", stepped from the first style"
        log.append(f"{name}: the first style's y instance sits at {first_at['y']} (solved from the {what}), this one "
                   f"{step:+d} from it at {yloc}")
    if stem_t is None:  # the Latin keeps the n stem the base draws at the y location
        stem_t = L.stem_cap700(B.tiny(yloc, "nHx"))
        log.append(f"{name}: n stem target {stem_t:.1f}, the base's at the y instance")
    else:
        log.append(f"{name}: n stem target {stem_t:.1f}")
    hangul_at = None
    if "hangul" in first_at:
        if not aim:
            hangul_at = {"location": yloc, "weight_from": weight_from}
        elif style is first:
            hangul_at = {"location": first_at["hangul"], "weight_from": first_at["hangul_weight_from"]}
        else:
            hangul_at = {"location": stepped(B, first_at["hangul"], step),
                         "weight_from": first_at["hangul_weight_from"] + ", stepped from the first style's Hangul location",
                         "stepped_from": {"style": first["name"], "location": first_at["hangul"]}}
    return yloc, ym, miss, stem_t, weight_from, hangul_at


def fit_hangul(B, T, f, fy, yloc, hloc, cap_y, first_at, log):
    """Move every Hangul glyph of the assembled font f by the first style's transform, from the base at hloc (fy,
    the y instance, when the Hangul follows it), then read the measuring syllables of f again. Returns fit-log.json's
    record: each target beside what the base draws at hloc and what the fitted font draws (before finish() scales
    the em), the transform, and how many glyphs moved."""
    xf = first_at["transform"]
    rows, _ = resolve_hangul(B, hloc, T, cap_y)
    moved, composites = L.transform_hangul(f, fy if hloc == yloc else B.full(hloc), xf)
    got = L.hangul_geometry(L.Face(f))
    for cls, row in rows["classes"].items():
        g = got["classes"].get(cls, {})
        for key, r in row.items():
            if g.get(key, got.get(key)) is not None:
                r["fitted"] = round(g.get(key, got.get(key)), 1)
    for key in ("stem", "adv"):
        if key in rows and got.get(key) is not None:
            rows[key]["fitted"] = round(got[key], 1)
    if "stem_h1" in rows and got["stem"] and "H1" in got["classes"]:
        rows["stem_h1"]["fitted"] = round(got["stem"] / got["classes"]["H1"]["face_h"], 4)
    limited = [c for c, t in xf["classes"].items() if "wanted" in t]
    log.append(f"Hangul: {len(moved)} glyphs from {hloc}, {composites} composites decomposed first; scale {xf['scale']}"
               + (f" (wanted {xf['scale_wanted']})" if xf["scale"] != xf["scale_wanted"] else "")
               + (f"; at the class limit: {', '.join(limited)}" if limited else ""))
    return {"location": hloc, **rows, "transform": xf, "glyphs_moved": len(moved), "composites_decomposed": composites}


def fit_style(B, T, style, args, log, first_at):
    tg = T["targets"]
    yloc, ym, missed, stem_t, weight_from, hangul_at = locate(B, T, args, style, first_at, log)
    log.append(f"{style['name']}: y instance {yloc}: contrast {ym['contrast']} (target {tg.get('contrast')}), "
               f"bar/stem {ym['bar_stem']} (target {tg.get('bar_stem')}), x-height/cap {ym['xh_cap']} (target {tg.get('xh_cap')})")
    cap_y = B.tiny(yloc, "nHx").bounds("H")[3]
    to_cap = L.CAP / cap_y  # raw units of the y instance -> cap-normalised
    # 2. x instance per class
    xloc, factor, aim = {}, {}, {}
    widths = tg.get("widths", {})
    H_t = (tg.get("H_stem") or stem_t * 1.05) * stem_t / (tg.get("n_stem") or stem_t)
    base_loc = {k: v for k, v in yloc.items() if k != "wght"}

    def solve_class(cls, target):
        """Location and factor that give this class `target` mean advance (raw units of the y instance)."""
        chars = L.CLASSES[cls]
        ch = STEM_CHAR[case_of(cls)]
        stem_raw = (stem_t if ch == "n" else H_t) / to_cap

        def mean_at(wd, s=1.0):
            l2 = solve_wght(B, {**base_loc, "wdth": wd} if "wdth" in B.axes else base_loc, ch, stem_raw / s)
            return class_mean(B.tiny(l2, chars + "nHx"), chars) * s, l2
        if "wdth" in B.axes:
            lo, de, hi = B.axes["wdth"]
            wd, _ = L.solve_axis(lambda v: v, lambda v: mean_at(v)[0], target, lo, hi, iters=9)
            got, l2 = mean_at(wd)
        else:
            got, l2 = mean_at(None)
        s = min(max(target / got, 1 - args.max_stretch), 1 + args.max_stretch)
        if abs(s - 1) > 1e-4:
            _, l2 = mean_at(l2.get("wdth"), s)
        return l2, round(s, 4)

    for cls in L.CLASSES:
        if cls not in widths:
            xloc[cls], factor[cls] = dict(yloc), 1.0
            continue
        aim[cls] = widths[cls] / to_cap
        xloc[cls], factor[cls] = solve_class(cls, aim[cls])
    # 3 and 4. assemble, measure, correct the factors
    fy = B.full(yloc)
    cls_of = class_map(fy)
    src = {cls: B.full(xloc[cls]) for cls in L.CLASSES}
    hist = []
    for it in range(args.iters):
        f = mix(fy, src, cls_of, factor, [])
        if tg.get("sides") or tg.get("rhythm"):
            space_font.respace(f, tg, {})  # widths include the sides, so set the sides before measuring widths
        face = L.Face(f)
        k = L.CAP / face.bounds("H")[3]
        errs = {}
        for cls, chars in L.CLASSES.items():
            if cls in widths:
                errs[cls] = class_mean(face, chars) * k / widths[cls] - 1
        hist.append({"iteration": it + 1, "factor": dict(factor),
                     "error_pct": {c: round(e * 100, 3) for c, e in errs.items()}})
        if all(abs(e) * 100 <= args.tol for e in errs.values()):
            break
        for cls, e in errs.items():
            new = factor[cls] / (1 + e)
            if abs(new - 1) > args.max_stretch and "wdth" in B.axes and abs(e) * 100 > args.tol:
                # The sidebearing moves pushed this class past the stretch limit: aim the width axis further
                # and take a new instance, instead of stretching.
                aim[cls] /= (1 + e)
                xloc[cls], factor[cls] = solve_class(cls, aim[cls])
                src[cls] = B.full(xloc[cls])
                continue
            factor[cls] = round(min(max(new, 1 - args.max_stretch), 1 + args.max_stretch), 4)
    alog = []
    f = mix(fy, src, cls_of, factor, alog)
    if tg.get("sides") or tg.get("rhythm"):
        slog = {}
        space_font.respace(f, tg, slog)
        alog.append(f"class sidebearings set inside the fit: moves {slog.get('side_moves')}")
    hangul = fit_hangul(B, T, f, fy, yloc, hangul_at["location"], cap_y, first_at, alog) if hangul_at else None
    log.extend(alog)
    notes, em_scale, removed = finish(f, T.get("cap_em"), T.get("vmetrics"))
    log.extend(notes)
    stuck = [c for c, e in hist[-1]["error_pct"].items() if abs(e) > args.tol]
    info = {"style": style, "n_stem_target": round(stem_t, 1), "y_location": yloc, "x_locations": xloc,
            "factors": factor, "iterations": hist, "stretch_limit_hit": stuck,
            "classes_measured": {c: L.CLASSES[c] for c in widths}, "em_scale": round(em_scale, 6),
            "overlaps_removed": removed}
    if missed and weight_from.startswith("n_stem"):
        info["weight_missed_pct"] = round(missed * 100, 1)
    if hangul:
        hangul.update({k: v for k, v in hangul_at.items() if k != "location"})
        if style is T["styles"][0] and first_at["hangul_miss"]:
            hangul["weight_missed_pct"] = round(first_at["hangul_miss"] * 100, 1)
        info["hangul"] = hangul
    return f, info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base", help="the approved base font, the file base.json names")
    ap.add_argument("targets")
    ap.add_argument("--base-json", help="base.json from record_base.py (required)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--loc", default="", help="axes to hold fixed, e.g. opsz=14,GRAD=0")
    ap.add_argument("--style", action="append", help="build only these styles (names from targets.json)")
    ap.add_argument("--max-stretch", type=float, default=0.03)
    ap.add_argument("--tol", type=float, default=0.3, help="class mean advance error allowed, percent")
    ap.add_argument("--iters", type=int, default=6)
    ap.add_argument("--no-contrast", action="store_true", help="do not scan opsz for contrast")
    a = ap.parse_args()
    files = C.Files()
    approved = C.load_base(files, a.base_json)
    base = C.require_base_font(files, a.base, approved, a.base_json)
    targets = files.read(a.targets, "targets.json")
    T = targets.json("targets.json")
    try:
        L.charset_unicodes(T.get("scripts", ["latin"]))
    except ValueError as e:
        raise C.Refused(f"{a.targets}: {e}")
    C.require_pinned_base(files, approved, T, a.targets)
    hangul_weight_aim(T)  # a stem target that cannot be solved is refused before anything is written
    fam = T["family"].replace(" ", "")
    styles = [s for s in T["styles"] if not a.style or s["name"] in a.style]
    style_paths = [os.path.join(a.out_dir, f"{fam}-{s['name']}.fit.ttf") for s in styles]
    log_path = os.path.join(a.out_dir, "fit-log.json")
    for p in [subset_path(a.out_dir), *style_paths, log_path]:
        files.check_output(p)
    sub, sub_rec = make_subset(files, base, T.get("scripts", ["latin"]), a.out_dir)
    print(f"subset of the approved base: {len(sub.getGlyphOrder())} glyphs, {sub_rec['file']}")
    B = Base(sub)
    if T.get("hangul") and not all(sub.getBestCmap().get(ord(c)) for c in L.HANGUL_CLASSES["H1"] + L.HANGUL_STEM):
        raise C.Refused(f"{a.targets} has Hangul targets, and the subset of the base lacks the H1 syllables "
                        f"{L.HANGUL_CLASSES['H1']}: the targets' scripts need korean, and the base needs Hangul")
    out = {"base": os.path.basename(a.base), "base_axes": B.axes, "targets": os.path.basename(a.targets),
           "subset": sub_rec, "styles": []}
    written = []
    first_at = locate_first(B, T, a)
    for style, p in zip(styles, style_paths):
        log = []
        f, info = fit_style(B, T, style, a, log, first_at)
        # a plain TrueType file, whatever container the instances came through
        written.append(files.write(p, C.font_bytes(f)))
        info["file"] = os.path.basename(p)
        info["log"] = log
        out["styles"].append(info)
        print(f"{style['name']}: wrote {p}")
        for line in log:
            print("  " + line)
        last = info["iterations"][-1]
        print(f"  width fit after {last['iteration']} pass(es), error % by class: {last['error_pct']}")
        print(f"  factors: {info['factors']}")
        if "hangul" in info:
            h = info["hangul"]
            stem = h.get("stem") or {}
            print(f"  hangul at {h['location']}: weight from {h['weight_from']}"
                  + (f", which no location tried reaches ({h['weight_missed_pct']:+.1f} %)"
                     if "weight_missed_pct" in h else "")
                  + (f"; stem {stem.get('fitted')} (target {stem['target']} from {stem['from']}, base {stem['base']})"
                     if stem else ""))
            xf = h["transform"]
            print(f"    scale {xf['scale']}" + (f" (wanted {xf['scale_wanted']})" if xf["scale"] != xf["scale_wanted"]
                                                else ""))
            for cls, row in h["classes"].items():
                t = xf["classes"][cls]
                print(f"    {cls}: x {t['sx']}, y {t['sy']}" + (f" (wanted {t['wanted']['sx']}, {t['wanted']['sy']})"
                                                               if "wanted" in t else "") + "; "
                      + ", ".join(f"{k} {r['target']} from {r['from']} (base {r['base']}, fitted {r.get('fitted')})"
                                  for k, r in row.items() if k in ("face_w", "face_h")))
        if info["stretch_limit_hit"]:
            print(f"  stretch limit reached for {info['stretch_limit_hit']}: the base cannot reach these widths "
                  f"within {a.max_stretch * 100:.0f} %. Say so, or pick a base with a width axis.")
    out["chain"] = C.make_chain(approved.sha, [base.entry()], written, targets.entry())
    files.write_json(log_path, out)


if __name__ == "__main__":
    main()

# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "brotli", "uharfbuzz", "numpy", "pillow", "skia-pathops"]
# ///
"""Gate a built font against targets.json, its open base, and the licence rules. Exit 1 on any failure.

  uv run check_font.py dist/ttf/*.ttf --targets targets.json --base-json base.json
      --fit-log build/fit-log.json --space-log build/*.space-log.json --package-log dist/package-log.json
      [--package dist/] [--reference ref.ttf | --reference-image shot.png --reference-text "line|line"]
      [--out-dir DIR]

First the chain, which refuses to go on (exit 1) when any link is broken. chain.verify_build is the check
package.py ran: base.json matches the base and its OFL text; every log was made from that base.json; fit_font.py
read only the base and this targets.json, and its subset is what the base gives again with the recorded arguments,
byte for byte (the glyph order and character map gates compare with that remade subset); space_font.py read only
fitted fonts and this targets.json. Then the package log: it records this targets.json and exactly these fit and
space logs, package.py took only spaced fonts, every font checked here is one of its outputs, and every output it
lists (each TTF and WOFF2) is in the package log's folder with the sha256 it records. Each input is read once
(chain.Files), so the gates run on the bytes the chain checked. That structure is the provenance guarantee: the
build steps never opened a reference font. What it cannot rule out: one agent that writes both the fonts and every
log by hand, consistently. The chain shows the files agree with each other and with the approved base, not who made
them.

Then the gates, each PASS, FAIL, INFO or NOT RUN, with the number behind it:
- metrics: x-height to cap, n stem, contrast, within the targets' tolerances (targets.json "tolerances").
- widths: every class mean advance, and the shaped paragraph when the targets came from a file.
- spacing: straight and round sidebearing means.
- kerning: every pair of letters, figures and punctuation, shaped. The smallest ink gap must clear min_gap.
- coverage: every character the targets' scripts need (for korean the 2,350 syllables of KS X 1001), and the
  counts of what fontlib.COVERAGE_REPORTED adds (the modern syllables, the compatibility jamo), not gated.
- provenance: glyph order and character map equal the subset's; every glyph is within 3 % of the height and
  40 % of the width of the subset's glyph at the fit's y location (y comes from there, x from the width classes).
  The Hangul a fit moved is checked against fit-log.json instead (gate_hangul): with Hangul targets, every style must
  have a Hangul record; its transform within the limits; every Hangul glyph a simple glyph whose points are, within
  1 unit each, the ones the build makes from the subset's glyph at the fit's Hangul location (the logged transform,
  overlap removal, the em scale and the track, step by step).
- hangul: per weight, the Hangul stem over the n stem against the reference's ratio (±0.05) and every class's face
  centre height against its target (±15 at cap 700), each NOT RUN without a reference that measured it; the
  vertical strokes of the classes and the Hangul ink that leaves its advance, reported.
  With --reference files, a diagnostic only: our outlines that have curves or at least 16 points are compared
  with the reference's, and any that share point structure and shape are listed (INFO). A CFF reference cannot
  be compared and is reported NOT RUN.
- validity: a ttx round trip, win metrics that cover every glyph, and fontbakery (NOT RUN when not installed).
- licence: OFL notice and URL in the name table, no trademark record, a new family name that is not the base's
  name or a Reserved Font Name, and no base family name in any table but the copyright line. With --package,
  OFL.txt and FONTLOG.txt must be there.
Renders: <out-dir>/overlay-<style>-<size>.png sets the reference and the font on the same lines at a text and
a display size, reference in red, ours in blue, overlap black, with that legend drawn above. With a screenshot
reference, the two are stacked at the same cap height instead (a screenshot of Hangul alone: the same H1 face height).

<out-dir>/check-report.json holds the approved base (file name, full sha256, source, licence and its sha256),
the approval as base.json records it (question, answer and decision, verbatim), the package outputs verified
above ("package": {"outputs": [{"file", "sha256"}]}, which font_book.py matches the fonts it copies against), and
every gate row. A report or render path that leads to an input, through a link or not, is refused.
"""
import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402

import chain as C  # noqa: E402
import fontlib as L  # noqa: E402

COVERAGE = L.COVERAGE
MIN_POINTS = 16  # a straight-sided outline with fewer points (a bar, a box, an L) matches too much to mean anything
HARMONY_RATIO = 0.05  # how far a weight's Hangul stem over its n stem may land from the reference's ratio
HARMONY_CENTRE = 15  # how far, at cap 700, a Hangul class's face centre may land from its target height
TEXT_SAMPLE = "Hamburgefonstiv quick brown 1234"
DISPLAY_SAMPLE = "Rag Gold"


class Gates:
    def __init__(self):
        self.rows = []

    def add(self, group, name, ok, detail, state=None):
        state = state or ("INFO" if ok is None else "PASS" if ok else "FAIL")
        self.rows.append((group, name, state, detail))

    def failed(self):
        return [r for r in self.rows if r[2] == "FAIL"]


def gate_metrics(G, m, T, style):
    tg, tol = T["targets"], T["tolerances"]
    stem_t = style.get("n_stem") if style else tg.get("n_stem")
    if not stem_t:
        G.add("metrics", "n stem", None, f"{m['n_stem']}, no target for this style (the fit log has the one it used)")
    elif m.get("n_stem"):
        G.add("metrics", "n stem", abs(m["n_stem"] - stem_t) <= tol["stem"], f"{m['n_stem']} vs {stem_t:.1f}, ±{tol['stem']}")
    if tg.get("xh") is not None:
        G.add("metrics", "x-height", abs(m["xh"] - tg["xh"]) <= tol["xh"], f"{m['xh']} vs {tg['xh']}, ±{tol['xh']} (cap 700)")
    if tg.get("contrast") is not None and m.get("contrast") is not None:
        G.add("metrics", "contrast o thin / o side", abs(m["contrast"] - tg["contrast"]) <= tol["contrast"],
              f"{m['contrast']} vs {tg['contrast']}, ±{tol['contrast']}")
    for k in ("asc", "desc", "H_bar", "bar_stem", "serif_ext", "serif_tip", "overshoot_lc"):
        if tg.get(k) is not None and m.get(k) is not None:
            G.add("metrics", k, None, f"{m[k]} vs {tg[k]}")


def gate_widths(G, m, T, first_style):
    tg, tol = T["targets"], T["tolerances"]
    for cls, v in (tg.get("widths") or {}).items():
        got = m["widths"].get(cls)
        if got is None:
            continue
        e = got / v - 1
        G.add("widths", cls, abs(e) * 100 <= tol["width_pct"], f"{got} vs {v}, {e * 100:+.2f}%")
    if first_style and tg.get("para") and m.get("para") and T.get("cap_em"):
        e = m["para"] / tg["para"] - 1
        G.add("widths", "paragraph, shaped", abs(e) * 100 <= tol["para_pct"], f"{e * 100:+.2f}%, ±{tol['para_pct']}%")
    for cls, v in (tg.get("sides") or {}).items():
        got = m["sides"].get(cls)
        if got is not None and first_style:
            G.add("spacing", f"{cls} side mean", abs(got - v) <= tol["side"], f"{got} vs {v}, ±{tol['side']}")


def gate_kerning(G, face, min_gap):
    """Every guarded pair as HarfBuzz sets it (fontlib.Face.pair_gap, the reading space_font.py's guard fixes)."""
    import space_font as S
    chars = [c for c in S.GUARD_CHARS if ord(c) in face.cmap]
    worst = []
    for a in chars:
        if a == "f":
            continue
        for b in chars:
            g = face.pair_gap(a + b)
            if g is not None:
                worst.append((g.gap, a + b))
    worst.sort()
    bad = [w for w in worst if w[0] < min_gap - 1]
    G.add("kerning", "collisions", not bad, f"{len(bad)} pairs under {min_gap} units; closest " +
          ", ".join(f"{p} {g:.0f}" for g, p in worst[:6]))


def gate_coverage(G, f, scripts):
    """Every character of each script's COVERAGE list, gated; the characters COVERAGE_REPORTED adds, counted."""
    cm = f.getBestCmap()
    for s in scripts:
        need = COVERAGE.get(s)
        if need is None:
            G.add("coverage", s, None, "no character list for this script in check_font.py")
            continue
        miss = [c for c in need if ord(c) not in cm]
        G.add("coverage", s, not miss, (f"{L.COVERAGE_NAMES[s]}: " if s in L.COVERAGE_NAMES else "")
              + f"{len(need) - len(miss)} of {len(need)}" + (f", missing {''.join(miss[:30])}" if miss else ""))
        for what, chars in L.COVERAGE_REPORTED.get(s, {}).items():
            G.add("coverage", f"{s}, {what}", None, f"{sum(ord(c) in cm for c in chars)} of {len(chars)}")


HANGUL_POINT_TOL = 1  # units at 1000 per em a Hangul point or advance may land from where the build puts it
OUTLINE_GATE = "every Hangul glyph where the logged transform puts it"


def built_hangul(inst, fitted, track):
    """Every Hangul glyph the way the build makes it from the base's instance at the fit's Hangul location, step by
    step as fit_font.py and space_font.py do: the logged transform (fontlib.transform_hangul, the fit's own function),
    overlaps removed when the fit removed them, the em scaled as finish() scales it (fontTools' scale_upem: every
    coordinate and advance times the new em over the old, rounded once), and the track added to both sides of every
    glyph with ink. name -> (points, contour ends, on-curve bits, advance)."""
    import copy
    from fontTools.misc.roundTools import otRound
    exp = copy.deepcopy(inst)
    members, _ = L.transform_hangul(exp, inst, fitted["hangul"]["transform"])
    if fitted.get("overlaps_removed", True):
        from fontTools.ttLib.removeOverlaps import removeOverlaps  # needs skia-pathops, as the fit did
        removeOverlaps(exp, glyphNames=list(members))
    k = 1000 / round(1000 / fitted["em_scale"])  # em_scale is 1000 over the em finish() scaled, at six decimals
    glyf, hm = exp["glyf"], exp["hmtx"].metrics
    out = {}
    for name in members:
        g, adv = glyf[name], otRound(hm[name][0] * k)
        if g.numberOfContours > 0:
            ink = track if adv else 0
            out[name] = ([(otRound(x * k) + ink, otRound(y * k)) for x, y in g.coordinates], list(g.endPtsOfContours),
                         [f & 1 for f in g.flags], adv + 2 * ink)
        else:
            out[name] = ([], [], [], adv)
    return out


def outline_far(g, want, adv):
    """How a fitted Hangul glyph g (and its advance) differs from the glyph the build makes (built_hangul): a
    composite, another point structure, or a point or the advance more than HANGUL_POINT_TOL units away. Returns
    (what is wrong or None, the largest distance of a point or the advance)."""
    pts, ends, on, want_adv = want
    if g.isComposite():
        return "is a composite", None
    got = list(g.coordinates) if g.numberOfContours > 0 else []
    got_ends = list(g.endPtsOfContours) if got else []
    if (got_ends, [f & 1 for f in g.flags] if got else []) != (ends, on):
        return (f"has {len(got_ends)} contours and {len(got)} points, the build makes {len(ends)} and {len(pts)}",
                None)
    dist = max([abs(adv - want_adv)] + [max(abs(a - c), abs(b - d)) for (a, b), (c, d) in zip(got, pts)])
    if dist > HANGUL_POINT_TOL:
        far = next(((i, p, q) for i, (p, q) in enumerate(zip(got, pts))
                    if max(abs(p[0] - q[0]), abs(p[1] - q[1])) > HANGUL_POINT_TOL), None)
        return (f"point {far[0]} at {tuple(far[1])}, the build puts it at {far[2]}" if far
                else f"advance {adv}, the build gives {want_adv}"), dist
    return None, dist


def gate_hangul(G, f, base, fitted, track=0):
    """The Hangul against the fit log's transform. `base` is the subset fit_font.py fitted from, `fitted` the fit
    log's record of this style, `track` the units space_font.py added to each side of every glyph with ink. The
    transform must lie within the limits (fontlib.hangul_transform_over, the check the fit ran), and every Hangul
    glyph must be the glyph the build makes from the base at the fit's Hangul location (built_hangul): a simple glyph
    with the same contours and points, each point and the advance within HANGUL_POINT_TOL units. Anything else moved
    it, inside the ink box or not. Returns the base's instance at that location."""
    import copy
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.varLib import instancer
    h = fitted.get("hangul")
    if not h:
        return
    xf = h["transform"]
    over = L.hangul_transform_over(xf)
    G.add("provenance", "Hangul transform within the limits", not over,
          f"scale {xf['scale']} (±{L.HANGUL_SCALE_LIMIT:.0%}); every class's x and y within ±{L.HANGUL_CLASS_LIMIT:.0%} "
          f"of it and its larger axis within {L.HANGUL_CLASS_LIMIT:.0%} of its smaller; the jamo at it, unmoved"
          + (": " + ", ".join(over) if over else ""))
    inst = instancer.instantiateVariableFont(copy.deepcopy(base), h["location"], updateFontNames=False)
    try:
        built = built_hangul(inst, fitted, track)
    except (ImportError, KeyError) as e:  # skia-pathops missing here, or a transform without a class
        G.add("provenance", OUTLINE_GATE, False, f"the Hangul cannot be made again as the fit made it: {e!r}")
        return inst
    igs, ihm, ogs, oglyf, ohm = inst.getGlyphSet(), inst["hmtx"].metrics, f.getGlyphSet(), f["glyf"], f["hmtx"].metrics
    far, worst, sides, k = [], 0, {"fitted": [], "base": []}, fitted["em_scale"]
    for name, want in built.items():
        problem, dist = outline_far(oglyf[name], want, ohm[name][0])
        worst = max(worst, dist or 0)
        if problem:
            far.append(f"{name} {problem}")
        p, q = BoundsPen(igs), BoundsPen(ogs)
        igs[name].draw(p)
        ogs[name].draw(q)
        if p.bounds and q.bounds:
            sides["fitted"].append(min(q.bounds[0], ohm[name][0] - q.bounds[2]))
            sides["base"].append(min(p.bounds[0], ihm[name][0] - p.bounds[2]) * k)
    G.add("provenance", OUTLINE_GATE, not far,
          f"{len(built) - len(far)} of {len(built)} simple, with the points the base at {h['location']} gets from the "
          f"fit log's transform, overlap removal, the em scale and the track: every point and advance within "
          f"{HANGUL_POINT_TOL} unit, the largest distance {worst:g}" + (": " + "; ".join(far[:4]) if far else ""))
    if sides["fitted"]:  # a face grown past its sides runs into the next syllable (references/fitting.md, Limits)
        G.add("hangul", "Hangul ink inside the advance", None, "; ".join(
            f"{what}: {sum(v < 0 for v in vals)} of {len(vals)} glyphs leave it, smallest side {min(vals):.0f}"
            for what, vals in sides.items()))
    return inst


def gate_harmony(G, face, T):
    """Weight harmony, per weight: the Hangul stem over the Latin n stem against the reference's ratio, and every
    class's Hangul face centre height against its target. Both are NOT RUN when no reference measured Latin (a
    screenshot of Hangul alone); each also needs its own target."""
    tg, h = T["targets"], T.get("hangul") or {}
    if not tg.get("n_stem"):
        for name in ("Hangul stem / Latin n stem", "Hangul face centre heights"):
            G.add("hangul", name, None, "no reference measured Latin", state="NOT RUN")
        return
    want = L.tagged_value(h.get("stem_n"), "ratio")
    geo = L.hangul_geometry(face)
    cap = face.bounds("H")[3]
    if not want:
        G.add("hangul", "Hangul stem / Latin n stem", None, "no reference measured the Hangul stem beside its own "
              "Latin n", state="NOT RUN")
    elif geo["stem"]:
        got = geo["stem"] / (L.stem_cap700(face) * cap / L.CAP)
        G.add("hangul", "Hangul stem / Latin n stem", abs(got - want) <= HARMONY_RATIO,
              f"{got:.3f} vs {want:.3f}, ±{HARMONY_RATIO}")
    per = {"cap700": cap / L.CAP, "em1000": face.upm / 1000}
    off = {}
    for cls, w in (h.get("classes") or {}).items():
        unit = next((u for u in per if L.tagged_value(w.get("cy"), u) is not None), None)
        if unit and cls in geo["classes"]:
            off[cls] = (geo["classes"][cls]["cy"] - L.tagged_value(w["cy"], unit) * per[unit]) * L.CAP / cap
    if not off:
        G.add("hangul", "Hangul face centre heights", None, "no reference gave a centre height (only a font file does)",
              state="NOT RUN")
    else:
        G.add("hangul", "Hangul face centre heights", all(abs(v) <= HARMONY_CENTRE for v in off.values()),
              ", ".join(f"{c} {v:+.1f}" for c, v in off.items()) + f" from the targets, ±{HARMONY_CENTRE} (cap 700)")


def gate_strokes(G, face, inst, k):
    """Report only: each class's vertical strokes in the fitted font against the base's at the fit's Hangul
    location (fontlib.hangul_class_strokes), and how far apart the classes are in each."""
    got, was = L.hangul_class_strokes(face), L.hangul_class_strokes(L.Face(inst))
    both = [c for c in got if c in was and was[c]]
    if not both:
        return

    def spread(v):
        return max(v) / min(v) - 1
    ratio = {c: got[c] / (was[c] * k) for c in both}
    G.add("hangul", "vertical strokes across the classes", None,
          f"fitted {spread([got[c] for c in both]):.1%} apart, base {spread([was[c] for c in both]):.1%}; fitted over "
          "base " + ", ".join(f"{c} {v:.3f}" for c, v in ratio.items()))


def gate_provenance(G, f, base, refs, yloc=None, skip=()):
    """`base` is the subset of the approved base that fit_font.py made and fitted from. Glyphs in `skip` (the Hangul
    a fit moved, which gate_hangul checks) are left out of the 3 % and 40 % comparison."""
    G.add("provenance", "glyph order equals the subset's", f.getGlyphOrder() == base.getGlyphOrder(), "")
    G.add("provenance", "character map equals the subset's", f.getBestCmap() == base.getBestCmap(), "")
    # Every glyph is the base's glyph, fitted. Its y coordinates come from the base at the fit's y location, so
    # against that instance, at the same cap height, its ink is within 3 % as tall. Widths move with the width
    # classes, so they may differ up to 40 %. Without a y location, the default instance is used and the gate
    # only informs, since a different optical size redraws marks.
    import copy
    from fontTools.varLib import instancer
    from fontTools.pens.boundsPen import BoundsPen
    bd = instancer.instantiateVariableFont(copy.deepcopy(base), yloc or {}, updateFontNames=False) if "fvar" in base else base

    def boxes(font):
        gs = font.getGlyphSet()
        out = {}
        for n in font.getGlyphOrder():
            p = BoundsPen(gs)
            gs[n].draw(p)
            out[n] = p.bounds
        cap = out[font.getBestCmap()[ord("H")]][3]
        return out, cap
    ob, oc = boxes(f)
    bb, bc = boxes(bd)
    far = []
    for n, b in ob.items():
        a = bb.get(n)
        if not a or not b or n in skip:
            continue
        wa, wb = (a[2] - a[0]) / bc, (b[2] - b[0]) / oc
        ha, hb = (a[3] - a[1]) / bc, (b[3] - b[1]) / oc
        if wa > 0.05 and ha > 0.05 and (abs(wb / wa - 1) > 0.40 or abs(hb / ha - 1) > 0.03):
            far.append(f"{n} {wb / wa - 1:+.0%} wide {hb / ha - 1:+.0%} tall")
    G.add("provenance", "every glyph traceable to its base glyph", (not far) if yloc is not None else None,
          f"{len(far)} outside 3 % height, 40 % width of the base at {yloc if yloc is not None else 'its default'}"
          + (": " + ", ".join(far[:6]) if far else ""))

    def outl(font, n):
        g = font["glyf"][n]
        if g.isComposite() or g.numberOfContours <= 0:
            return None
        c, e, fl = g.getCoordinates(font["glyf"])
        return list(c), tuple(e), tuple(x & 1 for x in fl)

    def norm(pts):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        w, h = (max(xs) - min(xs)) or 1, (max(ys) - min(ys)) or 1
        return [((x - min(xs)) / w, (y - min(ys)) / h) for x, y in pts]

    def comparable(o):
        """Outlines with a curve, or with MIN_POINTS points or more: simpler shapes match by accident."""
        return o and (0 in o[2] or len(o[0]) >= MIN_POINTS)
    gate = "outline comparison with a reference (diagnostic)"
    for rp in refs:
        ref = TTFont(rp)
        if "glyf" not in ref:
            G.add("provenance", gate, None, f"{os.path.basename(rp)} has CFF outlines, which cannot be compared "
                  "point by point with TrueType ones: not run", state="NOT RUN")
            continue
        idx = {}
        for n in ref.getGlyphOrder():
            o = outl(ref, n)
            if comparable(o):
                idx.setdefault((o[1], o[2]), []).append((n, o[0]))
        close, compared = [], 0
        for n in f.getGlyphOrder():
            o = outl(f, n)
            if not comparable(o):
                continue
            compared += 1
            for rn, pts in idx.get((o[1], o[2]), []):
                A, B = norm(o[0]), norm(pts)
                if max(max(abs(p[0] - q[0]), abs(p[1] - q[1])) for p, q in zip(A, B)) < 0.02:
                    close.append(f"{n}~{rn}")
        G.add("provenance", gate, None,
              f"{os.path.basename(rp)}: {compared} outlines compared, {len(close)} share point structure and shape"
              + (": " + ", ".join(close[:8]) + ". The chain shows the build never opened this file; if the "
                 "reference is itself built on the same open base, matches are expected, otherwise find out why"
                 if close else ""))


def gate_validity(G, blob, f):
    """`blob` is the font as read; the tools that need a file get a copy of those bytes."""
    tmp = tempfile.mkdtemp()
    try:
        x1, x2, rt = (os.path.join(tmp, n) for n in ("a.ttx", "b.ttx", "rt.ttf"))
        blob.font().saveXML(x1)
        g = TTFont()
        g.importXML(x1)
        g.save(rt)
        TTFont(rt).saveXML(x2)
        strip = lambda s: re.sub(r'<(checkSumAdjustment|modified|created) value="[^"]*"/>', "", re.sub(r"<ttFont[^>]*>", "", s))  # noqa: E731
        same = strip(open(x1).read()) == strip(open(x2).read())
        G.add("validity", "ttx round trip", same, "")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    glyf = f["glyf"]
    ymax = max(glyf[n].yMax for n in f.getGlyphOrder() if glyf[n].numberOfContours != 0)
    ymin = min(glyf[n].yMin for n in f.getGlyphOrder() if glyf[n].numberOfContours != 0)
    os2 = f["OS/2"]
    G.add("validity", "win metrics cover every glyph", os2.usWinAscent >= ymax and os2.usWinDescent >= -ymin,
          f"win {os2.usWinAscent}/{os2.usWinDescent}, glyphs reach {ymax}/{ymin}")
    left = [t for t in ("fvar", "gvar", "HVAR", "MVAR", "STAT") if t in f]
    left += [t + " VarStore" for t in ("GDEF",) if t in f and getattr(f[t].table, "VarStore", None)]
    G.add("validity", "no variation data left", not left, ", ".join(left))
    fb = shutil.which("fontbakery")
    if fb:
        tmp = tempfile.mkdtemp()
        try:
            local = os.path.join(tmp, os.path.basename(blob.path))
            with open(local, "wb") as fh:
                fh.write(blob.data)
            r = subprocess.run([fb, "check-universal", "-l", "FAIL", local], capture_output=True, text=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        out = r.stdout + r.stderr
        fails = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("FAIL ")]
        tail = ("; ".join(fails[:4]) or "no FAIL lines")[:300]
        G.add("validity", "fontbakery check-universal", r.returncode == 0, tail)
    else:
        G.add("validity", "fontbakery", None, "not installed, not run (uv tool install fontbakery)", state="NOT RUN")


def gate_licence(G, f, base, family, package):
    names = L.english_names(f)
    G.add("licence", "OFL notice in name 13", "Open Font License" in names.get(13, ""), names.get(13, "")[:60])
    G.add("licence", "OFL URL in name 14", "openfontlicense.org" in names.get(14, "") or "scripts.sil.org/OFL" in names.get(14, ""), names.get(14, ""))
    G.add("licence", "no trademark record (name 7)", 7 not in names, names.get(7, ""))
    bnames = L.english_names(base)
    base_fam = (bnames.get(16) or bnames.get(1) or "").strip()
    G.add("licence", "family renamed", names.get(16, names.get(1)) == family,
          f"{names.get(16, names.get(1))!r}, want {family!r}")
    words = [w for w in re.findall(r"[A-Za-z]{4,}", base_fam) if w.lower() not in ("serif", "sans", "mono", "display", "text")]
    hits = []
    for nid, v in names.items():
        if nid in (0,):
            continue
        for w in [base_fam] + words:
            if w and w.lower() in v.lower() and w.lower() not in family.lower():
                hits.append(f"name {nid}: {w}")
    for tag in f.keys():
        if tag in ("GlyphOrder", "name"):
            continue
        data = f.getTableData(tag).lower()
        if base_fam and (base_fam.lower().encode() in data or base_fam.lower().encode("utf-16-be") in data):
            hits.append(f"table {tag}")
    G.add("licence", "base's name only in the copyright line", not hits, ", ".join(hits[:8]))
    base_bits = [base_fam.lower()] + [w.lower() for w in words]
    G.add("licence", "new name avoids the base's name", not any(b and b in family.lower() for b in base_bits),
          f"{family!r} vs base {base_fam!r}")
    if package:
        for fn in ("OFL.txt", "FONTLOG.txt"):
            G.add("licence", f"{fn} in the package", os.path.exists(os.path.join(package, fn)), package)
        p = os.path.join(package, "OFL.txt")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                rfn = L.reserved_font_names(fh.read())
            clash = [r for r in rfn if r.lower() in family.lower()]
            G.add("licence", "new name avoids every Reserved Font Name", not clash, f"RFN {rfn or 'none'}")


def save_image(files, img, path):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    files.write(path, buf.getvalue())
    return path


def overlay(files, ref_face, ours, out_dir, tag):
    """Red reference, blue ours, black where both have ink. Both at the same cap height, baselines aligned."""
    from PIL import Image
    paths = []
    for name, text, cap_px in (("text", TEXT_SAMPLE, 28), ("display", DISPLAY_SAMPLE, 160)):
        imgs = []
        for fc in (ref_face, ours):
            px = cap_px * fc.upm / fc.bounds("H")[3]
            cov, base, _ = L.rasterize(fc, text, px)
            imgs.append((cov, int(round(base))))
        above = max(b for _, b in imgs)
        below = max(c.shape[0] - b for c, b in imgs)
        W = max(c.shape[1] for c, _ in imgs)
        layers = []
        for cov, b in imgs:
            canvas = np.zeros((above + below, W))
            canvas[above - b:above - b + cov.shape[0], :cov.shape[1]] = cov
            layers.append(canvas)
        A, B = layers
        rgb = np.clip(np.stack([1 - B, 1 - np.maximum(A, B), 1 - A], axis=-1), 0, 1)
        p = os.path.join(out_dir, f"overlay-{tag}-{name}.png")
        paths.append(save_image(files, with_legend(Image.fromarray((rgb * 255).astype(np.uint8))), p))
    return paths


LEGEND = (((220, 0, 0), "reference only"), ((0, 0, 220), "this font only"), ((0, 0, 0), "both"))


def with_legend(img):
    """The overlay with a band above it that says what each colour is."""
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.load_default(size=14)
    except TypeError:  # Pillow before 10.1 has one bitmap size
        font = ImageFont.load_default()
    band = 30
    out = Image.new("RGB", (max(img.width, 420), img.height + band), "white")
    out.paste(img, (0, band))
    d = ImageDraw.Draw(out)
    x = 10
    for colour, label in LEGEND:
        d.rectangle([x, 9, x + 12, 21], fill=colour)
        d.text((x + 18, 8), label, fill=(0, 0, 0), font=font)
        x += 24 + int(d.textlength(label, font=font)) + 16
    return out


def stacked(files, img_path, text, ours, out_dir, tag):
    """The screenshot above our render of the same text at the same cap height, for a reference with no file; a
    screenshot of Hangul alone has no cap height, so at the same H1 face height."""
    from PIL import Image
    shot = Image.open(img_path).convert("L")
    import measure_image as MI
    cov = MI.load_coverage(img_path)
    read = MI.measure_lines(cov, text.split("|"))
    if read["px_cap"]:
        px = read["px_cap"] * ours.upm / ours.bounds("H")[3]
    else:
        px = read["px_h1"] * ours.upm / L.hangul_geometry(ours)["classes"]["H1"]["face_h"]
    ours_imgs = [L.rasterize(ours, t, px)[0] for t in text.split("|")]
    W = max([shot.width] + [o.shape[1] for o in ours_imgs])
    rows = [np.pad(1 - np.asarray(shot, dtype=float) / 255, ((0, 0), (0, W - shot.width)))]
    rows += [np.pad(o, ((0, 0), (0, W - o.shape[1]))) for o in ours_imgs]
    sheet = np.vstack(rows)
    p = os.path.join(out_dir, f"stacked-{tag}.png")
    return [save_image(files, Image.fromarray((255 - sheet * 255).clip(0, 255).astype(np.uint8)), p)]


def verify_chain(files, a):
    """Every link from base.json to the fonts given, by the same chain.verify_build package.py ran, then the package
    log. Returns (the build, the package log's links, rows) or refuses."""
    b = C.verify_build(files, a.base_json, a.targets, a.fit_log, a.space_log)
    pk = C.verify_package_log(files, b, a.package_log, a.fonts)
    return b, pk, b.rows + pk.rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fonts", nargs="+")
    ap.add_argument("--targets", required=True)
    ap.add_argument("--base-json", help="base.json from record_base.py (required)")
    ap.add_argument("--fit-log", help="fit-log.json from fit_font.py (required)")
    ap.add_argument("--space-log", action="extend", nargs="+", default=[],
                    help="every .space-log.json, one or more after the flag; the flag may repeat (required)")
    ap.add_argument("--package-log", help="package-log.json from package.py (required)")
    ap.add_argument("--reference", action="append", default=[])
    ap.add_argument("--reference-image")
    ap.add_argument("--reference-text")
    ap.add_argument("--package")
    ap.add_argument("--out-dir", default=".")
    a = ap.parse_args()
    files = C.Files()
    b, pk, chain_rows = verify_chain(files, a)
    rec, fit, subset_font = b.rec, b.fit, b.subset
    T = b.T
    base_vf = b.approved.font.font()
    report = os.path.join(a.out_dir, "check-report.json")
    files.check_output(report)
    G = Gates()
    for name, detail in chain_rows:
        G.add("chain", name, True, detail)
    renders = []
    for i, (path, blob) in enumerate(zip(a.fonts, pk.fonts)):
        f = blob.font()
        sub = f["name"].getDebugName(17) or f["name"].getDebugName(2) or ""
        style = next((s for s in T["styles"] if s["name"] == sub), T["styles"][min(i, len(T["styles"]) - 1)])
        tag = style["name"]
        face = L.Face(f)
        m = L.measure_face(face)
        G.rows.append((f"--- {os.path.basename(path)} ({tag})", "", "", ""))
        gate_metrics(G, m, T, style)
        gate_widths(G, m, T, i == 0 or style is T["styles"][0])
        gate_kerning(G, face, T["tolerances"]["min_gap"])
        gate_coverage(G, f, T.get("scripts", ["latin"]))
        fitted = next((s for s in fit["styles"] if s["style"]["name"] == tag), {})
        if T.get("hangul") and not fitted.get("hangul"):
            G.add("provenance", "Hangul transform recorded", False, f"targets.json has Hangul targets, and fit-log.json "
                  f"records no Hangul transform for {tag}: the Hangul cannot be checked against what the fit did")
        hangul = L.hangul_glyphs(f) if fitted.get("hangul") else {}
        gate_provenance(G, f, subset_font, a.reference, fitted.get("y_location"), skip=hangul)
        if hangul:
            track = next((sp.get("track", 0) for sp in b.spaces if sp.get("input") == fitted.get("file")), 0)
            inst = gate_hangul(G, f, subset_font, fitted, track)
            gate_harmony(G, face, T)
            gate_strokes(G, face, inst, fitted["em_scale"])
        gate_validity(G, blob, f)
        gate_licence(G, f, base_vf, T["family"], a.package)
        if a.reference:
            renders += overlay(files, L.Face(a.reference[0]), face, a.out_dir, tag)
        elif a.reference_image and a.reference_text:
            renders += stacked(files, a.reference_image, a.reference_text, face, a.out_dir, tag)
    for group, name, state, detail in G.rows:
        if not name:
            print(group)
        else:
            print(f"  {state:7s}  {group:10s} {name:50s} {detail}")
    if renders:
        print("renders:", *renders, sep="\n  ")
    bad = G.failed()
    not_run = sorted({r[1] for r in G.rows if r[2] == "NOT RUN"})
    print(f"\n{len(bad)} failed, {sum(1 for r in G.rows if r[2] == 'PASS')} passed"
          + (f", not run: {'; '.join(not_run)}" if not_run else ""))
    base, lic = rec["font"], rec["license"]
    print(f"base {os.path.basename(base['file'])} sha256 {base['sha256']}, licence {lic['id']} sha256 {lic['sha256']}")
    print(f"approved: Q {rec['approval']['question']!r} A {rec['approval']['answer']!r}")
    # The record base.json keeps, as checked above, beside the gates: file names only, no builder paths.
    files.write_json(report, {
        "schema": "make-font/check-report@1",
        "base": {"file": os.path.basename(base["file"]), "sha256": base["sha256"], "source": rec["source"],
                 "license": {"id": lic["id"], "file": os.path.basename(lic["file"]), "sha256": lic["sha256"],
                             "name_id_13": lic["name_id_13"], "reserved_font_names": lic["reserved_font_names"]}},
        "approval": rec["approval"],
        "package": {"outputs": pk.outputs},
        "gates": [{"group": g, "gate": n, "state": s, "detail": d} for g, n, s, d in G.rows]})
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "brotli", "uharfbuzz", "numpy", "pillow"]
# ///
"""Measure a typeface from a screenshot: proportions, stems, contrast, serifs and, with the right text, widths.

  uv run measure_image.py <shot.png> --text "line one|line two" [--crop x0,y0,x1,y1] [--out m.json]
  uv run measure_image.py --selftest <open-font.ttf> [--px 120] [--out-dir dir]

The image holds one or more lines of dark text on a light ground (or the reverse), all at one size. --text gives
each line's characters, lines split by "|", in order from the top. Spaces do not matter. The script splits the
image into lines at blank rows, and each line into letters by connected ink (a dot joins the stem under it).
When the letter count and the text disagree it stops and says so: crop tighter, set the text larger, or fix
--text.

Best input: the four lines of fontlib.SAMPLE_LINES typed in the font, cap height 80 px or more. From those it
reads advances (n-X-n and H-X-H contexts) and sidebearings (nn, no, HH, HO). From any other text it reads
vertical proportions, stems and contrast only. Each number gets a confidence: high, medium or low. Pixel edges
are read at sub-pixel precision from the anti-aliasing, so the error is about half a pixel per edge.

A line with Hangul in it is cut into syllables by columns of ink instead, since a syllable is drawn in several
parts: the six lines of fontlib.SAMPLE_LINES_KO set each measured syllable between two 으, and the ink between
two anchors is one syllable. A line without the anchors is cut at its widest gaps, only when they stand clearly
apart from the gaps inside a syllable; otherwise the script stops. Hangul numbers are ratios, plus lengths at
cap height 700 when a Latin H in the same screenshot sets the scale. A screenshot of Hangul alone needs no H.

--selftest renders the sample lines from an open font (the Latin ones, the Korean ones, or both, as the font
has them), measures the pixels and the file, and prints the error per number. Run it once at the screenshot's
size to see what a screenshot can be trusted for.
"""
import argparse
import os
import statistics as st
import sys

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import fontlib as L  # noqa: E402

FLAT_BOTTOM = set("nhmxirklHNIEFLTBDKMPRXZ")
GAP_APART = 1.5  # without anchors, the narrowest cut must be this many times the widest gap left inside a syllable


# ------------------------------------------------------------------ pixels
def load_coverage(path, crop=None):
    from PIL import Image
    im = np.asarray(Image.open(path).convert("L"), dtype=np.float64) / 255.0
    if crop:
        x0, y0, x1, y1 = crop
        im = im[y0:y1, x0:x1]
    # Ink is whatever is rarer: dark on light or light on dark.
    cov = 1 - im if np.median(im) > 0.5 else im
    lo, hi = np.percentile(cov, 1), cov.max()
    return np.clip((cov - lo) / max(hi - lo, 1e-6), 0, 1)


def components(mask):
    """Label 8-connected ink using row runs and union-find. Returns a list of (rows, cols) index arrays."""
    runs = []
    for y in range(mask.shape[0]):
        row = mask[y]
        if not row.any():
            continue
        d = np.diff(np.concatenate(([0], row.astype(np.int8), [0])))
        for a, b in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
            runs.append((y, a, b))
    parent = list(range(len(runs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    by_row = {}
    for i, (y, a, b) in enumerate(runs):
        by_row.setdefault(y, []).append(i)
    for i, (y, a, b) in enumerate(runs):
        for j in by_row.get(y - 1, []):
            _, c, d = runs[j]
            if c <= b and d >= a:  # 8-connected: touching diagonally counts
                parent[find(i)] = find(j)
    groups = {}
    for i, r in enumerate(runs):
        groups.setdefault(find(i), []).append(r)
    out = []
    for rs in groups.values():
        ys = np.concatenate([np.full(b - a, y) for y, a, b in rs])
        xs = np.concatenate([np.arange(a, b) for y, a, b in rs])
        out.append((ys, xs))
    return out


class Letter:
    def __init__(self, comps, cov):
        ys = np.concatenate([c[0] for c in comps])
        xs = np.concatenate([c[1] for c in comps])
        self.y0, self.y1, self.x0, self.x1 = ys.min(), ys.max(), xs.min(), xs.max()
        m = np.zeros(cov.shape, dtype=bool)
        m[ys, xs] = True
        # Grow the mask by one pixel so the anti-aliased edge belongs to the letter.
        g = m.copy()
        g[1:] |= m[:-1]
        g[:-1] |= m[1:]
        g[:, 1:] |= m[:, :-1]
        g[:, :-1] |= m[:, 1:]
        self.cov = np.where(g, cov, 0.0)
        self.comps, self.full, self.ch = comps, cov, None

    def merge(self, other):
        return Letter(self.comps + other.comps, self.full)

    # edges, in pixels, with the partial coverage of the edge pixel as the fraction
    def top(self):
        p = self.cov.max(axis=1)
        r = int(np.argmax(p > 0.02))
        return r + 1 - p[r]

    def bottom(self):
        p = self.cov.max(axis=1)
        r = len(p) - 1 - int(np.argmax(p[::-1] > 0.02))
        return r + p[r]

    def left(self):
        p = self.cov.max(axis=0)
        c = int(np.argmax(p > 0.02))
        return c + 1 - p[c]

    def right(self):
        p = self.cov.max(axis=0)
        c = len(p) - 1 - int(np.argmax(p[::-1] > 0.02))
        return c + p[c]

    def hruns(self, y):
        return _runs(self.cov[int(round(y))], )

    def vruns(self, x):
        return _runs(self.cov[:, int(round(x))])


def _runs(line):
    """Ink runs along one pixel line: (start, end, width), width summed from coverage."""
    on = line > 0.02
    d = np.diff(np.concatenate(([0], on.astype(np.int8), [0])))
    out = []
    for a, b in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
        seg = line[a:b]
        if seg.max() < 0.5:
            continue
        w = seg.sum()
        start = a + 1 - seg[0]
        out.append((start, start + w, w))
    return out


def split_lines(cov, count=None):
    rows = (cov > 0.5).any(axis=1)
    d = np.diff(np.concatenate(([0], rows.astype(np.int8), [0])))
    bands = list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))
    # A band thinner than a fifth of the tallest is a stray accent row or noise: join it to its neighbour.
    if not bands:
        return []
    tall = max(b - a for a, b in bands)
    merged = []
    for a, b in bands:
        if merged and (b - a < tall * 0.2 or a - merged[-1][1] < 2):
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    # A Hangul syllable is drawn in parts with blank rows between them (a final under the vowel), and when every
    # syllable of a line has them there, the line reads as two bands. With more bands than `count` lines, join
    # across the narrowest gaps, when they stand clearly apart from the gaps kept between the lines.
    if count and len(merged) > count:
        gaps = [merged[i + 1][0] - merged[i][1] for i in range(len(merged) - 1)]
        order = sorted(range(len(gaps)), key=lambda i: gaps[i])
        join, keep = set(order[:len(merged) - count]), order[len(merged) - count:]
        wide = max(gaps[i] for i in join)
        if not keep or min(gaps[i] for i in keep) >= max(GAP_APART * wide, wide + 2):
            joined = merged[:1]
            for i, band in enumerate(merged[1:]):
                joined[-1:] = [(joined[-1][0], band[1])] if i in join else [joined[-1], band]
            merged = joined
    return merged


def letters_of(cov):
    # A low threshold keeps hairline joins (the arm of k, the ear of g) joined to their letter.
    comps = components(cov > 0.15)
    comps.sort(key=lambda c: -len(c[0]))
    boxes = [(c[0].min(), c[0].max(), c[1].min(), c[1].max()) for c in comps]
    owner = list(range(len(comps)))
    for i in range(len(comps)):
        y0, y1, x0, x1 = boxes[i]
        cx = (x0 + x1) / 2
        for j in range(i):  # bigger components first
            if owner[j] != j:
                continue
            Y0, Y1, X0, X1 = boxes[j]
            vertical_gap = y1 < Y0 or y0 > Y1
            if vertical_gap and X0 - 1 <= cx <= X1 + 1:
                owner[i] = j  # a dot or an accent over or under a bigger shape
                break
    groups = {}
    for i, o in enumerate(owner):
        groups.setdefault(o, []).append(comps[i])
    out = [Letter(g, cov) for g in groups.values()]
    out.sort(key=lambda t: t.x0)
    # Specks under 1 % of the median letter area are noise.
    if out:
        med = st.median(float((t.cov > 0.5).sum()) for t in out)
        out = [t for t in out if (t.cov > 0.5).sum() > med * 0.01]
    return out


def _spread(ls, chars):
    """How unevenly the same character is drawn across a line when ls is labelled with chars. A wrong join
    shifts every label after it, so repeated letters stop matching in width."""
    if len(ls) < len(chars):
        return 0.0
    w = {}
    for t, c in zip(ls, chars):
        w.setdefault(c, []).append(float(t.x1 - t.x0))
    return sum(st.pstdev(v) for v in w.values() if len(v) > 1)


# ------------------------------------------------------------------ Hangul lines
def column_groups(comps):
    """Ink joined by columns, left to right: components whose columns overlap or touch are one group, so a group
    ends at a column without ink. Returns [(first column, last column, components)]."""
    groups = []
    for c in sorted(comps, key=lambda c: c[1].min()):
        x0, x1 = c[1].min(), c[1].max()
        if groups and x0 <= groups[-1][1] + 1:
            g = groups[-1]
            groups[-1] = (g[0], max(g[1], x1), g[2] + [c])
        else:
            groups.append((x0, x1, [c]))
    return groups


def _shape(group, cov):
    """A group's width, height and top row, and its ink summed by column and by row."""
    x0, x1, comps = group
    ys = np.concatenate([c[0] for c in comps])
    box = cov[ys.min():ys.max() + 1, x0:x1 + 1]
    return x1 - x0 + 1, ys.max() - ys.min() + 1, ys.min(), box.sum(axis=0), box.sum(axis=1)


def _correlation(p, q):
    q = np.interp(np.linspace(0, 1, len(p)), np.linspace(0, 1, len(q)), q)
    p, q = p - p.mean(), q - q.mean()
    d = float(np.sqrt((p * p).sum() * (q * q).sum()))
    return float((p * q).sum()) / d if d else 0.0


def _same_glyph(s, a):
    """Whether a group drawn like s is the glyph a: the same box on the same line, and the same ink profiles."""
    def near(u, v):
        return abs(u - v) <= max(2, 0.06 * v)
    return (near(s[0], a[0]) and near(s[1], a[1]) and abs(int(s[2]) - int(a[2])) <= 2
            and _correlation(a[3], s[3]) > 0.9 and _correlation(a[4], s[4]) > 0.9)


def hangul_letters(cov, chars, text):
    """One Letter per character of a line with Hangul in it, and how the line was cut: "anchors" or "gaps".

    In the 으 X 으 form the first group of ink is an anchor, every group drawn like it is one, and the ink between
    two anchors is one syllable, whatever its gaps. Otherwise, or when the anchors found do not fit the text, the
    line is cut at its len(chars) - 1 widest gaps, and refused unless those stand clearly apart from the gaps left
    inside a syllable. A line with one group per character leaves no gap inside a syllable to compare, so it is
    refused too: its groups may as well be the parts of fewer syllables."""
    comps = components(cov > 0.15)
    if comps:
        med = st.median(len(c[0]) for c in comps)
        comps = [c for c in comps if len(c[0]) > med * 0.01]  # specks
    groups = column_groups(comps)
    a, n = L.HANGUL_ANCHOR, len(chars)

    def letters(bounds):
        return [Letter([c for g in groups[i:j] for c in g[2]], cov) for i, j in zip(bounds, bounds[1:])]
    anchored = n >= 3 and n % 2 and set(chars[0::2]) == {a} and a not in chars[1::2]
    if anchored and groups:
        ref = _shape(groups[0], cov)
        at = [i for i, g in enumerate(groups) if _same_glyph(_shape(g, cov), ref)]
        if (len(at) == (n + 1) // 2 and at[-1] == len(groups) - 1
                and all(j - i >= 2 for i, j in zip(at, at[1:]))):
            return letters(sorted({0, len(groups)} | {i for k in at for i in (k, k + 1)})), "anchors"
    if len(groups) < n:
        raise SystemExit(f"line {text!r}: {len(groups)} groups of ink for {n} characters, so some touch. Set the "
                         f"text larger or looser, or type the {a} X {a} lines (fontlib.SAMPLE_LINES_KO).")
    gaps = [int(groups[i + 1][0] - groups[i][1] - 1) for i in range(len(groups) - 1)]
    order = sorted(range(len(gaps)), key=lambda i: -gaps[i])
    cut, inner = sorted(order[:n - 1]), [gaps[i] for i in order[n - 1:]]
    why = f"its {a} anchors were not found" if anchored else f"it has no {a} anchors"
    if cut and not inner:
        raise SystemExit(f"line {text!r}: {why}, and it has one group of ink per character ({n}), so no gap is left "
                         "inside a syllable to show that the gaps between them stand apart: the groups may be the "
                         f"parts of fewer syllables. Type the {a} X {a} lines (fontlib.SAMPLE_LINES_KO).")
    if cut:
        narrow, wide = min(gaps[i] for i in cut), max(inner)
        if narrow < max(GAP_APART * wide, wide + 2):
            raise SystemExit(f"line {text!r}: {why}, and its gaps do not fall in two groups: the "
                             f"narrowest gap between syllables would be {narrow} px and the widest inside one "
                             f"{wide} px, so the syllables cannot be told apart. Type the {a} X {a} lines "
                             "(fontlib.SAMPLE_LINES_KO), or set the text looser.")
    return letters([0, *(i + 1 for i in cut), len(groups)]), "gaps"


class ImageInk:
    """Syllables read from a screenshot, for fontlib.hangul_geometry: pixels, with rows negated so y points up."""

    def __init__(self, letters):
        self.letters = letters

    def has(self, ch):
        return ch in self.letters

    def bounds(self, ch):
        t = self.letters[ch]
        return t.left(), -t.bottom(), t.right(), -t.top()

    def hspans(self, ch, y):
        return [(a, b) for a, b, _ in self.letters[ch].hruns(-y)]

    def vspans(self, ch, x):
        return [(-b, -a) for a, b, _ in reversed(self.letters[ch].vruns(x))]


def measure_hangul(lines, k, cut_at):
    """The hangul object from the Hangul lines. k turns pixels into cap700 units when a Latin H set the scale. The
    distance from one anchor to the next is reported per class, never a target: it holds the pair's kerning."""
    a = L.HANGUL_ANCHOR
    seen, pitch = {}, {}
    for ls, _ in lines:
        for i, t in enumerate(ls):
            seen.setdefault(t.ch, t)
            cls = L.hangul_class(t.ch)
            if cls and 0 < i < len(ls) - 1 and ls[i - 1].ch == a == ls[i + 1].ch:
                pitch.setdefault(cls, []).append(ls[i + 1].left() - ls[i - 1].left())
    geo = L.hangul_geometry(ImageInk(seen), font=False)
    if not geo["classes"]:
        return None
    geo["pitch"] = {cls: st.mean(v) for cls, v in pitch.items() if cls in geo["classes"]}
    face_px = (geo["classes"].get("H1") or next(iter(geo["classes"].values())))["face_h"]

    def conf(kind, px):
        if kind == "stroke":
            return conf_px(px)
        if kind == "edge":
            return "low" if face_px < 120 else "medium"
        return "high" if px >= 60 else "medium" if px >= 30 else "low"
    h = L.hangul_measurement(geo, {"cap700": k} if k else {}, conf)
    h["cut_at"] = cut_at
    return h


# ------------------------------------------------------------------ measuring
def conf_px(px):
    return "high" if px >= 6 else "medium" if px >= 3 else "low"


def measure_lines(cov, texts):
    bands = split_lines(cov, len(texts))
    if len(bands) != len(texts):
        raise SystemExit(f"found {len(bands)} lines of ink, --text has {len(texts)}. Crop or fix --text.")
    lines, joined, hangul, cut_at = [], [], [], []
    for (a, b), text in zip(bands, texts):
        pad = 2
        sub = cov[max(a - pad, 0):b + pad]
        chars = [c for c in text if not c.isspace()]
        if any(L.hangul_class(c) for c in chars):
            ls, how = hangul_letters(sub, chars, text)
            hangul.append(len(lines))
            cut_at.append(how)
        else:
            ls = letters_of(sub)
        # A letter drawn in detached parts (some k, some fractions) reads as two. Join the closest neighbours,
        # the pair with the most overlap, until the count fits, and say so.
        while len(ls) > len(chars) > 0:
            near = [j for j in range(len(ls) - 1) if ls[j + 1].x0 - ls[j].x1 <= 2]
            if not near:
                break
            i = min(near, key=lambda j: (_spread(ls[:j] + [ls[j].merge(ls[j + 1])] + ls[j + 2:], chars),
                                         ls[j + 1].x0 - ls[j].x1))
            ls[i:i + 2] = [ls[i].merge(ls[i + 1])]
            joined.append(text)
        if len(ls) != len(chars):
            raise SystemExit(f"line {text!r}: found {len(ls)} letters, the text has {len(chars)}. Letters that touch "
                             "merge into one. Set the text larger, or crop to a part that does not touch.")
        for t, c in zip(ls, chars):
            t.ch = c
        flat = [t.bottom() for t in ls if t.ch in FLAT_BOTTOM]
        base = st.median(flat) if flat else st.median(t.bottom() for t in ls)
        lines.append((ls, base))
    every = [t for ls, _ in lines for t in ls]

    def first(ch):
        for ls, base in lines:
            for t in ls:
                if t.ch == ch:
                    return t, base
        return None, None

    H, bH = first("H")
    hangul = [lines[i] for i in hangul]
    if H is None and hangul and len(hangul) == len(lines):
        h = measure_hangul(hangul, None, cut_at)
        if h is None:
            raise SystemExit(f"no Hangul class was read on two different syllables of its list "
                             f"(fontlib.HANGUL_CLASSES), and one syllable is never a target. Type the "
                             f"{L.HANGUL_ANCHOR} X {L.HANGUL_ANCHOR} lines (fontlib.SAMPLE_LINES_KO).")
        return {"source": "image", "cap_em": None, "px_cap": None, "confidence": {}, "hangul": h,
                "letters_read": len(every)}
    if H is None:
        raise SystemExit("an H is needed to set the scale (cap height 700). Add one to the text.")
    cap_px = bH - H.top()
    k = L.CAP / cap_px
    m = {"source": "image", "cap": L.CAP, "cap_em": None, "px_cap": round(cap_px, 1), "confidence": {}}
    C = m["confidence"]
    vconf = "high" if cap_px >= 60 else "medium" if cap_px >= 30 else "low"

    def put(key, val, conf):
        if val is not None:
            m[key] = round(val, 3) if isinstance(val, float) and abs(val) < 5 else round(val, 1)
            C[key] = conf

    def mean_tops(chs):
        v = [(base - t.top()) for ls, base in lines for t in ls if t.ch in chs]
        return st.mean(v) if v else None

    def mean_bottoms(chs):
        v = [(base - t.bottom()) for ls, base in lines for t in ls if t.ch in chs]
        return st.mean(v) if v else None

    xh = mean_tops("xz")
    if xh:
        put("xh", xh * k, vconf)
        put("xh_cap", xh / cap_px, vconf)
    asc = mean_tops("bdhkl")
    if asc:
        put("asc", asc * k, vconf)
    desc = mean_bottoms("pq")
    if desc:
        put("desc", desc * k, vconf)
    o, bo = first("o")
    if o and xh:
        put("overshoot_lc", ((bo - o.top()) - xh) * k, "low" if cap_px < 120 else "medium")
    n, bn = first("n")
    if n and xh:
        runs = n.hruns(bn - xh * 0.5)
        if runs:
            put("n_stem", runs[0][2] * k, conf_px(runs[0][2]))
        if len(runs) > 1:
            put("n_counter", (runs[1][0] - runs[0][1]) * k, vconf)
    Hr = H.hruns(bH - cap_px * 0.3)
    if Hr:
        put("H_stem", Hr[0][2] * k, conf_px(Hr[0][2]))
        if len(Hr) > 1:
            bar = H.vruns((Hr[0][1] + Hr[-1][0]) / 2)
            if bar:
                put("H_bar", bar[0][2] * k, conf_px(bar[0][2]))
    if o:
        mid_y = (o.top() + o.bottom()) / 2
        side = o.hruns(mid_y)
        thin = o.vruns((o.left() + o.right()) / 2)
        if side:
            put("o_side", side[0][2] * k, conf_px(side[0][2]))
        if thin:
            tmin = min(r[2] for r in thin)
            put("o_thin", tmin * k, conf_px(tmin))
    if m.get("o_side") and m.get("o_thin"):
        put("contrast", m["o_thin"] / m["o_side"], min(C["o_thin"], C["o_side"], key=["low", "medium", "high"].index))
    if m.get("H_bar") and m.get("H_stem"):
        put("bar_stem", m["H_bar"] / m["H_stem"], C["H_bar"])
    if Hr:
        foot = H.hruns(bH - max(1.5, cap_px * 0.012))
        ext_l = Hr[0][0] - foot[0][0] if foot else 0
        ext_r = foot[0][1] - Hr[0][1] if foot else 0
        ext = (ext_l + ext_r) / 2
        is_serif = ext > 0.12 * Hr[0][2] and ext > 1
        m["serif"] = bool(is_serif)
        C["serif"] = "high" if ext > 3 or ext < 0.5 else "medium"
        put("serif_ext", ext * k if is_serif else 0.0, conf_px(ext) if is_serif else C["serif"])
        if is_serif:
            tip = H.vruns(foot[0][0] + max(ext_l, 1) * 0.3)
            if tip:
                put("serif_tip", tip[-1][2] * k, "low" if tip[-1][2] < 6 else "medium")
    # Advances and sidebearings from the sample contexts. Kerning inside a context would bias them, so medium.

    def pitches(a, b):
        out = []
        for ls, _ in lines:
            for i in range(len(ls) - 1):
                if ls[i].ch == a and ls[i + 1].ch == b:
                    out.append((ls[i], ls[i + 1]))
        return out

    adv, ctx = {}, {}
    for ref in "nH":
        p = pitches(ref, ref)
        if p:
            adv[ref] = float(st.mean(b.left() - a.left() for a, b in p))
    for ls, _ in lines:
        for i in range(1, len(ls) - 1):
            ref = ls[i - 1].ch
            if ref in adv and ls[i + 1].ch == ref and ls[i].ch != ref:
                ctx.setdefault(ls[i].ch, []).append(float(ls[i + 1].left() - ls[i - 1].left() - adv[ref]))
    for c, v in ctx.items():
        adv.setdefault(c, st.mean(v))
    widths = {}
    for cls, chars in L.CLASSES.items():
        have = [adv[c] for c in chars if c in adv]
        if have:
            widths[cls] = round(st.mean(have) * k, 1)
            C["w_" + cls] = "medium" if len(have) * 2 >= len(chars) else "low"
    if widths:
        m["widths"] = widths
    lc = [adv[c] for c in L.LETTERS[:26] if c in adv]
    uc = [adv[c] for c in L.LETTERS[26:] if c in adv]
    if len(lc) == 26:
        put("lc_avg", st.mean(lc) * k, "medium")
    if len(uc) == 26:
        put("uc_avg", st.mean(uc) * k, "medium")
    # Sidebearings: half the n-n gap is the n side (n is close to symmetric). Every other side in a class comes
    # from its gap to the n (or H) beside it, minus that side. Same class membership as a font file.
    sides = {}
    half = {}
    for ref in "nH":
        same = pitches(ref, ref)
        if same:
            half[ref] = st.mean(b.left() - a.right() for a, b in same) / 2
    for cls, members in L.SIDE_CLASSES.items():
        ref = "n" if cls.startswith("lc") else "H"
        if ref not in half:
            continue
        vals = []
        for c, side in members:
            if c == ref:
                vals.append(half[ref])
                continue
            pairs = pitches(ref, c) if side == 0 else pitches(c, ref)
            vals += [b.left() - a.right() - half[ref] for a, b in pairs]
        if vals:
            sides[cls] = round(float(st.mean(vals)) * k, 1)
    if sides:
        m["sides"] = sides
        for key in sides:
            C["side_" + key] = "medium"
    if m.get("n_counter") and sides.get("lc_straight") is not None:
        put("rhythm", 2 * sides["lc_straight"] / m["n_counter"], "medium")
    if hangul:
        h = measure_hangul(hangul, k, cut_at)
        if h:
            m["hangul"] = h
        else:
            print("Hangul left out: no class was read on two different syllables of its list", file=sys.stderr)
    m["letters_read"] = len(every)
    m["joined_parts"] = len(joined)
    return m


def render_sheet(face, lines, px, path):
    """The lines drawn from the face's outlines, one under another, as a greyscale PNG at px pixels per em."""
    gap = int(px * 0.6)
    rows = [L.rasterize(face, line, px, pad=gap // 2)[0] for line in lines]
    w = max(r.shape[1] for r in rows)
    L.save_png(np.vstack([np.pad(r, ((0, 0), (0, w - r.shape[1]))) for r in rows]), path)
    return path


def compare_hangul(want, got):
    """The screenshot's Hangul numbers beside the file's, per class, in each unit both have."""
    def rows(name, w, g):
        for e in g or []:
            f = next((v["value"] for v in w or [] if v["unit"] == e["unit"]), None)
            if f:
                print(f"  {name:16s} {e['unit']:6s} {f:8.3f} {e['value']:8.3f} {(e['value'] / f - 1) * 100:+7.2f}%  "
                      f"{e['confidence']}")
    print(f"  {'hangul':16s} {'unit':6s} {'file':>8s} {'image':>8s} {'error':>8s}  confidence")
    for cls, c in want["classes"].items():
        for key in ("face_w", "face_h", "aspect", "face_w_h1", "face_h_h1"):
            rows(f"{cls} {key}", c.get(key), got["classes"].get(cls, {}).get(key))
    for key in ("stem", "stem_h1"):
        rows(key, want.get(key), got.get(key))
    for key in ("hstroke", "hstroke_h1", "overshoot", "contrast"):
        rows(f"report {key}", want["report"].get(key), got["report"].get(key))


def selftest(font, px, out_dir):
    face = L.Face(font, subset_text=L.MEASURE_TEXT + L.HANGUL_TEXT)
    latin = all(face.has(c) for c in "".join(L.SAMPLE_LINES) if not c.isspace())
    hangul = all(face.has(c) for c in "".join(L.SAMPLE_LINES_KO))
    lines = (L.SAMPLE_LINES if latin else []) + (L.SAMPLE_LINES_KO if hangul else [])
    if not lines:
        raise SystemExit(f"{font} has neither every letter of fontlib.SAMPLE_LINES nor of SAMPLE_LINES_KO")
    os.makedirs(out_dir, exist_ok=True)
    path = render_sheet(face, lines, px, os.path.join(out_dir, "selftest-sheet.png"))
    got = measure_lines(load_coverage(path), lines)
    print(f"selftest: {os.path.basename(font)} at {px}px per em, cap {got['px_cap']} px, sheet {path}")
    if hangul:
        lengths = {"cap700": L.CAP / face.bounds("H")[3]} if face.has("H") else {}
        compare_hangul(L.hangul_measurement(L.hangul_geometry(face), {**lengths, "em1000": 1000 / face.upm}),
                       got["hangul"])
    if not latin:
        return got
    want = L.measure_face(face)
    print(f"  {'key':14s} {'file':>8s} {'image':>8s} {'error':>8s}  confidence")
    worst = 0.0
    for key in ("xh", "asc", "desc", "n_stem", "H_stem", "H_bar", "o_side", "o_thin", "contrast", "serif_ext",
                "serif_tip", "n_counter", "lc_avg", "uc_avg"):
        a, b = want.get(key), got.get(key)
        if a is None or b is None:
            continue
        e = b - a
        print(f"  {key:14s} {a:8.3f} {b:8.3f} {e:+8.3f}  {got['confidence'].get(key)}")
    for cls in want["widths"]:
        a, b = want["widths"][cls], got.get("widths", {}).get(cls)
        if b is not None:
            e = b / a - 1
            worst = max(worst, abs(e))
            print(f"  w_{cls:12s} {a:8.1f} {b:8.1f} {e*100:+7.2f}%  {got['confidence'].get('w_' + cls)}")
    for cls in want["sides"]:
        a, b = want["sides"][cls], got.get("sides", {}).get(cls)
        if b is not None:
            print(f"  s_{cls:12s} {a:8.1f} {b:8.1f} {b - a:+8.1f}  medium")
    print(f"  largest class-width error {worst*100:.2f}%")
    return got


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image", nargs="?")
    ap.add_argument("--text", help='each line\'s characters, lines split by "|"')
    ap.add_argument("--crop")
    ap.add_argument("--out")
    ap.add_argument("--selftest", metavar="FONT")
    ap.add_argument("--px", type=float, default=120, help="selftest size in px per em")
    ap.add_argument("--out-dir", default=".")
    a = ap.parse_args()
    if a.selftest:
        m = selftest(a.selftest, a.px, a.out_dir)
    else:
        if not a.image or not a.text:
            ap.error("give an image and --text, or --selftest FONT")
        crop = [int(v) for v in a.crop.split(",")] if a.crop else None
        m = measure_lines(load_coverage(a.image, crop), a.text.split("|"))
        m["file"] = os.path.basename(a.image)
        for key in ("px_cap", "xh", "xh_cap", "asc", "desc", "n_stem", "H_stem", "H_bar", "o_side", "o_thin",
                    "contrast", "bar_stem", "serif", "serif_ext", "serif_tip", "n_counter", "rhythm", "lc_avg", "uc_avg"):
            if key in m:
                print(f"  {key:12s} {m[key]!s:>9}  {m['confidence'].get(key, '')}")
        if "widths" in m:
            print("  widths", m["widths"])
        if "sides" in m:
            print("  sides ", m["sides"])
        if m.get("hangul"):
            print("\n".join(L.hangul_summary(m["hangul"])))
    if a.out:
        L.save_json(m, a.out)


if __name__ == "__main__":
    main()

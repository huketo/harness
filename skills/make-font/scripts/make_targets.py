# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools"]
# ///
"""Turn reference measurements into targets.json, the numbers every later step aims at.

  uv run make_targets.py m1.json [m2.json ...] --family "New Family" --use text --scripts latin,cyrillic \\
      [--category sans] [--style Regular:400] [--style Medium:500:88] [--weight m1.json=2] --out targets.json

Inputs are files from measure_font.py or measure_image.py. With several references, each number is a weighted
mean: confidence high counts 3, medium 2, low 1, times any --weight given for that file. Where the references
disagree by more than a tolerance, the spread is recorded so the person can choose instead of the average.

--style NAME:WEIGHT[:STEM] lists the static weights to build. STEM is the n stem at cap 700. Leave it out and
the build keeps the base font's own stem ratio to the first style. The first style takes the measured n stem.
--use text | display | ui sets the gates' tolerances and which optical size the search prefers.
--category sans | serif | mono is the kind of face. By default it is mono when every class mean width is within
2 % of the others, serif when the references have serifs, else sans. The foundation search looks in that
category, and the package's CSS example falls back to sans-serif, serif or monospace from it.

Hangul: when --scripts has korean, the references' `hangul` objects merge into one `hangul` object of the same
shape. Every value is tagged with its unit (cap700, em1000 or ratio), and only values of one unit merge, by the
same weights; a value in another unit stays beside them as its own target. A number that is not a list of tagged
values, each with a value and one of the units its key takes, is refused, and so is a key outside the table in
references/measuring.md (HANGUL_SCHEMA). The advances take the form the merged
fixed_width names (one font-wide advance, or one per class), and a reference of the other form is left out of
them. No Latin number is needed: a screenshot of Hangul alone makes targets from its ratios.
"""
import argparse
import math
import os
import statistics as st
import sys

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fontlib as L  # noqa: E402

RANK = {"high": 3, "medium": 2, "low": 1}
CATEGORIES = ("sans", "serif", "mono")
SCALARS = ["xh", "xh_cap", "asc", "desc", "overshoot_lc", "overshoot_uc", "n_stem", "H_stem", "H_bar", "o_side",
           "o_thin", "contrast", "bar_stem", "serif_ext", "serif_tip", "n_counter", "rhythm", "lc_avg", "uc_avg",
           "space", "para"]
DISAGREE = {"xh_cap": 0.02, "contrast": 0.08, "n_stem": 8, "serif_ext": 20, "rhythm": 0.08}
HANGUL_DISAGREE = 0.04  # references whose values of one unit differ by more than this share are listed
HANGUL_PER_REFERENCE = ("units", "held_out", "cut_at", "left_out")  # how one reference was read, not a target
# The table of the hangul object in references/measuring.md, the contract the later steps read: per key, the units
# of its tagged list, the type of a name or a flag, or the keys of a group.
LENGTHS, RATIO = ("cap700", "em1000"), ("ratio",)
HANGUL_CLASS_SCHEMA = {
    "syllables": str, "face_w": LENGTHS, "face_h": LENGTHS, "face_w_cap": RATIO, "face_h_cap": RATIO,
    "face_w_h1": RATIO, "face_h_h1": RATIO, "aspect": RATIO, "cx": LENGTHS, "cy": LENGTHS, "side": LENGTHS,
    "side_asym": LENGTHS, "center_adv": RATIO, "adv": LENGTHS, "adv_cap": RATIO,
}
HANGUL_SCHEMA = {
    "classes": {cls: HANGUL_CLASS_SCHEMA for cls in L.HANGUL_CLASSES},
    "stem": LENGTHS, "stem_h1": RATIO, "stem_n": RATIO, "fixed_width": bool, "adv": LENGTHS, "adv_cap": RATIO,
    "report": {
        "overshoot": LENGTHS, "hstroke": LENGTHS, "overshoot_h1": RATIO, "hstroke_h1": RATIO, "contrast": RATIO,
        "pitch": {cls: ("cap700",) for cls in L.HANGUL_CLASSES}, "pitch_h1": {cls: RATIO for cls in L.HANGUL_CLASSES},
    },
}
ADVANCES = ("adv", "adv_cap")  # font-wide for fixed-width Hangul, per class for proportional Hangul, never both
TOLERANCES = {
    "text": {"stem": 3, "width_pct": 1.5, "para_pct": 1.5, "contrast": 0.05, "xh": 6, "side": 4, "min_gap": 6},
    "display": {"stem": 3, "width_pct": 1.0, "para_pct": 1.0, "contrast": 0.04, "xh": 4, "side": 3, "min_gap": 4},
    "ui": {"stem": 2, "width_pct": 1.5, "para_pct": 1.5, "contrast": 0.05, "xh": 5, "side": 4, "min_gap": 8},
}


def merge(ms, wts):
    out, conf, spread = {}, {}, {}

    def wmean(vals):
        tot = sum(w for _, w in vals)
        return sum(v * w for v, w in vals) / tot

    for key in SCALARS:
        vals = [(m[key], RANK.get(m.get("confidence", {}).get(key, "high"), 2) * w)
                for m, w in zip(ms, wts) if m.get(key) is not None]
        if not vals:
            continue
        out[key] = round(wmean(vals), 3 if abs(vals[0][0]) < 5 else 1)
        conf[key] = max((m.get("confidence", {}).get(key, "high") for m in ms if m.get(key) is not None), key=RANK.get)
        if len(vals) > 1:
            sp = max(v for v, _ in vals) - min(v for v, _ in vals)
            if key in DISAGREE and sp > DISAGREE[key]:
                spread[key] = [round(v, 3) for v, _ in vals]
    for group in ("widths", "sides"):
        keys = sorted({k for m in ms for k in (m.get(group) or {})})
        out[group] = {}
        for k in keys:
            prefix = "w_" if group == "widths" else "side_"
            vals = [(m[group][k], RANK.get(m.get("confidence", {}).get(prefix + k, "high"), 2) * w)
                    for m, w in zip(ms, wts) if (m.get(group) or {}).get(k) is not None]
            out[group][k] = round(wmean(vals), 1)
            if len(vals) > 1 and group == "widths":
                sp = max(v for v, _ in vals) / min(v for v, _ in vals) - 1
                if sp > 0.04:
                    spread["w_" + k] = [round(v, 1) for v, _ in vals]
    serif = [m.get("serif") for m in ms if m.get("serif") is not None]
    if serif:
        out["serif"] = st.mode(serif)
        if len(set(serif)) > 1:
            spread["serif"] = serif
    return out, conf, spread


def is_tag(e):
    v = e.get("value") if isinstance(e, dict) else None
    return (isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
            and e.get("unit") in L.UNITS and e.get("confidence", "high") in RANK)


def check_hangul(tree, where, schema=HANGUL_SCHEMA):
    """Refuses a reference's hangul object unless it holds only the keys of HANGUL_SCHEMA, and every number in it is
    a list of tagged values, each with a value and one of the units its key takes, at most one per unit: anything
    else cannot be merged by unit, or is not a target the later steps read."""
    for key, val in tree.items():
        at = f"{where}.{key}"
        if schema is HANGUL_SCHEMA and key in HANGUL_PER_REFERENCE:
            continue
        want = schema.get(key)
        if want is None:
            raise SystemExit(f"{at}: the hangul object has no such key; here it takes {', '.join(schema)} "
                             "(references/measuring.md)")
        if isinstance(want, type):
            if not isinstance(val, want):
                raise SystemExit(f"{at}: {val!r} is not a {want.__name__}")
        elif isinstance(want, dict):
            if not isinstance(val, dict):
                raise SystemExit(f"{at}: {val!r} is not an object of {', '.join(want)}")
            check_hangul(val, at, want)
        elif not (isinstance(val, list) and val and all(is_tag(e) for e in val)):
            raise SystemExit(f"{at}: {val!r} is not a list of values tagged with a unit, "
                             f'[{{"value": <number>, "unit": "<unit>"}}, ...]; its units are {", ".join(want)}')
        elif bad := sorted({e["unit"] for e in val} - set(want)):
            raise SystemExit(f"{at}: {', '.join(bad)} is not a unit of this key; its units are {', '.join(want)}")
        elif len({e["unit"] for e in val}) < len(val):
            raise SystemExit(f"{at}: {val!r} has two values in one unit")


def check_advances(h, where):
    """A reference's advances are in the one form its own fixed_width names: font-wide when fixed, per class when
    proportional."""
    per_class = [cls for cls, c in h.get("classes", {}).items() if set(ADVANCES) & set(c)]
    font_wide = set(ADVANCES) & set(h)
    if (per_class or font_wide) and "fixed_width" not in h:
        raise SystemExit(f"{where}: it has Hangul advances and no fixed_width to say which form they take")
    if h.get("fixed_width") and per_class:
        raise SystemExit(f"{where}: fixed_width is true, and {', '.join(per_class)} have advances of their own")
    if h.get("fixed_width") is False and font_wide:
        raise SystemExit(f"{where}: fixed_width is false, and it has a font-wide {', '.join(sorted(font_wide))}")


def one_advance_form(h):
    """The merged object keeps the advances of the form its fixed_width chose. A reference of the other form leaves
    its advances out; the references' answers are in spread.fixed_width."""
    if h.get("fixed_width"):
        for c in h.get("classes", {}).values():
            for key in ADVANCES:
                c.pop(key, None)
    else:
        for key in ADVANCES:
            h.pop(key, None)


def merge_tagged(vals, path, spread):
    """[(tagged values, weight)] -> one tagged value per unit, each the weighted mean of that unit's values."""
    by_unit = {}
    for entries, w in vals:
        for e in entries:
            by_unit.setdefault(e["unit"], []).append((e["value"], RANK.get(e.get("confidence"), 2) * w,
                                                      e.get("confidence", "high")))
    out = []
    for unit in L.UNITS:
        got = by_unit.get(unit)
        if not got:
            continue
        mean = sum(x * w for x, w, _ in got) / sum(w for _, w, _ in got)
        out.append({"value": round(mean, 4 if unit == "ratio" else 1), "unit": unit,
                    "confidence": max((c for _, _, c in got), key=RANK.get)})
        xs = [x for x, _, _ in got]
        if len(xs) > 1 and max(xs) - min(xs) > HANGUL_DISAGREE * max(abs(x) for x in xs):
            spread.setdefault(path, {})[unit] = xs
    return out


def merge_hangul(trees, path, spread):
    """[(hangul object or part of one, weight)] -> the merged object. Lists of tagged values merge unit by unit,
    objects merge key by key, a flag (fixed_width) takes the commoner answer, and names (syllables) are kept."""
    out = {}
    for key in dict.fromkeys(k for t, _ in trees for k in t if k not in HANGUL_PER_REFERENCE):
        vals = [(t[key], w) for t, w in trees if key in t]
        first = vals[0][0]
        if len({type(v) for v, _ in vals}) > 1:
            raise SystemExit(f"hangul.{path}{key}: the references disagree on what it is: "
                             + ", ".join(sorted({type(v).__name__ for v, _ in vals})))
        if isinstance(first, list):
            out[key] = merge_tagged(vals, path + key, spread)
        elif isinstance(first, dict):
            out[key] = merge_hangul(vals, f"{path}{key}.", spread)
        elif isinstance(first, bool):
            out[key] = st.mode(v for v, _ in vals)
            if len({v for v, _ in vals}) > 1:
                spread[path + key] = [v for v, _ in vals]
        else:
            out[key] = first
    return out


def category_of(t):
    """mono when every class is about one width, serif when the references have serifs, else sans."""
    w = [v for v in (t.get("widths") or {}).values() if v]
    if len(w) > 2 and max(w) / min(w) <= 1.02:
        return "mono"
    return "serif" if t.get("serif") else "sans"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("measurements", nargs="+")
    ap.add_argument("--family", required=True, help="the new family name. Never a reference's or the base's name")
    ap.add_argument("--use", choices=sorted(TOLERANCES), default="text")
    ap.add_argument("--scripts", default="latin")
    ap.add_argument("--category", choices=CATEGORIES)
    ap.add_argument("--style", action="append", default=[])
    ap.add_argument("--weight", action="append", default=[], help="FILE=N, how much one reference counts")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ms = [L.load_json(p) for p in a.measurements]
    for p, m in zip(a.measurements, ms):
        if m.get("hangul"):
            check_hangul(m["hangul"], f"{p}: hangul")
            check_advances(m["hangul"], f"{p}: hangul")
    wmap = {k: float(v) for k, v in (x.split("=") for x in a.weight)}
    wts = [wmap.get(p, wmap.get(os.path.basename(p), 1.0)) for p in a.measurements]
    t, conf, spread = merge(ms, wts)
    files = [m for m in ms if m.get("source") == "file"]
    scripts = [s.strip() for s in a.scripts.split(",") if s.strip()]
    hangul_refs = [(m["hangul"], w) for m, w in zip(ms, wts) if m.get("hangul")]
    styles = []
    for i, s in enumerate(a.style or ["Regular:400"]):
        parts = s.split(":")
        st_ = {"name": parts[0], "weight": int(parts[1]) if len(parts) > 1 else 400}
        if len(parts) > 2:
            st_["n_stem"] = float(parts[2])
        elif i == 0 and t.get("n_stem"):
            st_["n_stem"] = t["n_stem"]
        styles.append(st_)
    out = {
        "family": a.family,
        "use": a.use,
        "category": a.category or category_of(t),
        "scripts": scripts,
        "styles": styles,
        "targets": t,
        "confidence": conf,
        "spread": spread,
        "tolerances": TOLERANCES[a.use],
        "cap_em": round(st.mean(caps), 1) if (caps := [m["cap_em"] for m in files if m.get("cap_em")]) else None,
        "vmetrics": files[0].get("vmetrics") if files else None,
        "sources": [{"file": m.get("file"), "source": m.get("source")} for m in ms],
        "units": "cap-normalised: cap height 700",
    }
    if hangul_refs and "korean" in scripts:
        hspread = {}
        out["hangul"] = merge_hangul(hangul_refs, "", hspread)
        one_advance_form(out["hangul"])
        out["hangul"]["spread"] = hspread
    L.save_json(out, a.out)
    print(f"targets for {a.family!r} ({a.use}, {out['category']}) from {len(ms)} reference(s): {a.out}")
    for k in SCALARS + ["serif"]:
        if k in t:
            print(f"  {k:13s} {t[k]!s:>9}  {conf.get(k, '')}")
    print("  widths", t.get("widths"))
    print("  sides ", t.get("sides"))
    if "hangul" in out:
        print("\n".join(L.hangul_summary(out["hangul"])))
        if out["hangul"]["spread"]:
            print("  hangul references disagree on:", ", ".join(f"{k} {v}" for k, v in out["hangul"]["spread"].items()))
    elif hangul_refs:
        print("  Hangul measurements left out: --scripts has no korean")
    if spread:
        print("  references disagree on:", ", ".join(f"{k} {v}" for k, v in spread.items()))
    low = [k for k, v in conf.items() if v == "low"]
    if low:
        print("  low confidence:", ", ".join(low))


if __name__ == "__main__":
    main()

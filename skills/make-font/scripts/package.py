# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "brotli"]
# ///
"""Name, license and package the spaced fonts: TTF, WOFF2, OFL.txt, FONTLOG.txt, a CSS file, a README and the
package log.

  uv run package.py <Family-Regular.ttf> [<Family-Medium.ttf> ...] --targets targets.json
      --base-json base.json --fit-log build/fit-log.json --space-log build/*.space-log.json
      --holder "Name for the copyright line" --out-dir DIR [--replace]
      [--vendor ABCD] [--version 1.000] [--designer "..."] [--url https://...] [--web-unicodes "U+0000-00FF,..."]

Only fonts that came through the chain are packaged. chain.verify_build, the check check_font.py runs too, goes
first: base.json against the base and its OFL text; the fit log made from that base.json, from the base alone
and this targets.json, with a subset that the base gives again, byte for byte, with the recorded arguments; and
every space log made from that base.json and this targets.json, from fonts the fit log wrote. Then every font
given here must be an output of a space log. Unspaced fits (.fit.ttf) are skipped, and nothing left is a
refusal, and so are two fonts that would package as one file (two spaced fonts of one style): every output name
is decided before anything is written. --space-log takes one or more files, and may repeat. Each input is read
once (chain.Files): the bytes whose sha256 is checked are the bytes renamed, converted and compared, and the
package log's sha256 values are of those bytes and of the TTF and WOFF2 bytes written.

DIR may not be, or hold, any input (base.json, targets.json, a log, a font, the base or its licence), by the path
given, by that path's folder resolved, or by the file it links to, so --replace never removes a link to an input.
The package is built in a temporary folder beside DIR, private (0700) until it is published. Each TTF and WOFF2
there is checked against the chain: a plain TrueType file with the subset's glyph order and character map, and
the outlines and advances of the spaced font it came from. The package log, DIR/package-log.json, is written into
the same folder: base.json's sha256, the spaced fonts as inputs, the TTF and WOFF2 as outputs (each with the
sha256 of the spaced font it came from, under "from"), targets.json and
the fit and space logs, each by file name and sha256, and under "webfonts" each WOFF2's size in bytes, its glyph
count and the seconds it took to build. There is one WOFF2 per weight, never split by range. One rename then publishes the folder and its log together,
and only then does the folder get the usual folder mode (0777 less the umask). An existing, non-empty DIR is
refused unless --replace is given; then the old package is moved aside, and deleted only once the new one is in
place.

The new family name comes from targets.json. The script refuses a name that contains the base family's name or
any Reserved Font Name of the base, because the OFL forbids a modified version to use them.

Name table: the base's copyright line stays (the OFL requires it), ours is added under it. The trademark
record (ID 7) and every other base name record go, except the names of stylistic sets. ID 9 names the modifier
only; the base's designers are credited in FONTLOG.txt. IDs 13 and 14 carry the OFL notice and URL. OS/2 gets
the vendor ID, the weight class and the style bits.

OFL.txt is the base's licence file, byte for byte, with our copyright line added at the top. FONTLOG.txt lists
the base, what changed and why, from the fit and space logs, and the provenance record: the base's sha256 and
source, and the person's approval in their own words.
"""
import argparse
import datetime
import io
import os
import re
import shutil
import sys
import tempfile
import time

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontTools import subset  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402

import chain as C  # noqa: E402
import fontlib as L  # noqa: E402

OFL_NOTICE = ("This Font Software is licensed under the SIL Open Font License, Version 1.1. "
              "This license is available with a FAQ at: https://openfontlicense.org")
OFL_URL = "https://openfontlicense.org"
WEIGHT_NAMES = {100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular", 500: "Medium", 600: "SemiBold",
                700: "Bold", 800: "ExtraBold", 900: "Black"}
FALLBACK = {"sans": "sans-serif", "serif": "serif", "mono": "monospace"}


LEGACY_ACCENTS = "`\u00a8\u00af\u00b4\u00b8\u02c6\u02c7\u02d8\u02d9\u02da\u02db\u02dc\u02dd"


def fix_legacy_accents(f):
    """Spacing accents (U+00B4 and friends) are base glyphs, not marks. Some bases class them as marks in GDEF,
    which makes shapers zero their width. Returns the glyphs changed."""
    if "GDEF" not in f or not f["GDEF"].table.GlyphClassDef:
        return []
    cd = f["GDEF"].table.GlyphClassDef.classDefs
    cm = f.getBestCmap()
    out = []
    for ch in LEGACY_ACCENTS:
        n = cm.get(ord(ch))
        if n and cd.get(n) == 3:
            cd[n] = 1
            out.append(n)
    return out


def ps_name(family, style):
    return re.sub(r"[^A-Za-z0-9]", "", family) + "-" + re.sub(r"[^A-Za-z0-9]", "", style)


def plan_outputs(fonts, T):
    """Each font's style and the TTF and WOFF2 names it packages as, decided before anything is written: a font
    matches the style its filename ends in (-<Style>), never the order a glob gives. Refuses a font that matches no
    style, and two fonts that would package as one file, which would leave only the second."""
    plan, taken = [], {}
    for p in fonts:
        stem = os.path.splitext(os.path.basename(p))[0].lower()
        style = next((s for s in T["styles"]
                      if stem.endswith("-" + re.sub(r"[^A-Za-z0-9]", "", s["name"]).lower())), None)
        if style is None:
            raise C.Refused(f"{p}: its name does not end in -<Style> for any style in targets.json "
                            f"({[s['name'] for s in T['styles']]})")
        ps = ps_name(T["family"], style["name"])
        names = (f"ttf/{ps}.ttf", f"webfonts/{ps}.woff2")
        for n in names:
            if n.lower() in taken:
                raise C.Refused(f"{taken[n.lower()]} and {p} would both package as {n} (style {style['name']}). "
                                "Give one spaced font per style.")
            taken[n.lower()] = p
        plan.append((p, style, ps) + names)
    return plan


def check_name(family, base_family, rfn):
    bad = [w for w in [base_family] + rfn if w and w.lower() in family.lower()]
    bits = [w for w in re.findall(r"[A-Za-z]{4,}", base_family)
            if w.lower() not in ("serif", "sans", "mono", "display", "text", "grotesk", "slab")]
    bad += [w for w in bits if w.lower() in family.lower()]
    if bad:
        raise SystemExit(f"refused: {family!r} uses {sorted(set(bad))}, the base's name or a Reserved Font Name. "
                         "Pick a new family name and set it in targets.json.")
    return rfn


def set_names(f, bnames, family, style, weight, a, version):
    ps = ps_name(family, style)
    ribbi = style in ("Regular", "Bold", "Italic", "Bold Italic")
    year = datetime.date.today().year
    recs = {
        0: f"{bnames.get(0, '').strip()}\nCopyright {year} {a.holder} (modifications)".strip(),
        1: family if ribbi else f"{family} {style}",
        2: style if ribbi else "Regular",
        3: f"{version:.3f};{a.vendor};{ps}",
        4: f"{family} {style}",
        5: f"Version {version:.3f}",
        6: ps,
        8: a.holder,
        9: f"{a.designer or a.holder} (modifications)",
        13: OFL_NOTICE,
        14: OFL_URL,
        16: family,
        17: style,
    }
    if a.url:
        recs[11] = a.url
    keep = set()
    for tag in ("GSUB", "GPOS"):
        if tag in f:
            for fr in f[tag].table.FeatureList.FeatureRecord:
                p = fr.Feature.FeatureParams
                if p is not None and hasattr(p, "UINameID"):
                    keep.add(p.UINameID)
    name = f["name"]
    name.names = [r for r in name.names if r.nameID in keep and r.platformID == 3]
    for nid, s in recs.items():
        name.setName(s, nid, 3, 1, 0x409)
    os2 = f["OS/2"]
    os2.achVendID = a.vendor.ljust(4)[:4]
    os2.usWeightClass = weight
    sel = os2.fsSelection & (1 << 7)  # keep USE_TYPO_METRICS
    if "Bold" not in style and "Italic" not in style:
        sel |= 1 << 6  # REGULAR: name ID 2 is Regular for every upright style that is not Bold
    if style == "Bold":
        sel |= 1 << 5
    os2.fsSelection = sel
    f["head"].macStyle = 1 if style == "Bold" else 0
    f["head"].fontRevision = version
    f["post"].italicAngle = 0
    return ps


def provenance(rec, fit):
    """The record base.json keeps, as plain text: hashes, source and the person's own words. No local paths."""
    font, lic, src, appr = rec["font"], rec["license"], rec["source"], rec["approval"]
    where = {"google-fonts": f"Google Fonts, {src.get('url')}",
             "manifest": f"manifest entry {src.get('manifest_entry')}",
             "local": "a file the requester supplied"}[src["kind"]]
    sub = (fit or {}).get("subset") or {}
    lines = ["Provenance", "-" * 10,
             f"Base font: {os.path.basename(font['file'])}, sha256 {font['sha256']}, from {where}.",
             f"Licence: {lic['id']}, {os.path.basename(lic['file'])} sha256 {lic['sha256']}.",
             f"Name ID 13 of the base: {lic['name_id_13']}",
             f"Reserved Font Names: {', '.join(lic['reserved_font_names']) or 'none'}.",
             f"Approved by the requester, recorded {appr['recorded_at']}. Question and answer, verbatim:",
             "  Q: " + appr["question"].replace("\n", "\n     "),
             "  A: " + appr["answer"].replace("\n", "\n     ")]
    if sub:
        lines.append(f"Fitted from a subset of the base made by the build itself, sha256 {sub['sha256']}.")
    lines += ["The approval is the requester's statement; the build cannot check it. Every step checked the base's",
              "and the licence's sha256 against this record, and took only fonts the previous step wrote.", ""]
    return lines


def fontlog(T, bn, base, rec, fit, spaces, version, a, files):
    today = datetime.date.today().isoformat()
    lines = [f"FONTLOG for {T['family']}", "", "Basic font information", "-" * 22,
             f"{T['family']} is a modified version of {bn.get(16) or bn.get(1)}, released under the SIL Open Font "
             "License 1.1. Its proportions, widths and spacing were fitted to measurements of typefaces the "
             "requester chose. Every outline comes from the open base. No outline, point or kerning pair was taken "
             "from any other font.", "",
             f"Use: {T.get('use')}. Scripts: {', '.join(T.get('scripts', []))}.", "",
             "Files: " + ", ".join(files), "", "ChangeLog", "-" * 9, f"{today} (version {version:.3f})"]
    n = 1
    lines.append(f"  {n}. Base: {os.path.basename(rec['font']['file'])}, axes {L.axes_of(base)}.")
    if fit:
        for s in fit["styles"]:
            n += 1
            lines.append(f"  {n}. {s['style']['name']}: y coordinates from {s['y_location']}; x per width class from "
                         f"its own location, factors {s['factors']}.")
            last = s["iterations"][-1]
            lines.append(f"     Width fit: {last['iteration']} pass(es), error % by class {last['error_pct']}.")
            if s.get("stretch_limit_hit"):
                lines.append(f"     Stretch limit reached for {s['stretch_limit_hit']}.")
    for sp in spaces:
        n += 1
        lines.append(f"  {n}. Spacing ({sp.get('input')}): side moves {sp.get('side_moves')}, track {sp.get('track', 0)}, "
                     f"{len(sp.get('guard', []))} pairs opened by the collision guard.")
    n += 1
    lines.append(f"  {n}. Renamed to {T['family']}, trademark record removed, OFL notice set, overlaps removed, "
                 "variation tables removed, spacing accents classed as base glyphs in GDEF.")
    lines += ["", "Acknowledgements", "-" * 16, f"Original design: {bn.get(9, 'see the copyright line')}.",
              f"Original copyright: {bn.get(0, '')}", f"Modifications: {a.designer or a.holder}.", ""]
    lines += provenance(rec, fit)
    return "\n".join(lines)


def css(family, faces):
    out = []
    for ps, weight in faces:
        out.append(f"""@font-face {{
  font-family: "{family}";
  src: url("webfonts/{ps}.woff2") format("woff2");
  font-weight: {weight};
  font-style: normal;
  font-display: swap;
}}""")
    return "\n".join(out) + "\n"


def drawings(font):
    """Every glyph as decomposed pen strokes with its advance, keyed by glyph name."""
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    gs, hm = font.getGlyphSet(), font["hmtx"].metrics
    out = {}
    for n in font.getGlyphOrder():
        pen = DecomposingRecordingPen(gs)
        gs[n].draw(pen)
        out[n] = (pen.value, hm[n][0])
    return out


def verify(built, subset_font):
    """Each packaged TTF and WOFF2 against the chain: the subset's glyph order and character map, and the spaced
    font's outlines and advances. built: [(spaced font as read, TTF name, TTF bytes, WOFF2 name, WOFF2 bytes)]."""
    order, cmap = subset_font.getGlyphOrder(), subset_font.getBestCmap()
    for src_b, ttf_name, ttf_data, woff_name, woff_data in built:
        src, ttf, woff = src_b.font(), TTFont(io.BytesIO(ttf_data)), TTFont(io.BytesIO(woff_data))
        if ttf.flavor is not None or ttf_data[:4] not in C.TRUETYPE:
            raise C.Refused(f"{ttf_name} is not a plain TrueType file (flavor {ttf.flavor!r})")
        if ttf.getGlyphOrder() != order or ttf.getBestCmap() != cmap:
            raise C.Refused(f"{ttf_name}: glyph order or character map differs from the subset fit_font.py recorded")
        ds, dt = drawings(src), drawings(ttf)
        diff = [n for n in order if ds.get(n) != dt.get(n)]
        if diff:
            raise C.Refused(f"{ttf_name}: {len(diff)} glyphs differ from {src_b.path} ({', '.join(diff[:6])})")
        if woff.flavor != "woff2":
            raise C.Refused(f"{woff_name} is not WOFF2")
        dw, wcmap = drawings(woff), woff.getBestCmap()
        bad = [u for u, g in wcmap.items() if cmap.get(u) is None or dw[g] != dt[cmap[u]]]
        if bad:
            raise C.Refused(f"{woff_name}: {len(bad)} characters differ from the TTF "
                            f"({', '.join(f'U+{u:04X}' for u in bad[:6])})")


def folder_mode():
    """The mode os.mkdir gives a folder: 0777 less the umask."""
    umask = os.umask(0)
    os.umask(umask)
    return 0o777 & ~umask


def publish(private_fd, out_dir, replace):
    """Move the finished package, its log inside it, into place with one rename. With replace, the package already
    there is moved aside first and deleted only once the new one is in place; if the new one cannot be moved in,
    the old one goes back.

    The package is staged as STAGED inside an owner-only (0700) folder that mkdtemp made next to out_dir, and every
    rename here starts from that folder's descriptor, opened when it was made. Another user who can write to the
    parent folder can rename or replace the private folder's entry, but cannot reach inside it, and the rename
    still takes the verified STAGED child of the folder the descriptor holds. The package gets the usual folder mode
    only once it is in place, through a descriptor to that same child."""
    fd = os.open(STAGED, os.O_RDONLY | os.O_DIRECTORY, dir_fd=private_fd)
    try:
        if not (replace and os.path.isdir(out_dir) and os.listdir(out_dir)):
            os.rename(STAGED, out_dir, src_dir_fd=private_fd)  # onto a missing or empty folder
            os.fchmod(fd, folder_mode())
            return
        os.rename(out_dir, "old", dst_dir_fd=private_fd)
        try:
            os.rename(STAGED, out_dir, src_dir_fd=private_fd)
        except OSError:
            os.rename("old", out_dir, src_dir_fd=private_fd)
            raise
        os.fchmod(fd, folder_mode())
    finally:
        os.close(fd)


STAGED = "package"


def discard_staging(private, out_dir):
    """Delete the private staging folder, unless --replace moved the previous package into it and neither package
    got back to out_dir (both renames failed, or the run stopped between them). Returns the kept backup's path."""
    backup = os.path.join(private, "old")
    if os.path.lexists(backup) and not os.path.lexists(out_dir):
        return backup
    shutil.rmtree(private, ignore_errors=True)
    return None


def inside(path, folder):
    """True when path is folder or lies in it, read every way --replace could reach it: the path as given, its
    folder's links resolved (where its own entry is), and every link resolved (the file it leads to). The folder is
    read as given and resolved too. A link inside the package to an input outside is inside: replacing the package
    would delete it."""
    given = os.path.abspath(path)
    paths = {given, os.path.join(os.path.realpath(os.path.dirname(given)), os.path.basename(given)),
             os.path.realpath(path)}
    folders = {os.path.abspath(folder), os.path.realpath(folder)}
    return any(p == f or p.startswith(f.rstrip(os.sep) + os.sep) for p in paths for f in folders)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fonts", nargs="+")
    ap.add_argument("--targets", required=True)
    ap.add_argument("--base-json", help="base.json from record_base.py (required)")
    ap.add_argument("--fit-log", help="fit-log.json from fit_font.py (required)")
    ap.add_argument("--space-log", action="extend", nargs="+", default=[],
                    help="the .space-log.json of every font, one or more after the flag; the flag may repeat "
                         "(required)")
    ap.add_argument("--holder", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--replace", action="store_true",
                    help="replace a non-empty --out-dir; the old package is deleted only once the new one is in place")
    ap.add_argument("--vendor", default="NONE")
    ap.add_argument("--version", type=float, default=1.0)
    ap.add_argument("--designer")
    ap.add_argument("--url")
    ap.add_argument("--web-unicodes", help="subset the WOFF2 files to these ranges; default keeps every glyph")
    a = ap.parse_args()
    files = C.Files()
    b = C.verify_build(files, a.base_json, a.targets, a.fit_log, a.space_log)
    rec, base_sha = b.rec, b.base_sha
    fonts = [p for p in a.fonts if not p.endswith(".fit.ttf")]
    for p in [p for p in a.fonts if p.endswith(".fit.ttf")]:
        print(f"skip {p}: an unspaced fit; package the spaced file step 7 wrote")
    if not fonts:
        raise C.Refused("no spaced font to package: every file given is an unspaced fit (.fit.ttf). Give the "
                        "fonts space_font.py wrote.")
    spaced = [C.require_output(files, p, b.spaces, "--space-log", "space_font.py") for p in fonts]
    out_dir = os.path.abspath(a.out_dir)
    held = [p for p in [*a.fonts, *files.paths()] if inside(p, out_dir)]
    if held:
        raise C.Refused(f"--out-dir {a.out_dir} is or holds an input, {held[0]}; publishing there would replace it. "
                        "Pick an --out-dir outside the build folder.")
    if os.path.exists(out_dir) and not os.path.isdir(out_dir):
        raise C.Refused(f"--out-dir {a.out_dir} is a file, not a folder")
    if os.path.isdir(out_dir) and os.listdir(out_dir) and not a.replace:
        raise C.Refused(f"--out-dir {a.out_dir} already holds files. Remove it, pick a new --out-dir, or pass "
                        "--replace.")

    T = b.T
    base = b.approved.font.font()
    bn = L.english_names(base)
    bfam = bn.get(16) or bn.get(1)
    licence = b.approved.licence.data
    rfn = list(dict.fromkeys(rec["license"]["reserved_font_names"] + L.reserved_font_names(bn.get(0) or "")))
    check_name(T["family"], bfam, rfn)
    plan = plan_outputs(fonts, T)

    parent = os.path.dirname(out_dir)
    os.makedirs(parent, exist_ok=True)
    private = tempfile.mkdtemp(prefix=".package-", dir=parent)  # owner-only; publish() renames out of it by descriptor
    private_fd = os.open(private, os.O_RDONLY | os.O_DIRECTORY)
    tmp = os.path.join(private, STAGED)
    os.mkdir(tmp, 0o700)
    try:
        faces, listed, built, webfonts = [], [], [], []
        for (p, style, ps, ttf_name, woff_name), src in zip(plan, spaced):
            f = src.font()
            set_names(f, bn, T["family"], style["name"], style["weight"], a, a.version)
            fixed = fix_legacy_accents(f)
            if fixed:
                print(f"{style['name']}: {len(fixed)} spacing accents reclassed from mark to base in GDEF")
            ttf_data = C.font_bytes(f)
            started = time.perf_counter()
            w = TTFont(io.BytesIO(ttf_data))
            opts = subset.Options()
            opts.layout_features = ["*"]
            opts.name_IDs = ["*"]
            opts.name_languages = ["*"]
            opts.notdef_outline = True
            opts.glyph_names = False
            opts.flavor = "woff2"
            sub_ = subset.Subsetter(opts)
            if a.web_unicodes:
                sub_.populate(unicodes=subset.parse_unicodes(a.web_unicodes))
            else:
                sub_.populate(glyphs=w.getGlyphOrder())
            sub_.subset(w)
            woff_data = C.font_bytes(w, "woff2")
            seconds = time.perf_counter() - started
            for name, data in ((ttf_name, ttf_data), (woff_name, woff_data)):
                files.write(os.path.join(tmp, name), data)
            built.append((src, ttf_name, ttf_data, woff_name, woff_data))
            faces.append((ps, style["weight"]))
            listed += [ttf_name, woff_name]
            webfonts.append({"style": style["name"], "file": woff_name, "bytes": len(woff_data),
                             "glyphs": len(w.getGlyphOrder()), "seconds": round(seconds, 1)})
            print(f"{style['name']}: {ttf_name} ({len(f.getGlyphOrder())} glyphs, {len(ttf_data)} bytes), {woff_name} "
                  f"({len(w.getGlyphOrder())} glyphs, {len(woff_data)} bytes, {seconds:.1f} s)")
        verify(built, b.subset)
        year = datetime.date.today().year
        with open(os.path.join(tmp, "OFL.txt"), "wb") as fh:
            fh.write(f"Copyright {year} {a.holder} (modifications)\n".encode("utf-8") + licence)
        listed += ["OFL.txt", "FONTLOG.txt", "fonts.css", "README.md", "package-log.json"]
        with open(os.path.join(tmp, "FONTLOG.txt"), "w", encoding="utf-8") as fh:
            fh.write(fontlog(T, bn, base, rec, b.fit, b.spaces, a.version, a, listed))
        with open(os.path.join(tmp, "fonts.css"), "w", encoding="utf-8") as fh:
            fh.write(css(T["family"], faces))
        category = T.get("category") or ("serif" if T["targets"].get("serif") else "sans")
        weights = ", ".join(f"{s['name']} {s['weight']}" for s in T["styles"][:len(fonts)])
        readme = f"""# {T['family']}

A {T.get('use', 'text')} typeface in {len(fonts)} weight{'s' if len(fonts) > 1 else ''} ({weights}), for {', '.join(T.get('scripts', []))}.

{T['family']} is a modified version of an open font, fitted to measured proportions, widths and spacing. Every
outline comes from that base. FONTLOG.txt lists what changed.

## Files

- `ttf/`: desktop fonts. Install by opening the file.
- `webfonts/`: WOFF2 files for the web, with `fonts.css` beside them.
- `OFL.txt`: the licence. `FONTLOG.txt`: the base and every change.
- `package-log.json`: the provenance chain, by sha256: the approval record, the build logs, the fonts packaged
  and the files made from them.

## Use on the web

Copy `webfonts/` and `fonts.css` next to your stylesheet, then:

```css
@import url("fonts.css");
body {{ font-family: "{T['family']}", {FALLBACK.get(category, 'sans-serif')}; }}
```

## Licence

SIL Open Font License 1.1. You may use, embed, modify and redistribute the fonts, and sell them only as part of
a larger work. A modified version keeps this licence and the copyright lines, and needs a new name.
{('Reserved Font Names of the base: ' + ', '.join(rfn) + '.') if rfn else 'The base declares no Reserved Font Name.'}
"""
        with open(os.path.join(tmp, "README.md"), "w", encoding="utf-8") as fh:
            fh.write(readme)
        # The log goes in the package, by file name and sha256 (no builder paths), so one rename publishes both.
        # Every sha256 is of the bytes this run read or wrote.
        name = os.path.basename
        chain = {"base_json_sha256": base_sha, "inputs": [s.entry(name(s.path)) for s in spaced],
                 "outputs": [{"file": n, "sha256": C.sha256_bytes(d), "from": src.sha256}
                             for src, tn, td, wn, wd in built for n, d in ((tn, td), (wn, wd))],
                 "targets": b.targets.entry(name(a.targets))}
        L.save_json({"chain": chain, "fit_log": b.fit.blob.entry(name(a.fit_log)),
                     "space_logs": [sp.blob.entry(name(p)) for p, sp in zip(a.space_log, b.spaces)],
                     "files": listed, "webfonts": webfonts}, os.path.join(tmp, "package-log.json"))
        publish(private_fd, out_dir, a.replace)
    finally:
        os.close(private_fd)
        kept = discard_staging(private, out_dir)
        if kept:
            print(f"the previous package was kept at {kept}; move it back to {out_dir}", file=sys.stderr)
    print(f"verified against the chain, wrote {a.out_dir}: " + ", ".join(listed))


if __name__ == "__main__":
    main()

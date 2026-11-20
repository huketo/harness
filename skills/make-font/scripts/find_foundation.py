# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "brotli", "uharfbuzz"]
# ///
"""Find the OFL-1.1 variable font closest to targets.json, to build on.

  uv run find_foundation.py targets.json --cache DIR --out shortlist.json
      [--category serif] [--shortlist 8] [--families "Family A,Family B"] [--local DIR ...] [--offline]

Two passes.
1. Coarse: the Fontsource catalogue (api.fontsource.org) lists every Google Fonts family with its category,
   licence and scripts. Families under the OFL, in the category, that cover every script in targets.json and
   have a variable font in google/fonts are kept. One small Latin WOFF2 per family, near weight 400, is measured
   and ranked.
2. Fine: the best --shortlist families are downloaded whole from the google/fonts GitHub repository, with their
   OFL.txt. A variable font is solved on its weight axis so the n stem meets the target, and sampled across
   its optical-size axis. A width axis makes width gaps cheap, but only in the direction it can move: an axis
   that only narrows does not help a font that is too narrow.

With korean in the targets' scripts neither pass runs: the bases are the fonts pinned in bases.json beside this
script (URL, version, sha256, Reserved Font Names), since a Latin coarse file cannot measure Hangul. Each is fetched
to --cache, skipped unless it has the pinned sha256 and qualifies again (a TrueType variable font with every modern
syllable and the basic Latin letters and figures, an OFL.txt and name ID 13 that record_base.py accepts), and ranked
by the same distance plus the Hangul ratios (fontlib.hangul_distance). --local and --families are refused there.

Only the SIL Open Font License 1.1 is kept, and only TrueType (glyf) variable fonts: the fit needs both.
--local adds font files you already have; each needs the OFL notice in name ID 13 and is a candidate only. Put
its OFL.txt beside it, since the approval step records that file.
--families skips the coarse pass and measures only those families (still OFL only).
--offline reads only the cache and --local: nothing is downloaded, and a file missing from the cache is skipped.
GITHUB_TOKEN, when set, is sent over HTTPS to api.github.com and raw.githubusercontent.com only, never printed.
Every hop of a redirect is checked again, through urllib and through the curl fallback alike: a hop to any other
origin goes without it. A 403 or 429 from GitHub stops the search with the remaining limit, the reset time and
what to do.
Downloads go to --cache and are only read, never run. The ranking is a distance: each number's gap to the
target, divided by what counts as a small gap, squared, weighted, summed, square-rooted. The score adds a
penalty for missing axes: 0 with wdth and wght, 0.5 to 0.75 with wght alone. Lower is closer. Math, symbol and
icon families are skipped, and so are families whose main script is not one asked for.

The shortlist is for the person to choose from. Record their answer with record_base.py before fitting.
"""
import argparse
import glob
import io
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontTools.ttLib import TTFont  # noqa: E402

import chain as C  # noqa: E402
import fontlib as L  # noqa: E402

UA = {"User-Agent": "make-font-skill/1.0"}
CATALOG = "https://api.fontsource.org/v1/fonts"
TREE = "https://api.github.com/repos/google/fonts/git/trees/main?recursive=1"
RAW = "https://raw.githubusercontent.com/google/fonts/main/"
COARSE = "https://cdn.jsdelivr.net/fontsource/fonts/{id}@latest/latin-{w}-normal.woff2"
# The origins (scheme, host, port) GITHUB_TOKEN may be sent to. Every hop of a redirect is checked against it.
AUTH_ORIGINS = frozenset({("https", "api.github.com", 443), ("https", "raw.githubusercontent.com", 443)})
OPEN = ("OFL-1.1", "OFL")
USEFUL_AXES = ("wdth", "wght", "opsz", "GRAD")
SKIP_WORDS = ("Math", "Symbols", "Icons", "Emoji", "Barcode")
STRETCH = 0.03  # fit_font.py's default --max-stretch: a width gap beyond it needs the axis
LICENCE_FILES = ("OFL.txt", "OFL-1.1.txt", "LICENSE.txt", "LICENSE", "OFL")


class FetchError(Exception):
    pass


def safe(name):
    """A catalogue id or family as a cache file name: letters, digits, _ and - only, so no entry can leave --cache."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(name))


# ------------------------------------------------------------------ downloads
def origin(url):
    u = urllib.parse.urlsplit(url)
    return (u.scheme.lower(), (u.hostname or "").lower(), u.port or {"https": 443, "http": 80}.get(u.scheme.lower()))


def auth_headers(url, env=os.environ):
    """The GitHub token, for the GitHub API and raw hosts over HTTPS only."""
    token = env.get("GITHUB_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token and origin(url) in AUTH_ORIGINS else {}


def limit_advice(status, headers, env=os.environ):
    """What a 403 or 429 means and what to do. Reads the rate-limit headers; never the token."""
    def get(k):
        v = headers.get(k) if headers is not None else None
        return v.strip() if isinstance(v, str) and v.strip() else None
    parts = [f"HTTP {status}"]
    lim, rem, reset, retry = (get(k) for k in ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset",
                                               "Retry-After"))
    if rem is not None:
        parts.append(f"{rem} of {lim or '?'} requests left")
    if reset and reset.isdigit():
        parts.append("the limit resets at " + time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(int(reset))))
    if retry:
        parts.append(f"retry after {retry} s")
    fix = ("GITHUB_TOKEN is set, so this is that token's limit: wait for the reset" if env.get("GITHUB_TOKEN") else
           "set GITHUB_TOKEN to a GitHub token (no scopes needed) for 5,000 requests an hour")
    return "; ".join(parts) + f". To go on: {fix}, or run with --offline on a filled --cache."


REDIRECTS = (301, 302, 303, 307, 308)
MAX_HOPS = 10


def curl_command(url, path, header_file, env=os.environ):
    """curl arguments and the config it reads on stdin, for one hop: curl follows no redirect itself. Headers go
    through the config, so a token never shows in the process list. --disable, which curl honours only as its
    first argument, keeps it from reading the user's .curlrc, where trace-ascii would log the token and
    location-trusted would send it past the hop check: the config on stdin is the only one."""
    argv = ["curl", "--disable", "-sS", "--proto", "=http,https", "--config", "-", "-A", UA["User-Agent"], "-o", path,
            "-D", header_file, "-w", "%{http_code} %{redirect_url}", url]
    config = "".join(f'header = "{k}: {v}"\n' for k, v in auth_headers(url, env).items())
    return argv, config


def curl_fetch(url, path):
    """Download through curl, for a Python without CA certificates. Each redirect hop is a new curl run whose
    headers come from auth_headers for that hop's URL, so the token goes only where urllib would send it."""
    with tempfile.TemporaryDirectory() as td:
        hdr = os.path.join(td, "headers")
        for _ in range(MAX_HOPS + 1):
            argv, config = curl_command(url, path, hdr)
            r = subprocess.run(argv, input=config, capture_output=True, text=True)
            status, _, nxt = r.stdout.strip().partition(" ")
            code = int(status) if status.isdigit() else 0
            if code in REDIRECTS and nxt.strip():
                url = urllib.parse.urljoin(url, nxt.strip())
                continue
            if code == 200:
                return
            headers = {}
            if os.path.exists(hdr):
                for line in open(hdr, encoding="latin-1"):
                    k, _, v = line.partition(":")
                    if v:
                        headers[k.strip()] = v.strip()
            if os.path.exists(path):
                os.remove(path)
            if code in (403, 429):
                raise FetchError(f"{url}: refused, " + limit_advice(code, {k.title(): v for k, v in headers.items()}))
            raise FetchError(f"{url}: HTTP {code or 'error'} {r.stderr.strip()[:200]}")
    if os.path.exists(path):
        os.remove(path)
    raise FetchError(f"{url}: more than {MAX_HOPS} redirects")


class AuthRedirect(urllib.request.HTTPRedirectHandler):
    """Python's redirect handler copies the request's headers to the next hop, a token included. This one takes
    the token off every hop and sets it again only where auth_headers allows it for that hop's URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None:
            for held in (new.headers, new.unredirected_hdrs):
                for k in [k for k in held if k.lower() == "authorization"]:
                    del held[k]
            for k, v in auth_headers(new.full_url).items():
                new.add_unredirected_header(k, v)
        return new


def fetch(url, path, offline=False):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    if offline:
        raise FetchError(f"{url}: not in the cache, and --offline downloads nothing")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    part = path + ".part"
    try:
        ctx = None
        try:
            import certifi
            import ssl
            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            pass
        req = urllib.request.Request(url, headers=UA)
        for k, v in auth_headers(url).items():
            req.add_unredirected_header(k, v)
        opener = urllib.request.build_opener(AuthRedirect, urllib.request.HTTPSHandler(context=ctx))
        with opener.open(req, timeout=60) as r:
            data = r.read()
        with open(part, "wb") as fh:
            fh.write(data)
    except urllib.error.HTTPError as e:
        e.close()
        if e.code in (403, 429):
            raise FetchError(f"{url}: refused, " + limit_advice(e.code, e.headers))
        raise FetchError(f"{url}: HTTP {e.code}")
    except urllib.error.URLError:
        # Some Python installs ship without CA certificates. curl uses the system's.
        curl_fetch(url, part)
    os.replace(part, path)
    return path


# ------------------------------------------------------------------ licences and candidates
def licence_of(font, ofl_text=None):
    """OFL-1.1 when name ID 13 carries the OFL notice and the licence text, if given, is the OFL 1.1. Anything else
    (Apache-2.0 included) is None: not a base."""
    n = L.english_names(font)
    ok = L.is_ofl_11_notice(n.get(13)) and (ofl_text is None or L.is_ofl_11_text(ofl_text))
    return {"licence": "OFL-1.1" if ok else None,
            "reserved_font_names": L.reserved_font_names(ofl_text or ""),
            "copyright": n.get(0), "trademark": n.get(7)}


def candidates(catalog, category, scripts, wanted=()):
    """Catalogue families that may be a base: Google Fonts, OFL, and either asked for by name or in the category
    with every script."""
    ofl = [c for c in catalog if c.get("type") == "google" and c.get("license") in OPEN]
    if wanted:
        return [c for c in ofl if c["family"].lower() in wanted]
    return [c for c in ofl if c.get("category") == category and scripts <= set(c.get("subsets", []))
            and "normal" in c.get("styles", []) and c.get("defSubset") in scripts
            and not any(w in c["family"] for w in SKIP_WORDS)]


def licence_beside(path):
    for name in LICENCE_FILES:
        p = os.path.join(os.path.dirname(path), name)
        if os.path.isfile(p):
            with open(p, encoding="utf-8", errors="replace") as fh:
                if L.is_ofl_11_text(fh.read()):
                    return os.path.abspath(p)
    return None


# ------------------------------------------------------------------ the width axis
def wdth_room(axes, loc):
    """Which way the width axis can still move from the location measured."""
    w = axes.get("wdth")
    if not isinstance(w, (tuple, list)):
        return {"narrow": False, "widen": False}
    lo, de, hi = w
    at = loc.get("wdth", de)
    return {"narrow": lo < at, "widen": hi > at}


def width_weight(axes, loc):
    """A class width gap counts a quarter when the width axis can move toward the target, else in full."""
    room = wdth_room(axes, loc)

    def weight(cls, d):
        return 0.25 if (d > 0 and room["narrow"]) or (d < 0 and room["widen"]) else 1.0
    return weight


def axis_penalty(axes, deltas=None):
    """A font with fewer useful axes ranks behind a close one that has them. wdth matters most, and counts only
    when it can move the way the widths beyond the stretch limit need (deltas, when known)."""
    useful = [a for a in USEFUL_AXES if a in axes]
    if "wdth" in useful and deltas and isinstance(axes.get("wdth"), (tuple, list)):
        room = wdth_room(axes, {})
        need = {"widen" if v < 0 else "narrow" for k, v in deltas.items()
                if k.startswith("w_") and isinstance(v, (int, float)) and abs(v) > STRETCH}
        if need and not all(room[n] for n in need):
            useful.remove("wdth")
    if "wdth" in useful and "wght" in useful:
        return 0.0
    if "wght" in useful:
        return 0.5 if len(useful) > 1 else 0.75
    return 1.5


def evaluate(path, tg, styles, use, quick=False, T=None):
    """Measure one candidate the way the targets were measured. Returns the best location and its distance. With T
    and its hangul object, the Hangul is measured too: without an n stem the wght is solved from the Hangul stem as
    the fit solves it (before any transform), and the Hangul ratios add their distance (fontlib.hangul_distance)."""
    f = path if isinstance(path, TTFont) else TTFont(path)
    axes = L.axes_of(f)
    hangul = (T or {}).get("hangul")
    small = L.subset_font(f, L.SOLVE_TEXT + (L.HANGUL_TEXT if hangul else ""), layout=False)
    stem = styles[0].get("n_stem") or tg.get("n_stem")
    aim = None
    if hangul and not stem and not quick:
        import fit_font
        aim = fit_font.hangul_weight_aim(T)
    opsz_try = [None]
    if "opsz" in axes and not quick:
        lo, de, hi = axes["opsz"]
        pref = {"text": [lo + (de - lo) * 0.5, de, de + (hi - de) * 0.15],
                "ui": [de, lo + (de - lo) * 0.5],
                "display": [de, de + (hi - de) * 0.35, hi]}[use]
        opsz_try = sorted({round(min(max(v, lo), hi), 1) for v in pref})
    best = None
    for opsz in opsz_try:
        loc = {} if opsz is None else {"opsz": opsz}
        try:
            if "wght" in axes and stem and not quick:
                w, _ = L.solve_axis(lambda v: L.Face(small, {**loc, "wght": v}), L.stem_cap700, stem,
                                    axes["wght"][0], axes["wght"][2], iters=10)
                loc["wght"] = round(w, 1)
            elif "wght" in axes and aim:
                w, _ = L.solve_axis(lambda v: L.Face(small, {**loc, "wght": v}), aim[2], aim[1], axes["wght"][0],
                                    axes["wght"][2])
                loc["wght"] = round(w, 1)
            face = L.Face(small, loc or None)
            m = L.measure_face(face)
            if hangul:
                hm = L.hangul_measurement(L.hangul_geometry(face), {"cap700": L.CAP / face.bounds("H")[3],
                                                                    "em1000": 1000 / face.upm}, n_stem=m.get("n_stem"))
        except Exception as e:  # a font without the letters the measurement needs
            return {"error": f"{type(e).__name__}: {e}"}
        skip = ("n_stem",) if quick or "wght" not in axes else ()
        d, deltas = L.distance(tg, m, width_weight(axes, loc), skip)
        if hangul:
            hd, hdeltas = L.hangul_distance(hangul, hm, skip=("stem_h1",) if aim and "wght" in axes else ())
            d = round((d ** 2 + hd ** 2) ** 0.5, 3)
            deltas.update({"hangul." + k: v for k, v in hdeltas.items()})
        if best is None or d < best["distance"]:
            best = {"distance": d, "deltas": deltas, "loc": loc, "measured": m}
    best["axes"] = axes
    best["useful_axes"] = [a for a in USEFUL_AXES if a in axes]
    best["wdth_room"] = wdth_room(axes, best["loc"])
    best["glyphs"] = len(f.getGlyphOrder())
    return best


def glyf_vf(f):
    return "glyf" in f and "fvar" in f and "gvar" in f


BASE_LATIN = L.LETTERS + "0123456789"  # the Latin every fit measures


def qualify(font, ofl_text):
    """Why a manifest font cannot be a Hangul base, or []: it must be a TrueType variable font (glyf, fvar, gvar)
    with every modern Hangul syllable and the basic Latin letters and figures, and an OFL.txt and name ID 13 that
    record_base.py accepts (the same fontlib checks)."""
    out = [] if glyf_vf(font) else ["not a TrueType (glyf) variable font"]
    cm = font.getBestCmap()
    for what, chars in (("modern Hangul syllables", L.MODERN_SYLLABLES), ("basic Latin letters and figures", BASE_LATIN)):
        miss = [c for c in chars if ord(c) not in cm]
        if miss:
            out.append(f"{len(miss)} of the {len(chars)} {what} missing ({''.join(miss[:10])})")
    if problem := L.ofl_11_text_problem(ofl_text):
        out.append(f"its OFL.txt: {problem}")
    if problem := L.ofl_11_notice_problem(L.english_names(font).get(13)):
        out.append(f"its name ID 13: {problem}")
    return out


def coverage_of(font, scripts):
    """script -> "have of need", and the characters missing, for every script asked."""
    cm = font.getBestCmap()
    out = {}
    for s in scripts:
        need = L.COVERAGE.get(s, "")
        miss = "".join(c for c in need if ord(c) not in cm)
        out[s] = f"{len(need) - len(miss)} of {len(need)}" + (f", missing {miss[:20]}" if miss else "")
    return out


def manifest_rows(manifest, cache, T, offline=False):
    """Every base the pinned manifest lists, ranked by the same distance as a fine candidate, Hangul included. Each
    entry's font and OFL.txt go to cache/manifest/<entry>/ (read from there with --offline) and are skipped unless
    both have the sha256 the manifest pins and qualify() finds nothing. Nothing else is searched."""
    rows = []
    for key, e in manifest["families"].items():
        folder = os.path.join(cache, "manifest", safe(key))
        font_url = e["files"][0]["url"]
        try:
            font_path = fetch(font_url, os.path.join(folder, safe_file(font_url)), offline)
            lic_path = fetch(e["license"]["url"], os.path.join(folder, "OFL.txt"), offline)
        except FetchError as err:
            if not offline and "refused" in str(err):
                raise SystemExit(str(err))
            print(f"skip {e['family']}: {err}")
            continue
        # Read each file once: the bytes that pass the pin are the bytes qualified and ranked.
        with open(font_path, "rb") as fh:
            font_bytes = fh.read()
        with open(lic_path, "rb") as fh:
            lic_bytes = fh.read()
        changed = [f"{os.path.basename(p)} has sha256 {got}, the manifest pins {want}"
                   for p, data, want in ((font_path, font_bytes, e["files"][0]["sha256"]),
                                         (lic_path, lic_bytes, e["license"]["sha256"]))
                   if (got := hashlib.sha256(data).hexdigest()) != want]
        if changed:
            print(f"skip {e['family']}: {'; '.join(changed)}. Delete the cached file to download it again; a "
                  "different file is not this entry.")
            continue
        f = TTFont(io.BytesIO(font_bytes))
        ofl_text = lic_bytes.decode("utf-8", errors="replace")
        problems = qualify(f, ofl_text)
        if problems:
            print(f"skip {e['family']}: {'; '.join(problems)}")
            continue
        r = evaluate(f, T["targets"], T["styles"], T.get("use", "text"), T=T)
        rows.append({"family": e["family"], "file": os.path.abspath(font_path), "origin": f"manifest/{key}",
                     "url": font_url, "manifest_entry": key, "version": e.get("version"),
                     "licence_path": os.path.abspath(lic_path), "coverage": coverage_of(f, T.get("scripts", [])),
                     **licence_of(f, ofl_text), **r})
        print(f"manifest {e['family']:26s} distance {r.get('distance')} at {r.get('loc')}", flush=True)
    return rows


def safe_file(url):
    """The file name at the end of a URL, as a cache file name (letters, digits, [ ] . _ and - only)."""
    return re.sub(r"[^A-Za-z0-9_.\[\]-]", "_", urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1]))


def search_rows(a, tg, styles, use, scripts, category):
    """The Google Fonts candidates (coarse, then fine) and the --local fonts, measured."""
    rows = []
    for d in a.local:
        for p in sorted(glob.glob(os.path.join(d, "*.[ot]tf")) + glob.glob(os.path.join(d, "*.woff2"))):
            f = TTFont(p)
            lic_path = licence_beside(p)
            lic = licence_of(f, open(lic_path, encoding="utf-8").read() if lic_path else None)
            name = f["name"].getDebugName(16) or f["name"].getDebugName(1)
            if not lic["licence"]:
                print(f"skip {os.path.basename(p)}: no OFL-1.1 notice in its name table, so it cannot be a base")
                continue
            if not glyf_vf(f):
                print(f"skip {os.path.basename(p)}: not a TrueType variable font, so the fit cannot use it")
                continue
            r = evaluate(p, tg, styles, use)
            rows.append({"family": name, "file": os.path.abspath(p), "origin": "local", "url": None,
                         "licence_path": lic_path, **lic, **r})
            print(f"local  {name:28s} distance {r.get('distance')}"
                  + ("" if lic_path else "  (no OFL.txt beside it: the approval step will need --licence)"), flush=True)

    try:
        tree_path = fetch(TREE, os.path.join(a.cache, "google-fonts-tree.json"), a.offline)
        catalog_path = fetch(CATALOG, os.path.join(a.cache, "fontsource-catalog.json"), a.offline)
    except FetchError as e:
        if not a.offline:
            raise SystemExit(f"cannot list the Google Fonts families: {e}")
        print(f"offline, and the catalogue is not cached ({e}): only --local fonts are searched")
        tree_path = None
    if tree_path:
        with open(tree_path, encoding="utf-8") as fh:
            tree = [t["path"] for t in json.load(fh)["tree"]]
        with open(catalog_path, encoding="utf-8") as fh:
            catalog = json.load(fh)
        wanted = [s.strip().lower() for s in a.families.split(",") if s.strip()]
        fams = candidates(catalog, category, scripts, wanted)
        for w in wanted:
            if not any(c["family"].lower() == w for c in fams):
                print(f"skip {w}: not an OFL family in the catalogue")
        print(f"catalogue: {len(fams)} {category} families under the OFL, covering {sorted(scripts)}", flush=True)

        def variable_files(folder):
            return [p for p in tree if p.startswith(f"ofl/{folder}/") and p.endswith(".ttf") and "[" in p
                    and "Italic" not in p]
        coarse = []
        if not wanted:
            for c in fams:
                folder = c["family"].lower().replace(" ", "").replace("-", "")
                vf = variable_files(folder)
                if not vf:
                    continue  # a static family: the fit needs a variable font
                w = min(c.get("weights") or [400], key=lambda x: abs(x - styles[0].get("weight", 400)))
                p = os.path.join(a.cache, "coarse", f"{safe(c['id'])}-{w}.woff2")
                try:
                    fetch(COARSE.format(id=c["id"], w=w), p, a.offline)
                    r = evaluate(p, tg, styles, use, quick=True)
                except Exception as e:
                    r = {"error": str(e)}
                if "distance" in r:
                    axes = dict.fromkeys(vf[0].split("[")[1].split("]")[0].split(","))
                    coarse.append((r["distance"] + axis_penalty(axes), c))
            coarse.sort(key=lambda x: x[0])
            print("coarse ranking, top 15:", ", ".join(f"{c['family']} {d:.1f}" for d, c in coarse[:15]), flush=True)
            fams = [c for _, c in coarse[:a.shortlist]]
        for c in fams:
            folder = c["family"].lower().replace(" ", "").replace("-", "")
            vf = variable_files(folder)
            if not vf:
                print(f"skip {c['family']}: no variable font in google/fonts/ofl/{folder}")
                continue
            path = vf[0]
            lic_file = next((p for p in tree if p.startswith(os.path.dirname(path) + "/") and
                             os.path.basename(p) == "OFL.txt"), None)
            if not lic_file:
                print(f"skip {c['family']}: no OFL.txt beside {path}")
                continue
            cache_dir = os.path.join(a.cache, "full", safe(folder))
            try:
                local = fetch(RAW + urllib.parse.quote(path), os.path.join(cache_dir, os.path.basename(path)),
                              a.offline)
                lic_path = fetch(RAW + urllib.parse.quote(lic_file), os.path.join(cache_dir, "OFL.txt"), a.offline)
            except FetchError as e:
                if not a.offline and "refused" in str(e):
                    raise SystemExit(str(e))
                print(f"skip {c['family']}: {e}")
                continue
            with open(lic_path, encoding="utf-8", errors="replace") as fh:
                ofl_text = fh.read()
            f = TTFont(local)
            lic = licence_of(f, ofl_text)
            if not lic["licence"] or not glyf_vf(f):
                print(f"skip {c['family']}: {'not OFL-1.1' if not lic['licence'] else 'not a TrueType variable font'}")
                continue
            r = evaluate(local, tg, styles, use)
            rows.append({"family": c["family"], "file": os.path.abspath(local), "origin": "google/fonts/" + path,
                         "url": RAW + urllib.parse.quote(path), "licence_file": lic_file,
                         "licence_path": os.path.abspath(lic_path), **lic, **r})
            print(f"fine   {c['family']:28s} distance {r.get('distance')} at {r.get('loc')}", flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets")
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--category", help="a Fontsource category; default from targets.json's category")
    ap.add_argument("--shortlist", type=int, default=8)
    ap.add_argument("--families", default="")
    ap.add_argument("--local", action="append", default=[])
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    T = L.load_json(a.targets)
    tg, styles, use = T["targets"], T["styles"], T.get("use", "text")
    scripts = set(T.get("scripts", ["latin"]))
    cat = T.get("category") or ("serif" if tg.get("serif") else "sans")
    category = a.category or {"sans": "sans-serif", "serif": "serif", "mono": "monospace"}.get(cat, "sans-serif")
    if "korean" in scripts:
        if a.local or a.families:
            raise SystemExit("with korean in the targets' scripts, the bases are the pinned manifest's (bases.json, "
                             "references/foundation.md): --local and --families do not apply")
        print(f"korean: ranking the pinned bases of {os.path.basename(C.MANIFEST)} only", flush=True)
        rows = manifest_rows(L.load_json(C.MANIFEST), a.cache, T, a.offline)
    else:
        rows = search_rows(a, tg, styles, use, scripts, category)
    rows = [r for r in rows if "distance" in r]
    for r in rows:
        r["score"] = round(r["distance"] + axis_penalty(r["axes"], r["deltas"]), 3)
    rows.sort(key=lambda r: r["score"])
    L.save_json({"targets": a.targets, "category": category, "rows": rows}, a.out)
    print(f"\nshortlist ({len(rows)}), closest first. Deltas are candidate minus target, widths in percent:")
    keys = ["xh_cap", "contrast", "bar_stem", "serif_ext", "rhythm"]
    print(f"  {'family':26s} {'score':>6s} {'axes':16s} " + " ".join(f"{k:>9s}" for k in keys) + "  widths (lc / uc)")
    for r in rows:
        dl = r["deltas"]
        wl = [v for k, v in dl.items() if k.startswith("w_lc")]
        wu = [v for k, v in dl.items() if k.startswith("w_uc")]
        ws = f"{sum(wl) / len(wl) * 100:+.1f}% / {sum(wu) / len(wu) * 100:+.1f}%" if wl and wu else ""
        room = r.get("wdth_room") or {}
        moves = "+".join(k for k in ("narrow", "widen") if room.get(k)) or "fixed"
        wd = f" wdth {moves}" if "wdth" in r["axes"] else ""
        print(f"  {r['family'][:26]:26s} {r['score']:6.2f} {','.join(r['useful_axes']):16s} " +
              " ".join(f"{dl.get(k, ''):>9}" for k in keys) + f"  {ws}  {r.get('licence')}{wd}"
              + (f" RFN {r['reserved_font_names']}" if r.get("reserved_font_names") else ""))
        hd = {k.split(".", 1)[1]: v for k, v in dl.items() if k.startswith("hangul.")}
        if hd:
            print("    hangul " + ", ".join(f"{k} {v * 100:+.1f}%" for k, v in hd.items()))
        if r.get("coverage"):
            print("    covers " + "; ".join(f"{k} {v}" for k, v in r["coverage"].items()))
    print(f"\nwrote {a.out}")
    print("next: show the person the top rows and ask which to build on. For their pick, print the approval "
          f"question with record_base.py --shortlist {a.out} --family ... --question-only --out base.json, ask it "
          "as printed, then record their answer verbatim (SKILL.md step 5).")


if __name__ == "__main__":
    main()

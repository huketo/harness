#!/usr/bin/env python3
"""Fetch official brand logos and inline them into a diagram, with no third-party deps.

Logo mode is opt-in; see references/primitive-logos.md for when to use it.

Usage:
  python3 logos.py fetch  LOGODIR spec [spec ...]
  python3 logos.py inline DRAFT.html LOGODIR OUT.html

Spec forms (fetch):
  name              slug == name              e.g. hono
  name:slug         different slug            e.g. betterauth:better-auth
  name=URL          explicit official file    e.g. orpc=https://orpc.unnoq.com/logo.webp
  name:aws/Service  official AWS icon         e.g. lambda:aws/lambda, user:aws/General-User

Sources, in order: svgl -> devicon -> gilbarbara/logos. aws/ specs (and the slugs aws,
amazonwebservices, aws-*) read AWS's own icon package instead. simple-icons is deliberately
not a source: its glyphs are monochrome redraws, not the official marks.

fetch writes LOGODIR/<name>.<ext>, LOGODIR/<name>_dark.<ext> when the source has a
dark-theme variant, and LOGODIR/manifest.json. It never recolors a logo. Every file is
checked before it is written: an SVG must be well-formed XML with no ENTITY, script,
foreignObject, event handler, external reference, or remote CSS; a raster must be PNG,
WebP, or JPEG by its magic bytes. A file that fails is rejected, not cleaned.

inline replaces %%LOGO_<name>%% tokens in DRAFT.html with data:image URIs of the files in
LOGODIR and %%LOGO_CREDITS%% with the colophon credit line built from manifest.json, and
fails on any unresolved token or unsafe file.

Adapted from caru-ini/stack-diagram scripts/fetch_icons.py and scripts/build.py (MIT,
see LICENSE.stack-diagram).
"""
from __future__ import annotations

import base64
import functools
import http.client
import io
import json
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

UA = {"User-Agent": "Mozilla/5.0 (diagram-design-skill)"}
NAME_RE = re.compile(r"[A-Za-z0-9_-]+")  # becomes a filename and a %%LOGO_<name>%% token
TOKEN_RE = re.compile(r"%%LOGO_([A-Za-z0-9_-]+)%%")
MIME = {"svg": "image/svg+xml", "png": "image/png", "webp": "image/webp",
        "jpg": "image/jpeg", "jpeg": "image/jpeg"}
CREDIT = {"svgl": "svgl", "devicon": "devicon", "gilbarbara": "gilbarbara/logos",
          "aws": "AWS Architecture Icons", "explicit": "brand's own site"}

AWS_ICONS_PAGE = "https://aws.amazon.com/architecture/icons/"
AWS_PACKAGE_RE = re.compile(r"""(?:https:)?//[\w.-]+\.awsstatic\.com/[^"'\s]+/Icon-package_[^"'\s/]+\.zip""")
AWS_ICON_RE = re.compile(r"Architecture-Service-Icons_[^/]+/[^/]+/64/Arch_(.+)_64\.svg"
                         r"|Architecture-Group-Icons_[^/]+/(.+)_32\.svg"
                         r"|Resource-Icons_[^/]+/Res_General-Icons/Res_48_Light/Res_(.+)_48_Light\.svg")
AWS_ALIASES = {
    "s3": "Amazon-Simple-Storage-Service", "glacier": "Amazon-Simple-Storage-Service-Glacier",
    "sqs": "Amazon-Simple-Queue-Service", "sns": "Amazon-Simple-Notification-Service",
    "ses": "Amazon-Simple-Email-Service", "ecs": "Amazon-Elastic-Container-Service",
    "eks": "Amazon-Elastic-Kubernetes-Service", "ecr": "Amazon-Elastic-Container-Registry",
    "elb": "Elastic-Load-Balancing", "alb": "Elastic-Load-Balancing", "nlb": "Elastic-Load-Balancing",
    "iam": "AWS-Identity-and-Access-Management", "kms": "AWS-Key-Management-Service",
    "msk": "Amazon-Managed-Streaming-for-Apache-Kafka", "opensearch": "Amazon-OpenSearch-Service",
    "vpc": "Virtual-private-cloud-VPC",
}
AWS_PACKAGES: dict[str, zipfile.ZipFile] = {}

# Entity declarations are checked before the XML parser ever sees the bytes. A plain
# SVG 1.1 DOCTYPE (common in Illustrator exports) is harmless; an internal subset or
# ENTITY declaration is how entity-expansion attacks are written. The parser drops
# processing instructions, so an xml-stylesheet one is checked here too.
RAW_UNSAFE = [
    (re.compile(rb"<!\s*entity|<!\s*doctype[^>]*\[", re.I), "ENTITY declaration or internal DTD subset"),
    (re.compile(rb"<\?\s*xml-stylesheet", re.I), "xml-stylesheet processing instruction"),
]
# Everything below is judged on parsed names and decoded values, so namespace prefixes,
# character references, and CSS escapes cannot hide it.
BLOCKED_ELEMENTS = {"script", "foreignobject", "iframe", "embed", "object", "audio", "video",
                    "handler", "listener"}
XHTML_NS = "{http://www.w3.org/1999/xhtml}"
LOCAL_REF_RE = re.compile(r"#|data:image/(?:png|jpe?g|webp|gif)[;,]", re.I)
# Judge what follows every url( opener on its own. Matching whole url(...) tokens lets a
# malformed one (unterminated, or a quoted string broken by a newline) swallow the next.
CSS_URL_OPEN_RE = re.compile(r"url\(\s*['\"]?\s*", re.I)
# Inside CSS (a <style> element or a style attribute) a logo needs neither string-URL
# functions nor a string that names a scheme or a path. URL parsers forgive missing
# slashes ('https:/x' resolves to https://x), so a string is judged by its start alone,
# after every quote, the same way url( targets are.
CSS_STRING_URL_FUNC_RE = re.compile(r"(?<![\w-])(?:-webkit-)?(?:image|image-set|cross-fade|src)\(", re.I)
CSS_QUOTE_OPEN_RE = re.compile(r"['\"]\s*")
CSS_SCHEME_OR_PATH_RE = re.compile(r"[a-z][a-z0-9+.-]*:|[/\\]", re.I)
CSS_ESCAPE_RE = re.compile(r"\\(?:([0-9a-fA-F]{1,6})[ \t\r\n\f]?|(\n)|(.))", re.S)


def css_plain(text: str) -> str:
    """CSS text with comments removed and escapes decoded, so `u\\72l(` reads as `url(`."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)

    def unescape(m: re.Match[str]) -> str:
        if m.group(1):
            cp = int(m.group(1), 16)
            return chr(cp) if 0 < cp <= 0x10FFFF else "\ufffd"
        return "" if m.group(2) else m.group(3)

    return CSS_ESCAPE_RE.sub(unescape, text)


def value_problem(value: str, css: bool = False) -> str | None:
    """Why this attribute value (or, with css=True, this CSS text) must not be embedded."""
    plain = css_plain(value)
    squashed = re.sub(r"[\s\x00-\x1f]", "", plain).lower()
    if "javascript:" in squashed or "vbscript:" in squashed:
        return "script URL"
    if "@import" in squashed:
        return "CSS @import"
    if css:
        if CSS_STRING_URL_FUNC_RE.search(plain):
            return "CSS string-URL function"
        for m in CSS_QUOTE_OPEN_RE.finditer(plain):
            target = plain[m.end():]
            if CSS_SCHEME_OR_PATH_RE.match(target) and not LOCAL_REF_RE.match(target):
                return f"URL-like string in CSS ({target[:40]})"
    for m in CSS_URL_OPEN_RE.finditer(plain):
        target = plain[m.end():]
        if not LOCAL_REF_RE.match(target):
            return f"external url() ({target[:40]})"
    return None


def svg_verdict(b: bytes) -> tuple[bool, str | None]:
    """(is_svg, rejection reason). Not well-formed or not rooted at <svg> is a plain miss
    (a 404 page, say); is_svg with a reason is a real SVG that must not be embedded."""
    for pattern, reason in RAW_UNSAFE:
        if pattern.search(b):
            return True, reason
    try:
        root = ET.fromstring(b)
    except ET.ParseError:
        return False, None
    if root.tag.rsplit("}", 1)[-1] != "svg":
        return False, None
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        local = el.tag.rsplit("}", 1)[-1].lower()
        if local in BLOCKED_ELEMENTS or el.tag.startswith(XHTML_NS):
            return True, f"<{local}> element"
        if local == "style":
            problem = value_problem("".join(el.itertext()), css=True)
            if problem:
                return True, f"<style>: {problem}"
        for key, value in el.attrib.items():
            name = key.rsplit("}", 1)[-1].lower()
            if name.startswith("on"):
                return True, f"event-handler attribute {name}"
            if name == "href" and not LOCAL_REF_RE.match(value.strip()):
                return True, f"external href ({value.strip()[:40]})"
            problem = value_problem(value, css=name == "style")
            if problem:
                return True, f"{name}: {problem}"
    return True, None


def raster_ext(b: bytes) -> str | None:
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "webp"
    if b[:3] == b"\xff\xd8\xff":
        return "jpg"
    return None


def looks_svg(b: bytes) -> bool:
    return b.lstrip()[:200].lstrip().startswith((b"<svg", b"<?xml", b"<!--", b"<!DOCTYPE"))


def classify(b: bytes) -> tuple[str | None, str | None]:
    """(extension, rejection reason). A miss (404 page, empty body) is (None, None)."""
    if len(b) < 50:
        return None, None
    if looks_svg(b):
        is_svg, problem = svg_verdict(b)
        if problem:
            return None, problem
        return ("svg" if is_svg else None), None
    ext = raster_ext(b)
    return (ext, None) if ext else (None, None)


def white_fill(b: bytes) -> bool:
    """True only when the mark is white overall: at least one white paint and no
    non-white paint (a white detail on a colored logo is not a white logo)."""
    if not looks_svg(b):
        return False
    s = b.decode("utf-8", "ignore")
    paints = re.findall(r'(?:fill|stroke|stop-color)[=:]\s*"?([#a-zA-Z][^";\s>]*)', s)
    white = colored = False
    for p in paints:
        p = p.strip().lower()
        if p in ("none", "transparent", "currentcolor") or p.startswith("url("):
            continue
        if re.fullmatch(r"#f{3}(f{3})?|white", p):
            white = True
        else:
            colored = True
    return white and not colored


def get(url: str, timeout: int = 20) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def read(url: str) -> bytes:
    """Bytes of url; '<AWS package URL>#<member>' reads from the already-downloaded zip."""
    zip_url, _, member = url.partition("#")
    return AWS_PACKAGES[zip_url].read(member) if zip_url in AWS_PACKAGES else get(url)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def svgl_lookup(slug: str):
    """(url, dark_url or None) for an exact normalized-title hit on svgl, else None.
    svgl search is fuzzy, so a loose hit would silently ship another brand's logo."""
    queries = [slug, re.sub(r"[-_.]+", " ", slug).strip()]
    targets = {norm(slug)}
    if len(slug) > 4 and slug.endswith("js"):
        queries.append(slug[:-2])
        targets.add(norm(slug[:-2]))
    for q in dict.fromkeys(queries):
        try:
            items = json.loads(get(f"https://api.svgl.app?search={urllib.parse.quote(q)}"))
        except Exception:
            continue
        for it in items if isinstance(items, list) else []:
            if norm(it.get("title", "")) in targets:
                route = it.get("route")
                if isinstance(route, dict):  # light/dark split: tiles are white -> light
                    light, dark = route.get("light"), route.get("dark")
                    return (light, dark) if light else (dark, None)
                return route, None
    return None


@functools.lru_cache(maxsize=1)
def aws_index():
    """{normalized name: (name, url, dark url or None)} from AWS's icon package. The
    package URL changes per release, so it is read from the icons page each run."""
    link = AWS_PACKAGE_RE.search(get(AWS_ICONS_PAGE).decode("utf-8", "ignore"))
    if not link:
        raise OSError(f"no Icon-package link on {AWS_ICONS_PAGE}")
    url = urllib.parse.urljoin(AWS_ICONS_PAGE, link.group())
    AWS_PACKAGES[url] = zipfile.ZipFile(io.BytesIO(get(url, timeout=120)))
    files = set(AWS_PACKAGES[url].namelist())
    index = {}
    for f in sorted(files):
        m = AWS_ICON_RE.fullmatch(f)
        if m:
            # the General- prefix keeps General-Shield from taking the short name of AWS-Shield
            name = m.group(1) or m.group(2) or f"General-{m.group(3)}"
            dark = f.replace("_Light", "_Dark") if m.group(3) else f[:-4] + "_Dark.svg"
            index.setdefault(norm(name), (name, f"{url}#{f}", f"{url}#{dark}" if dark in files else None))
    return index


def aws_sources(query: str):
    """Exact match on a package name or acronym; the AWS-/Amazon- prefix is optional.
    A miss lists every name, because a partial match could ship the wrong service."""
    try:
        index = aws_index()
    except (OSError, zipfile.BadZipFile, http.client.HTTPException) as e:
        print(f"AWS  icon package unavailable: {e}")
        return []
    q = norm(AWS_ALIASES.get(norm(query), query))
    hit = index.get(q) or next((v for k, v in index.items() if re.sub(r"^(aws|amazon)", "", k) == q), None)
    if hit:
        return [("aws", hit[1], hit[2])]
    print(f"AWS  {query!r} is not a name in the package. Names: {', '.join(sorted(v[0] for v in index.values()))}")
    return []


def sources(slug: str):
    if slug.startswith("aws/"):
        return aws_sources(slug[4:])
    if norm(slug) in ("aws", "amazonwebservices"):
        return aws_sources("AWS-Cloud-logo")
    if slug[:4].lower() == "aws-":
        return aws_sources(slug[4:])
    out = []
    svgl = svgl_lookup(slug)
    if svgl:
        out.append(("svgl", *svgl))
    return out + [
        ("devicon", f"https://raw.githubusercontent.com/devicons/devicon/master/icons/{slug}/{slug}-original.svg", None),
        ("gilbarbara", f"https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/{slug}-icon.svg", None),
        ("gilbarbara", f"https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/{slug}.svg", None),
    ]


def parse_spec(spec: str):
    """(name, tries) where tries is a list of (source, url, dark_url)."""
    if "=" in spec:
        name, url = spec.split("=", 1)
        return name, [("explicit", url, None)]
    if ":" in spec:
        name, slug = spec.split(":", 1)
        return name, sources(slug)
    return spec, sources(spec.lower().replace(" ", ""))


def fetch(outdir: pathlib.Path, specs: list[str]) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    mpath = outdir / "manifest.json"
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {}  # merge across runs
    failed, bad = [], False
    for spec in specs:
        name = spec.split("=", 1)[0].split(":", 1)[0]
        if not NAME_RE.fullmatch(name) or name.endswith("_dark"):
            print(f"SKIP {name!r}: name must match [A-Za-z0-9_-]+ and must not end in _dark")
            bad = True
            continue
        name, tries = parse_spec(spec)
        got, rejected = None, []
        for src, url, dark_url in tries:
            try:
                b = read(url)
            except (urllib.error.URLError, urllib.error.HTTPError, OSError, KeyError, ValueError):
                continue
            ext, problem = classify(b)
            if problem:
                rejected.append(f"{src}: {problem}")
                continue
            if ext:
                got = (src, url, dark_url, b, ext)
                break
        if not got:
            failed.append((name, rejected))
            continue
        src, url, dark_url, b, ext = got
        # inline embeds whichever <name>.* it finds, so a re-fetch must not leave the old file
        for old in [*outdir.glob(f"{name}.*"), *outdir.glob(f"{name}_dark.*")]:
            if old != mpath:
                old.unlink()
        path = outdir / f"{name}.{ext}"
        path.write_bytes(b)
        entry = {"source": src, "url": url, "file": path.name, "bytes": len(b)}
        if white_fill(b):
            entry["white_fill"] = True
            entry["note"] = ("white fill detected; MAY be a false positive (an inner detail on a "
                             "colored logo). Inspect it; use a dark tile only if the mark is white "
                             "overall. Never recolor.")
        if dark_url:
            try:
                db = read(dark_url)
            except (urllib.error.URLError, urllib.error.HTTPError, OSError, KeyError, ValueError):
                db = b""
            dext, dproblem = classify(db)
            if dext:
                dpath = outdir / f"{name}_dark.{dext}"
                dpath.write_bytes(db)
                entry["dark_file"] = dpath.name
            elif dproblem:
                print(f"     {name}_dark rejected: {dproblem}")
        manifest[name] = entry
        flag = " [WHITE FILL -> check, maybe dark tile]" if entry.get("white_fill") else ""
        if "dark_file" in entry:
            flag += f" +{entry['dark_file']}"
        print(f"OK   {name:<16} {src:<12} {len(b):>7}B .{ext}{flag}")
    mpath.write_text(json.dumps(manifest, indent=2) + "\n")
    for name, rejected in failed:
        why = f" (rejected unsafe: {'; '.join(rejected)})" if rejected else ""
        print(f"FAIL {name:<16} no source has a safe copy{why}. Try name:otherslug, or name=URL "
              f"with the official file from the project's repo or site (/logo.svg, /favicon.svg).")
    return 1 if failed or bad else 0


def credits(logodir: pathlib.Path) -> str:
    mpath = logodir / "manifest.json"
    if not mpath.exists():
        return ""
    manifest = json.loads(mpath.read_text())
    used = dict.fromkeys(CREDIT.get(e.get("source"), e.get("source", "?")) for e in manifest.values())
    return "logos: " + " / ".join(used) + ". Brand logos are trademarks of their owners."


def inline(draft: pathlib.Path, logodir: pathlib.Path, out: pathlib.Path) -> int:
    html = draft.read_text(encoding="utf-8")
    files = {f.stem: f for f in sorted(logodir.iterdir()) if f.suffix.lstrip(".").lower() in MIME}
    missing, unsafe = [], []

    def replace(m: re.Match[str]) -> str:
        f = files.get(m.group(1))
        if f is None:
            missing.append(m.group(0))
            return m.group(0)
        b = f.read_bytes()
        ext, problem = classify(b)
        if problem or not ext:
            unsafe.append(f"{f.name}: {problem or 'not a recognised image'}")
            return m.group(0)
        return f"data:{MIME[ext]};base64,{base64.b64encode(b).decode()}"

    html = html.replace("%%LOGO_CREDITS%%", credits(logodir))
    html = TOKEN_RE.sub(replace, html)
    if unsafe:
        print("unsafe logo files (not embedded):\n  " + "\n  ".join(unsafe), file=sys.stderr)
    if missing:
        print(f"unresolved tokens: {', '.join(sorted(set(missing)))} (missing files in {logodir}?)",
              file=sys.stderr)
    if unsafe or missing:
        return 1
    out.write_text(html, encoding="utf-8")
    print(f"built {out} ({len(html) // 1024} KB)")
    line = credits(logodir)
    if line:
        print(f"colophon: {line}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[0] == "fetch":
        return fetch(pathlib.Path(argv[1]), argv[2:])
    if len(argv) == 4 and argv[0] == "inline":
        return inline(pathlib.Path(argv[1]), pathlib.Path(argv[2]), pathlib.Path(argv[3]))
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

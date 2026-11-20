# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow"]
# ///
"""The rights chain and the seal between steps (SKILL.md, "What the code holds").

Rights are the person's statement. This module binds that statement to the hash of the file it is about, finds the
collected material it must never be, and seals each step's output so the next step goes on only while it matches:

- brief.json `trace_sources`: the files the person said they hold rights in, each with its sha256, the kind of right
  (own-drawing, own-brand, licensed), the question shown to them and their answer, both verbatim.
- collections: every `manifest.json` under `${XDG_CACHE_HOME:-~/.cache}/hstack/make-logo/`, each listing every file
  with its sha256 (fetch_arena.mjs, fetch_photos.mjs).
- build.json `files` and check.json `build_sha256`, `refs_sha256`, `calibration_sha256`: what package_logo.py and
  logo_book.py recompute before they go on.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SHIPPED_CALIBRATION = os.path.join(HERE, "calibration.json")
RIGHTS = ("own-drawing", "own-brand", "licensed")
HEX64 = re.compile(r"[0-9a-f]{64}")
# Why the distance checks could not compare a reference (trace_ref.reference_set), in each document language.
NOT_CHECKED = {
    "en": {"blank": "a blank image", "no-ink": "no ink found", "unreadable": "not readable as an image",
           "gone": "listed in a collection manifest, but the file is gone"},
    "ko": {"blank": "빈 이미지", "no-ink": "잉크를 찾지 못함", "unreadable": "이미지로 읽을 수 없음",
           "gone": "수집 manifest에는 있지만 파일이 없음"},
}


class Refused(SystemExit):
    """A step that will not go on. `reason` is a short stable code; the message says what to do instead."""

    def __init__(self, reason: str, message: str, **detail):
        self.reason = reason
        self.detail = detail
        super().__init__(f"refused ({reason}): {message}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def read_json(path: str):
    return json.loads(read_bytes(path))


def write_bytes(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)


def digest(hexes) -> str:
    """The sha256 of a set of sha256s: sorted, joined with newlines."""
    return sha256_bytes("\n".join(sorted(hexes)).encode())


def cache_root() -> str:
    base = os.environ.get("XDG_CACHE_HOME", "")
    if not os.path.isabs(base):  # the XDG spec ignores an empty or relative value
        base = os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "hstack", "make-logo")


def calibration_file(path: str | None) -> str:
    return os.path.abspath(path) if path else SHIPPED_CALIBRATION


def refs_sha256(folders: list[str]) -> str:
    """Over every image file in the --refs folders as they are now, never from a saved list."""
    sys.path.insert(0, HERE)
    import logolib as L

    return digest(sha256_file(p) for p in L.images(folders))


# Collections ------------------------------------------------------------------------------------------------------

def collected(root: str | None = None) -> list[tuple[str, str]]:
    """(file, sha256 listed for it) for every item of every collection manifest under the cache."""
    root = root or cache_root()
    out = []
    for d, dirs, names in os.walk(root):
        dirs.sort()
        if "manifest.json" not in names:
            continue
        man = os.path.join(d, "manifest.json")
        for it in read_json(man).get("items", []):
            sha = it.get("sha256")
            if not (isinstance(sha, str) and HEX64.fullmatch(sha)):
                raise Refused("manifest", f"{man} lists {it.get('file')!r} without a sha256. Fetch that collection "
                                          "again with this version of fetch_arena.mjs or fetch_photos.mjs.")
            out.append((os.path.join(d, it["file"]), sha))
    return out


def collected_sha256(root: str | None = None) -> str:
    return digest(sha for _, sha in collected(root))


# The brief --------------------------------------------------------------------------------------------------------

def load_brief(path: str) -> dict:
    """brief.json with its sha256 and its trace_sources, each entry checked for every field."""
    raw = read_bytes(path)
    data = json.loads(raw)
    entries = data.get("trace_sources", [])
    if not isinstance(entries, list):
        raise Refused("brief", f"{path}: trace_sources must be a list")
    for e in entries:
        missing = [k for k in ("file", "question", "answer") if not (isinstance(e, dict) and isinstance(e.get(k), str) and e[k].strip())]
        if missing:
            raise Refused("brief", f"{path}: a trace_sources entry has no {', '.join(missing)}: {e!r}")
        if not (isinstance(e.get("sha256"), str) and HEX64.fullmatch(e["sha256"])):
            raise Refused("brief", f"{path}: trace_sources entry {e['file']!r} needs the file's sha256 (64 lowercase hex)")
        if e.get("rights") not in RIGHTS:
            raise Refused("brief", f"{path}: trace_sources entry {e['file']!r} has rights {e.get('rights')!r}; use one of {', '.join(RIGHTS)}")
    return {"path": os.path.abspath(path), "sha256": sha256_bytes(raw), "data": data, "trace_sources": entries}


def entry_file(brief: dict, entry: dict) -> str:
    f = entry["file"]
    return f if os.path.isabs(f) else os.path.join(os.path.dirname(brief["path"]), f)


def trace_source(brief: dict, source: str, source_sha: str) -> dict:
    """The person's statement about this exact file, or a refusal."""
    for e in brief["trace_sources"]:
        if e["sha256"] == source_sha:
            return e
    for e in brief["trace_sources"]:
        if os.path.abspath(entry_file(brief, e)) == os.path.abspath(source):
            raise Refused("not-in-brief", f"{source} changed after the person answered for it (sha256 {source_sha}, "
                                          f"their answer is for {e['sha256']}). Ask them again about this file.")
    raise Refused("not-in-brief", f"{source} (sha256 {source_sha}) is not in {brief['path']} trace_sources. Trace only "
                                  "a file the person said they hold rights in, and record their answer first.")


def language(brief_data: dict | None) -> str:
    """The language the documents are written in: the brief's `language`, else Korean when the brief is."""
    if not brief_data:
        return "en"
    lang = str(brief_data.get("language", "")).lower()
    if lang:
        return "ko" if lang.startswith("ko") else "en"

    def strings(v):
        if isinstance(v, str):
            yield v
        elif isinstance(v, dict):
            for x in v.values():
                yield from strings(x)
        elif isinstance(v, list):
            for x in v:
                yield from strings(x)

    return "ko" if any(re.search(r"[가-힣]", s) for s in strings(brief_data)) else "en"


# The seal ---------------------------------------------------------------------------------------------------------

def inside(build: str, rel: str) -> str:
    if os.path.isabs(rel) or ".." in rel.replace("\\", "/").split("/"):
        raise Refused("build-changed", f"{build}/build.json lists {rel!r}, which is outside the build folder")
    return os.path.join(build, rel)


MARK = ("mark.svg", "mark-grid.svg")  # every build writes these
LOCKUPS = ("wordmark.svg", "lockup.svg", "lockup-stacked.svg")  # and these when it has a wordmark


def verified_files(build: str, info: dict) -> dict[str, bytes]:
    """The bytes of every file build.json lists, each read once and matched to its sha256: the steps after the build
    read the build's files from here only. Refuses a list that leaves out a file the build must have written: the
    mark and its grid, the wordmark and lockups of a build with a wordmark, and each font licence it names."""
    files = info.get("files")
    if not isinstance(files, dict):
        raise Refused("build-changed", f"{build}/build.json has no file list. Build it again with build_logo.py.")
    need = [*MARK, *(LOCKUPS if "wordmark" in info else ()), *info.get("fonts", {}).values()]
    missing = [rel for rel in need if rel not in files]
    if missing:
        raise Refused("build-changed", f"{build}/build.json does not list {', '.join(missing)}, which such a build "
                                       "writes. Build again with build_logo.py.")
    out = {}
    for rel, sha in files.items():
        p = inside(build, rel)
        data = read_bytes(p) if os.path.isfile(p) else None
        if data is None or sha256_bytes(data) != sha:
            raise Refused("build-changed", f"{p} is missing or changed after build_logo.py wrote it. Build again.")
        out[rel] = data
    return out


def traces(build: str, info: dict, files: dict[str, bytes]) -> list[dict]:
    """Each verified trace of a build: its build.json entry, its provenance record (from `files`, the verified
    bytes), where its files are, and the traced source's bytes (`source`), read once and still of the sha256 it was
    traced from."""
    out = []
    by_sha = {sha: rel for rel, sha in info["files"].items()}
    for t in info.get("traces", []):
        rec_rel = by_sha.get(t.get("provenance_sha256"))
        if not rec_rel or not rec_rel.endswith(".provenance.json"):
            raise Refused("build-changed", f"{build}/build.json names a trace whose provenance file it does not list")
        prov = json.loads(files[rec_rel])
        svg_rel = rec_rel[: -len(".provenance.json")]
        ts = prov.get("trace_source", {})
        agree = (prov["source"]["sha256"] == t["source_sha256"] == ts.get("sha256") and prov.get("svg_sha256") == t["svg_sha256"]
                 == info["files"].get(svg_rel) and ts.get("rights") == t["rights"] and ts.get("answer") == t["answer"])
        if not agree:
            raise Refused("build-changed", f"{build}/build.json and {rec_rel} disagree about the trace. Build again.")
        src = prov["source"]["file"]
        data = read_bytes(src) if os.path.isfile(src) else None
        if data is None or sha256_bytes(data) != t["source_sha256"]:
            raise Refused("source-changed", f"the traced source {src} is gone or changed since the build. Build again.")
        out.append({"trace": t, "provenance": prov, "svg": svg_rel, "record": rec_rel, "source": data})
    return out


def sealed(build: str, refs: list[str], calibration: str | None,
           require_ok: bool = True) -> tuple[dict, dict, dict[str, bytes]]:
    """(build.json, check.json, verified_files()) of a build whose check still holds, or a refusal naming what
    changed."""
    bpath, cpath = os.path.join(build, "build.json"), os.path.join(build, "check.json")
    if not os.path.isfile(bpath):
        raise Refused("not-built", f"{build} has no build.json")
    if not os.path.isfile(cpath):
        raise Refused("not-checked", f"{build} has no check.json. Run check_logo.py on it first.")
    raw = read_bytes(bpath)
    info, chk = json.loads(raw), read_json(cpath)
    if chk.get("build_sha256") != sha256_bytes(raw):
        raise Refused("stale-check", f"{build}/build.json changed since check_logo.py ran (a new build?). Check it again.")
    files = verified_files(build, info)
    if chk.get("refs_sha256") != refs_sha256(refs):
        raise Refused("refs-changed", f"the --refs folders now hold other files than when {build} was checked. Pass the "
                                      "same folders, or check again against these.")
    if chk.get("calibration_sha256") != sha256_file(calibration_file(calibration)):
        raise Refused("calibration-changed", f"{build} was checked with another calibration. Pass the same --calibration, "
                                             "or check again.")
    if require_ok and not chk.get("ok"):
        raise Refused("check-failed", f"{build} failed check_logo.py. Change the recipe, build and check again.")
    return info, chk, files

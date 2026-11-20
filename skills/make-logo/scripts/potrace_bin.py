# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow"]
# ///
"""Find potrace for trace_ref.py: the one on PATH first; else, on linux-x86_64, the pinned 1.16 build from potrace's
own site, kept in `${XDG_CACHE_HOME:-~/.cache}/hstack/make-logo/potrace/` only when the archive and the binary match
their sha256. Other platforms get the install command.

    uv run potrace_bin.py        # prints the potrace it would use, fetching the pinned build if needed
"""
from __future__ import annotations

import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rights as R  # noqa: E402

VERSION = "1.16"
URL = "https://potrace.sourceforge.net/download/1.16/potrace-1.16.linux-x86_64.tar.gz"
# Checked 2026-11-20: the same bytes as the SHA1 potrace's site publishes (download/SHA1SUMS.html,
# 49f8d3f968ce7466529dc866f4070b9ef6b25b3f) and as an earlier, separate download.
ARCHIVE_SHA256 = "158ef1cb6bde9f057510c7aa8b555117be10fa5318cd875f6a26a5811dadc2d8"
MEMBER = "potrace-1.16.linux-x86_64/potrace"
BINARY_SHA256 = "e2d26f8322a7770a6ccdcf30889503b6c61e27ed8a30f13fc8f340174eb435b0"
INSTALL = ("potrace is not on PATH. Install it and run again: brew install potrace (macOS), apt install potrace or "
           "dnf install potrace (Linux), or the build for your system from https://potrace.sourceforge.net/#downloading "
           "(Windows: put potrace.exe on PATH).")


def cached() -> str:
    return os.path.join(R.cache_root(), "potrace", VERSION, "potrace")


def find() -> str | None:
    """potrace without the network: PATH, then the cached pinned build if it is still the pinned binary."""
    on_path = shutil.which("potrace")
    if on_path:
        return os.path.abspath(on_path)
    c = cached()
    if os.path.isfile(c) and R.sha256_file(c) == BINARY_SHA256:
        return c
    return None


def install(dest: str, url: str = URL, archive_sha256: str = ARCHIVE_SHA256, member: str = MEMBER,
            binary_sha256: str = BINARY_SHA256) -> str:
    """Download the archive, refuse it unless it and the binary in it have the pinned sha256, then write the binary."""
    req = urllib.request.Request(url, headers={"User-Agent": "make-logo"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    got = R.sha256_bytes(data)
    if got != archive_sha256:
        raise R.Refused("potrace-hash", f"{url} has sha256 {got}, not the pinned {archive_sha256}; not using it")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        f = tf.extractfile(member)
        if f is None:
            raise R.Refused("potrace-hash", f"{url} holds no {member}")
        blob = f.read()
    got = R.sha256_bytes(blob)
    if got != binary_sha256:
        raise R.Refused("potrace-hash", f"{member} in {url} has sha256 {got}, not the pinned {binary_sha256}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with open(tmp, "wb") as out:
        out.write(blob)
    os.chmod(tmp, 0o755)
    os.replace(tmp, dest)
    return dest


def describe(path: str) -> dict:
    r = subprocess.run([path, "--version"], capture_output=True, text=True, check=True)
    return {"path": os.path.abspath(path), "sha256": R.sha256_file(path), "version": r.stdout.strip().splitlines()[0]}


def resolve() -> dict:
    """{path, sha256, version} of the potrace to use, fetching the pinned build on linux-x86_64 when none is found."""
    p = find()
    if not p:
        if not (sys.platform.startswith("linux") and platform.machine().lower() in ("x86_64", "amd64")):
            raise SystemExit(INSTALL)
        print(f"potrace is not on PATH: fetching the pinned potrace {VERSION} for linux-x86_64 into {cached()}", file=sys.stderr)
        p = install(cached())
    return describe(p)


if __name__ == "__main__":
    print(json.dumps(resolve(), indent=1))

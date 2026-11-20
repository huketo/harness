# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow"]
# ///
"""potrace_bin: PATH first, then the pinned linux-x86_64 build, kept in the cache only when its sha256 matches.
Downloads here are file:// URLs to archives built in the test; nothing reaches the network."""
from __future__ import annotations

import io
import os
import pathlib
import sys
import tarfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_fixtures as G  # noqa: E402
import potrace_bin as P  # noqa: E402
import rights as R  # noqa: E402

FAKE = b"#!/bin/sh\necho 'potrace 1.16. synthetic test binary'\n"


def archive(tmp: str, member: str = P.MEMBER, data: bytes = FAKE) -> tuple[str, str]:
    """A .tar.gz holding one executable at `member`; returns its file:// URL and sha256."""
    path = os.path.join(tmp, "potrace.tar.gz")
    with tarfile.open(path, "w:gz") as tf:
        info = tarfile.TarInfo(member)
        info.size, info.mode = len(data), 0o755
        tf.addfile(info, io.BytesIO(data))
    return pathlib.Path(path).as_uri(), R.sha256_file(path)


class Resolver(unittest.TestCase):
    def setUp(self):
        self.ws = G.Workspace()
        self.addCleanup(self.ws.close)
        self.empty_path = self.ws.path("empty-bin", "x")[:-2]
        os.makedirs(self.empty_path, exist_ok=True)

    def test_refuses_a_download_whose_sha256_differs(self):
        url, _ = archive(self.ws.root)
        with self.assertRaises(R.Refused) as cm:
            P.install(P.cached(), url=url)
        self.assertEqual(cm.exception.reason, "potrace-hash", str(cm.exception))
        self.assertFalse(os.path.exists(P.cached()))

    def test_refuses_an_archive_whose_binary_differs(self):
        url, sha = archive(self.ws.root)
        with self.assertRaises(R.Refused) as cm:
            P.install(P.cached(), url=url, archive_sha256=sha)
        self.assertEqual(cm.exception.reason, "potrace-hash", str(cm.exception))
        self.assertFalse(os.path.exists(P.cached()))

    def test_installs_the_binary_when_both_hashes_match(self):
        url, sha = archive(self.ws.root)
        path = P.install(P.cached(), url=url, archive_sha256=sha, binary_sha256=R.sha256_bytes(FAKE))
        self.assertEqual(path, P.cached())
        self.assertEqual(R.read_bytes(path), FAKE)
        self.assertTrue(os.access(path, os.X_OK))
        self.assertTrue(path.startswith(os.environ["XDG_CACHE_HOME"]))

    def test_find_takes_a_cached_binary_only_when_it_is_the_pinned_one(self):
        os.makedirs(os.path.dirname(P.cached()))
        R.write_bytes(P.cached(), FAKE)
        os.chmod(P.cached(), 0o755)
        with mock.patch.dict(os.environ, {"PATH": self.empty_path}):
            self.assertIsNone(P.find(), "a cached binary that is not the pinned one was taken")
            with mock.patch.object(P, "BINARY_SHA256", R.sha256_bytes(FAKE)):  # the fixture stands in for the pin
                self.assertEqual(P.find(), P.cached())

    def test_other_platforms_are_told_how_to_install(self):
        with mock.patch.dict(os.environ, {"PATH": self.empty_path}), mock.patch.object(P.sys, "platform", "darwin"):
            with self.assertRaises(SystemExit) as cm:
                P.resolve()
        self.assertIn("brew install potrace", str(cm.exception))


if __name__ == "__main__":
    unittest.main()

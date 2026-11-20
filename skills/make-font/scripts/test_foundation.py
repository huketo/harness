# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "uharfbuzz"]
# ///
"""find_foundation.py: GitHub authentication, rate-limit advice, the width axis direction, and the pinned manifest of
Hangul bases, which is all it ranks when the targets' scripts have korean."""
import hashlib
import http.server
import os
import shutil
import tempfile
import threading
import unittest
from unittest import mock

import chain as C
import find_foundation as FF
import fontlib as L
import testfonts as T

TOKEN = "synthetic-token-value-for-tests"


class GitHubAuth(unittest.TestCase):
    def test_token_goes_only_to_github(self):
        env = {"GITHUB_TOKEN": TOKEN}
        self.assertEqual(FF.auth_headers(FF.TREE, env), {"Authorization": f"Bearer {TOKEN}"})
        self.assertEqual(FF.auth_headers(FF.RAW + "ofl/x/OFL.txt", env), {"Authorization": f"Bearer {TOKEN}"})
        self.assertEqual(FF.auth_headers(FF.CATALOG, env), {})
        self.assertEqual(FF.auth_headers(FF.COARSE.format(id="x", w=400), env), {})
        self.assertEqual(FF.auth_headers(FF.TREE, {}), {})

    def test_no_token_over_plain_http_even_to_a_github_host(self):
        env = {"GITHUB_TOKEN": TOKEN}
        self.assertEqual(FF.auth_headers("http://api.github.com/repos/google/fonts", env), {})
        self.assertEqual(FF.auth_headers("http://raw.githubusercontent.com/google/fonts/main/x", env), {})
        self.assertEqual(FF.auth_headers("https://api.github.com:8443/repos/google/fonts", env), {})

    def test_curl_gets_the_token_on_stdin_not_in_its_arguments(self):
        argv, config = FF.curl_command(FF.TREE, "/tmp/out.json", "/tmp/headers.txt", {"GITHUB_TOKEN": TOKEN})
        self.assertNotIn(TOKEN, " ".join(argv))
        self.assertIn(TOKEN, config)
        argv, config = FF.curl_command(FF.CATALOG, "/tmp/out.json", "/tmp/headers.txt", {"GITHUB_TOKEN": TOKEN})
        self.assertNotIn(TOKEN, config)

    def test_curl_reads_no_config_file_only_its_standard_input(self):
        argv, _ = FF.curl_command(FF.TREE, "/tmp/out.json", "/tmp/headers.txt", {"GITHUB_TOKEN": TOKEN})
        self.assertEqual(argv[:2], ["curl", "--disable"], "--disable works only as curl's first argument")
        self.assertEqual(argv[argv.index("--config") + 1], "-")


class Server:
    """A local HTTP server that records the headers of every request. With `to`, it redirects every request
    there; else it answers 200 with a body."""

    def __init__(self, test, to=None):
        seen = self.seen = []

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append({k.lower(): v for k, v in self.headers.items()})
                if to and self.path == "/start":
                    self.send_response(302)
                    self.send_header("Location", to() if callable(to) else to)
                    self.end_headers()
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"synthetic font bytes")

            def log_message(self, *a):
                pass
        self.srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        test.addCleanup(self.srv.server_close)
        test.addCleanup(self.srv.shutdown)
        self.port = self.srv.server_address[1]
        self.origin = ("http", "127.0.0.1", self.port)

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"


class Redirects(unittest.TestCase):
    """The token goes only to an allowed origin, on every hop of a redirect. Server A stands in for a GitHub host
    (its origin is allowed for the test); server B is another origin, same host, other port."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="mf-redirect-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.b = Server(self)
        self.a = Server(self, to=self.b.url("/file"))
        env = mock.patch.dict(os.environ, {"GITHUB_TOKEN": TOKEN}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        origins = mock.patch.object(FF, "AUTH_ORIGINS", frozenset({self.a.origin}))
        origins.start()
        self.addCleanup(origins.stop)

    def assert_token_stayed_home(self, path):
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), b"synthetic font bytes")
        self.assertEqual([h.get("authorization") for h in self.a.seen], [f"Bearer {TOKEN}"])
        self.assertEqual(len(self.b.seen), 1)
        self.assertNotIn("authorization", self.b.seen[0], "the token followed the redirect to another origin")

    def test_urllib_drops_the_token_when_a_redirect_leaves_the_origin(self):
        path = os.path.join(self.dir, "font.ttf")
        FF.fetch(self.a.url("/start"), path)
        self.assert_token_stayed_home(path)

    def test_curl_drops_the_token_when_a_redirect_leaves_the_origin(self):
        if not shutil.which("curl"):
            self.skipTest("curl is not on PATH, so the curl path cannot run here")
        path = os.path.join(self.dir, "font.ttf")
        FF.curl_fetch(self.a.url("/start"), path)
        self.assert_token_stayed_home(path)

    def test_curl_ignores_the_users_curlrc(self):
        """A ~/.curlrc could log every header (trace-ascii) or send the token on (location-trusted)."""
        if not shutil.which("curl"):
            self.skipTest("curl is not on PATH, so the curl path cannot run here")
        home = os.path.join(self.dir, "home")
        os.makedirs(home)
        for name in (".curlrc", "curlrc"):
            with open(os.path.join(home, name), "w", encoding="utf-8") as fh:
                fh.write('header = "X-From-Curlrc: read"\n')
        with mock.patch.dict(os.environ, {"HOME": home, "CURL_HOME": home, "XDG_CONFIG_HOME": home}):
            FF.curl_fetch(self.b.url("/file"), os.path.join(self.dir, "font.ttf"))
        self.assertEqual(len(self.b.seen), 1)
        self.assertNotIn("x-from-curlrc", self.b.seen[0], "curl read the user's config file")

    def test_urllib_keeps_the_token_on_a_redirect_within_the_origin(self):
        home = Server(self, to=lambda: home.url("/file"))
        with mock.patch.object(FF, "AUTH_ORIGINS", frozenset({home.origin})):
            FF.fetch(home.url("/start"), os.path.join(self.dir, "font.ttf"))
        self.assertEqual([h.get("authorization") for h in home.seen], [f"Bearer {TOKEN}"] * 2)


class RateLimit(unittest.TestCase):
    def serve(self, status, headers):
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(b'{"message": "API rate limit exceeded"}')

            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_address[1]}/repos/google/fonts/git/trees/main"

    def fetch_error(self, url, env):
        d = tempfile.mkdtemp(prefix="mf-fetch-")
        self.addCleanup(shutil.rmtree, d, True)
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(FF.FetchError) as cm:
                FF.fetch(url, os.path.join(d, "tree.json"))
        self.assertFalse(os.path.exists(os.path.join(d, "tree.json")))
        return str(cm.exception)

    def test_403_names_the_remaining_limit_and_the_fix(self):
        url = self.serve(403, {"X-RateLimit-Limit": "60", "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1767225600"})
        msg = self.fetch_error(url, {})
        self.assertIn("403", msg)
        self.assertIn("0 of 60", msg)
        self.assertIn("2026-01-01 00:00 UTC", msg)
        self.assertIn("GITHUB_TOKEN", msg)
        self.assertIn("--offline", msg)

    def test_429_with_a_token_never_prints_it(self):
        url = self.serve(429, {"Retry-After": "30"})
        msg = self.fetch_error(url, {"GITHUB_TOKEN": TOKEN})
        self.assertIn("429", msg)
        self.assertIn("30 s", msg)
        self.assertNotIn(TOKEN, msg)


class WidthAxis(unittest.TestCase):
    def test_room_on_each_side_of_the_location(self):
        self.assertEqual(FF.wdth_room({"wdth": (75, 100, 100)}, {}), {"narrow": True, "widen": False})
        self.assertEqual(FF.wdth_room({"wdth": (75, 100, 125)}, {"wdth": 125}), {"narrow": True, "widen": False})
        self.assertEqual(FF.wdth_room({"wdth": (100, 100, 125)}, {}), {"narrow": False, "widen": True})
        self.assertEqual(FF.wdth_room({"wght": (100, 400, 900)}, {}), {"narrow": False, "widen": False})

    def test_a_width_gap_counts_less_only_when_the_axis_can_close_it(self):
        weight = FF.width_weight({"wdth": (75, 100, 100)}, {})
        self.assertLess(weight("lc_round", +0.05), 1.0)   # too wide: the axis can narrow it
        self.assertEqual(weight("lc_round", -0.05), 1.0)  # too narrow: this axis cannot widen
        static = FF.width_weight({"wght": (100, 400, 900)}, {})
        self.assertEqual(static("lc_round", +0.05), 1.0)

    def test_the_axis_penalty_ignores_a_width_axis_pointing_the_wrong_way(self):
        axes = {"wdth": (75, 100, 100), "wght": (100, 400, 900)}
        self.assertEqual(FF.axis_penalty(axes, {"w_lc_round": +0.06}), 0.0)
        self.assertGreater(FF.axis_penalty(axes, {"w_lc_round": -0.06}), 0.0)


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class HangulManifest(unittest.TestCase):
    """Synthetic manifests of Hangul bases, each file already in the cache where find_foundation.py keeps it: one
    with the targets' own proportions, one whose Hangul is drawn 1.2 times larger against its Latin, one whose cached
    file is not the pinned one, and one without the modern syllables."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="mf-manifest-")
        p = cls.p = staticmethod(lambda *n: os.path.join(cls.dir, *n))
        cls.cache = p("cache")
        cls.manifest = {"families": {}}
        ofl = T.write(p("OFL.txt"), T.ofl_text())
        every = dict(syllables=L.MODERN_SYLLABLES, alphabet=True)
        fonts = {"near": every, "far": dict(every, scale=1.2), "changed": every, "few": dict(alphabet=True)}
        for key, kw in fonts.items():
            folder = os.path.join(cls.cache, "manifest", key)
            os.makedirs(folder)
            url = f"https://fonts.example/{key}/Lumen%5Bwght%5D.ttf"
            font = T.hangul_vf(os.path.join(folder, FF.safe_file(url)), **kw)
            lic = shutil.copy(ofl, os.path.join(folder, "OFL.txt"))
            cls.manifest["families"][key] = {
                "family": f"Lumen {key.title()}", "category": "sans", "version": "1.000", "rfn": [],
                "license": {"url": f"https://fonts.example/{key}/OFL.txt", "sha256": sha256(lic)},
                "files": [{"weight": "100 900", "url": url,
                           "sha256": "0" * 64 if key == "changed" else sha256(font)}]}
        T.instance(T.hangul_vf(p("ref.ttf"), alphabet=True), p("ref-400.ttf"), 400)
        assert T.run("measure_font.py", p("ref-400.ttf"), "--out", p("m.json")).returncode == 0
        r = T.run("make_targets.py", p("m.json"), "--family", T.NEW_FAMILY, "--scripts", "latin,korean", "--out",
                  p("targets.json"))
        assert r.returncode == 0, r.stderr
        cls.T = L.load_json(p("targets.json"))
        with mock.patch("builtins.print") as said:
            cls.rows = FF.manifest_rows(cls.manifest, cls.cache, cls.T, offline=True)
        cls.said = " ".join(str(c.args[0]) for c in said.call_args_list)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def test_only_qualified_files_with_the_pinned_sha256_are_ranked(self):
        self.assertEqual(sorted(r["manifest_entry"] for r in self.rows), ["far", "near"], self.said)
        self.assertIn("skip Lumen Changed: Lumen[wght].ttf has sha256", self.said)
        self.assertIn("skip Lumen Few:", self.said)
        near, far = (next(r for r in self.rows if r["manifest_entry"] == k) for k in ("near", "far"))
        self.assertLess(near["distance"], 1)
        self.assertGreater(far["distance"], near["distance"] + 5)
        self.assertGreater(abs(far["deltas"]["hangul.H1.face_h_cap"]), 0.15)
        self.assertEqual(near["origin"], "manifest/near")
        self.assertEqual(near["coverage"]["korean"], "2350 of 2350")

    def test_qualify_names_what_a_hangul_base_lacks(self):
        from fontTools.ttLib import TTFont
        few = TTFont(os.path.join(self.cache, "manifest", "few", "Lumen[wght].ttf"))
        problems = FF.qualify(few, T.ofl_text())
        self.assertTrue(any("of the 11172 modern Hangul syllables missing" in x for x in problems), problems)
        self.assertTrue(any("OFL.txt" in x for x in FF.qualify(few, T.APACHE_TEXT)))
        static = TTFont(T.glyf_static(self.p("static.ttf")))
        self.assertIn("not a TrueType (glyf) variable font", FF.qualify(static, T.ofl_text()))

    def test_the_approval_question_names_the_pinned_manifest_entry(self):
        L.save_json({"rows": self.rows}, self.p("shortlist.json"))
        skill = T.pinned_skill(self.p("approval"), self.manifest)
        r = T.run("record_base.py", "--shortlist", self.p("shortlist.json"), "--family", "Lumen Near",
                  "--question-only", "--out", self.p("base.json"), skill=skill)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("from the pinned manifest entry near (https://fonts.example/near/Lumen%5Bwght%5D.ttf)", r.stdout)

    def test_korean_targets_search_the_manifest_and_nothing_else(self):
        out = self.p("shortlist-cli.json")
        r = T.run("find_foundation.py", self.p("targets.json"), "--cache", self.p("empty-cache"), "--offline",
                  "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ranking the pinned bases of bases.json only", r.stdout)
        self.assertNotIn("catalogue", r.stdout)
        self.assertIn("not in the cache", r.stdout)  # the pinned base, never downloaded here
        self.assertEqual(L.load_json(out)["rows"], [])
        for flag in (("--local", self.dir), ("--families", "Lumen Near")):
            with self.subTest(flag=flag[0]):
                r = T.run("find_foundation.py", self.p("targets.json"), "--cache", self.p("empty-cache"), "--offline",
                          *flag, "--out", out)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("pinned manifest", r.stderr)

    def test_the_pinned_manifest_names_each_file_by_a_commit_and_its_sha256(self):
        pinned = L.load_json(C.MANIFEST)["families"]
        self.assertEqual(list(pinned), ["noto-sans-kr"])
        for key, e in pinned.items():
            for f in [*e["files"], e["license"]]:
                with self.subTest(entry=key, url=f["url"]):
                    self.assertRegex(f["sha256"], r"^[0-9a-f]{64}$")
                    self.assertRegex(f["url"], r"^https://raw\.githubusercontent\.com/google/fonts/[0-9a-f]{40}/")
            self.assertEqual(e["rfn"], ["Source"])


if __name__ == "__main__":
    unittest.main()

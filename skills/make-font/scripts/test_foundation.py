# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools", "uharfbuzz"]
# ///
"""find_foundation.py: GitHub authentication, rate-limit advice and the width axis direction."""
import http.server
import os
import shutil
import tempfile
import threading
import unittest
from unittest import mock

import find_foundation as FF

TOKEN = "synthetic-token-value-for-tests"


class GitHubAuth(unittest.TestCase):
    def test_token_goes_only_to_github(self):
        env = {"GITHUB_TOKEN": TOKEN}
        self.assertEqual(FF.auth_headers(FF.TREE, env), {"Authorization": f"Bearer {TOKEN}"})
        self.assertEqual(FF.auth_headers(FF.RAW + "ofl/x/OFL.txt", env), {"Authorization": f"Bearer {TOKEN}"})
        self.assertEqual(FF.auth_headers(FF.CATALOG, env), {})
        self.assertEqual(FF.auth_headers(FF.COARSE.format(id="x", w=400), env), {})
        self.assertEqual(FF.auth_headers(FF.TREE, {}), {})

    def test_curl_gets_the_token_on_stdin_not_in_its_arguments(self):
        argv, config = FF.curl_command(FF.TREE, "/tmp/out.json", "/tmp/headers.txt", {"GITHUB_TOKEN": TOKEN})
        self.assertNotIn(TOKEN, " ".join(argv))
        self.assertIn(TOKEN, config)
        argv, config = FF.curl_command(FF.CATALOG, "/tmp/out.json", "/tmp/headers.txt", {"GITHUB_TOKEN": TOKEN})
        self.assertNotIn(TOKEN, config)


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


if __name__ == "__main__":
    unittest.main()

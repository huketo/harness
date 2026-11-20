# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "skia-pathops", "fonttools", "uharfbuzz", "resvg-py"]
# ///
"""The tracing gates: trace_ref.trace() refuses a source the person holds no stated rights in, a collected file, and a
mask or vector close to a collected or reference logo; build_logo.py re-runs it for every trace shape, and
check_logo.py leaves out only the verified source. Synthetic marks, a temporary cache, potrace from potrace_bin."""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_logo as B  # noqa: E402
import check_logo as C  # noqa: E402
import distance as D  # noqa: E402
import gate_fixtures as G  # noqa: E402
import rights as R  # noqa: E402
import trace_ref as T  # noqa: E402

LIMIT = D.load_calibration(None)["limit"]


def reencoded(im: Image.Image) -> Image.Image:
    """The same picture saved again: smaller and as a JPEG, so its bytes and hash differ."""
    buf = io.BytesIO()
    im.resize((450, 450), Image.LANCZOS).save(buf, "JPEG", quality=80)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


@G.needs_potrace
class TraceGates(unittest.TestCase):
    def setUp(self):
        self.ws = G.Workspace()
        self.addCleanup(self.ws.close)
        self.ext = G.mark_image(G.external)
        self.arena = self.ws.collection("arena", {"logos/50000001.png": self.ext})
        self.mine = os.path.dirname(self.ws.image("refs/mine/liked.png", G.mark_image(lambda d, x, y, s: d.ellipse([x, y, x + s, y + s], fill="black"))))
        self.sketch = self.ws.image("sketches/own.png", G.mark_image(G.own))
        self.out = self.ws.path("trace", "t.svg")

    def trace(self, source: str, entries: list[dict], refs: list[str] | None = None, **kw) -> dict:
        brief = self.ws.brief(entries)
        return T.trace(source, brief=brief, refs=refs or [self.mine, self.arena], out=self.out, **kw)

    def refused(self, reason: str, source: str, entries: list[dict], **kw) -> R.Refused:
        with self.assertRaises(R.Refused) as cm:
            self.trace(source, entries, **kw)
        self.assertEqual(cm.exception.reason, reason, str(cm.exception))
        self.assertFalse(os.path.exists(self.out), "a refused trace wrote its SVG")
        return cm.exception

    def test_refuses_a_file_not_in_trace_sources(self):
        other = self.ws.image("sketches/other.png", G.mark_image(G.own).rotate(90))
        self.refused("not-in-brief", self.sketch, [self.ws.entry(other)])

    def test_refuses_a_file_whose_hash_is_in_a_collection_manifest(self):
        collected = os.path.join(self.arena, "logos", "50000001.png")
        self.refused("collected", collected, [self.ws.entry(collected)])

    def test_refuses_a_renamed_collected_file(self):
        renamed = self.ws.path("sketches", "my-drawing.png")
        shutil.copyfile(os.path.join(self.arena, "logos", "50000001.png"), renamed)
        self.refused("collected", renamed, [self.ws.entry(renamed)])

    def test_refuses_a_re_encoded_collected_file_by_its_mask(self):
        resaved = self.ws.image("sketches/resaved.jpg", reencoded(self.ext), "JPEG", quality=90)
        e = self.refused("mask-too-close", resaved, [self.ws.entry(resaved)])
        self.assertGreaterEqual(e.detail["mask_nearest"]["score"], LIMIT)

    def test_refuses_one_external_mark_cropped_out_of_two_shapes(self):
        im, d = G.canvas(1100, 520)
        G.own(d, 40, 60, 400)
        G.external(d, 640, 60, 400)
        both = self.ws.image("sketches/both.png", im)
        whole = self.trace(both, [self.ws.entry(both)])
        print(f"\n  whole raster: mask {whole['provenance']['gate']['mask_nearest']['score']:.4f}, limit {LIMIT:.4f}")
        self.assertLess(whole["provenance"]["gate"]["mask_nearest"]["score"], LIMIT)
        os.remove(self.out)
        e = self.refused("mask-too-close", both, [self.ws.entry(both)], crop=(0.55, 0, 0.45, 1))
        print(f"  cropped mark: mask {e.detail['mask_nearest']['score']:.4f}")
        self.assertGreaterEqual(e.detail["mask_nearest"]["score"], LIMIT)

    def test_refuses_a_small_external_mark_beside_dots_by_its_vector(self):
        im, d = G.canvas(1200, 400)
        G.external(d, 40, 110, 180)
        G.halftone(d, 330, 20, 1180, 380)
        wide = self.ws.image("sketches/wide.png", im)
        e = self.refused("vector-too-close", wide, [self.ws.entry(wide)])
        mask, vector = e.detail["mask_nearest"]["score"], e.detail["vector_nearest"]["score"]
        print(f"\n  wide canvas: mask {mask:.4f}, vector {vector:.4f}, limit {LIMIT:.4f}")
        self.assertLess(mask, LIMIT)
        self.assertGreaterEqual(vector, LIMIT)

    def test_own_sketch_in_the_moodboard_is_left_out_and_other_references_are_not(self):
        shutil.copyfile(self.sketch, os.path.join(self.mine, "own-sketch.png"))
        r = self.trace(self.sketch, [self.ws.entry(self.sketch)])
        self.assertLess(r["provenance"]["gate"]["mask_nearest"]["score"], LIMIT)
        self.assertLess(r["provenance"]["gate"]["vector_nearest"]["score"], LIMIT)
        os.remove(self.out)
        self.ws.image("refs/mine/own-sketch-copy.jpg", reencoded(G.mark_image(G.own)), "JPEG", quality=90)
        e = self.refused("mask-too-close", self.sketch, [self.ws.entry(self.sketch)])
        self.assertTrue(e.detail["mask_nearest"]["ref"].endswith("own-sketch-copy.jpg"))

    def test_writes_provenance_beside_the_svg(self):
        entry = self.ws.entry(self.sketch)
        r = self.trace(self.sketch, [entry], crop=(0.1, 0.1, 0.8, 0.8), threshold=0.4)
        rec = R.read_json(self.out + ".provenance.json")
        self.assertEqual(rec, r["provenance"])
        self.assertEqual(rec["schema"], "make-logo/trace@1")
        self.assertEqual(rec["source"], {"file": os.path.abspath(self.sketch), "sha256": R.sha256_file(self.sketch)})
        self.assertEqual(rec["trace_source"], entry)
        self.assertEqual(rec["brief_sha256"], R.sha256_file(self.ws.path("brief.json")))
        self.assertEqual(rec["raster"]["crop"], [0.1, 0.1, 0.8, 0.8])
        self.assertEqual((rec["raster"]["threshold"], rec["raster"]["invert"], rec["raster"]["long_side"]), (0.4, False, 1200))
        self.assertIn("--turdsize", rec["raster"]["potrace_args"])
        self.assertRegex(rec["mask_sha256"], "^[0-9a-f]{64}$")
        self.assertEqual(rec["gate"]["calibration_sha256"], R.sha256_file(R.calibration_file(None)))
        self.assertEqual(rec["gate"]["refs_sha256"], R.refs_sha256([self.mine, self.arena]))
        self.assertEqual(rec["gate"]["collected_sha256"], R.collected_sha256())
        self.assertEqual(rec["gate"]["limit"], LIMIT)
        self.assertEqual(rec["potrace"]["sha256"], R.sha256_file(rec["potrace"]["path"]))
        self.assertIn("1.16", rec["potrace"]["version"])
        self.assertEqual(rec["svg_sha256"], R.sha256_file(self.out))


@G.needs_potrace
class BuildGates(unittest.TestCase):
    """build_logo.py trusts no trace SVG: it checks the record, then traces again with every gate."""

    def setUp(self):
        self.ws = G.Workspace()
        self.addCleanup(self.ws.close)
        self.arena = self.ws.collection("arena", {"logos/50000001.png": G.mark_image(G.external)})
        self.mine = os.path.dirname(self.ws.image("refs/mine/liked.png", G.mark_image(lambda d, x, y, s: d.ellipse([x, y, x + s, y + s], fill="black"))))
        self.sketch = self.ws.image("sketches/own.png", G.mark_image(G.own))
        self.brief = self.ws.brief([self.ws.entry(self.sketch)])
        self.svg = self.ws.path("trace", "own.svg")
        T.trace(self.sketch, brief=self.brief, refs=[self.mine, self.arena], out=self.svg)

    def recipe(self, file: str = "trace/own.svg", **extra) -> str:
        spec = {"name": "Tessera", "title": "Own L", "idea": "The person's own L, cut once.", "grid": 48,
                "mark": [{"shape": "trace", "file": file, "x": 2, "y": 2, "size": 44},
                         {"op": "cut", "shape": "rect", "x": 20, "y": 20, "w": 4, "h": 4}],
                "palette": {"ink": "#151515", "paper": "#f7f5f1", "accent": "#e8562a", "neutral": "#9b9187", "tint": "#e7e2da"},
                **extra}
        p = self.ws.path("dirs", "own.json")
        R.write_bytes(p, json.dumps(spec).encode())
        return p

    def build(self, recipe: str, out: str = "build/own") -> str:
        out = os.path.join(self.ws.root, out)
        cwd = os.getcwd()
        os.chdir(self.ws.root)
        try:
            B.main([recipe, "--out", out, "--fonts", self.ws.fonts, "--brief", self.brief, "--refs", self.mine, self.arena])
        finally:
            os.chdir(cwd)
        return out

    def assert_build_refused(self, reason: str, recipe: str) -> None:
        with self.assertRaises(R.Refused) as cm:
            self.build(recipe)
        self.assertEqual(cm.exception.reason, reason, str(cm.exception))
        self.assertFalse(os.path.exists(self.ws.path("build", "own", "build.json")))

    def test_refuses_a_trace_svg_without_its_provenance(self):
        shutil.copyfile(self.svg, self.ws.path("trace", "bare.svg"))
        self.assert_build_refused("no-provenance", self.recipe("trace/bare.svg"))

    def test_refuses_a_trace_svg_whose_hash_differs_from_its_provenance(self):
        R.write_bytes(self.svg, R.read_bytes(self.svg) + "<!-- edited -->\n".encode())
        self.assert_build_refused("svg-changed", self.recipe())

    def test_refuses_traced_from_written_in_the_recipe(self):
        self.assert_build_refused("traced-from", self.recipe(traced_from="mine 2"))

    def test_records_the_trace_it_made_and_never_traced_from(self):
        out = self.build(self.recipe())
        info = R.read_json(os.path.join(out, "build.json"))
        self.assertNotIn("traced_from", json.dumps(info))
        [t] = info["traces"]
        self.assertEqual(t["source_sha256"], R.sha256_file(self.sketch))
        self.assertEqual((t["rights"], t["answer"]), ("own-drawing", G.ANSWER))
        self.assertEqual(t["svg_sha256"], info["files"]["trace/0.svg"])
        self.assertEqual(t["provenance_sha256"], info["files"]["trace/0.svg.provenance.json"])
        for rel, sha in info["files"].items():
            self.assertEqual(R.sha256_file(os.path.join(out, rel)), sha, rel)
        self.assertNotIn("build.json", info["files"])

    def test_resolves_the_trace_path_from_the_working_folder_or_the_recipe(self):
        self.build(self.recipe("trace/own.svg"))
        self.build(self.recipe("../trace/own.svg"), "build/own-2")

    def test_checks_the_collections_again_at_build_time(self):
        self.ws.collection("world", {"cafe/60000001.png": reencoded(G.mark_image(G.own))})
        self.assert_build_refused("mask-too-close", self.recipe())

    def test_check_leaves_out_only_the_verified_source(self):
        shutil.copyfile(self.sketch, os.path.join(self.mine, "own-sketch.png"))
        out = self.build(self.recipe())
        refs = [self.mine, self.arena]
        with self.assertRaises(SystemExit) as cm:
            C.main([out, "--refs", *refs])
        self.assertEqual(cm.exception.code, 0)
        chk = R.read_json(os.path.join(out, "check.json"))
        self.assertTrue(chk["ok"])
        self.assertNotIn("own-sketch.png", json.dumps(chk["nearest"]))
        [s] = chk["source_scores"]
        self.assertEqual(s["source_sha256"], R.sha256_file(self.sketch))
        self.assertEqual(chk["build_sha256"], R.sha256_file(os.path.join(out, "build.json")))
        self.assertEqual(chk["refs_sha256"], R.refs_sha256(refs))
        self.ws.image("refs/mine/own-sketch-copy.jpg", reencoded(G.mark_image(G.own)), "JPEG", quality=90)
        with self.assertRaises(SystemExit) as cm:
            C.main([out, "--refs", *refs])
        self.assertEqual(cm.exception.code, 1)
        row = next(c for c in R.read_json(os.path.join(out, "check.json"))["checks"] if c["check"] == "nearest reference")
        self.assertFalse(row["ok"])


if __name__ == "__main__":
    unittest.main()

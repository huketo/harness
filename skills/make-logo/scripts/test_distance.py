# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "resvg-py"]
# ///
"""distance.py's measures and calibration file, and calibrate.py's --features: synthetic marks drawn with Pillow."""
from __future__ import annotations

import io
import json
import math
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calibrate as C  # noqa: E402
import distance as D  # noqa: E402

SIDE = 600


def mark(*draws) -> np.ndarray:
    """Ink (True) drawn on a SIDE square, cropped to its box the way logolib.segment() returns a mark."""
    im = Image.new("L", (SIDE, SIDE), 0)
    d = ImageDraw.Draw(im)
    for f in draws:
        f(d)
    m = np.array(im) > 127
    rows, cols = np.nonzero(m)
    return m[rows.min():rows.max() + 1, cols.min():cols.max() + 1]


def disc(d):
    d.ellipse([100, 100, 500, 500], fill=255)


def ring_hole(d):
    d.ellipse([188, 188, 412, 412], fill=0)


def carved_l(d):
    """An L cut through the disc, closed inside it."""
    d.rectangle([225, 180, 280, 380], fill=0)
    d.rectangle([225, 325, 390, 380], fill=0)


def compare(a: np.ndarray, b: np.ndarray) -> dict:
    return D.compare(D.prepare(a), D.prepare(b, poses=False))


class CandidateFeatures(unittest.TestCase):
    """negative, skeleton and thickness on pairs whose answer is known by construction."""

    def test_the_same_disc_twice_is_identical_on_every_measure(self):
        d = compare(mark(disc), mark(disc))
        self.assertEqual((d["negative"], d["skeleton"], d["thickness"]), (1.0, 0.0, 0.0), d)

    def test_a_disc_and_a_ring_share_no_negative_space_skeleton_or_thickness(self):
        # The disc's convex hull holds no gap; the ring's is its hole. The disc's skeleton is its centre, 0.88 of the
        # box thick; the ring's is a circle 0.19 of the box thick.
        d = compare(mark(disc), mark(disc, ring_hole))
        self.assertLess(d["negative"], 0.1, d)
        self.assertGreater(d["skeleton"], 150, d)
        self.assertGreater(d["thickness"], 500, d)

    def test_a_disc_and_the_disc_with_an_l_carved_through_it(self):
        d = compare(mark(disc), mark(disc, carved_l))
        self.assertGreater(d["overlap"], 0.8, d)
        self.assertLess(d["negative"], 0.1, d)
        self.assertGreater(d["skeleton"], 150, d)
        self.assertGreater(d["thickness"], 500, d)

    def test_a_carved_disc_and_a_ring_part_on_the_new_measures_though_their_silhouettes_meet(self):
        # The pair the plan names: a coin with an L carved through it against a ring-shaped reference.
        d = compare(mark(disc, carved_l), mark(disc, ring_hole))
        self.assertGreater(d["overlap"], 0.7, d)
        self.assertLess(d["negative"], 0.6, d)
        self.assertGreater(d["skeleton"], 25, d)
        self.assertGreater(d["thickness"], 25, d)

    def test_a_mirrored_copy_matches_on_the_new_measures(self):
        m = mark(disc, carved_l)
        d = compare(m[:, ::-1], m)
        self.assertEqual((d["negative"], d["skeleton"], d["thickness"]), (1.0, 0.0, 0.0), d)


class Calibration(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.pairs = [compare(mark(disc), mark(disc, ring_hole)), compare(mark(disc, carved_l), mark(disc, ring_hole)),
                      compare(mark(disc, carved_l), mark(disc, carved_l))]

    def write(self, fused: dict) -> str:
        path = os.path.join(self.dir, "calibration.json")
        with open(path, "w") as f:
            json.dump({"fused": fused}, f)
        return path

    def test_the_shipped_file_reads_with_its_three_features(self):
        cal = D.load_calibration(None)
        self.assertEqual(cal["features"], ["overlap", "edges/100", "hash"])
        self.assertEqual(len(cal["weights"]), 4)

    def test_the_shipped_file_scores_by_the_three_feature_formula(self):
        cal = D.load_calibration(None)
        w = cal["weights"]
        for d in self.pairs:
            z = w[0] * d["overlap"] + w[1] * d["edges"] / 100 + w[2] * d["hash"] + w[3]
            self.assertEqual(D.fused(d, cal), round(1 / (1 + math.exp(-z)), 4), d)

    def test_fused_uses_only_the_features_the_file_lists(self):
        cal = D.load_calibration(self.write({"weights": [6.0, -2.0], "features": ["negative"], "limit": 0.5}))
        for d in self.pairs:
            moved = {**d, "overlap": 1 - d["overlap"], "edges": 0.0, "hash": 0.0, "skeleton": 999.0, "thickness": 999.0}
            self.assertEqual(D.fused(d, cal), round(1 / (1 + math.exp(-(6 * d["negative"] - 2))), 4), d)
            self.assertEqual(D.fused(moved, cal), D.fused(d, cal))

    def test_a_file_naming_an_unknown_feature_is_refused(self):
        path = self.write({"weights": [1.0, 0.0], "features": ["colour"], "limit": 0.5})
        with self.assertRaises(SystemExit) as cm:
            D.load_calibration(path)
        self.assertIn("colour", str(cm.exception.code))

    def test_a_file_whose_weights_do_not_match_its_features_is_refused(self):
        path = self.write({"weights": [1.0, 2.0, 3.0], "features": ["overlap", "edges/100", "hash"], "limit": 0.5})
        with self.assertRaises(SystemExit):
            D.load_calibration(path)


def png(path: str, m: np.ndarray, margin: int = 60) -> str:
    im = Image.new("L", (m.shape[1] + 2 * margin, m.shape[0] + 2 * margin), 255)
    im.paste(Image.fromarray(np.where(m, 0, 255).astype(np.uint8)), (margin, margin))
    im.convert("RGB").save(path)
    return path


class Cli(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def run_main(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as cm:
            D.main(list(argv))
        return cm.exception.code, out.getvalue()

    def test_no_reference_with_a_mark_is_not_checked_rather_than_clear(self):
        cand = png(os.path.join(self.dir, "cand.png"), mark(disc, carved_l))
        refs = os.path.join(self.dir, "refs")
        os.mkdir(refs)
        Image.new("RGB", (300, 300), "white").save(os.path.join(refs, "blank.png"))
        report = os.path.join(self.dir, "out.json")
        code, out = self.run_main(cand, refs, "--json", report)
        self.assertEqual(code, 2, out)
        self.assertIn("not checked", out)
        self.assertNotIn("clear", out)
        with open(report) as f:
            self.assertEqual(json.load(f)["verdict"], "not checked")

    def test_a_copy_is_too_close_and_another_mark_is_clear(self):
        cand = png(os.path.join(self.dir, "cand.png"), mark(disc, carved_l))
        refs = os.path.join(self.dir, "refs")
        os.mkdir(refs)
        png(os.path.join(refs, "same.png"), mark(disc, carved_l)[:, ::-1])
        self.assertEqual(self.run_main(cand, refs)[0], 1)
        os.remove(os.path.join(refs, "same.png"))
        png(os.path.join(refs, "bar.png"), np.ones((40, 400), bool))
        self.assertEqual(self.run_main(cand, refs)[0], 0)


def shapes() -> list[np.ndarray]:
    """Eight marks unlike each other, enough references for calibrate.py to fit and set a limit."""
    def poly(*pts):
        return lambda d: d.polygon(list(pts), fill=255)

    def rect(*box):
        return lambda d: d.rectangle(list(box), fill=255)

    return [mark(disc), mark(disc, ring_hole), mark(disc, carved_l), mark(poly((300, 100), (500, 480), (100, 480))),
            mark(rect(100, 100, 500, 180), rect(260, 100, 340, 500)), mark(rect(100, 280, 500, 320)),
            mark(rect(120, 120, 480, 480), lambda d: d.rectangle([200, 200, 400, 400], fill=0)),
            mark(poly((300, 100), (360, 260), (500, 260), (390, 360), (430, 500), (300, 410), (170, 500), (210, 360),
                      (100, 260), (240, 260)))]


class Calibrate(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        refs = [{"file": png(os.path.join(self.dir, f"ref-{i}.png"), m), "usable": True}
                for i, m in enumerate(shapes())]
        self.measurements = os.path.join(self.dir, "measurements.json")
        with open(self.measurements, "w") as f:
            json.dump({"references": refs}, f)

    def calibrate(self, *extra: str) -> dict:
        out = os.path.join(self.dir, "calibration.json")
        with redirect_stdout(io.StringIO()):
            C.main([self.measurements, "--out", out, *extra])
        return D.load_calibration(out)

    def test_by_default_it_fits_the_features_of_the_shipped_model(self):
        self.assertEqual(self.calibrate()["features"], D.load_calibration(None)["features"])

    def test_it_fits_and_records_the_features_asked_for(self):
        cal = self.calibrate("--features", "overlap,edges/100,hash,negative,skeleton/100,thickness/100")
        self.assertEqual(cal["features"], ["overlap", "edges/100", "hash", "negative", "skeleton/100", "thickness/100"])
        self.assertEqual(len(cal["weights"]), 7)
        d = compare(mark(disc, carved_l), mark(disc, carved_l))
        self.assertGreater(D.fused(d, cal), cal["limit"])

    def test_an_unknown_feature_is_refused_before_anything_is_measured(self):
        with self.assertRaises(SystemExit) as cm:
            self.calibrate("--features", "overlap,colour")
        self.assertIn("colour", str(cm.exception.code))


if __name__ == "__main__":
    unittest.main()

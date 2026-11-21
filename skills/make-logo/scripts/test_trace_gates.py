# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "skia-pathops", "fonttools", "uharfbuzz", "resvg-py"]
# ///
"""The tracing gates: trace_ref.trace() refuses a source the person holds no stated rights in, a collected file, a
mask or vector close to a collected or reference logo, and the same picture as a collected image (a photo the masks
can't read); build_logo.py re-runs it for every trace shape, and check_logo.py leaves out only the verified source and
runs the same-picture gate again. Synthetic marks and photos, a temporary cache, potrace from potrace_bin."""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

import numpy as np
import resvg_py
from PIL import Image, ImageEnhance

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_logo as B  # noqa: E402
import check_logo as C  # noqa: E402
import distance as D  # noqa: E402
import gate_fixtures as G  # noqa: E402
import logolib as L  # noqa: E402
import rights as R  # noqa: E402
import same_picture as SP  # noqa: E402
import trace_ref as T  # noqa: E402

LIMIT = D.load_calibration(None)["limit"]


def png(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def reencoded(im: Image.Image) -> Image.Image:
    """The same picture saved again: smaller and as a JPEG, so its bytes and hash differ."""
    buf = io.BytesIO()
    im.resize((450, 450), Image.LANCZOS).save(buf, "JPEG", quality=80)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def edited(im: Image.Image) -> dict[str, tuple[Image.Image, str, dict]]:
    """Copies of a picture made to get it past the gates, by file name: saved again, cut, resized, brightened."""
    W, H = im.size
    return {"jpeg-q75.jpg": (im, "JPEG", {"quality": 75}), "webp.webp": (im, "WEBP", {}),
            "cut-4pc.png": (im.crop((round(W * .04), round(H * .04), round(W * .96), round(H * .96))), "PNG", {}),
            "cut-10pc-left.png": (im.crop((round(W * .1), 0, W, H)), "PNG", {}),
            "half-size.png": (im.resize((W // 2, H // 2), Image.LANCZOS), "PNG", {}),
            "brighter.png": (ImageEnhance.Brightness(im).enhance(1.1), "PNG", {})}


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

    def test_refuses_a_re_encoded_copy_of_a_reference_whose_ink_fills_the_frame(self):
        ref = self.ws.image("refs/mine/close-crop.png", G.tight(G.mark_image(G.badge)))
        self.assertFalse(L.usable(L.segment(L.load(ref)))[0], "the fixture must be a reference unfit for measuring")
        copy = self.ws.image("sketches/copy.jpg", G.padded(reencoded(G.tight(G.mark_image(G.badge)))), "JPEG", quality=90)
        e = self.refused("mask-too-close", copy, [self.ws.entry(copy)])
        self.assertTrue(e.detail["mask_nearest"]["ref"].endswith("close-crop.png"), e.detail)

    def test_refuses_a_copy_of_a_16_px_reference(self):
        im, d = G.canvas(16, 16)
        G.badge(d, 4, 4, 8)  # a favicon: the mark 8 px across, padded
        tiny = self.ws.image("refs/mine/favicon.png", im)
        self.assertFalse(L.segment(L.load(tiny))["ok"], "the fixture must be too small to split at its own size")
        copy = self.ws.image("sketches/favicon.bmp", Image.open(tiny), "BMP")
        e = self.refused("mask-too-close", copy, [self.ws.entry(copy)])
        self.assertTrue(e.detail["mask_nearest"]["ref"].endswith("favicon.png"), e.detail)

    def test_refuses_a_rendering_of_a_collected_svg(self):
        self.ws.collection("world", {"marks/70000001.svg": G.badge_svg()})
        png = bytes(resvg_py.svg_to_bytes(svg_string=G.badge_svg().decode(), width=450, background="#ffffff"))
        drawn = self.ws.image("sketches/drawn.png", Image.open(io.BytesIO(png)).convert("RGB"))
        e = self.refused("mask-too-close", drawn, [self.ws.entry(drawn)])
        self.assertTrue(e.detail["mask_nearest"]["ref"].endswith("70000001.svg"), e.detail)

    def test_refuses_a_copy_of_a_light_mark_on_a_transparent_ground(self):
        light = self.ws.image("refs/mine/light.png", G.light_on_clear(G.mark_image(G.badge)))
        self.assertFalse(L.segment(L.load(light))["ok"], "the fixture must show no ink flattened onto white")
        dark = self.ws.image("sketches/dark.jpg", reencoded(G.mark_image(G.badge)), "JPEG", quality=90)
        e = self.refused("mask-too-close", dark, [self.ws.entry(dark)])
        self.assertTrue(e.detail["mask_nearest"]["ref"].endswith("light.png"), e.detail)

    def test_compares_both_grounds_of_a_transparent_reference(self):
        sheet = self.ws.image("refs/mine/sheet.png", G.dark_and_light_on_clear(G.mark_image(G.tee), G.mark_image(G.badge)))
        self.assertTrue(L.segment(L.load(sheet))["ok"], "the fixture must split on white, where only the dark mark shows")
        dark = self.ws.image("sketches/dark.jpg", reencoded(G.mark_image(G.badge)), "JPEG", quality=90)
        e = self.refused("mask-too-close", dark, [self.ws.entry(dark)])
        print(f"\n  light mark on a transparent sheet: mask {e.detail['mask_nearest']['score']:.4f}, limit {LIMIT:.4f}")
        self.assertTrue(e.detail["mask_nearest"]["ref"].endswith("sheet.png"), e.detail)

    def test_refuses_a_sheet_whose_split_leaves_a_mark_out(self):
        sheet = self.ws.image("refs/mine/sheet.png", G.dark_mark_and_small_light_mark())
        self.assertFalse(L.segment(L.flatten(Image.open(sheet), (0, 0, 0)))["ok"],
                         "the fixture's small light mark must be dropped as a speck on black")
        copy = self.ws.image("sketches/badge.jpg", reencoded(G.mark_image(G.badge)), "JPEG", quality=90)
        e = self.refused("not-comparable", copy, [self.ws.entry(copy)])
        self.assertIn(sheet, str(e))
        self.assertIn("one mark", str(e))
        print(f"\n  sheet with a 16 px light mark: {T.gate_masks(R.read_bytes(sheet))[1]}")
        # The person crops the sheet into one file for each mark; the small one is compared, and the copy refused.
        with Image.open(sheet) as im:
            self.ws.image("refs/mine/sheet-tee.png", im.crop((0, 0, 600, 600)))
            self.ws.image("refs/mine/sheet-badge.png", im.crop(G.SMALL_MARK_BOX))
        os.remove(sheet)
        e = self.refused("mask-too-close", copy, [self.ws.entry(copy)])
        print(f"  the small mark cropped on its own: mask {e.detail['mask_nearest']['score']:.4f}, limit {LIMIT:.4f}")
        self.assertTrue(e.detail["mask_nearest"]["ref"].endswith("sheet-badge.png"), e.detail)

    def test_refuses_a_collection_or_a_folder_in_it_that_is_a_link(self):
        entry = self.ws.entry(self.sketch)
        elsewhere = os.path.dirname(self.ws.image("elsewhere/channel/1.png", G.mark_image(G.badge)))
        channel = os.path.join(self.arena, "channel")  # a pull would write through it, and no manifest would list it
        whole = os.path.join(R.cache_root(), "linked")
        for link, target in ((channel, elsewhere), (whole, os.path.dirname(elsewhere))):
            os.symlink(target, link)
            e = self.refused("collection-linked", self.sketch, [entry])
            self.assertIn(link, str(e))
            with self.assertRaises(R.Refused) as cm:  # and so do package_logo.py and logo_book.py (rights.sealed)
                R.collected_sha256()
            self.assertEqual(cm.exception.reason, "collection-linked", str(cm.exception))
            os.remove(link)
        self.assertEqual(self.trace(self.sketch, [entry])["svg"], self.out)

    def test_refuses_a_reference_that_is_not_there_by_name(self):
        entry = self.ws.entry(self.sketch)
        named = self.ws.path("refs", "named.png")  # on the command line, never written
        typo = self.ws.path("refs", "mien")
        link = os.path.join(self.mine, "linked.png")
        os.symlink(self.ws.path("nowhere.png"), link)
        e = self.refused("refs-missing", self.sketch, [entry], refs=[self.mine, self.arena, named, typo])
        for f in (named, typo, link):
            self.assertIn(f, str(e))
        os.remove(link)
        self.assertEqual(self.trace(self.sketch, [entry])["svg"], self.out)

    def test_refuses_while_a_collection_holds_a_file_its_manifest_does_not_list(self):
        entry = self.ws.entry(self.sketch)
        # A pull that wrote an image and stopped before rewriting the manifest.
        unlisted = os.path.join(self.arena, "logos", "50000002.png")
        G.mark_image(G.badge).save(unlisted, "PNG")
        e = self.refused("collection-unlisted", self.sketch, [entry])
        self.assertIn(unlisted, str(e))
        self.assertIn("collection.mjs arena", str(e))
        os.remove(unlisted)
        # Traces of a pull that never finished: a download and a manifest half written, a first pull with no manifest.
        for rel in ("logos/50000003.png.part", "manifest.json.part"):
            R.write_bytes(os.path.join(self.arena, rel), b"half")
            e = self.refused("collection-unlisted", self.sketch, [entry])
            self.assertIn(os.path.join(self.arena, rel), str(e))
            os.remove(os.path.join(self.arena, rel))
        first = os.path.join(R.cache_root(), "fresh", "channel", "1.png")
        os.makedirs(os.path.dirname(first))
        G.mark_image(G.badge).save(first, "PNG")
        e = self.refused("collection-unlisted", self.sketch, [entry])
        self.assertIn("collection.mjs fresh", str(e))
        os.remove(first)
        self.assertEqual(self.trace(self.sketch, [entry])["svg"], self.out)

    def test_refuses_while_a_reference_cannot_be_compared(self):
        blank = self.ws.image("refs/mine/blank.png", Image.new("RGB", (300, 300), "white"))
        broken = self.ws.path("refs", "mine", "broken.png")
        R.write_bytes(broken, b"not an image")
        e = self.refused("not-comparable", self.sketch, [self.ws.entry(self.sketch)])
        for f in (blank, broken):
            self.assertIn(f, str(e))
        os.remove(blank)  # the person takes the files out, or replaces them, and the trace goes on
        os.remove(broken)
        self.assertEqual(self.trace(self.sketch, [self.ws.entry(self.sketch)])["svg"], self.out)

    def test_compares_a_collected_original_the_brief_also_lists(self):
        collected = os.path.join(self.arena, "logos", "50000001.png")
        resaved = self.ws.image("sketches/resaved.jpg", reencoded(self.ext), "JPEG", quality=90)
        e = self.refused("mask-too-close", resaved, [self.ws.entry(collected), self.ws.entry(resaved)])
        self.assertTrue(e.detail["mask_nearest"]["ref"].endswith("50000001.png"), e.detail)

    def test_refuses_edited_copies_of_a_collected_photo_that_the_masks_miss(self):
        self.ws.collection("world", {"mockups/90000001.png": G.photo(0)})
        for name, (im, fmt, save) in edited(G.photo(0)).items():
            with self.subTest(name):
                copy = self.ws.image(f"sketches/{name}", im, fmt, **save)
                self.out = self.ws.path("trace", f"{name}.svg")
                e = self.refused("collected-copy", copy, [self.ws.entry(copy)])
                near = e.detail["copy_nearest"]
                print(f"\n  {name}: same picture {near['score']:.4f} (limit {SP.LIMIT}), mask "
                      f"{e.detail['mask_nearest']['score']:.4f}, path {e.detail['vector_nearest']['score']:.4f}")
                self.assertTrue(near["ref"].endswith("90000001.png"), near)
                self.assertGreaterEqual(near["score"], SP.LIMIT)
                self.assertIn("90000001.png", str(e))
                # What the mask and path gates missed: the photo split by Otsu is not the source cut at 0.5.
                self.assertLess(e.detail["mask_nearest"]["score"], LIMIT)
                self.assertLess(e.detail["vector_nearest"]["score"], LIMIT)

    def test_traces_another_photo_and_records_its_nearest_picture(self):
        self.ws.collection("world", {"mockups/90000001.png": G.photo(0)})
        own = self.ws.image("sketches/own-photo.png", G.photo(1))
        gate = self.trace(own, [self.ws.entry(own)])["provenance"]["gate"]
        self.assertIn("copy_nearest", gate)
        print(f"\n  another photo: same picture {gate['copy_nearest']['score']:.4f} against {gate['copy_nearest']['ref']}")
        self.assertLess(gate["copy_nearest"]["score"], SP.LIMIT)
        self.assertEqual(gate["copy_limit"], SP.LIMIT)

    def test_refuses_the_crop_of_a_page_that_holds_a_collected_photo(self):
        self.ws.collection("world", {"mockups/90000001.png": G.photo(0)})
        page, d = G.canvas(1400, 600)
        page.paste(G.photo(0), (60, 60))
        G.own(d, 860, 100, 400)
        board = self.ws.image("sketches/board.png", page)
        e = self.refused("collected-copy", board, [self.ws.entry(board)], crop=(60 / 1400, 60 / 600, 640 / 1400, 480 / 600))
        self.assertTrue(e.detail["copy_nearest"]["ref"].endswith("90000001.png"), e.detail)
        whole = self.trace(board, [self.ws.entry(board)])["provenance"]["gate"]
        self.assertLess(whole["copy_nearest"]["score"], SP.LIMIT, "the whole page is not the photo")

    def test_refuses_a_cut_out_of_a_collected_photo_whose_clear_ground_hides_no_colour(self):
        # A background remover's cut-out keeps a fifth of the photo and zeroes the colour under the rest, so flattened
        # on any ground it is mostly not the photo; the pixels it shows are the photo's own.
        self.ws.collection("world", {"mockups/90000001.png": G.photo(0)})
        copy = self.ws.image("sketches/cut-out.png", G.photo(0, cut_out=True))
        e = self.refused("collected-copy", copy, [self.ws.entry(copy)])
        self.assertTrue(e.detail["copy_nearest"]["ref"].endswith("90000001.png"), e.detail)

    def test_traces_a_cut_out_of_another_photo(self):
        self.ws.collection("world", {"mockups/90000001.png": G.photo(0)})
        own = self.ws.image("sketches/own-cut-out.png", G.photo(1, cut_out=True))
        gate = self.trace(own, [self.ws.entry(own)])["provenance"]["gate"]
        print(f"\n  another photo's cut-out: same picture {gate['copy_nearest']['score']:.4f}")
        self.assertLess(gate["copy_nearest"]["score"], SP.LIMIT)

    def test_refuses_the_picture_a_collected_jpeg_shows_once_its_exif_orientation_turns_it(self):
        self.ws.collection("world", {"mockups/90000001.jpg": G.exif_turned(G.photo(0))})
        shown = self.ws.image("sketches/shown.png", G.photo(0))
        e = self.refused("collected-copy", shown, [self.ws.entry(shown)])
        self.assertTrue(e.detail["copy_nearest"]["ref"].endswith("90000001.jpg"), e.detail)

    def test_refuses_a_jpeg_whose_exif_orientation_shows_a_collected_photo(self):
        self.ws.collection("world", {"mockups/90000001.png": G.photo(0)})
        turned = self.ws.path("sketches", "turned.jpg")
        R.write_bytes(turned, G.exif_turned(G.photo(0)))
        e = self.refused("collected-copy", turned, [self.ws.entry(turned)])
        self.assertTrue(e.detail["copy_nearest"]["ref"].endswith("90000001.png"), e.detail)

    def test_refuses_a_redrawing_of_the_mark_a_reference_shows_by_its_exif_orientation(self):
        # A JPEG of a mark stored on its side with the EXIF orientation that shows it upright, collected or in --refs.
        # The mark drawn again on a wide page is another picture, which the same-picture gate passes, so only the mask
        # gate can see the copy: it must compare the reference as shown and as stored.
        for name, draw in (("L", G.own), ("triangle", G.badge)):
            turned = G.exif_turned(G.mark_image(draw))
            for where in ("collected", "refs"):
                if where == "collected":
                    ref = os.path.join(self.ws.collection("world", {"logos/90000001.jpg": turned}), "logos",
                                       "90000001.jpg")
                else:
                    ref = self.ws.path("refs", "mine", "turned.jpg")
                    R.write_bytes(ref, turned)
                for seen in ("shown", "stored"):
                    with self.subTest(name, where=where, seen=seen):
                        page, d = G.canvas(900, 500)
                        draw(d, 60, 50, 400)
                        if seen == "stored":
                            page = page.transpose(Image.Transpose.ROTATE_90)
                        redrawn = self.ws.image(f"sketches/{name}-{where}-{seen}.png", page)
                        self.out = self.ws.path("trace", f"{name}-{where}-{seen}.svg")
                        self.assertLess(SP.score(SP.source(R.read_bytes(redrawn)), SP.picture(turned)), SP.LIMIT,
                                        "the redrawing must be another picture")
                        e = self.refused("mask-too-close", redrawn, [self.ws.entry(redrawn)])
                        print(f"\n  {name} redrawn as a {where} EXIF 6 JPEG is {seen}: mask "
                              f"{e.detail['mask_nearest']['score']:.4f}")
                        self.assertEqual(e.detail["mask_nearest"]["ref"], ref)
                if where == "collected":
                    shutil.rmtree(os.path.dirname(os.path.dirname(ref)))
                else:
                    os.remove(ref)

    def test_refuses_a_collected_file_that_no_longer_has_its_manifest_hash(self):
        world = self.ws.collection("world", {"cafe/60000001.png": G.mark_image(G.tee)})
        listed = os.path.join(world, "cafe", "60000001.png")
        G.mark_image(G.badge).save(listed, "PNG")
        self.refused("collection-changed", self.sketch, [self.ws.entry(self.sketch)])
        os.remove(listed)
        self.refused("collection-changed", self.sketch, [self.ws.entry(self.sketch)])

    def test_traces_the_bytes_it_hashed(self):
        entry = self.ws.entry(self.sketch)
        first = self.trace(self.sketch, [entry])["provenance"]["mask_sha256"]
        os.remove(self.out)
        real = R.trace_source

        def changed_after_hashing(*a, **kw):  # another program rewrites the file between the hash and the raster
            G.mark_image(G.own).rotate(90).save(self.sketch, "PNG")
            return real(*a, **kw)

        with mock.patch.object(R, "trace_source", changed_after_hashing):
            r = self.trace(self.sketch, [entry])
        self.assertEqual(r["provenance"]["source"]["sha256"], entry["sha256"])
        self.assertEqual(r["provenance"]["mask_sha256"], first)

    def test_records_the_hashes_of_the_references_and_calibration_it_judged_with(self):
        fresh = self.ws.image("refs/mine/fresh.png", G.mark_image(G.tee))
        cal = self.ws.path("calibration.json")
        shutil.copyfile(R.calibration_file(None), cal)
        refs_before, cal_before = R.refs_sha256([self.mine, self.arena]), R.sha256_file(cal)
        changed = R.read_json(cal)
        changed["fused"]["limit"] = 0.99
        fired, real = [], L.segment

        def change_while_judging(*a, **kw):  # the reference and the calibration change mid-run
            if not fired:
                fired.append(True)
                G.mark_image(G.own).rotate(45).save(fresh, "PNG")
                R.write_bytes(cal, json.dumps(changed).encode())
            return real(*a, **kw)

        # Start with no features cached by an earlier test, so every reference is read and judged now.
        with mock.patch.dict(T._PREPARED, clear=True), mock.patch.object(L, "segment", change_while_judging):
            r = self.trace(self.sketch, [self.ws.entry(self.sketch)], calibration=cal)
        self.assertTrue(fired, "no reference was read while the hook was in place")
        gate = r["provenance"]["gate"]
        self.assertEqual((gate["refs_sha256"], gate["calibration_sha256"], gate["limit"]), (refs_before, cal_before, LIMIT))

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
        self.assertNotIn("not_checked", rec["gate"])
        self.assertEqual(rec["potrace"]["sha256"], R.sha256_file(rec["potrace"]["path"]))
        said = subprocess.run([rec["potrace"]["path"], "--version"], capture_output=True, text=True, check=True).stdout
        self.assertEqual(rec["potrace"]["version"], said.strip().splitlines()[0])
        self.assertEqual(rec["svg_sha256"], R.sha256_file(self.out))


class PartlyClear(unittest.TestCase):
    """same_picture.gate(), which trace, check, package and book all call, on a collected photo copied with part of it
    made clear: every copy that shows MIN_SHOWN or more of the photo and MIN_HELD or more of its subject (the box and
    the ball) is that photo, whatever shape is cleared and whatever colour is left under the clear pixels; the same
    copies of another photo are not. A copy that shows less of the subject is not asked for (references/building.md,
    "Same picture")."""

    SHOWN = (0.9, 0.65, 0.4, 0.2)  # each over MIN_SHOWN
    SHAPES = (("edges", 0), ("centre", 0), ("patches", 8), ("patches", 32))
    HIDDEN = ("kept", "zeroed", "noise")

    @classmethod
    def setUpClass(cls):
        cls.collected = [("world/mockups/90000001.png", "", SP.picture(png(G.photo(0))))]

    def verdicts(self, seed: int, collected=None) -> list[tuple[str, float, str | None, float]]:
        """(copy, share of the subject it shows, refusal or None, score) of each cleared copy of photo `seed` against
        photo 0, or against `collected`."""
        subject = np.asarray(G.photo(seed, cut_out=True).getchannel("A")) > 0
        out = []
        for shown in self.SHOWN:
            for shape, cell in self.SHAPES:
                for hidden in self.HIDDEN:
                    name = f"{shown:.0%} shown, {shape}{f' {cell} px' if cell else ''}, colour {hidden}"
                    copy = G.cleared(G.photo(seed), shown, shape, hidden, cell)
                    held = float((np.asarray(copy.getchannel("A"))[subject] > 0).mean())
                    try:
                        out.append((name, held, None, SP.gate(name, SP.source(png(copy)),
                                                             collected or self.collected)["score"]))
                    except R.Refused as e:
                        out.append((name, held, e.reason, e.detail["copy_nearest"]["score"]))
        return out

    def test_refuses_every_partly_clear_copy_of_a_collected_photo(self):
        verdicts = self.verdicts(0)
        print("\n" + "\n".join(f"  {name}, {held:.0%} of the subject: {score:.4f}" for name, held, _, score in verdicts))
        self.assertGreater(min(self.SHOWN), SP.MIN_SHOWN)
        self.assertEqual([(name, held, score) for name, held, why, score in verdicts
                          if held >= SP.MIN_HELD and why != "collected-copy"], [])

    def test_passes_the_same_copies_of_another_photo(self):
        verdicts = self.verdicts(1)
        print(f"\n  highest: {max(score for *_, score in verdicts):.4f}")
        self.assertEqual([(name, score) for name, _, why, score in verdicts if why is not None], [])

    def test_passes_copies_of_a_photo_against_another_staged_alike(self):
        """Photo 0 with its centre clear holds under a fifth of its detail: what shows is the lit wall around the box and
        the ball, as in photo 1. A refinement free to leave MIN_HELD behind found a window there scoring 0.9469."""
        verdicts = self.verdicts(0, [("world/mockups/90000002.png", "", SP.picture(png(G.photo(1))))])
        print(f"\n  highest: {max(score for *_, score in verdicts):.4f}")
        self.assertEqual([(name, score) for name, _, why, score in verdicts if why is not None], [])

    def test_refuses_a_partly_clear_copy_cut_at_the_edges_too(self):
        """Photo 1 with its centre clear shows 65% of it, and what shows holds about a quarter of its detail at 32 px
        (0.26 to 0.28 once cut 2 to 5% each side) but less at 64 px (0.23 to 0.25), where the sharp edges of the box
        and the ball, in the clear centre, weigh more. Held to MIN_HELD at 64 px too, these copies scored 0.40 to
        0.82."""
        photo = G.photo(1)
        collected = [("world/mockups/90000002.png", "", SP.picture(png(photo)))]
        copy = G.cleared(photo, 0.65, "centre", "zeroed")
        W, H = copy.size
        verdicts = {}
        for cut in (0.02, 0.04, 0.05):
            part = copy.crop((round(cut * W), round(cut * H), round((1 - cut) * W), round((1 - cut) * H)))
            try:
                verdicts[cut] = SP.gate(f"cut {cut:.0%}", SP.source(png(part)), collected)["score"]
            except R.Refused as e:
                verdicts[cut] = e.reason
        self.assertEqual(verdicts, dict.fromkeys(verdicts, "collected-copy"))


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

    def test_refuses_a_record_whose_raster_arguments_were_changed(self):
        rec = self.svg + ".provenance.json"
        prov = R.read_json(rec)
        prov["raster"]["crop"] = [0, 0, 0.9, 1]
        R.write_bytes(rec, json.dumps(prov, indent=1).encode())
        self.assert_build_refused("record-changed", self.recipe())

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
        # Another reference, there when the direction is built, close to what the recipe made of the trace but not to
        # the trace: the trace passes its gates, and the check holds the mark to the usual limit against it.
        out = self.assembled()
        svg = R.read_bytes(os.path.join(out, "mark.svg")).decode()
        png = bytes(resvg_py.svg_to_bytes(svg_string=svg, width=400, background="#ffffff"))
        self.ws.image("refs/mine/like-the-mark.png", G.padded(Image.open(io.BytesIO(png)).convert("RGB")))
        out = self.assembled()
        self.assertEqual(self.check_exit(out).code, 1)
        chk = R.read_json(os.path.join(out, "check.json"))
        self.assertFalse(next(c for c in chk["checks"] if c["check"] == "nearest reference")["ok"])
        self.assertTrue(chk["nearest"][0]["ref"].endswith("like-the-mark.png"), chk["nearest"])

    def assembled(self) -> str:
        """A traced direction whose other shapes take it far from its source, so the distance check alone passes it."""
        return self.build(self.recipe(mark=[{"shape": "trace", "file": "trace/own.svg", "x": 28, "y": 28, "size": 18},
                                            {"shape": "ring", "cx": 16, "cy": 16, "r": 14, "width": 5},
                                            {"shape": "rect", "x": 2, "y": 40, "w": 24, "h": 6}]))

    def check_exit(self, out: str, *extra: str) -> SystemExit:
        with self.assertRaises(SystemExit) as cm:
            C.main([out, "--refs", self.mine, self.arena, *extra])
        return cm.exception

    def assert_check_refused(self, out: str, *extra: str) -> None:
        e = self.check_exit(out, *extra)
        self.assertIsInstance(e, R.Refused, f"check_logo.py exited {e.code} instead of refusing")
        self.assertEqual(e.reason, "trace-gate-stale", str(e))
        self.assertFalse(os.path.exists(os.path.join(out, "check.json")), "a refused check left its old check.json")

    def test_check_refuses_a_trace_gated_before_a_reference_was_added(self):
        out = self.assembled()
        self.assertEqual(self.check_exit(out).code, 0)
        # The person's L drawn again on a wide page: the same mark, another picture.
        page, d = G.canvas(900, 500)
        G.own(d, 60, 50, 400)
        self.ws.image("refs/mine/sketch-on-a-wide-page.png", page)
        with self.assertRaises(R.Refused) as cm:  # the trace gate, run now, refuses the source
            T.trace(self.sketch, brief=self.brief, refs=[self.mine, self.arena], out=self.ws.path("trace", "again.svg"))
        self.assertEqual(cm.exception.reason, "mask-too-close")
        self.assert_check_refused(out)

    def test_check_refuses_a_trace_gated_with_another_calibration(self):
        out = self.assembled()
        cal = R.read_json(R.calibration_file(None))
        cal["fused"]["limit"] = 0.95
        other = self.ws.path("calibration.json")
        R.write_bytes(other, json.dumps(cal).encode())
        self.assert_check_refused(out, "--calibration", other)

    def test_check_refuses_once_a_collected_file_changed(self):
        photos = self.ws.collection("photos", {"p/80000001.png": G.mark_image(G.tee)})
        out = self.assembled()
        self.assertEqual(self.check_exit(out).code, 0)
        G.mark_image(G.badge).save(os.path.join(photos, "p", "80000001.png"), "PNG")
        e = self.check_exit(out)
        self.assertIsInstance(e, R.Refused, f"check_logo.py exited {e.code} instead of refusing")
        self.assertEqual(e.reason, "collection-changed", str(e))
        self.assertFalse(os.path.exists(os.path.join(out, "check.json")), "a refused check left its old check.json")

    def test_check_refuses_while_a_collection_holds_a_file_its_manifest_does_not_list(self):
        world = self.ws.collection("world", {"cafe/60000001.png": G.mark_image(G.tee)})  # outside --refs
        out = self.assembled()
        self.assertEqual(self.check_exit(out).code, 0)
        G.mark_image(G.badge).save(os.path.join(world, "cafe", "60000002.png"), "PNG")
        e = self.check_exit(out)
        self.assertIsInstance(e, R.Refused, f"check_logo.py exited {e.code} instead of refusing")
        self.assertEqual(e.reason, "collection-unlisted", str(e))
        self.assertFalse(os.path.exists(os.path.join(out, "check.json")), "a refused check left its old check.json")

    def test_check_refuses_once_a_copy_of_the_source_is_collected(self):
        out = self.assembled()
        self.assertEqual(self.check_exit(out).code, 0)
        world = self.ws.collection("world", {"cafe/60000001.png": reencoded(G.mark_image(G.own))})
        e = self.check_exit(out)
        self.assertIsInstance(e, R.Refused, f"check_logo.py exited {e.code} instead of refusing")
        self.assertEqual(e.reason, "collected-copy", str(e))
        self.assertIn(os.path.join(world, "cafe", "60000001.png"), str(e))
        self.assertFalse(os.path.exists(os.path.join(out, "check.json")), "a refused check left its old check.json")

    def test_check_refuses_a_trace_gated_before_a_collection_was_added(self):
        out = self.assembled()
        self.assertEqual(self.check_exit(out).code, 0)
        self.ws.collection("world", {"cafe/60000001.png": G.mark_image(G.badge)})
        self.assert_check_refused(out)


if __name__ == "__main__":
    unittest.main()

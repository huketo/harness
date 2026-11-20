# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "skia-pathops", "fonttools", "uharfbuzz", "resvg-py"]
# ///
"""The seal between the steps: build.json lists every file the build wrote with its sha256, check.json binds that
build.json, the --refs folders and the calibration, and package_logo.py and logo_book.py go on only while all of it
still matches. Also the book and the trademark sheet: what they show, in the brief's language. Synthetic marks and
fonts, a temporary cache."""
from __future__ import annotations

import html
import io
import json
import os
import re
import shutil
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

import resvg_py
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_logo as B  # noqa: E402
import check_logo as C  # noqa: E402
import distance as D  # noqa: E402
import gate_fixtures as G  # noqa: E402
import logo_book as LB  # noqa: E402
import logolib as L  # noqa: E402
import package_logo as PK  # noqa: E402
import rights as R  # noqa: E402
import same_picture as SP  # noqa: E402
import trace_ref as T  # noqa: E402

LIMIT = D.load_calibration(None)["limit"]
FAKE_PATH = "M0 0L9 0L9 9Z"

PALETTE = {"ink": "#151515", "paper": "#f7f5f1", "accent": "#c2410c", "neutral": "#9b9187", "tint": "#e7e2da"}


class Project(unittest.TestCase):
    """A workspace with one reference folder and one collection, and helpers that run each step's main()."""

    def setUp(self):
        self.ws = G.Workspace()
        self.addCleanup(self.ws.close)
        self.mine = os.path.dirname(self.ws.image("refs/mine/liked.png", G.mark_image(G.external)))
        self.refs = [self.mine]
        self.brief = self.ws.brief([])

    def recipe(self, name: str = "one", wordmark: bool = True, mark: list | None = None, **extra) -> str:
        spec = {"name": "Tessera", "title": f"Direction {name}", "idea": "Two squares, one turned.", "grid": 48,
                "mark": mark or [{"shape": "rect", "x": 6, "y": 6, "w": 24, "h": 24},
                                 {"op": "xor", "shape": "rect", "x": 18, "y": 18, "w": 24, "h": 24, "rotate": 12}],
                "palette": PALETTE, **extra}
        if wordmark:
            spec["wordmark"] = {"text": "Tessera", "font": "Tessera Sans", "weight": 400}
        p = self.ws.path("dirs", f"{name}.json")
        R.write_bytes(p, json.dumps(spec).encode())
        return p

    def build(self, recipe: str, out: str = "build/one") -> str:
        out = os.path.join(self.ws.root, out)
        B.main([recipe, "--out", out, "--fonts", self.ws.fonts, "--brief", self.brief, "--refs", *self.refs])
        return out

    def check(self, *builds: str, extra: tuple = ()) -> int:
        with self.assertRaises(SystemExit) as cm:
            C.main([*builds, "--refs", *self.refs, *extra])
        return cm.exception.code

    def check_refused(self, reason: str, *builds: str) -> None:
        with self.assertRaises(SystemExit) as cm:
            C.main([*builds, "--refs", *self.refs])
        self.assertIsInstance(cm.exception, R.Refused, f"check_logo.py exited {cm.exception.code} instead of refusing")
        self.assertEqual(cm.exception.reason, reason, str(cm.exception))

    def sheet(self, build: str, out: str = "package", *extra: str) -> str:
        return R.read_bytes(os.path.join(self.package(build, out, *extra), "trademark-search.md")).decode()

    def package(self, build: str, out: str = "package", *extra: str) -> str:
        out = os.path.join(self.ws.root, out)
        PK.main([build, "--out", out, "--refs", *self.refs, "--brief", self.brief, *extra])
        return out

    def book(self, *builds: str, extra: tuple = ()) -> str:
        out = os.path.join(self.ws.root, "book")
        LB.main([*builds, "--out", out, "--name", "Tessera", "--line", "Synthetic test product", "--refs", *self.refs,
                 "--brief", self.brief, "--fonts", self.ws.fonts, *extra])
        return out

    def refused(self, reason: str, fn, *args, **kw) -> None:
        with self.assertRaises(R.Refused) as cm:
            fn(*args, **kw)
        self.assertEqual(cm.exception.reason, reason, str(cm.exception))

    def pages(self, book: str) -> dict[str, str]:
        """Each page's HTML by its slug in pages.json."""
        order = R.read_json(os.path.join(book, "pages.json"))["pages"]
        doc = R.read_bytes(os.path.join(book, "index.html")).decode()
        return {slug: re.search(rf'<section class="page[^"]*" id="p{n:02d}".*?</section>', doc, re.S).group(0) for n, slug in order}


class Seal(Project):
    def test_a_check_with_no_reference_mark_says_not_checked(self):
        empty = os.path.join(self.ws.root, "refs", "empty")
        os.makedirs(empty)
        self.refs = [empty]
        b = self.build(self.recipe())
        cal = R.read_json(R.calibration_file(None))
        cal["fused"]["limit"] = 0.0
        zero = self.ws.path("calibration-zero.json")
        R.write_bytes(zero, json.dumps(cal).encode())
        for extra, ok in (((), True), (("--calibration", zero), False)):
            self.check(b, extra=extra)
            rows = {r["check"]: r for r in R.read_json(os.path.join(b, "check.json"))["checks"]}
            self.assertEqual(rows["nearest reference"]["value"], "not checked")
            self.assertEqual(rows["nearest reference"]["ok"], ok, extra)

    def test_package_and_book_refuse_a_build_that_was_never_checked(self):
        b = self.build(self.recipe())
        self.refused("not-checked", self.package, b)
        self.refused("not-checked", self.book, b)

    def test_rebuilding_without_the_wordmark_in_the_same_folder(self):
        b = self.build(self.recipe())
        self.assertEqual(self.check(b), 0)
        stale_lockup = LB.read_svg(R.read_bytes(os.path.join(b, "lockup.svg")).decode())[1]
        self.build(self.recipe(wordmark=False))
        self.assertTrue(os.path.exists(os.path.join(b, "lockup.svg")), "the fixture needs the old lockup left on disk")
        self.refused("stale-check", self.package, b)
        self.refused("stale-check", self.book, b)
        self.assertEqual(self.check(b), 0)
        pkg = self.package(b)
        self.assertEqual(sorted(os.listdir(os.path.join(pkg, "svg"))),
                         sorted(f"mark-{c}.svg" for c in ("ink", "reversed", "accent", "black")))
        self.assertNotIn("lockup-1600.png", os.listdir(os.path.join(pkg, "png")))
        self.assertEqual(os.listdir(os.path.join(pkg, "LICENSES")), [])
        book = self.book(b)
        doc = R.read_bytes(os.path.join(book, "index.html")).decode()
        self.assertNotIn(stale_lockup, doc)
        mark = LB.read_svg(R.read_bytes(os.path.join(b, "mark.svg")).decode())[1]
        self.assertIn(mark, self.pages(book)["d1-use"], "the in-use page draws the mark where the lockup would go")

    def test_refuses_once_a_reference_is_added_after_the_check(self):
        b = self.build(self.recipe())
        self.assertEqual(self.check(b), 0)
        self.ws.image("refs/mine/added-later.png", G.mark_image(G.own))
        self.refused("refs-changed", self.package, b)
        self.refused("refs-changed", self.book, b)

    def test_refuses_a_reference_that_is_not_there_by_name(self):
        b = self.build(self.recipe())
        self.assertEqual(self.check(b), 0)
        link = os.path.join(self.mine, "linked.png")
        os.symlink(self.ws.path("nowhere.png"), link)
        for step in (self.package, self.book):
            with self.assertRaises(R.Refused) as cm:
                step(b)
            self.assertEqual(cm.exception.reason, "refs-missing", str(cm.exception))
            self.assertIn(link, str(cm.exception))
        self.check_refused("refs-missing", b)
        self.assertFalse(os.path.exists(os.path.join(b, "check.json")), "a refused check left its old check.json")

    def test_refuses_a_reference_folder_it_cannot_list(self):
        if os.geteuid() == 0:
            self.skipTest("root lists any folder")
        b = self.build(self.recipe())
        named = os.path.dirname(self.ws.image("refs/named/hidden.png", G.mark_image(G.own)))
        inner = os.path.dirname(self.ws.image("refs/mine/inner/hidden.png", G.mark_image(G.own)))
        self.refs = [self.mine, named]
        for locked in (named, inner):
            os.chmod(locked, 0)
            self.addCleanup(os.chmod, locked, 0o755)
            # check_logo.py; package_logo.py and logo_book.py (rights.sealed); trace_ref.py
            for step in (lambda: C.main([b, "--refs", *self.refs]), lambda: R.refs_sha256(self.refs),
                         lambda: T.reference_set(self.refs)):
                with self.assertRaises(SystemExit) as cm:
                    step()
                self.assertIsInstance(cm.exception, R.Refused, f"exited {cm.exception.code} instead of refusing")
                self.assertEqual(cm.exception.reason, "refs-missing", str(cm.exception))
                self.assertIn(locked, str(cm.exception))
            os.chmod(locked, 0o755)
        self.assertEqual(self.check(b), 0)

    def test_refuses_a_linked_folder_inside_the_references(self):
        b = self.build(self.recipe())
        target = os.path.dirname(self.ws.image("elsewhere/kept/away.png", G.mark_image(G.own)))
        link = os.path.join(self.mine, "linked")
        os.symlink(target, link)
        for step in (lambda: C.main([b, "--refs", *self.refs]), lambda: R.refs_sha256(self.refs),
                     lambda: T.reference_set(self.refs)):
            with self.assertRaises(SystemExit) as cm:
                step()
            self.assertIsInstance(cm.exception, R.Refused, f"exited {cm.exception.code} instead of refusing")
            self.assertEqual(cm.exception.reason, "refs-missing", str(cm.exception))
            self.assertIn(link, str(cm.exception))
        os.remove(link)
        self.assertEqual(self.check(b), 0)

    def test_refuses_a_file_changed_after_the_check(self):
        b = self.build(self.recipe())
        self.assertEqual(self.check(b), 0)
        R.write_bytes(os.path.join(b, "mark.svg"), R.read_bytes(os.path.join(b, "mark.svg")) + "<!-- edited -->\n".encode())
        self.refused("build-changed", self.package, b)

    def test_refuses_another_calibration_than_the_check_used(self):
        b = self.build(self.recipe())
        self.assertEqual(self.check(b), 0)
        cal = R.read_json(R.calibration_file(None))
        cal["fused"]["limit"] = 0.5
        other = self.ws.path("calibration.json")
        R.write_bytes(other, json.dumps(cal).encode())
        self.refused("calibration-changed", self.package, b, "package", "--calibration", other)

    def test_package_refuses_a_failed_check(self):
        b = self.build(self.recipe(palette={**PALETTE, "ink": "#dddddd"}))
        self.assertEqual(self.check(b), 1)
        self.refused("check-failed", self.package, b)

    def test_package_writes_only_into_a_new_folder(self):
        b = self.build(self.recipe())
        self.assertEqual(self.check(b), 0)
        R.write_bytes(self.ws.path("package", "old.txt"), "left from before".encode())
        with self.assertRaises(SystemExit):
            self.package(b)

    def test_book_leaves_out_a_failed_direction_unless_asked(self):
        good = self.build(self.recipe("good"), "build/good")
        bad = self.build(self.recipe("bad", palette={**PALETTE, "ink": "#dddddd"}), "build/bad")
        self.assertEqual(self.check(good, bad), 1)
        pages = self.pages(self.book(good, bad))
        self.assertIn("Direction good", pages["directions-1"])
        self.assertNotIn("Direction bad", "".join(pages.values()))
        pages = self.pages(self.book(good, bad, extra=("--include-failed",)))
        self.assertIn("Direction bad", pages["directions-1"])
        self.assertIn(LB.TEXT["en"]["failed"], pages["directions-1"])

    def test_sheet_says_the_mark_was_drawn_when_nothing_was_traced(self):
        b = self.build(self.recipe())
        self.assertEqual(self.check(b), 0)
        sheet = R.read_bytes(os.path.join(self.package(b), "trademark-search.md")).decode()
        self.assertIn("check_logo.py compared the mark with", sheet)
        self.assertNotIn(PK.TRACED_NOTE["en"], sheet)
        self.assertNotIn("Where the mark came from", sheet)
        self.assertIn("kipris.or.kr", sheet)

    def test_korean_brief_gives_a_korean_book_and_sheet(self):
        self.brief = self.ws.brief([], name="테세라", what="동네 카페를 위한 장부 앱")
        b = self.build(self.recipe())
        self.assertEqual(self.check(b), 0)
        book = self.book(b)
        doc = R.read_bytes(os.path.join(book, "index.html")).decode()
        self.assertIn('<html lang="ko">', doc)
        self.assertIn(LB.TEXT["ko"]["logo_directions"], doc)
        self.assertEqual(R.sha256_file(os.path.join(book, "fonts", "book.ttf")),
                         R.sha256_file(os.path.join(self.ws.fonts, "notosanskr", "NotoSansKR-Regular.ttf")))
        sheet = R.read_bytes(os.path.join(self.package(b), "trademark-search.md")).decode()
        self.assertIn("check_logo.py는 이 마크를", sheet)
        self.assertNotIn(PK.TRACED_NOTE["ko"], sheet)
        self.assertIn("KIPRIS", sheet)
        self.assertIn("https://www.kipris.or.kr", sheet)

    def test_check_refuses_a_build_json_that_leaves_out_a_part_it_wrote(self):
        for rel in ("mark.svg", "mark-grid.svg", "lockup.svg"):
            with self.subTest(rel=rel):
                b = self.build(self.recipe(), f"build/{rel[:-4]}")
                bj = os.path.join(b, "build.json")
                info = R.read_json(bj)
                del info["files"][rel]
                R.write_bytes(bj, json.dumps(info, indent=1).encode())
                self.check_refused("build-changed", b)

    def test_book_and_package_read_only_the_bytes_they_verified(self):
        b = self.build(self.recipe())
        self.assertEqual(self.check(b), 0)
        parts = ("mark.svg", "mark-grid.svg", "wordmark.svg", "lockup.svg", "lockup-stacked.svg")
        kept = {rel: R.read_bytes(os.path.join(b, rel)) for rel in parts}
        fake = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 9" width="9" height="9"><path fill="#151515" d="{FAKE_PATH}"/></svg>\n'
        real = R.sealed

        def swapped_after_the_seal(*a, **kw):  # another program rewrites the parts once they have been verified
            r = real(*a, **kw)
            for rel in parts:
                R.write_bytes(os.path.join(b, rel), fake.encode())
            return r

        with mock.patch.object(R, "sealed", swapped_after_the_seal):
            doc = R.read_bytes(os.path.join(self.book(b), "index.html")).decode()
        for rel, data in kept.items():
            R.write_bytes(os.path.join(b, rel), data)
        self.assertNotIn(FAKE_PATH, doc)
        self.assertIn(re.search(r' d="([^"]+)"', kept["mark.svg"].decode()).group(1), doc)
        with mock.patch.object(R, "sealed", swapped_after_the_seal):
            pkg = self.package(b)
        for name in os.listdir(os.path.join(pkg, "svg")):
            self.assertNotIn(FAKE_PATH, R.read_bytes(os.path.join(pkg, "svg", name)).decode(), name)

    def test_book_prints_braces_in_the_person_s_words_as_written(self):
        b = self.build(self.recipe(idea="One {N} for every receipt."))
        self.assertEqual(self.check(b), 0)
        book = self.book(b, extra=("--line", "Counts {N} receipts", "--tagline", "{N} a day", "--note", "You have {N} new"))
        doc = R.read_bytes(os.path.join(book, "index.html")).decode()
        for words in ("One {N} for every receipt.", "Counts {N} receipts", "{N} a day", "You have {N} new"):
            self.assertIn(html.escape(words), doc)
        self.assertIn('<div class="num">02</div>', doc)

    def test_book_uses_only_the_photos_it_can_credit(self):
        d = self.ws.collection("photos", {"a.png": G.mark_image(G.own), "b.png": G.mark_image(G.tee)})
        man = R.read_json(os.path.join(d, "manifest.json"))
        man["items"][0].update(title="A field", creator="Synthetic Creator", license="CC0 1.0", source="https://example.org/a")
        R.write_bytes(os.path.join(d, "manifest.json"), json.dumps(man).encode())
        b = self.build(self.recipe())
        self.assertEqual(self.check(b), 0)
        book = self.book(b, extra=("--photos", d))
        self.assertEqual(os.listdir(os.path.join(book, "photos")), ["a.png"])
        self.assertIn("Synthetic Creator", self.pages(book)["credits"])
        self.assertNotIn("b.png", R.read_bytes(os.path.join(book, "index.html")).decode())

    def test_book_leaves_out_a_photo_changed_since_its_manifest_credited_it(self):
        d = self.ws.collection("photos", {"a.png": G.mark_image(G.own), "b.png": G.mark_image(G.tee)})
        man = R.read_json(os.path.join(d, "manifest.json"))
        for it in man["items"]:
            it.update(title="A field", creator="Synthetic Creator", license="CC0 1.0", source="https://example.org/" + it["file"])
        R.write_bytes(os.path.join(d, "manifest.json"), json.dumps(man).encode())
        G.mark_image(G.badge).save(os.path.join(d, "b.png"), "PNG")  # replaced by hand; its credits are for the old one
        b = self.build(self.recipe())
        self.assertEqual(self.check(b), 0)
        book = self.book(b, extra=("--photos", d))
        self.assertEqual(os.listdir(os.path.join(book, "photos")), ["a.png"])
        self.assertNotIn("b.png", R.read_bytes(os.path.join(book, "index.html")).decode())

    def test_sheet_counts_what_check_compared(self):
        self.ws.image("refs/mine/tee.png", G.mark_image(G.tee))
        b = self.build(self.recipe())
        self.assertEqual(self.check(b), 0)
        en, ko = self.sheet(b, "package-en", "--lang", "en"), self.sheet(b, "package-ko", "--lang", "ko")
        self.assertNotIn("every reference", en)
        self.assertIn("compared the mark with 2 reference images", en)
        self.assertNotIn("참고 로고 전부", ko)
        self.assertIn("참고 이미지 2개", ko)
        for sheet in (en, ko):
            self.assertIn(f"{LIMIT:.3f}", sheet)


class CheckReferences(Project):
    """check_logo.py compares every reference it can split into ink and ground, and names the ones it can't."""

    def test_check_compares_a_reference_whose_ink_fills_the_frame(self):
        b = self.build(self.recipe())
        self.assertEqual(self.check(b), 0)
        svg = R.read_bytes(os.path.join(b, "mark.svg")).decode()
        png = bytes(resvg_py.svg_to_bytes(svg_string=svg, width=400, background="#ffffff"))
        ref = self.ws.image("refs/mine/close-crop.png", Image.open(io.BytesIO(png)).convert("RGB"))
        self.assertFalse(L.usable(L.segment(L.load(ref)))[0], "the fixture must be a reference unfit for measuring")
        self.assertEqual(self.check(b), 1)
        chk = R.read_json(os.path.join(b, "check.json"))
        self.assertTrue(chk["nearest"][0]["ref"].endswith("close-crop.png"), chk["nearest"])

    def test_check_compares_an_svg_reference(self):
        b = self.build(self.recipe())
        self.assertEqual(self.check(b), 0)
        R.write_bytes(self.ws.path("refs", "mine", "close.svg"), R.read_bytes(os.path.join(b, "mark.svg")))
        self.assertEqual(self.check(b), 1)
        chk = R.read_json(os.path.join(b, "check.json"))
        self.assertTrue(chk["nearest"][0]["ref"].endswith("close.svg"), chk["nearest"])

    def test_check_compares_both_grounds_of_a_transparent_reference(self):
        b = self.build(self.recipe())
        self.assertEqual(self.check(b), 0)
        svg = R.read_bytes(os.path.join(b, "mark.svg")).decode()
        png = bytes(resvg_py.svg_to_bytes(svg_string=svg, width=400, background="#ffffff"))
        mark = G.padded(Image.open(io.BytesIO(png)).convert("RGB"))
        sheet = self.ws.image("refs/mine/sheet.png", G.dark_and_light_on_clear(G.mark_image(G.tee), mark))
        self.assertTrue(L.segment(L.load(sheet))["ok"], "the fixture must split on white, where only the dark mark shows")
        self.assertEqual(self.check(b), 1)
        chk = R.read_json(os.path.join(b, "check.json"))
        self.assertTrue(chk["nearest"][0]["ref"].endswith("sheet.png"), chk["nearest"])
        self.assertEqual(chk["refs_compared"], 2, "a sheet compared on both grounds is still one reference image")

    def test_check_refuses_while_a_reference_cannot_be_compared(self):
        b = self.build(self.recipe())
        self.assertEqual(self.check(b), 0)
        blank = self.ws.image("refs/mine/blank.png", Image.new("RGB", (300, 300), "white"))
        broken = self.ws.path("refs", "mine", "broken.png")
        R.write_bytes(broken, b"not an image")
        sheet = self.ws.image("refs/mine/sheet.png", G.dark_mark_and_small_light_mark())  # the split misses a mark
        with self.assertRaises(SystemExit) as cm:
            C.main([b, "--refs", *self.refs])
        e = cm.exception
        self.assertIsInstance(e, R.Refused, f"check_logo.py exited {e.code} instead of refusing")
        self.assertEqual(e.reason, "not-comparable", str(e))
        for f in (blank, broken, sheet):
            self.assertIn(f, str(e))
        self.assertFalse(os.path.exists(os.path.join(b, "check.json")), "a refused check left its old check.json")

    def test_check_records_the_hashes_of_what_it_judged_with(self):
        fresh = self.ws.image("refs/mine/fresh.png", G.mark_image(G.tee))
        cal = self.ws.path("calibration.json")
        R.write_bytes(cal, R.read_bytes(R.calibration_file(None)))
        refs_before, cal_before = R.refs_sha256(self.refs), R.sha256_file(cal)
        changed = R.read_json(cal)
        changed["fused"]["limit"] = 0.99
        b = self.build(self.recipe())
        fired, real = [], L.segment

        def change_while_judging(*a, **kw):  # the reference and the calibration change mid-run
            if not fired:
                fired.append(True)
                G.mark_image(G.own).save(fresh, "PNG")
                R.write_bytes(cal, json.dumps(changed).encode())
            return real(*a, **kw)

        # Start with no features cached by an earlier test, so every reference is read and judged now.
        with mock.patch.dict(T._PREPARED, clear=True), mock.patch.object(L, "segment", change_while_judging):
            self.assertEqual(self.check(b, extra=("--calibration", cal)), 0)
        self.assertTrue(fired, "no reference was read while the hook was in place")
        chk = R.read_json(os.path.join(b, "check.json"))
        self.assertEqual((chk["refs_sha256"], chk["calibration_sha256"]), (refs_before, cal_before))


@G.needs_potrace
class TracedDocuments(Project):
    """A traced direction: the book's overview and its own page, and the trademark sheet, show where it came from."""

    def setUp(self):
        super().setUp()
        self.sketch = self.ws.image("sketches/own.png", G.mark_image(G.own))
        self.entry = self.ws.entry(self.sketch)
        self.entry["answer"] = 'synthetic test approval: "yes, I drew it" <not a real person>'
        self.brief = self.ws.brief([self.entry])
        T.trace(self.sketch, brief=self.brief, refs=self.refs, out=self.ws.path("trace", "own.svg"))
        cwd = os.getcwd()
        os.chdir(self.ws.root)
        self.addCleanup(os.chdir, cwd)
        self.b = self.build(self.recipe(mark=[{"shape": "trace", "file": "trace/own.svg", "x": 2, "y": 2, "size": 44}]))
        self.assertEqual(self.check(self.b), 0)
        self.score = R.read_json(os.path.join(self.b, "check.json"))["source_scores"][0]["score"]

    def test_book_shows_source_rights_answer_and_score(self):
        pages = self.pages(self.book(self.b))
        for slug in ("directions-1", "d1-trace"):
            page = pages[slug]
            self.assertIn(html.escape(self.entry["file"]), page, slug)
            self.assertIn(html.escape(LB.TEXT["en"]["rights"]["own-drawing"]), page, slug)
            self.assertIn(html.escape(self.entry["answer"]), page, slug)
            self.assertIn(f"{self.score:.3f}", page, slug)
        self.assertIn(html.escape(self.entry["question"]), pages["d1-trace"])

    def test_sheet_claims_only_the_shapes_the_recipe_has(self):
        turned = self.build(self.recipe(mark=[{"shape": "trace", "file": "trace/own.svg", "x": 2, "y": 2, "size": 44,
                                               "rotate": 30}]), "build/turned")
        self.assertEqual(self.check(turned), 0)
        en, ko = self.sheet(turned, "package-en", "--lang", "en"), self.sheet(turned, "package-ko", "--lang", "ko")
        for claim in ("as potrace drew it", "then changed with grid shapes"):
            self.assertNotIn(claim, en)
        for claim in ("그린 그대로", "격자 도형으로 고친"):
            self.assertNotIn(claim, ko)
        self.assertIn("the recipe uses the trace's outline and no other shape", en)
        self.assertIn("레시피는 그 트레이스의 윤곽을 쓰며 다른 도형은 쓰지 않았습니다", ko)
        cut = self.build(self.recipe(mark=[{"shape": "trace", "file": "trace/own.svg", "x": 2, "y": 2, "size": 44},
                                           {"op": "cut", "shape": "rect", "x": 20, "y": 20, "w": 4, "h": 4}]), "build/cut")
        self.assertEqual(self.check(cut), 0)
        self.assertIn("`cut rect`", self.sheet(cut, "package-cut"))

    def test_package_and_book_refuse_once_the_collections_changed(self):
        chk = R.read_json(os.path.join(self.b, "check.json"))
        self.assertEqual(chk.get("collected_sha256"), R.collected_sha256())
        self.ws.collection("world", {"cafe/60000001.png": G.mark_image(G.tee)})  # outside --refs
        self.refused("collections-changed", self.package, self.b)
        self.refused("collections-changed", self.book, self.b)

    def test_package_and_book_refuse_once_a_collection_holds_the_source_or_a_copy(self):
        world = self.ws.collection("world", {"cafe/60000001.png": R.read_bytes(self.sketch)})  # outside --refs
        self.refused("collected", self.package, self.b)
        self.refused("collected", self.book, self.b)
        shutil.rmtree(world)
        buf = io.BytesIO()
        G.mark_image(G.own).resize((450, 450), Image.LANCZOS).save(buf, "JPEG", quality=80)
        self.ws.collection("world", {"cafe/60000002.jpg": buf.getvalue()})
        self.refused("collected-copy", self.package, self.b)
        self.refused("collected-copy", self.book, self.b)
        for wrote in ("package", "book"):
            self.assertFalse(os.path.exists(os.path.join(self.ws.root, wrote)), f"{wrote} wrote files before refusing")

    def test_package_and_book_refuse_a_pull_that_stopped_before_its_manifest(self):
        # The first pull of a collection wrote the source's bytes, then stopped before it wrote manifest.json: the
        # collections' digest is unchanged, and nothing lists the file.
        first = os.path.join(R.cache_root(), "world", "cafe", "60000001.png")
        os.makedirs(os.path.dirname(first))
        R.write_bytes(first, R.read_bytes(self.sketch))
        for step, wrote in ((self.package, "package"), (self.book, "book")):
            with self.assertRaises(R.Refused) as cm:
                step(self.b)
            self.assertEqual(cm.exception.reason, "collection-unlisted", str(cm.exception))
            self.assertIn("collection.mjs world", str(cm.exception))
            self.assertFalse(os.path.exists(os.path.join(self.ws.root, wrote)), f"{wrote} wrote files before refusing")

    def test_package_and_book_write_nothing_once_the_source_changed(self):
        G.mark_image(G.own).rotate(90).save(self.sketch, "PNG")
        self.refused("source-changed", self.package, self.b)
        self.assertFalse(os.path.exists(os.path.join(self.ws.root, "package")), "package wrote files before refusing")
        self.refused("source-changed", self.book, self.b)
        self.assertFalse(os.path.exists(os.path.join(self.ws.root, "book")), "the book wrote files before refusing")

    def test_sheet_shows_the_statement_and_says_it_was_traced(self):
        sheet = R.read_bytes(os.path.join(self.package(self.b), "trademark-search.md")).decode()
        self.assertIn(PK.TRACED_NOTE["en"], sheet)
        self.assertIn(self.entry["answer"], sheet)
        self.assertIn(self.entry["sha256"], sheet)
        self.assertIn(f"{self.score:.3f}", sheet)


@G.needs_potrace
class SamePictureAtEveryStep(Project):
    """trace, check, package and book judge one traced source alike: each compares it as a picture with every
    collected image, whatever the brief claims, and with no --refs image."""

    def setUp(self):
        super().setUp()
        mood = self.ws.image("refs/mine/mood.png", G.photo(2))  # the person's own photo, on the moodboard
        self.ws.image("refs/mine/found.png", G.photo(3))  # a photo they found
        world = self.ws.collection("world", {"mockups/90000001.png": G.photo(0)})
        # They claim the collected photo too: a collected image is compared all the same.
        self.claims = [self.ws.entry(mood), self.ws.entry(os.path.join(world, "mockups", "90000001.png"))]
        cwd = os.getcwd()
        os.chdir(self.ws.root)
        self.addCleanup(os.chdir, cwd)

    def verdicts(self, name: str, picture: Image.Image) -> dict[str, str | None]:
        """Each step's refusal of a JPEG copy of `picture` traced into a direction, or None. The direction is traced,
        built and checked as a version without the same-picture gate would, so each step has one to judge."""
        copy = self.ws.image(f"sketches/{name}.jpg", picture, "JPEG", quality=75)
        self.brief = self.ws.brief([*self.claims, self.ws.entry(copy)])
        with mock.patch.object(SP, "LIMIT", 2.0):
            T.trace(copy, brief=self.brief, refs=self.refs, out=self.ws.path("trace", f"{name}.svg"))
            b = self.build(self.recipe(name, mark=[{"shape": "trace", "file": f"trace/{name}.svg", "x": 2, "y": 2,
                                                    "size": 44}]), f"build/{name}")
            self.assertEqual(self.check(b), 0)

        def refusal(step) -> str | None:
            try:
                with redirect_stdout(io.StringIO()):
                    step()
            except R.Refused as e:
                return e.reason
            except SystemExit as e:  # check_logo.py's exit status
                self.assertEqual(e.code, 0)
            return None

        return {"trace": refusal(lambda: T.trace(copy, brief=self.brief, refs=self.refs,
                                                 out=self.ws.path("trace", f"{name}-again.svg"))),
                "package": refusal(lambda: self.package(b, f"package-{name}")),
                "book": refusal(lambda: LB.main([b, "--out", self.ws.path(f"book-{name}"), "--name", "Tessera",
                                                 "--line", "Synthetic test product", "--refs", *self.refs, "--brief",
                                                 self.brief, "--fonts", self.ws.fonts])),
                "check": refusal(lambda: C.main([b, "--refs", *self.refs]))}  # last: a refusal removes check.json

    def test_every_step_refuses_a_copy_of_a_collected_photo(self):
        self.assertEqual(self.verdicts("collected", G.photo(0)), dict.fromkeys(("trace", "package", "book", "check"),
                                                                                "collected-copy"))

    def test_every_step_passes_a_copy_of_a_refs_photo(self):
        for name, seed in (("mood", 2), ("found", 3)):  # in trace_sources, and not
            with self.subTest(name):
                self.assertEqual(self.verdicts(name, G.photo(seed)), dict.fromkeys(("trace", "package", "book", "check")))


if __name__ == "__main__":
    unittest.main()

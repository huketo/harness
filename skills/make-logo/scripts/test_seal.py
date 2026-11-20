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
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_logo as B  # noqa: E402
import check_logo as C  # noqa: E402
import gate_fixtures as G  # noqa: E402
import logo_book as LB  # noqa: E402
import package_logo as PK  # noqa: E402
import rights as R  # noqa: E402
import trace_ref as T  # noqa: E402

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

    def check(self, *builds: str) -> int:
        with self.assertRaises(SystemExit) as cm:
            C.main([*builds, "--refs", *self.refs])
        return cm.exception.code

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
    def test_package_and_book_refuse_a_build_that_was_never_checked(self):
        b = self.build(self.recipe())
        self.refused("not-checked", self.package, b)
        self.refused("not-checked", self.book, b)

    def test_rebuilding_without_the_wordmark_in_the_same_folder(self):
        b = self.build(self.recipe())
        self.assertEqual(self.check(b), 0)
        stale_lockup = LB.read_svg(os.path.join(b, "lockup.svg"))[1]
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
        mark = LB.read_svg(os.path.join(b, "mark.svg"))[1]
        self.assertIn(mark, self.pages(book)["d1-use"], "the in-use page draws the mark where the lockup would go")

    def test_refuses_once_a_reference_is_added_after_the_check(self):
        b = self.build(self.recipe())
        self.assertEqual(self.check(b), 0)
        self.ws.image("refs/mine/added-later.png", G.mark_image(G.own))
        self.refused("refs-changed", self.package, b)
        self.refused("refs-changed", self.book, b)

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
        self.assertIn(PK.CHECKED["en"]["drawn"], sheet)
        self.assertNotIn(PK.CHECKED["en"]["traced"], sheet)
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
        self.assertIn(PK.CHECKED["ko"]["drawn"], sheet)
        self.assertIn("KIPRIS", sheet)
        self.assertIn("https://www.kipris.or.kr", sheet)


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

    def test_sheet_shows_the_statement_and_says_it_was_traced(self):
        sheet = R.read_bytes(os.path.join(self.package(self.b), "trademark-search.md")).decode()
        self.assertIn(PK.CHECKED["en"]["traced"], sheet)
        self.assertNotIn(PK.CHECKED["en"]["drawn"], sheet)
        self.assertIn(self.entry["answer"], sheet)
        self.assertIn(self.entry["sha256"], sheet)
        self.assertIn(f"{self.score:.3f}", sheet)


if __name__ == "__main__":
    unittest.main()

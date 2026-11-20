# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "fonttools", "uharfbuzz"]
# ///
"""Reserved Font Names come only from the OFL's copyright lines (fonts.reserved_font_names): the five shared cases,
each line inside an otherwise unmodified OFL-1.1 text, whose own definition of the term yields nothing."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fonts as F  # noqa: E402
import gate_fixtures as G  # noqa: E402

CASES = [
    ("Copyright 2021 The Tessera Project Authors", []),
    ('Copyright 2021 The Tessera Project Authors, with Reserved Font Name "Tessera".', ["Tessera"]),
    ('Copyright (c) 2019 Lumen Type, with Reserved Font Names "Lumen" and "Lumen Ledger".', ["Lumen", "Lumen Ledger"]),
    ("Copyright 2017 Example Foundry, with Reserved Font Name Coda and Coda Mono.", ["Coda", "Coda Mono"]),
    ('Copyright 2022 Arbor Type, with Reserved Font Names "Arbor", "Arbor Text" and "Arbor Display".',
     ["Arbor", "Arbor Text", "Arbor Display"]),
]


class ReservedFontNames(unittest.TestCase):
    def test_the_five_shared_cases(self):
        for line, expected in CASES:
            with self.subTest(line=line):
                self.assertEqual(F.reserved_font_names(line + "\n" + G.OFL_BODY), expected)

    def test_fetch_reports_the_names_from_the_copyright_line(self):
        ws = G.Workspace()
        self.addCleanup(ws.close)
        G.install_font(ws.fonts, "Lumen Sans", CASES[2][0])
        self.assertEqual(F.fetch("Lumen Sans", ws.fonts)["reserved_names"], ["Lumen", "Lumen Ledger"])


if __name__ == "__main__":
    unittest.main()

# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools"]
# ///
"""Record the base the person approved, in base.json. Run it only after the person answered.

  uv run record_base.py --shortlist shortlist.json --family "Family" \\
      --question "the question you asked, verbatim" --answer "their answer, verbatim" --out base.json
  uv run record_base.py --font <base-vf.ttf> --licence <OFL.txt> --source google-fonts|manifest|local \\
      [--url URL] [--manifest-entry ID] --question "..." --answer "..." --out base.json

Only a person can decide that a font may be the base. This script cannot check that decision; it binds it to the
files: the font's sha256, the OFL text's sha256, name ID 13 exactly as the font carries it, the Reserved Font
Names from the OFL's copyright lines, where the font came from, and the question and answer word for word.

It refuses a base that this skill cannot build on: an OFL text that is not the SIL Open Font License 1.1 (an
Apache-2.0 font is not a base), a name ID 13 that does not carry the OFL notice, CFF outlines, or a static font.
base.json is written once. A second run with the same record leaves it as it is; any other content is refused.
fit_font.py, space_font.py, package.py and check_font.py all start from it.
"""
import argparse
import datetime
import json
import os
import sys

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontTools.ttLib import TTFont  # noqa: E402

import chain as C  # noqa: E402
import fontlib as L  # noqa: E402

SOURCES = ("google-fonts", "manifest", "local")


def check_font_file(path):
    """The base must be one TrueType-flavoured variable font."""
    try:
        f = TTFont(path)
    except Exception as e:  # a file fontTools cannot read is not a font
        raise C.Refused(f"{path} is not a font fontTools can read: {e}")
    if "CFF " in f or "CFF2" in f or "glyf" not in f:
        raise C.Refused(f"{path} has CFF outlines. The base must be a TrueType (glyf) variable font.")
    if "fvar" not in f or "gvar" not in f:
        raise C.Refused(f"{path} is a static font. The base must be a variable font (fvar and gvar).")
    return f


def from_shortlist(path, family):
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)["rows"]
    row = next((r for r in rows if r["family"].lower() == family.lower()), None)
    if row is None:
        raise C.Refused(f"{family!r} is not in {path}: {', '.join(r['family'] for r in rows)}")
    if not row.get("licence_path"):
        raise C.Refused(f"{family!r} in {path} has no OFL text beside it; pass --font and --licence")
    kind = "google-fonts" if str(row.get("origin", "")).startswith("google/fonts/") else "local"
    return row["file"], row["licence_path"], kind, row.get("url")


def build(a):
    font_path, lic_path, kind, url = a.font, a.licence, a.source, a.url
    if a.shortlist:
        if not a.family:
            raise C.Refused("--shortlist needs --family, the name of the row the person approved")
        font_path, lic_path, kind, url = from_shortlist(a.shortlist, a.family)
    if not font_path or not lic_path or not kind:
        raise C.Refused("give --shortlist with --family, or --font, --licence and --source")
    if kind not in SOURCES:
        raise C.Refused(f"--source is one of {', '.join(SOURCES)}")
    if kind == "google-fonts" and not url:
        raise C.Refused("--source google-fonts needs --url, the address the font was fetched from")
    if kind == "manifest" and not a.manifest_entry:
        raise C.Refused("--source manifest needs --manifest-entry, the pinned entry the font came from")
    if kind == "local" and (url or a.manifest_entry):
        raise C.Refused("--source local takes neither --url nor --manifest-entry")
    question, answer = a.question or "", a.answer or ""
    if not question.strip() or not answer.strip():
        raise C.Refused("--question and --answer are both required, verbatim: the approval is the person's, "
                        "and base.json keeps their words")
    f = check_font_file(font_path)
    with open(lic_path, "rb") as fh:
        lic_bytes = fh.read()
    lic_text = lic_bytes.decode("utf-8", errors="replace")
    if not L.is_ofl_11_text(lic_text):
        raise C.Refused(f"{lic_path} is not the SIL Open Font License 1.1 text. This skill builds only on OFL-1.1 "
                        "fonts; an Apache-2.0 or other licence is not a base.")
    n13 = L.english_names(f).get(13)
    if not L.names_ofl(n13):
        raise C.Refused(f"{font_path}: name ID 13 is {n13!r}, not the OFL-1.1 notice. The font itself must "
                        "declare the OFL-1.1.")
    return {
        "schema": C.SCHEMA,
        "font": {"file": os.path.abspath(font_path), "sha256": C.sha256_file(font_path)},
        "source": {"kind": kind, "url": url if kind != "local" else None,
                   "manifest_entry": a.manifest_entry if kind == "manifest" else None},
        "license": {"id": C.LICENCE_ID, "file": os.path.abspath(lic_path), "sha256": C.sha256_bytes(lic_bytes),
                    "name_id_13": n13, "reserved_font_names": L.reserved_font_names(lic_text)},
        "approval": {"question": question, "answer": answer,
                     "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shortlist", help="shortlist.json from find_foundation.py")
    ap.add_argument("--family", help="with --shortlist: the family the person approved")
    ap.add_argument("--font")
    ap.add_argument("--licence", help="the base's OFL.txt")
    ap.add_argument("--source", choices=SOURCES)
    ap.add_argument("--url")
    ap.add_argument("--manifest-entry")
    ap.add_argument("--question", help="the question shown to the person, verbatim")
    ap.add_argument("--answer", help="the person's answer, verbatim")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rec = build(a)
    _, wrote = C.write_base(a.out, rec)
    lic = rec["license"]
    print(f"{'wrote' if wrote else 'unchanged, already records this approval:'} {a.out}")
    print(f"  base    {os.path.basename(rec['font']['file'])} sha256 {rec['font']['sha256']}")
    print(f"  licence {lic['id']}, {os.path.basename(lic['file'])} sha256 {lic['sha256']}")
    print(f"  Reserved Font Names: {', '.join(lic['reserved_font_names']) or 'none'}")
    print(f"  answer  {rec['approval']['answer']!r}")


if __name__ == "__main__":
    main()

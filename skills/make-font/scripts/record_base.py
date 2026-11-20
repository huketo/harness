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
import chain as C  # noqa: E402

SOURCES = ("google-fonts", "manifest", "local")


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
    files = C.read_base(font_path, lic_path)
    return {
        "schema": C.SCHEMA,
        "font": {"file": os.path.abspath(font_path), "sha256": files["font_sha256"]},
        "source": {"kind": kind, "url": url if kind != "local" else None,
                   "manifest_entry": a.manifest_entry if kind == "manifest" else None},
        "license": {"id": C.LICENCE_ID, "file": os.path.abspath(lic_path), "sha256": files["license_sha256"],
                    "name_id_13": files["name_id_13"], "reserved_font_names": files["reserved_font_names"]},
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

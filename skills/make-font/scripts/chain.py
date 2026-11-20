# /// script
# requires-python = "==3.12.*"
# dependencies = ["fonttools"]
# ///
"""The provenance chain: base.json, the record of the base a person approved, and the chain object each step
writes into its log.

A person states that a font may be the base. Code cannot prove that statement; it binds it to the bytes of the
font and its licence. base.json holds the font's and the OFL text's sha256 and the person's words, verbatim.
Every step that writes a font checks base.json against the files before it does anything, accepts an input font
only if the previous step's log lists its sha256 as an output, and lists its own inputs and outputs in its log:

  "chain": {"base_json_sha256": "...", "inputs": [{"file", "sha256"}], "outputs": [{"file", "sha256"}],
            "targets": {"file", "sha256"}}

"targets" is the targets.json the step read; it is the only other file a building step opens.
"""
import hashlib
import io
import json
import os

from fontTools.ttLib import TTFont

import fontlib as L

SCHEMA = "make-font/base@1"
LICENCE_ID = "OFL-1.1"


class Refused(SystemExit):
    """A broken chain. The message goes to stderr and the exit status is 1."""

    def __init__(self, msg):
        super().__init__("refused: " + msg)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    with open(path, "rb") as fh:
        return sha256_bytes(fh.read())


def entry(path):
    return {"file": os.path.abspath(path), "sha256": sha256_file(path)}


# ------------------------------------------------------------------ the base's files
CONTAINERS = {b"wOFF": "a WOFF file", b"wOF2": "a WOFF2 file", b"ttcf": "a font collection",
              b"OTTO": "a font with CFF outlines"}
TRUETYPE = (b"\x00\x01\x00\x00", b"true")


def read_base(font_path, lic_path):
    """The one check of a base's files. record_base.py runs it before it asks and before it records, and every
    step that reads base.json runs it again. Each file is read once, so what is checked is what is hashed.
    Returns what base.json records about the files."""
    try:
        with open(font_path, "rb") as fh:
            data = fh.read()
        with open(lic_path, "rb") as fh:
            lic = fh.read()
    except OSError as e:
        raise Refused(f"cannot read the base's files: {e}")
    kind = CONTAINERS.get(data[:4])
    if kind:
        raise Refused(f"{font_path} is {kind}. The base must be one TrueType (glyf) variable font in a plain .ttf "
                      "file; WOFF, WOFF2, collections and CFF fonts are not bases.")
    if data[:4] not in TRUETYPE:
        raise Refused(f"{font_path} is not a TrueType font file")
    try:
        f = TTFont(io.BytesIO(data))
        has = set(f.keys())
    except Exception as e:  # a file fontTools cannot read is not a font
        raise Refused(f"{font_path} is not a font fontTools can read: {e}")
    if "glyf" not in has or "CFF " in has or "CFF2" in has:
        raise Refused(f"{font_path} has no TrueType (glyf) outlines. The base must be a glyf variable font.")
    if "fvar" not in has or "gvar" not in has:
        raise Refused(f"{font_path} is a static font. The base must be a variable font (fvar and gvar).")
    try:
        text = lic.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = ""
    if not L.is_ofl_11_text(text):
        raise Refused(f"{lic_path} is not the SIL Open Font License 1.1 text (copyright lines, then the licence "
                      f"word for word). This skill builds only on {LICENCE_ID} fonts; a licence title alone, an "
                      "edited licence, Apache-2.0 or any other licence is not a base.")
    n13 = L.english_names(f).get(13)
    if not L.is_ofl_11_notice(n13):
        raise Refused(f"{font_path}: name ID 13 is {n13!r}, not a notice of the {LICENCE_ID} alone. The font itself "
                      "must declare the SIL Open Font License, Version 1.1.")
    return {"font_sha256": sha256_bytes(data), "license_sha256": sha256_bytes(lic), "name_id_13": n13,
            "reserved_font_names": L.reserved_font_names(text)}


# ------------------------------------------------------------------ base.json
def _without_time(rec):
    rec = json.loads(json.dumps(rec))
    rec.get("approval", {}).pop("recorded_at", None)
    return rec


def write_base(path, rec):
    """Write base.json once. An existing file with the same record (recorded_at aside) is left as it is; one with
    any other content is refused, so an approval is never rewritten."""
    if os.path.exists(path):
        with open(path, "rb") as fh:
            raw = fh.read()
        try:
            old = json.loads(raw)
        except ValueError:
            old = None
        if old is not None and _without_time(old) == _without_time(rec):
            return raw, False
        raise Refused(f"{path} already exists with a different record. base.json is written once, by the "
                      "approval step, and never rewritten. Start a new build folder for another base or answer.")
    data = (json.dumps(rec, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    with open(path, "xb") as fh:
        fh.write(data)
    return data, True


def load_base(path):
    """Read base.json and check it against the files it names. Returns (record, sha256 of base.json's bytes)."""
    if not path:
        raise Refused("no --base-json. Every build step starts from base.json, the record of the base the person "
                      "approved (record_base.py writes it).")
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
        rec = json.loads(raw)
    except (OSError, ValueError) as e:
        raise Refused(f"cannot read {path}: {e}")
    if rec.get("schema") != SCHEMA:
        raise Refused(f"{path} is not a {SCHEMA} record")
    lic, font, appr = rec.get("license") or {}, rec.get("font") or {}, rec.get("approval") or {}
    if lic.get("id") != LICENCE_ID:
        raise Refused(f"{path} records the licence {lic.get('id')!r}. This skill builds only on {LICENCE_ID} fonts.")
    if not (appr.get("question") or "").strip() or not (appr.get("answer") or "").strip():
        raise Refused(f"{path} holds no approval: the question and the person's answer are both required")
    for what, rec_ in (("base font", font), ("licence text", lic)):
        f = rec_.get("file")
        if not f or not os.path.exists(f):
            raise Refused(f"the {what} {f!r} named in {path} does not exist")
        got = sha256_file(f)
        if got != rec_.get("sha256"):
            raise Refused(f"the {what} {f} has sha256 {got}, but {path} records {rec_.get('sha256')}. It changed "
                          "after the person approved it.")
    files = read_base(font["file"], lic["file"])
    if (files["font_sha256"], files["license_sha256"]) != (font["sha256"], lic["sha256"]):
        raise Refused(f"the base's files changed while {path} was being checked")
    if files["name_id_13"] != lic.get("name_id_13"):
        raise Refused(f"{path} records name ID 13 as {lic.get('name_id_13')!r}, but the base says "
                      f"{files['name_id_13']!r}. base.json was edited after the approval step wrote it.")
    if files["reserved_font_names"] != lic.get("reserved_font_names"):
        raise Refused(f"{path} records the Reserved Font Names {lic.get('reserved_font_names')!r}, but the licence "
                      f"declares {files['reserved_font_names']!r}. base.json was edited after the approval step "
                      "wrote it.")
    return rec, sha256_bytes(raw)


def require_base_font(path, rec, base_json):
    """The font a step was given must be the approved base, byte for byte."""
    got = sha256_file(path)
    if got != rec["font"]["sha256"]:
        raise Refused(f"{path} (sha256 {got}) is not the approved base in {base_json} "
                      f"({rec['font']['file']}, sha256 {rec['font']['sha256']}). fit_font.py builds only on that "
                      "file and makes its own subset of it; it takes no font made elsewhere, a subset included.")
    return got


# ------------------------------------------------------------------ step logs
def make_chain(base_sha, inputs, outputs, targets=None):
    out = {"base_json_sha256": base_sha, "inputs": [entry(p) for p in inputs], "outputs": [entry(p) for p in outputs]}
    if targets:
        out["targets"] = entry(targets)
    return out


def load_log(path, base_sha, flag, step):
    """Read one step's log and check that it was made from this base.json."""
    if not path:
        raise Refused(f"no {flag}. The input must come with the log {step} wrote, so its sha256 can be checked.")
    try:
        with open(path, encoding="utf-8") as fh:
            log = json.load(fh)
    except (OSError, ValueError) as e:
        raise Refused(f"cannot read {flag} {path}: {e}")
    chain = log.get("chain")
    if not isinstance(chain, dict) or not isinstance(chain.get("outputs"), list):
        raise Refused(f"{path} has no chain: it was not written by {step} from an approved base")
    if chain.get("base_json_sha256") != base_sha:
        raise Refused(f"{path} was made from another base.json (sha256 {chain.get('base_json_sha256')}, this one "
                      f"is {base_sha})")
    return log


def outputs(*logs):
    return {o["sha256"] for log in logs for o in log["chain"]["outputs"]}


def require_output(path, logs, flag, step):
    """An input font is accepted only when the previous step's log lists its sha256 as an output."""
    got = sha256_file(path)
    if got not in outputs(*logs):
        raise Refused(f"{path} (sha256 {got}) is not an output listed in the {flag} log(s) {step} wrote. Only "
                      "fonts that came through the chain from the approved base are accepted.")
    return got

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


def entry(path, name=None):
    """A file as a chain entry. `name` replaces the absolute path, for a log that ships with the package."""
    return {"file": name if name is not None else os.path.abspath(path), "sha256": sha256_file(path)}


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
    names = L.english_names(f)
    return {"font_sha256": sha256_bytes(data), "license_sha256": sha256_bytes(lic), "name_id_13": n13,
            "reserved_font_names": L.reserved_font_names(text), "family": names.get(16) or names.get(1)}


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
    require_approval(appr, font["sha256"], lic["sha256"], path)
    return rec, sha256_bytes(raw)


APPROVED = "approved"


def require_approval(appr, font_sha, licence_sha, where):
    """The approval binds the person's answer to these files: the question they saw named both sha256 values,
    their answer is kept verbatim, and the decision is the word "approved", never read out of the answer."""
    if not (appr.get("question") or "").strip() or not (appr.get("answer") or "").strip():
        raise Refused(f"{where}: no approval. The question and the person's answer are both required, verbatim.")
    missing = [what for what, h in (("font", font_sha), ("licence", licence_sha)) if h not in appr["question"]]
    if missing:
        raise Refused(f"{where}: the approval question does not name the {' and '.join(missing)} sha256. Ask the "
                      "question record_base.py --question-only prints, so the answer is about these exact files.")
    if appr.get("decision") != APPROVED:
        raise Refused(f"{where}: the approval decision is {appr.get('decision')!r}. Only --decision {APPROVED} "
                      "records a base, and only when the person approved it.")


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


# ------------------------------------------------------------------ the subset
def subset_args(unicodes):
    """The pyftsubset arguments fit_font.py subsets the base with, in order. fit-log.json records them."""
    return [f"--unicodes={unicodes}", "--layout-features=*", "--glyph-names", "--notdef-outline", "--name-IDs=*",
            "--name-languages=*", "--legacy-kern"]


def build_subset(base_path, args):
    """The subset of the base these arguments give, as the bytes of a plain TrueType file. The same base,
    arguments and fontTools version give the same bytes, which is what lets package.py and check_font.py make it
    again instead of trusting a file."""
    from fontTools import subset
    opts = subset.Options()
    rest = opts.parse_opts(list(args), ignore_unknown=["unicodes"])
    if not rest or any(not r.startswith("--unicodes=") for r in rest):
        raise ValueError(f"expected pyftsubset options and one --unicodes=, got {list(args)!r}")
    unicodes = [u for r in rest for u in subset.parse_unicodes(r.split("=", 1)[1])]
    f = TTFont(base_path, recalcTimestamp=False)
    s = subset.Subsetter(opts)
    s.populate(unicodes=unicodes)
    s.subset(f)
    f.flavor = None
    buf = io.BytesIO()
    f.save(buf)
    return buf.getvalue()


def rebuild_subset(rec, fit, fit_log):
    """Make the fit's subset again from the verified base with the arguments fit-log.json records, and refuse
    unless it has the sha256 the log records. The subset file itself is never read. Returns the subset."""
    import fontTools
    sub = fit.get("subset") or {}
    if sub.get("source_sha256") != rec["font"]["sha256"]:
        raise Refused(f"{fit_log}: its subset was not made from the approved base")
    try:
        data = build_subset(rec["font"]["file"], sub.get("args") or [])
    except Exception as e:  # arguments from a log are input: any failure to apply them is a broken link
        raise Refused(f"{fit_log}: the subset arguments it records cannot be applied to the approved base: {e}")
    got = sha256_bytes(data)
    if got != sub.get("sha256"):
        why = "the recorded subset was made from another font, or the log was edited"
        if sub.get("fonttools") and sub["fonttools"] != fontTools.version:
            why += f", or fontTools changed (the fit ran {sub['fonttools']}, this is {fontTools.version})"
        raise Refused(f"{fit_log}: the subset made again from the approved base with the recorded arguments has "
                      f"sha256 {got}, but the log records {sub.get('sha256')}: {why}. Run fit_font.py again.")
    return TTFont(io.BytesIO(data))


# ------------------------------------------------------------------ the whole chain
class Build:
    """What checking the chain up to the spaced fonts established, for package.py and check_font.py."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def verify_build(base_json, targets, fit_log, space_logs):
    """The chain from base.json to the spaced fonts, checked one way for package.py and check_font.py. base.json
    matches the base and its licence; the fit log was made from this base.json, read the base alone and this
    targets.json, and its subset is what the base gives with the recorded arguments, byte for byte; every space
    log was made from this base.json and this targets.json, from fonts the fit log wrote. Refuses at the first
    broken link."""
    rec, base_sha = load_base(base_json)
    rows = [("base.json matches the base and its OFL text",
             f"font sha256 {rec['font']['sha256']}, licence sha256 {rec['license']['sha256']}")]
    if not targets or not os.path.isfile(targets):
        raise Refused(f"no targets.json at {targets!r}")
    targets_sha = sha256_file(targets)
    fit = load_log(fit_log, base_sha, "--fit-log", "fit_font.py")
    if [e.get("sha256") for e in fit["chain"].get("inputs") or []] != [rec["font"]["sha256"]]:
        raise Refused(f"{fit_log}: fit_font.py's input is not exactly the approved base")
    if (fit["chain"].get("targets") or {}).get("sha256") != targets_sha:
        raise Refused(f"{fit_log}: fit_font.py read another targets.json than {targets} (sha256 {targets_sha}). "
                      "Fit again with this targets.json, or package with the one the fit read.")
    rows.append(("fit read only the approved base and targets.json", f"{len(fit['chain']['outputs'])} fonts written"))
    subset = rebuild_subset(rec, fit, fit_log)
    rows.append(("fit's subset made again from the approved base, byte for byte", f"sha256 {fit['subset']['sha256']}"))
    if not space_logs:
        raise Refused("no --space-log. The chain runs through the log space_font.py wrote for every style.")
    spaces = [load_log(p, base_sha, "--space-log", "space_font.py") for p in space_logs]
    fit_out = outputs(fit)
    for p, sp in zip(space_logs, spaces):
        ins = sp["chain"].get("inputs") or []
        if not ins or any(e.get("sha256") not in fit_out for e in ins):
            raise Refused(f"{p}: space_font.py's input is not a font the fit log {fit_log} lists as an output")
        if (sp["chain"].get("targets") or {}).get("sha256") != targets_sha:
            raise Refused(f"{p}: space_font.py read another targets.json than {targets}")
    rows.append(("space read only fitted fonts and targets.json", f"{len(spaces)} space logs"))
    return Build(rec=rec, base_sha=base_sha, targets_sha=targets_sha, fit=fit, spaces=spaces, subset=subset,
                 rows=rows, fit_log=fit_log, space_logs=list(space_logs))


def verify_package_log(b, package_log, fonts):
    """The links after the spaced fonts, for check_font.py: the package log was made from this base.json and this
    targets.json, from exactly these fit and space logs, took only spaced fonts, and lists every font checked as
    an output. Returns the rows it adds."""
    pkg = load_log(package_log, b.base_sha, "--package-log", "package.py")
    if (pkg["chain"].get("targets") or {}).get("sha256") != b.targets_sha:
        raise Refused(f"{package_log}: package.py read another targets.json")
    if (pkg.get("fit_log") or {}).get("sha256") != sha256_file(b.fit_log):
        raise Refused(f"{package_log}: package.py recorded another fit log than {b.fit_log}")
    if sorted(e.get("sha256") for e in pkg.get("space_logs") or []) != sorted(sha256_file(p) for p in b.space_logs):
        raise Refused(f"{package_log}: package.py recorded other space logs than {', '.join(b.space_logs)}")
    ins = pkg["chain"].get("inputs") or []
    if not ins or any(e.get("sha256") not in outputs(*b.spaces) for e in ins):
        raise Refused(f"{package_log}: package.py took a font that is not an output of the space logs")
    for p in fonts:
        require_output(p, [pkg], "--package-log", "package.py")
    return [("package read these logs and took only spaced fonts", f"{len(ins)} fonts"),
            ("every font checked is a package output", f"{len(fonts)} fonts")]

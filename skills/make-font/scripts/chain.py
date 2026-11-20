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

Every step reads each file once, through Files: the bytes it hashes are the bytes it parses, converts, checks and
copies, and the sha256 it logs is the sha256 of those bytes. Every step writes through Files too, which refuses an
output path that leads to a file the step read (by its name, a symbolic link or a hard link) and never writes
through a link.
"""
import hashlib
import io
import json
import os
import secrets

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


class Record:
    """What a check established, by name."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


# ------------------------------------------------------------------ reading and writing
class Blob:
    """One file as a step read it: its path, its bytes and their sha256."""

    def __init__(self, path, data):
        self.path, self.data, self.sha256 = path, data, sha256_bytes(data)

    def json(self, what="file"):
        try:
            return json.loads(self.data.decode("utf-8-sig"))
        except ValueError as e:
            raise Refused(f"the {what} {self.path} is not JSON: {e}")

    def font(self, **kw):
        return TTFont(io.BytesIO(self.data), **kw)

    def entry(self, name=None):
        """The file as a chain entry. `name` replaces the absolute path, for a log that ships with the package."""
        return {"file": name if name is not None else os.path.abspath(self.path), "sha256": self.sha256}


class Files:
    """The files one run of a step reads and writes.

    Each file is read once: asking for a path again, or for another path that resolves to the same file, gives
    the bytes first read, so nothing can change a file between the check of it and its use. An output is refused
    when its path leads to a file this run read, by name, through a symbolic link or as a hard link, and it is
    written beside its path and renamed onto it, so it never writes through a link."""

    def __init__(self):
        self._by_path, self._by_id, self._asked = {}, {}, []

    def read(self, path, what="file"):
        self._asked.append(path)
        key = os.path.realpath(path)
        if key not in self._by_path:
            try:
                with open(path, "rb") as fh:
                    st = os.fstat(fh.fileno())
                    data = fh.read()
            except OSError as e:
                raise Refused(f"cannot read the {what} {path}: {e}")
            blob = Blob(path, data)
            self._by_path[key] = self._by_id[(st.st_dev, st.st_ino)] = blob
        return self._by_path[key]

    def paths(self):
        """Every path this run was asked to read, as given, in order: a file read by two names has both."""
        return list(dict.fromkeys(self._asked))

    def check_output(self, path):
        hit = self._by_path.get(os.path.realpath(path))
        if hit is None:
            try:
                st = os.stat(path)
                hit = self._by_id.get((st.st_dev, st.st_ino))
            except OSError:
                pass
        if hit is not None:
            raise Refused(f"the output {path} leads to {hit.path}, an input of this step (by name or through a "
                          "link). Writing there would replace it. Pick an output path away from the inputs.")

    def write(self, path, data):
        """Write one output and return its chain entry, the sha256 of these bytes."""
        self.check_output(path)
        folder = os.path.dirname(os.path.abspath(path))
        os.makedirs(folder, exist_ok=True)
        part = os.path.join(folder, f".{os.path.basename(path)}.{secrets.token_hex(4)}.part")
        fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(part, path)
        except BaseException:
            if os.path.lexists(part):
                os.remove(part)
            raise
        return {"file": os.path.abspath(path), "sha256": sha256_bytes(data)}

    def write_json(self, path, obj):
        return self.write(path, json.dumps(obj, indent=1, ensure_ascii=False).encode("utf-8"))


def font_bytes(font, flavor=None):
    """A font serialized once: a plain TrueType file unless a flavor (woff2) is given."""
    font.flavor = flavor
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ the base's files
CONTAINERS = {b"wOFF": "a WOFF file", b"wOF2": "a WOFF2 file", b"ttcf": "a font collection",
              b"OTTO": "a font with CFF outlines"}
TRUETYPE = (b"\x00\x01\x00\x00", b"true")


def read_base(files, font_path, lic_path):
    """The one check of a base's files. record_base.py runs it before it asks and before it records, and every
    step that reads base.json runs it again, on the bytes the step uses. Returns what base.json records about the
    files, with the files themselves."""
    font_b, lic_b = files.read(font_path, "base font"), files.read(lic_path, "licence text")
    data = font_b.data
    kind = CONTAINERS.get(data[:4])
    if kind:
        raise Refused(f"{font_path} is {kind}. The base must be one TrueType (glyf) variable font in a plain .ttf "
                      "file; WOFF, WOFF2, collections and CFF fonts are not bases.")
    if data[:4] not in TRUETYPE:
        raise Refused(f"{font_path} is not a TrueType font file")
    try:
        f = font_b.font()
        has = set(f.keys())
    except Exception as e:  # a file fontTools cannot read is not a font
        raise Refused(f"{font_path} is not a font fontTools can read: {e}")
    if "glyf" not in has or "CFF " in has or "CFF2" in has:
        raise Refused(f"{font_path} has no TrueType (glyf) outlines. The base must be a glyf variable font.")
    if "fvar" not in has or "gvar" not in has:
        raise Refused(f"{font_path} is a static font. The base must be a variable font (fvar and gvar).")
    try:
        text = lic_b.data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = ""
    problem = L.ofl_11_text_problem(text)
    if problem:
        raise Refused(f"{lic_path} is not the SIL Open Font License 1.1 text: {problem}. This skill builds only on "
                      f"{LICENCE_ID} fonts, whose OFL.txt is copyright lines, then the licence word for word; a "
                      "licence title alone, an edited licence, Apache-2.0 or any other licence is not a base.")
    names = L.english_names(f)
    n13 = names.get(13)
    problem = L.ofl_11_notice_problem(n13)
    if problem:
        raise Refused(f"{font_path}: name ID 13 is {n13!r}, not a supported notice that grants the {LICENCE_ID} "
                      f"alone: {problem}. The supported form is {L.NOTICE_FORM}; any other clause, another version "
                      "or licence, a denial or an exception is refused.")
    return Record(font=font_b, licence=lic_b, name_id_13=n13, reserved_font_names=L.reserved_font_names(text),
                  family=names.get(16) or names.get(1))


SOURCES = ("google-fonts", "manifest", "local")
MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bases.json")  # the pinned bases for Hangul


def pinned_entry(files, source, font, licence):
    """The bases.json entry a manifest source names, when the font and licence, as read, are the files it pins: the
    font's sha256 is one of the entry's files', the licence's is the entry's licence's, and the source URL is that
    file's URL. Anything else is refused, so a base said to come from the pinned manifest is one, byte for byte,
    whatever a shortlist or a cache held. Returns the entry."""
    key = source.get("manifest_entry")
    families = (files.read(MANIFEST, "pinned manifest").json("pinned manifest") or {}).get("families") or {}
    entry = families.get(key)
    if entry is None:
        raise Refused(f"the pinned manifest {MANIFEST} has no entry {key!r} (it has {', '.join(families) or 'none'}). "
                      "A base from the manifest is a row of find_foundation.py's shortlist.")
    pinned = next((f for f in entry.get("files") or [] if f.get("sha256") == font.sha256), None)
    if pinned is None:
        raise Refused(f"the font {font.path} has sha256 {font.sha256}, and the pinned manifest entry {key} pins "
                      f"{', '.join(str(f.get('sha256')) for f in entry.get('files') or [])}. It is not the pinned "
                      "file: download it again with find_foundation.py, whose cache keeps only pinned files.")
    want = (entry.get("license") or {}).get("sha256")
    if licence.sha256 != want:
        raise Refused(f"the licence {licence.path} has sha256 {licence.sha256}, and the pinned manifest entry {key} "
                      f"pins {want} for its licence. It is not the pinned OFL text.")
    if source.get("url") != pinned.get("url"):
        raise Refused(f"the source URL {source.get('url')!r} is not the one the pinned manifest entry {key} pins for "
                      f"this file ({pinned.get('url')})")
    return entry


def needs_pinned_base(T):
    """Whether these targets take only a base from the pinned manifest: korean in their scripts, or Hangul targets."""
    return "korean" in (T.get("scripts") or []) or bool(T.get("hangul"))


def require_pinned_base(files, approved, T, targets_path):
    """A build with korean in its scripts builds only on a base of the pinned manifest: base.json records the source
    as a manifest entry, and the base's font and licence, as this step read them, are the files that entry pins
    (pinned_entry). Returns the entry's name, or None when the targets need no pinned base."""
    if not needs_pinned_base(T):
        return None
    src = approved.rec.get("source") or {}
    if src.get("kind") != "manifest":
        raise Refused(f"{targets_path} has korean in its scripts, and {approved.path} records a base from "
                      f"{src.get('kind')!r}. A Hangul build takes only a base from the pinned manifest (bases.json): "
                      "rank it with find_foundation.py and approve its shortlist row with record_base.py.")
    pinned_entry(files, src, approved.font, approved.licence)
    return src["manifest_entry"]


def approval_question(font_file, licence_file, source, base):
    """The approval question for these files from this source, with the sha256 of both, so the answer belongs to
    these exact bytes. record_base.py prints it, and the record step and every later step make it again and
    accept only the same words."""
    url = f" ({source['url']})" if source.get("url") else ""
    where = {"google-fonts": f"from Google Fonts{url}",
             "manifest": f"from the pinned manifest entry {source.get('manifest_entry')}{url}",
             "local": "a file you supplied"}[source["kind"]]
    rfn = base.reserved_font_names
    rfn = (f"Its Reserved Font Names, which the new name may not use: {', '.join(rfn)}." if rfn
           else "It declares no Reserved Font Name.")
    return (f"May I build the new font on {base.family}, {where}? The font file is {os.path.basename(font_file)}, "
            f"sha256 {base.font.sha256}. Its licence is the SIL Open Font License 1.1, "
            f"{os.path.basename(licence_file)}, sha256 {base.licence.sha256}. {rfn} The new font stays under the OFL "
            "1.1 with a new name. Only these exact files are approved; a changed file needs a new question.")


# ------------------------------------------------------------------ base.json
def _without_time(rec):
    rec = json.loads(json.dumps(rec))
    rec.get("approval", {}).pop("recorded_at", None)
    return rec


def write_base(files, path, rec):
    """Write base.json once. An existing file with the same record (recorded_at aside) is left as it is; one with
    any other content is refused, so an approval is never rewritten."""
    files.check_output(path)
    if os.path.lexists(path):
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


def load_base(files, path):
    """Read base.json and check it against the files it names, read once: the same check of the files the
    approval step ran, the notice and Reserved Font Names it recorded, and the approval made again from them.
    Returns the record, base.json's sha256, and the base font and licence as read."""
    if not path:
        raise Refused("no --base-json. Every build step starts from base.json, the record of the base the person "
                      "approved (record_base.py writes it).")
    blob = files.read(path, "base.json")
    rec = blob.json("base.json")
    if not isinstance(rec, dict) or rec.get("schema") != SCHEMA:
        raise Refused(f"{path} is not a {SCHEMA} record")
    lic, font, appr, src = (rec.get(k) or {} for k in ("license", "font", "approval", "source"))
    if lic.get("id") != LICENCE_ID:
        raise Refused(f"{path} records the licence {lic.get('id')!r}. This skill builds only on {LICENCE_ID} fonts.")
    for what, sec in (("base font", font), ("licence text", lic)):
        if not sec.get("file"):
            raise Refused(f"{path} names no {what}")
        got = files.read(sec["file"], what).sha256
        if got != sec.get("sha256"):
            raise Refused(f"the {what} {sec['file']} has sha256 {got}, but {path} records {sec.get('sha256')}. It "
                          "changed after the person approved it.")
    base = read_base(files, font["file"], lic["file"])
    if base.name_id_13 != lic.get("name_id_13"):
        raise Refused(f"{path} records name ID 13 as {lic.get('name_id_13')!r}, but the base says "
                      f"{base.name_id_13!r}. base.json was edited after the approval step wrote it.")
    if base.reserved_font_names != lic.get("reserved_font_names"):
        raise Refused(f"{path} records the Reserved Font Names {lic.get('reserved_font_names')!r}, but the licence "
                      f"declares {base.reserved_font_names!r}. base.json was edited after the approval step wrote it.")
    if src.get("kind") not in SOURCES:
        raise Refused(f"{path} records the source {src.get('kind')!r}, not one of {', '.join(SOURCES)}")
    require_approval(appr, approval_question(font["file"], lic["file"], src, base), path)
    return Record(rec=rec, sha=blob.sha256, font=base.font, licence=base.licence, path=path)


APPROVED = "approved"


def require_approval(appr, question, where):
    """The approval binds the person's answer to these files: the question they saw is, word for word, the one
    these files and this source give (it names both sha256 values and where the font came from), their answer is
    kept verbatim, and the decision is the word "approved", never read out of the answer."""
    if not (appr.get("question") or "").strip() or not (appr.get("answer") or "").strip():
        raise Refused(f"{where}: no approval. The question and the person's answer are both required, verbatim.")
    if appr["question"] != question:
        raise Refused(f"{where}: the approval question is not, word for word, the one record_base.py --question-only "
                      "prints for these files and this source. The answer belongs to the question the person saw; "
                      "if a file or the source changed, ask again.")
    if appr.get("decision") != APPROVED:
        raise Refused(f"{where}: the approval decision is {appr.get('decision')!r}. Only --decision {APPROVED} "
                      "records a base, and only when the person approved it.")


def require_base_font(files, path, approved, base_json):
    """The font a step was given must be the approved base, byte for byte. Returns it as read."""
    got = files.read(path, "base font")
    if got.sha256 != approved.font.sha256:
        raise Refused(f"{path} (sha256 {got.sha256}) is not the approved base in {base_json} "
                      f"({approved.font.path}, sha256 {approved.font.sha256}). fit_font.py builds only on that "
                      "file and makes its own subset of it; it takes no font made elsewhere, a subset included.")
    return got


# ------------------------------------------------------------------ step logs
def make_chain(base_sha, inputs, outputs, targets=None):
    """A log's chain object, from entries: Blob.entry() for what the step read, Files.write's result for what it
    wrote."""
    out = {"base_json_sha256": base_sha, "inputs": list(inputs), "outputs": list(outputs)}
    if targets:
        out["targets"] = targets
    return out


class Log(dict):
    """A step's log as parsed, with the Blob it was parsed from."""

    def __init__(self, blob, data):
        super().__init__(data)
        self.blob = blob


def load_log(files, path, base_sha, flag, step):
    """Read one step's log and check that it was made from this base.json."""
    if not path:
        raise Refused(f"no {flag}. The input must come with the log {step} wrote, so its sha256 can be checked.")
    blob = files.read(path, flag)
    log = blob.json(flag)
    chain = log.get("chain") if isinstance(log, dict) else None
    if not isinstance(chain, dict) or not isinstance(chain.get("outputs"), list):
        raise Refused(f"{path} has no chain: it was not written by {step} from an approved base")
    if chain.get("base_json_sha256") != base_sha:
        raise Refused(f"{path} was made from another base.json (sha256 {chain.get('base_json_sha256')}, this one "
                      f"is {base_sha})")
    return Log(blob, log)


def outputs(*logs):
    return {o["sha256"] for log in logs for o in log["chain"]["outputs"]}


def require_output(files, path, logs, flag, step):
    """An input font is accepted only when the previous step's log lists its sha256 as an output. Returns it as
    read."""
    got = files.read(path, "font")
    if got.sha256 not in outputs(*logs):
        raise Refused(f"{path} (sha256 {got.sha256}) is not an output listed in the {flag} log(s) {step} wrote. "
                      "Only fonts that came through the chain from the approved base are accepted.")
    return got


# ------------------------------------------------------------------ the subset
def subset_args(unicodes):
    """The pyftsubset arguments fit_font.py subsets the base with, in order. fit-log.json records them."""
    return [f"--unicodes={unicodes}", "--layout-features=*", "--glyph-names", "--notdef-outline", "--name-IDs=*",
            "--name-languages=*", "--legacy-kern"]


# fontTools serializes GSUB and GPOS with HarfBuzz's repacker whenever it can import uharfbuzz, and with its own
# serializer otherwise; the two give different bytes. Each script runs in its own uv environment, and not all of
# them install uharfbuzz, so the subset is always written with fontTools' own serializer.
PURE_SERIALIZER = {"fontTools.ttLib.tables.otBase:USE_HARFBUZZ_REPACKER": False}


def build_subset(base_data, args):
    """The subset of the base (its bytes) these arguments give, as the bytes of a plain TrueType file. The same
    base, arguments and fontTools version give the same bytes, whatever optional packages are installed, which is
    what lets package.py and check_font.py make it again instead of trusting a file."""
    from fontTools import subset
    opts = subset.Options()
    rest = opts.parse_opts(list(args), ignore_unknown=["unicodes"])
    if not rest or any(not r.startswith("--unicodes=") for r in rest):
        raise ValueError(f"expected pyftsubset options and one --unicodes=, got {list(args)!r}")
    unicodes = [u for r in rest for u in subset.parse_unicodes(r.split("=", 1)[1])]
    f = TTFont(io.BytesIO(base_data), recalcTimestamp=False, cfg=PURE_SERIALIZER)
    s = subset.Subsetter(opts)
    s.populate(unicodes=unicodes)
    s.subset(f)
    f.flavor = None
    buf = io.BytesIO()
    f.save(buf)
    return buf.getvalue()


def rebuild_subset(approved, fit, fit_log):
    """Make the fit's subset again from the verified base with the arguments fit-log.json records, and refuse
    unless it has the sha256 the log records. The subset file itself is never read. Returns the subset."""
    import fontTools
    sub = fit.get("subset") or {}
    if sub.get("source_sha256") != approved.font.sha256:
        raise Refused(f"{fit_log}: its subset was not made from the approved base")
    try:
        data = build_subset(approved.font.data, sub.get("args") or [])
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
def verify_build(files, base_json, targets, fit_log, space_logs):
    """The chain from base.json to the spaced fonts, checked one way for package.py and check_font.py. base.json
    matches the base and its licence, and with korean in the targets' scripts the base is a pinned manifest entry's
    files (require_pinned_base); the fit log was made from this base.json, read the base alone and this
    targets.json, and its subset is what the base gives with the recorded arguments, byte for byte; every space
    log was made from this base.json and this targets.json, from fonts the fit log wrote. Refuses at the first
    broken link."""
    ap = load_base(files, base_json)
    rows = [("base.json matches the base and its OFL text",
             f"font sha256 {ap.font.sha256}, licence sha256 {ap.licence.sha256}")]
    if not targets:
        raise Refused("no --targets")
    tb = files.read(targets, "targets.json")
    T = tb.json("targets.json")
    pinned = require_pinned_base(files, ap, T, targets)
    if pinned:
        rows.append(("the base is the pinned manifest entry the targets' korean needs", pinned))
    fit = load_log(files, fit_log, ap.sha, "--fit-log", "fit_font.py")
    if [e.get("sha256") for e in fit["chain"].get("inputs") or []] != [ap.font.sha256]:
        raise Refused(f"{fit_log}: fit_font.py's input is not exactly the approved base")
    if (fit["chain"].get("targets") or {}).get("sha256") != tb.sha256:
        raise Refused(f"{fit_log}: fit_font.py read another targets.json than {targets} (sha256 {tb.sha256}). "
                      "Fit again with this targets.json, or package with the one the fit read.")
    rows.append(("fit read only the approved base and targets.json", f"{len(fit['chain']['outputs'])} fonts written"))
    subset = rebuild_subset(ap, fit, fit_log)
    rows.append(("fit's subset made again from the approved base, byte for byte", f"sha256 {fit['subset']['sha256']}"))
    if not space_logs:
        raise Refused("no --space-log. The chain runs through the log space_font.py wrote for every style.")
    spaces = [load_log(files, p, ap.sha, "--space-log", "space_font.py") for p in space_logs]
    fit_out = outputs(fit)
    for p, sp in zip(space_logs, spaces):
        ins = sp["chain"].get("inputs") or []
        if not ins or any(e.get("sha256") not in fit_out for e in ins):
            raise Refused(f"{p}: space_font.py's input is not a font the fit log {fit_log} lists as an output")
        if (sp["chain"].get("targets") or {}).get("sha256") != tb.sha256:
            raise Refused(f"{p}: space_font.py read another targets.json than {targets}")
    rows.append(("space read only fitted fonts and targets.json", f"{len(spaces)} space logs"))
    return Record(approved=ap, rec=ap.rec, base_sha=ap.sha, targets=tb, T=T, fit=fit, spaces=spaces, subset=subset,
                  rows=rows)


def verify_package_log(files, b, package_log, fonts):
    """The links after the spaced fonts, for check_font.py: the package log was made from this base.json and this
    targets.json, from exactly these fit and space logs, took only spaced fonts, and lists every font checked as
    an output; and every output it lists is in its folder with the sha256 it records. Returns the rows it adds,
    the fonts as read, and the outputs it verified."""
    pkg = load_log(files, package_log, b.base_sha, "--package-log", "package.py")
    if (pkg["chain"].get("targets") or {}).get("sha256") != b.targets.sha256:
        raise Refused(f"{package_log}: package.py read another targets.json")
    if (pkg.get("fit_log") or {}).get("sha256") != b.fit.blob.sha256:
        raise Refused(f"{package_log}: package.py recorded another fit log than {b.fit.blob.path}")
    if sorted(e.get("sha256") for e in pkg.get("space_logs") or []) != sorted(s.blob.sha256 for s in b.spaces):
        raise Refused(f"{package_log}: package.py recorded other space logs than "
                      f"{', '.join(s.blob.path for s in b.spaces)}")
    ins = pkg["chain"].get("inputs") or []
    if not ins or any(e.get("sha256") not in outputs(*b.spaces) for e in ins):
        raise Refused(f"{package_log}: package.py took a font that is not an output of the space logs")
    # "from" names the spaced font an output came from. Packages made before it was recorded have none; the Hangul
    # outline check, which needs it, fails without it (check_font.space_track).
    if any("from" in e and e["from"] not in {i.get("sha256") for i in ins} for e in pkg["chain"]["outputs"]):
        raise Refused(f"{package_log}: an output names a spaced font it came from that is not among the inputs")
    checked = [require_output(files, p, [pkg], "--package-log", "package.py") for p in fonts]
    folder = os.path.dirname(os.path.abspath(package_log))
    verified = []
    for e in pkg["chain"]["outputs"]:
        name = str(e.get("file") or "")
        if not name or os.path.isabs(name) or os.path.normpath(name).split(os.sep)[0] == "..":
            raise Refused(f"{package_log}: the output {name!r} is not a file inside the package")
        got = files.read(os.path.join(folder, name), "package output")
        if got.sha256 != e.get("sha256"):
            raise Refused(f"{package_log}: the package output {name} has sha256 {got.sha256}, but the log records "
                          f"{e.get('sha256')}. The package changed after package.py wrote it.")
        verified.append({"file": name, "sha256": got.sha256})
    rows = [("package read these logs and took only spaced fonts", f"{len(ins)} fonts"),
            ("every font checked is a package output", f"{len(fonts)} fonts"),
            ("every package output is in the package with its logged sha256", f"{len(verified)} files")]
    return Record(rows=rows, fonts=checked, outputs=verified,
                  made_from={e["sha256"]: e["from"] for e in pkg["chain"]["outputs"] if "from" in e})

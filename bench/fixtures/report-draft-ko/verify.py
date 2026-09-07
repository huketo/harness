"""Machine layer for the daily-report draft task.

Checks structure only: both deliverables exist, the Markdown draft carries the
three required sections in order with at least one item each, and the HTML
fragment is exactly the two nested `<ul>` lists the template asks for. Writing
quality is graded by the rubric judge, not here.

The HTML is parsed with `html.parser`, not matched with regexes, so open and
close tags have to correspond, text has to sit directly inside an `<li>`, every
item has to carry text, and neither the characters the template says to escape
nor an unknown character reference can slip through.
"""

from __future__ import annotations

import re
import sys
from html.entities import name2codepoint
from html.parser import HTMLParser
from pathlib import Path

MARKDOWN = Path("answers/report.md")
HTML = Path("answers/report.html")

SECTIONS = ("오늘 한 일", "다음 계획", "비고")
HTML_SECTIONS = ("오늘 한 일", "다음 계획")
ALLOWED_TAGS = ("ul", "li")
ESCAPE_REQUIRED = "&<>·×"
ITEM = re.compile(r"^[ \t]*-[ \t]+\S")

failures: list[str] = []


class Fragment(HTMLParser):
    """`<ul>`/`<li>` fragment validator with an explicit element stack."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.stack: list[str] = []
        self.item_text: list[str] = []
        self.top_level_lists = 0
        self.items = 0
        self.errors: list[str] = []

    def fail(self, message: str) -> None:
        if message not in self.errors:
            self.errors.append(message)

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag not in ALLOWED_TAGS:
            self.fail(f"uses <{tag}>; only <ul> and <li> are allowed")
            return
        if tag == "ul":
            if not self.stack:
                self.top_level_lists += 1
            elif self.stack[-1] != "li":
                self.fail("a nested <ul> must sit directly inside an <li>")
        else:
            self.items += 1
            if not self.stack or self.stack[-1] != "ul":
                self.fail("an <li> must sit directly inside a <ul>")
            self.item_text.append("")
        self.stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: object) -> None:
        self.fail(f"uses the self-closing tag <{tag}/>; only paired <ul> and <li> are allowed")

    def handle_endtag(self, tag: str) -> None:
        if tag not in ALLOWED_TAGS:
            self.fail(f"uses </{tag}>; only <ul> and <li> are allowed")
            return
        if not self.stack or self.stack[-1] != tag:
            open_tag = f"<{self.stack[-1]}>" if self.stack else "nothing"
            self.fail(f"closes </{tag}> while {open_tag} is open")
            return
        self.stack.pop()
        if tag == "li" and not self.item_text.pop().strip():
            self.fail("has an <li> with no text of its own")

    def handle_data(self, data: str) -> None:
        raw = sorted({character for character in ESCAPE_REQUIRED if character in data})
        if raw:
            self.fail(f"leaves raw {' '.join(raw)} in text; use the named entities the template lists")
        self.add_text(data)

    def add_text(self, text: str) -> None:
        """Text is only allowed where its direct parent is an `<li>`."""
        if self.stack and self.stack[-1] == "li":
            self.item_text[-1] += text
        elif text.strip():
            self.fail(f"puts text where only <ul> and <li> tags may sit: {text.strip()[:40]!r}")

    def handle_entityref(self, name: str) -> None:
        if name not in name2codepoint:
            self.fail(f"uses the unknown character reference &{name};")
            return
        self.add_text(chr(name2codepoint[name]))

    def handle_charref(self, name: str) -> None:
        hexadecimal = name[:1].lower() == "x"
        try:
            code = int(name[1:] if hexadecimal else name, 16 if hexadecimal else 10)
        except ValueError:
            code = -1
        if not 0 < code <= 0x10FFFF or 0xD800 <= code <= 0xDFFF:
            self.fail(f"uses the invalid numeric character reference &#{name};")
            return
        self.add_text(chr(code))

    def finish(self) -> None:
        self.close()
        if self.stack:
            self.fail(f"leaves {', '.join(f'<{tag}>' for tag in reversed(self.stack))} unclosed")
        if self.top_level_lists != len(HTML_SECTIONS):
            self.fail(
                f"has {self.top_level_lists} top-level <ul> list(s); the template asks for "
                f"exactly {len(HTML_SECTIONS)}, one per section ({', '.join(HTML_SECTIONS)})"
            )


missing = [str(path) for path in (MARKDOWN, HTML) if not path.is_file()]
if missing:
    print(f"missing deliverable(s): {', '.join(missing)}", file=sys.stderr)
    raise SystemExit(1)

draft = MARKDOWN.read_text(encoding="utf-8")
offsets: dict[str, int] = {}
for section in SECTIONS:
    found = re.search(rf"^##[ \t]+{re.escape(section)}[ \t]*$", draft, flags=re.MULTILINE)
    if found is None:
        failures.append(f"{MARKDOWN} has no '## {section}' heading")
    else:
        offsets[section] = found.start()

if len(offsets) == len(SECTIONS):
    ordered = sorted(SECTIONS, key=lambda section: offsets[section])
    if tuple(ordered) != SECTIONS:
        failures.append(f"{MARKDOWN} orders the sections as {' / '.join(ordered)}; required: {' / '.join(SECTIONS)}")
    bounds = sorted(offsets.values()) + [len(draft)]
    for index, section in enumerate(ordered):
        body = draft[bounds[index] : bounds[index + 1]].splitlines()[1:]
        if not any(ITEM.match(line) for line in body):
            failures.append(f"section '{section}' in {MARKDOWN} has no '- ' item")

fragment = Fragment()
fragment.feed(HTML.read_text(encoding="utf-8"))
fragment.finish()
if fragment.items == 0:
    fragment.fail("contains no <li> item")
failures.extend(f"{HTML} {error}" for error in fragment.errors)

if failures:
    for failure in failures:
        print(failure, file=sys.stderr)
    raise SystemExit(1)

print(f"{MARKDOWN}: {len(SECTIONS)} sections present; {HTML}: {fragment.items} items in {fragment.top_level_lists} lists")

# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""The skill runs its Python through uv: every script declares PEP 723 metadata, and every documented command
uses `uv run`."""
import glob
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


BLOCK = re.compile(r"\A# /// script\n((?:#.*\n)*?)# ///\n")


class Pep723(unittest.TestCase):
    def test_every_python_file_opens_with_a_script_block(self):
        files = sorted(glob.glob(os.path.join(HERE, "*.py")))
        self.assertTrue(files)
        for path in files:
            with self.subTest(file=os.path.basename(path)):
                m = BLOCK.match(read(path))
                self.assertIsNotNone(m, "no PEP 723 block at the top")
                self.assertIn("requires-python", m.group(1))
                self.assertIn("dependencies", m.group(1))


class Commands(unittest.TestCase):
    def test_documented_python_commands_use_uv_run(self):
        docs = [os.path.join(SKILL, "SKILL.md")] + sorted(glob.glob(os.path.join(SKILL, "references", "*.md")))
        for path in docs:
            text = read(path)
            with self.subTest(doc=os.path.relpath(path, SKILL)):
                direct = re.search(r".{0,40}python3? -I.{0,40}", text)
                self.assertIsNone(direct, f"runs python directly: {direct and direct.group(0)!r}")
                for m in re.finditer(r"`([^`]*\b\w+\.py\b[^`]*)`", text):
                    cmd = m.group(1)
                    if " " in cmd.strip():  # a command, not a bare file name
                        self.assertTrue(cmd.startswith("uv run "), cmd)


if __name__ == "__main__":
    unittest.main()

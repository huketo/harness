import importlib.util
from pathlib import Path
import sys
import unittest


spec = importlib.util.spec_from_file_location(
    "img_gen_catalog", Path(__file__).parents[1] / "scripts" / "build_catalog.py"
)
catalog = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = catalog
spec.loader.exec_module(catalog)


class ReadmeAssociationTests(unittest.TestCase):
    def test_multiple_prompts_do_not_assign_first_prompt_to_every_image(self):
        readme = (
            '<h2>Examples</h2>\n<img src="docs/a.png"><img src="docs/b.png">\n'
            '#### A\n```text\nPrompt A\n```\n'
            '#### B\n```text\nPrompt B\n```\n'
        )
        prompt, _, _, _ = catalog.infer_readme_details(
            readme, {"offset": readme.index('<img src="docs/b.png">'), "line": 2}
        )
        self.assertEqual(prompt, "")

    def test_single_original_prompt_keeps_unicode_and_line_breaks(self):
        original = '정확히 "작은 휴식"\n구도와 질감을 보존한다.'
        readme = '<img src="docs/a.png">\n```text\n' + original + '\n```'
        prompt, metadata, _, _ = catalog.infer_readme_details(
            readme, {"offset": 0, "line": 1}
        )
        self.assertEqual(prompt, original)
        self.assertEqual(metadata, "")


if __name__ == "__main__":
    unittest.main()

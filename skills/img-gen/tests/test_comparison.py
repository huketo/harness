import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "img_gen_comparison", Path(__file__).parents[1] / "scripts" / "build_comparison.py"
)
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class OutputSafetyTests(unittest.TestCase):
    def test_output_cannot_replace_input_directory_even_without_references(self):
        for source_name in ("catalog", "results"):
            with self.subTest(source=source_name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                catalog_dir = root / "catalog"
                results_dir = root / "results"
                catalog_dir.mkdir()
                results_dir.mkdir()
                catalog_path = catalog_dir / "catalog.json"
                results_path = results_dir / "results.json"
                catalog_path.write_text(json.dumps({"schema_version": 1, "entries": []}))
                results_path.write_text(json.dumps({
                    "schema_version": 1, "title": "Empty comparison",
                    "description": "No references", "cases": [],
                }))
                output = root / source_name
                (output / "assets").mkdir()
                original = output / "assets" / "original.png"
                original.write_bytes(b"preserve original bytes")
                index = output / "index.html"
                index.write_text("existing input page")
                with self.assertRaises(ValueError):
                    comparison.build(catalog_path, results_path, output)
                self.assertEqual(original.read_bytes(), b"preserve original bytes")
                self.assertEqual(index.read_text(), "existing input page")


if __name__ == "__main__":
    unittest.main()

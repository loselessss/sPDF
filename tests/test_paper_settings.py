import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paperorganizer import settings as paper_settings


class PaperSettingsTests(unittest.TestCase):
    def test_folders_and_model_are_stored_separately(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "paper-settings.json"
            with mock.patch.object(paper_settings, "PATH", str(config)):
                paper_settings.set_paper_settings(
                    str(Path(temp) / "input"),
                    str(Path(temp) / "organized"), "qwen3:8b", True)
                self.assertTrue(paper_settings.paper_auto_enabled())
                self.assertEqual(paper_settings.paper_model(), "qwen3:8b")
                self.assertNotEqual(paper_settings.paper_input_dir(),
                                    paper_settings.paper_organized_dir())
                data = json.loads(config.read_text(encoding="utf-8"))
                self.assertEqual(set(data), {
                    "input_dir", "organized_dir", "model", "auto_enabled"})


if __name__ == "__main__":
    unittest.main()

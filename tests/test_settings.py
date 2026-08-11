import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pdfeditor import settings


class AutomaticUpdateScheduleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings_path = str(Path(self.directory.name) / "settings.json")
        self.path_patch = patch.object(settings, "PATH", self.settings_path)
        self.path_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        self.directory.cleanup()

    def test_first_automatic_check_is_due(self):
        self.assertTrue(settings.automatic_update_check_due(now=1000))

    def test_automatic_check_is_limited_to_once_per_24_hours(self):
        settings.mark_automatic_update_check(now=1000)

        self.assertFalse(settings.automatic_update_check_due(
            now=1000 + 24 * 60 * 60 - 1))
        self.assertTrue(settings.automatic_update_check_due(
            now=1000 + 24 * 60 * 60))

    def test_clock_rollback_does_not_block_checks_indefinitely(self):
        settings.mark_automatic_update_check(now=2000)

        self.assertTrue(settings.automatic_update_check_due(now=1000))


if __name__ == "__main__":
    unittest.main()

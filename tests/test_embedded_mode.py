import importlib.util
import os
import unittest
from unittest.mock import patch


HAS_PYQT5 = importlib.util.find_spec("PyQt5") is not None


@unittest.skipUnless(HAS_PYQT5, "PyQt5가 설치된 환경에서 실행")
class EmbeddedModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # Other localization tests intentionally switch the process-wide
        # catalog. Embedded-mode assertions use the international default.
        from pdfeditor.i18n import set_language
        set_language("en")

    def test_internal_module_window_disables_all_update_entry_points(self):
        from PyQt5.QtWidgets import QAction
        from pdfeditor.app import AppWindow

        with patch("pdfeditor.app.settings.ui_language", return_value="en"):
            window = AppWindow()
        menu_texts = [action.text() for action in window.findChildren(QAction)]

        self.assertFalse(window.updates_enabled)
        self.assertIsNone(window._update_service)
        self.assertFalse(window.check_for_updates(manual=True))
        self.assertNotIn("Check for Updates...", menu_texts)
        window.close()

    def test_standalone_window_keeps_update_feature(self):
        from PyQt5.QtWidgets import QAction
        from pdfeditor.app import AppWindow

        with patch("pdfeditor.app.settings.automatic_update_check_due",
                   return_value=False), patch(
                       "pdfeditor.app.settings.ui_language", return_value="en"):
            window = AppWindow(updates_enabled=True)
        menu_texts = [action.text() for action in window.findChildren(QAction)]

        self.assertTrue(window.updates_enabled)
        self.assertIsNotNone(window._update_service)
        self.assertIn("Check for Updates...", menu_texts)
        window.close()


if __name__ == "__main__":
    unittest.main()

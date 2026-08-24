import importlib.util
import unittest
from types import SimpleNamespace
from unittest.mock import Mock


HAS_PYQT5 = importlib.util.find_spec("PyQt5") is not None


@unittest.skipUnless(HAS_PYQT5, "PyQt5가 설치된 환경에서 실행")
class WindowViewModeTests(unittest.TestCase):
    def test_full_screen_toggle_preserves_regular_chrome(self):
        from pdfeditor.app import AppWindow

        host = Mock()
        host.presentation_active = False
        host.isFullScreen.return_value = False
        AppWindow.toggle_full_screen(host)
        host.showFullScreen.assert_called_once_with()
        host.showNormal.assert_not_called()

        host.reset_mock()
        host.presentation_active = False
        host.isFullScreen.return_value = True
        AppWindow.toggle_full_screen(host)
        host.showNormal.assert_called_once_with()

    def test_presentation_hides_and_restores_window_chrome(self):
        from pdfeditor.app import AppWindow

        host = Mock()
        host.presentation_active = False
        host._presentation_tab = None
        host._presentation_window_state = None
        host.isFullScreen.return_value = False
        host.menuBar.return_value.isHidden.return_value = False
        host._tabs.tabBar.return_value.isHidden.return_value = False
        tab = Mock(doc=SimpleNamespace())

        AppWindow.toggle_presentation(host, tab)

        self.assertIs(host._presentation_tab, tab)
        tab.set_presentation_chrome_hidden.assert_called_once_with(True)
        host.menuBar.return_value.hide.assert_called_once_with()
        host._tabs.tabBar.return_value.hide.assert_called_once_with()
        host.showFullScreen.assert_called_once_with()

        host.presentation_active = True
        AppWindow.toggle_presentation(host, tab)

        self.assertIsNone(host._presentation_tab)
        tab.set_presentation_chrome_hidden.assert_called_with(False)
        host.showNormal.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

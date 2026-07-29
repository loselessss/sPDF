import importlib.util
import os
import unittest


HAS_PYQT5 = importlib.util.find_spec("PyQt5") is not None


@unittest.skipUnless(HAS_PYQT5, "PyQt5가 설치된 환경에서 실행")
class ThumbnailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_long_document_can_scroll_to_last_thumbnail(self):
        from pdfeditor.widgets import ThumbList

        thumbs = ThumbList()
        thumbs.resize(180, 700)
        thumbs.reset_pages(50)
        thumbs.show()
        self.app.processEvents()

        thumbs.verticalScrollBar().setValue(
            thumbs.verticalScrollBar().maximum())
        self.app.processEvents()

        rows = thumbs.visible_rows()
        self.assertIn(49, rows)
        self.assertGreater(rows[0], 21)
        thumbs.close()

    def test_thumbnail_panel_width_is_adjustable_in_splitter(self):
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QSplitter, QWidget
        from pdfeditor.widgets import ThumbList

        splitter = QSplitter(Qt.Horizontal)
        thumbs = ThumbList()
        splitter.addWidget(thumbs)
        splitter.addWidget(QWidget())
        splitter.resize(900, 700)
        splitter.setSizes([160, 740])
        splitter.show()
        self.app.processEvents()
        initial_width = thumbs.width()

        splitter.setSizes([300, 600])
        self.app.processEvents()

        self.assertGreater(thumbs.width(), initial_width)
        splitter.close()


if __name__ == "__main__":
    unittest.main()

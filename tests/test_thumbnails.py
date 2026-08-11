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

    def test_page_organizer_renders_rows_after_ten_when_scrolled(self):
        from pdfeditor.page_organizer import PageOrganizerList

        pages = PageOrganizerList(None)
        pages.resize(600, 700)
        pages.reset_pages(50)
        pages.show()
        self.app.processEvents()

        pages.verticalScrollBar().setValue(
            pages.verticalScrollBar().maximum())
        self.app.processEvents()

        rows = pages.visible_rows()
        self.assertIn(49, rows)
        self.assertGreater(rows[0], 10)
        pages.close()

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

    def test_thumbnail_content_follows_panel_width_without_losing_labels(self):
        from pdfeditor.widgets import ThumbList

        thumbs = ThumbList()
        thumbs.resize(180, 700)
        thumbs.reset_pages(3)
        thumbs.show()
        self.app.processEvents()
        narrow = thumbs.thumbnail_width()
        narrow_height = thumbs.item(0).sizeHint().height()

        thumbs.resize(320, 700)
        self.app.processEvents()

        self.assertGreater(thumbs.thumbnail_width(), narrow)
        self.assertGreater(thumbs.item(0).sizeHint().height(), narrow_height)
        self.assertEqual([thumbs.item(i).text() for i in range(3)],
                         ["1", "2", "3"])
        thumbs.close()

    def test_viewport_marker_can_be_updated_without_changing_item_geometry(self):
        from PyQt5.QtCore import QRectF
        from pdfeditor.widgets import ThumbList

        thumbs = ThumbList()
        thumbs.resize(180, 500)
        thumbs.reset_pages(2)
        before = thumbs.item(0).sizeHint()
        thumbs.set_viewport_marker(0, QRectF(0.2, 0.3, 0.4, 0.5))

        self.assertEqual(thumbs.item(0).sizeHint(), before)
        self.assertEqual(thumbs._viewport_page, 0)
        self.assertEqual(thumbs._viewport_rect, QRectF(0.2, 0.3, 0.4, 0.5))
        thumbs.close()


if __name__ == "__main__":
    unittest.main()

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

    def test_two_digit_page_number_has_its_own_visible_band(self):
        from PyQt5.QtCore import QRectF
        from PyQt5.QtGui import QImage
        from pdfeditor.widgets import ThumbList

        thumbs = ThumbList()
        thumbs.resize(180, 700)
        thumbs.reset_pages(15)
        thumbs.show()
        thumbs.set_thumb(9, QImage(120, 180, QImage.Format_RGB888))
        thumbs.scrollToItem(thumbs.item(9))
        self.app.processEvents()

        image_rect = thumbs._thumbnail_image_rect(9)
        label_rect = thumbs._thumbnail_label_rect(9)
        self.assertEqual(thumbs.item(9).text(), "10")
        self.assertFalse(label_rect.isEmpty())
        self.assertGreaterEqual(label_rect.top(), image_rect.bottom())
        self.assertTrue(label_rect.intersects(QRectF(thumbs.viewport().rect())))
        thumbs.close()

    def test_thumbnail_pixmaps_outside_nearby_window_are_released(self):
        from PyQt5.QtGui import QImage
        from pdfeditor.widgets import ThumbList

        thumbs = ThumbList()
        thumbs.reset_pages(30)
        image = QImage(20, 30, QImage.Format_RGB888)
        for row in (0, 1, 10, 11, 20):
            thumbs.set_thumb(row, image)

        thumbs.evict_thumbnails_outside(8, 13)

        self.assertEqual(thumbs._rendered_rows, {10, 11})
        self.assertTrue(thumbs.item(0).icon().isNull())
        self.assertFalse(thumbs.item(10).icon().isNull())
        thumbs.close()

    def test_two_page_spread_marks_both_thumbnail_rows(self):
        from pdfeditor.widgets import THUMB_SPREAD_ROLE, ThumbList

        thumbs = ThumbList()
        thumbs.reset_pages(5)
        thumbs.set_spread_pages([2, 3])

        self.assertFalse(thumbs.item(1).data(THUMB_SPREAD_ROLE))
        self.assertTrue(thumbs.item(2).data(THUMB_SPREAD_ROLE))
        self.assertTrue(thumbs.item(3).data(THUMB_SPREAD_ROLE))
        thumbs.set_spread_pages([4])
        self.assertFalse(thumbs.item(2).data(THUMB_SPREAD_ROLE))
        self.assertFalse(thumbs.item(3).data(THUMB_SPREAD_ROLE))
        self.assertTrue(thumbs.item(4).data(THUMB_SPREAD_ROLE))
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

    def test_thumbnail_click_uses_centered_page_image_rect(self):
        from PyQt5.QtCore import QPoint
        from PyQt5.QtGui import QImage
        from pdfeditor.widgets import ThumbList

        thumbs = ThumbList()
        thumbs.resize(180, 500)
        thumbs.reset_pages(1)
        thumbs.show()
        thumbs.set_thumb(0, QImage(120, 60, QImage.Format_RGB888))
        self.app.processEvents()

        item_rect = thumbs.visualItemRect(thumbs.item(0))
        image_rect = thumbs._thumbnail_image_rect(0)
        self.assertGreater(image_rect.top(), item_rect.top())
        target = thumbs.thumbnail_point_at(
            QPoint(round(image_rect.center().x()), round(image_rect.center().y())))
        self.assertIsNotNone(target)
        self.assertEqual(target[0], 0)
        self.assertAlmostEqual(target[1].x(), 0.5, places=1)
        self.assertAlmostEqual(target[1].y(), 0.5, places=1)
        thumbs.close()


if __name__ == "__main__":
    unittest.main()

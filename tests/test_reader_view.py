"""Reader compositor, coordinate mapping and bounded CPU tile regressions."""

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch


HAS_QT = importlib.util.find_spec("PyQt5") is not None


@unittest.skipUnless(HAS_QT, "PyQt5 is required")
class ReaderViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        import fitz
        from pdfeditor.core import Document
        from pdfeditor.reader_view import ReaderPageView
        self.directory = tempfile.TemporaryDirectory()
        path = Path(self.directory.name) / "reader.pdf"
        with fitz.open() as pdf:
            for index in range(12):
                page = pdf.new_page(width=600, height=840)
                page.draw_rect((50, 50, 260, 320), color=(1, 0, 0),
                               fill=(0.2, 0.6, 0.8))
                page.insert_text((70, 100), "Reader page %s" % index)
                if index == 1:
                    page.set_cropbox(fitz.Rect(20, 30, 580, 820))
                    page.set_rotation(90)
            pdf.save(path)
        self.doc = Document(str(path), read_only=True)
        self.view = ReaderPageView(use_opengl=False)
        self.view.resize(720, 560)
        self.view.show()
        self.app.processEvents()
        self.view.render_document(self.doc, [0], 0)
        self.view.stop_rendering()

    def tearDown(self):
        self.view.clear()
        self.view.close()
        self.view.deleteLater()
        self.doc.close()
        self.app.processEvents()
        self.directory.cleanup()

    def finish_tiles(self):
        self.view._plan_tiles()
        self.view._tile_timer.stop()
        while self.view._pending:
            self.view._render_next_tile()
            self.view._tile_timer.stop()

    def test_zoom_immediately_reuses_images_and_preserves_pointer(self):
        from PyQt5.QtCore import QPoint
        self.view.preview_zoom(2)
        self.view.centerOn(600, 700)
        cursor = QPoint(260, 240)
        before = self.view.canvas._page_point(self.view.mapToScene(cursor))
        with patch.object(self.doc, "render") as full, \
                patch.object(self.doc, "render_region") as tile:
            self.view.preview_zoom(8, cursor)
            full.assert_not_called()
            tile.assert_not_called()
        after = self.view.canvas._page_point(self.view.mapToScene(cursor))
        self.assertEqual(before[0], after[0])
        self.assertLess((before[1] - after[1]).manhattanLength(), 0.3)
        self.assertEqual(self.view.canvas.zoom, 8)
        self.assertEqual(self.view.sceneRect().width(), 4800)
        self.assertLess(self.view.canvas.width(), 1000)
        self.assertLessEqual(self.view.viewport().width(), 720)
        self.assertTrue(self.view._refine_timer.isActive())

    def test_only_requested_pages_have_bounded_previews(self):
        from pdfeditor.reader_view import PREVIEW_PIXELS
        with patch.object(self.doc, "render", wraps=self.doc.render) as render:
            self.view.render_document(self.doc, [10, 11], 11)
        self.assertEqual([call.args[0] for call in render.call_args_list], [10, 11])
        self.assertEqual(set(self.view._previews), {10, 11})
        self.assertEqual(self.view.canvas._active_page, 11)
        for pix in self.view._previews.values():
            self.assertLessEqual(pix.width() * pix.height(), PREVIEW_PIXELS + 3000)
        self.view.render_document(self.doc, [11], 11)
        self.assertEqual(set(self.view._previews), {11})

    def test_800_percent_uses_visible_small_tiles_not_full_page(self):
        from pdfeditor.reader_view import MAX_VISIBLE_TILES, TILE_PIXELS
        self.view.preview_zoom(8)
        self.view.centerOn(2400, 3360)
        with patch.object(self.doc, "render") as full, \
                patch.object(self.doc, "render_region", wraps=self.doc.render_region) as region:
            self.finish_tiles()
        full.assert_not_called()
        self.assertGreater(region.call_count, 0)
        self.assertLessEqual(region.call_count, MAX_VISIBLE_TILES)
        for pixmap, rect in self.view._tiles.values():
            self.assertLessEqual(pixmap.width(), TILE_PIXELS + 3)
            self.assertLessEqual(pixmap.height(), TILE_PIXELS + 3)
            self.assertLess(rect.width(), 65)

    def test_tile_lru_is_bounded_across_zoom_and_page_changes(self):
        from pdfeditor import reader_view
        with patch.object(reader_view, "TILE_CACHE_BYTES", 3 * 1024 * 1024):
            for page in (0, 1, 2):
                self.view.render_document(self.doc, [page], page)
                for zoom in (2, 4, 8):
                    self.view.preview_zoom(zoom)
                    self.finish_tiles()
                    self.assertLessEqual(self.view._tile_bytes, reader_view.TILE_CACHE_BYTES)
                    self.assertEqual(self.view._tile_bytes, sum(
                        pix.width() * pix.height() * 4
                        for pix, _rect in self.view._tiles.values()))

    def test_same_view_reuses_cached_tiles(self):
        self.finish_tiles()
        keys = set(self.view._tiles)
        with patch.object(self.doc, "render_region") as region:
            self.finish_tiles()
        region.assert_not_called()
        self.assertEqual(keys, self.view._wanted)

    def test_thumbnail_center_and_visible_marker_agree(self):
        from PyQt5.QtCore import QPointF
        self.view.preview_zoom(8)
        self.view.center_on_page_fraction(QPointF(0.6, 0.7))
        marker = self.view.visible_page_rect()
        self.assertAlmostEqual(marker.center().x(), 0.6, delta=0.001)
        self.assertAlmostEqual(marker.center().y(), 0.7, delta=0.001)
        self.view.preview_zoom(0.3)
        self.assertIsNone(self.view.visible_page_rect())

    def test_two_page_ctrl_click_activates_correct_pdf_coordinates(self):
        from PyQt5.QtCore import QPointF, Qt
        from PyQt5.QtTest import QTest
        self.view.zoom = 0.4
        self.view.render_document(self.doc, [0, 1], 0)
        rect = self.view.canvas._pages[1][2]
        self.assertEqual(rect.left(), 600 * 0.4 + 16)
        position = self.view.mapFromScene(rect.topLeft() + QPointF(100, 100) * 0.4)
        activated, clicked = [], []
        self.view.canvas.page_activated.connect(activated.append)
        self.view.canvas.ctrl_clicked.connect(clicked.append)
        QTest.mouseClick(self.view.viewport(), Qt.LeftButton, Qt.ControlModifier, position)
        self.assertEqual(activated, [1])
        self.assertEqual(len(clicked), 1)
        self.assertLess((clicked[0] - QPointF(100, 100)).manhattanLength(), 1)

    def test_selection_and_hand_drag_are_forwarded(self):
        from PyQt5.QtCore import QEvent, QPointF, Qt
        from PyQt5.QtGui import QMouseEvent
        self.view.preview_zoom(2)
        self.view.centerOn(600, 700)
        start = self.view.viewport().rect().center()
        end = start + QPointF(30, 20).toPoint()
        selected = []
        self.view.canvas.drag_selected.connect(lambda a, b: selected.append((a, b)))
        def drag():
            for name, event_type, point, button, buttons in (
                ("mousePressEvent", QEvent.MouseButtonPress, start, Qt.LeftButton, Qt.LeftButton),
                ("mouseMoveEvent", QEvent.MouseMove, end, Qt.NoButton, Qt.LeftButton),
                ("mouseReleaseEvent", QEvent.MouseButtonRelease, end, Qt.LeftButton, Qt.NoButton),
            ):
                event = QMouseEvent(event_type, QPointF(point),
                                    QPointF(self.view.viewport().mapToGlobal(point)),
                                    button, buttons, Qt.NoModifier)
                getattr(self.view, name)(event)
        drag()
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0][1] - selected[0][0], QPointF(15, 10))
        self.view.set_interaction_mode("hand")
        before = self.view.verticalScrollBar().value()
        drag()
        self.assertEqual(self.view.verticalScrollBar().value(), before - 20)
        self.assertEqual(len(selected), 1)
        self.assertEqual(self.view.viewport().cursor().shape(), Qt.OpenHandCursor)

    def test_search_rect_can_scroll_into_view(self):
        from PyQt5.QtCore import QRectF
        self.view.preview_zoom(8)
        rect = QRectF(350, 640, 20, 15)
        self.view.ensure_rect_visible(rect)
        self.assertTrue(self.view._visible_scene_rect().contains(QRectF(2800, 5120, 160, 120)))

    def test_hide_clear_and_document_change_cancel_pending_tiles(self):
        self.view._plan_tiles()
        self.assertTrue(self.view._pending)
        self.view.hide()
        self.assertFalse(self.view._pending)
        self.assertFalse(self.view._tile_timer.isActive())
        self.assertFalse(self.view._refine_timer.isActive())
        self.view.show()
        self.finish_tiles()
        self.assertTrue(self.view._tiles)
        from pdfeditor.core import Document
        other = Document(self.doc.path, read_only=True)
        try:
            self.view.render_document(other, [0], 0)
            self.assertFalse(self.view._tiles)
            self.view.clear()
            self.assertIsNone(self.view._document)
            self.assertFalse(self.view._pending)
            self.assertFalse(self.view._previews)
        finally:
            other.close()

    def test_invalid_gl_context_falls_back_without_losing_document(self):
        self.view.preview_zoom(4)
        self.finish_tiles()
        self.view.centerOn(1200, 1600)
        state = (self.view.horizontalScrollBar().value(), self.view.verticalScrollBar().value())
        tiles = set(self.view._tiles)
        self.view._gpu_surface = Mock(isValid=Mock(return_value=False))
        self.view._verify_gpu()
        self.assertEqual(self.view.composition_backend, "cpu")
        self.assertIs(self.view._document, self.doc)
        self.assertEqual(tiles, set(self.view._tiles))
        self.assertEqual(state, (self.view.horizontalScrollBar().value(), self.view.verticalScrollBar().value()))

    def test_render_failure_keeps_preview_and_stops_queue(self):
        self.view._plan_tiles()
        errors = []
        self.view.render_failed.connect(errors.append)
        with patch.object(self.doc, "render_region", side_effect=RuntimeError("tile failure")):
            self.view._render_next_tile()
        self.assertEqual(errors, ["tile failure"])
        self.assertFalse(self.view._pending)
        self.assertIn(0, self.view._previews)

    def test_region_matches_full_render_including_cropped_rotated_page(self):
        for page in (0, 1):
            for zoom in (0.83, 2.15):
                width, height, stride, samples = self.doc.render(page, zoom)
                x, y, w, h, tile_stride, tile = self.doc.render_region(
                    page, zoom, (39.3, 40.2, 340.7, 390.1))
                expected = b"".join(samples[row * stride + x * 3:row * stride + (x + w) * 3]
                                    for row in range(y, y + h))
                self.assertEqual(tile_stride, w * 3)
                self.assertEqual(tile, expected)

    def test_region_rejects_unbounded_or_invalid_requests(self):
        for scale, rect in ((8, (0, 0, 600, 840)), (0, (0, 0, 10, 10)),
                            (float("inf"), (0, 0, 10, 10)), (1, (0, 0, 0, 0)),
                            (1, (0, float("nan"), 20, 20))):
            with self.subTest(scale=scale, rect=rect), self.assertRaises(ValueError):
                self.doc.render_region(0, scale, rect)


if __name__ == "__main__":
    unittest.main()

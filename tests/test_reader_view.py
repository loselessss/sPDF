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

    def test_render_device_distinguishes_hardware_direct2d_from_warp(self):
        from types import SimpleNamespace

        self.view._d2d_surface = Mock(
            info=SimpleNamespace(driver="hardware"))
        self.assertEqual(self.view.render_device, "gpu")
        self.view._d2d_surface.info.driver = "warp"
        self.assertEqual(self.view.render_device, "cpu")
        self.view._d2d_surface = None

    def test_page_diagnostic_distinguishes_direct_composite_and_fallback(self):
        from pdfeditor.gpu_raster import VectorPage, VectorPath

        commands = (("move", 0, 0), ("line", 10, 10))
        self.view._d2d_requested = True
        self.view._vector_pages = {
            0: VectorPage(True, (VectorPath(
                commands, stroke_argb=0xff000000),), features=("vector",)),
            1: VectorPage(True, features=("image", "vector")),
            2: VectorPage(False, reason="unsupported operation: begin-mask",
                          features=("vector",)),
        }
        self.assertEqual(self.view.render_diagnostic(0)["mode"], "direct")
        self.assertEqual(self.view.render_diagnostic(1)["mode"], "composite")
        fallback = self.view.render_diagnostic(2)
        self.assertEqual(fallback["mode"], "fallback")
        self.assertEqual(fallback["reason"], "unsupported operation: begin-mask")
        self.view._d2d_requested = False

    def test_forced_gpu_mode_rejects_direct2d_warp(self):
        from types import SimpleNamespace
        from pdfeditor import reader_view

        with patch.object(reader_view, "opengl_allowed", return_value=True), \
                patch.object(reader_view.settings, "render_backend",
                             return_value="gpu"), \
                patch.object(
                    reader_view, "probe_d2d_backend",
                    return_value=SimpleNamespace(available=True, driver="warp")):
            view = reader_view.ReaderPageView()
        try:
            self.assertFalse(view._d2d_requested)
            self.assertEqual(view.composition_backend, "cpu")
        finally:
            view.close()

    def test_direct2d_uploads_tiles_and_draws_interaction_overlays(self):
        from PyQt5.QtCore import QRectF

        class Bitmap:
            closed = False

            def close(self):
                self.closed = True

        class Surface:
            def __init__(self):
                self.created = []
                self.drawn = []
                self.filled = []
                self.stroked = []

            def create_bitmap_bgra(self, pixels, width, height, stride):
                self.created.append((len(pixels), width, height, stride))
                return Bitmap()

            def begin_frame(self, _color):
                pass

            def set_transform(self, *values):
                self.transform = values

            def draw_bitmap(self, bitmap, *rect):
                self.drawn.append((bitmap, rect))

            def fill_rect(self, *values):
                self.filled.append(values)

            def stroke_rect(self, *values):
                self.stroked.append(values)

            def end_frame(self):
                pass

        self.finish_tiles()
        self.view.canvas.set_selection([QRectF(60, 70, 80, 20)])
        self.view.canvas.set_edit_boxes([QRectF(70, 110, 90, 24)])
        surface = Surface()
        self.view._d2d_surface = surface
        ratio = max(1.0, self.view.viewport().devicePixelRatioF())
        self.view._d2d_size = (self.view.viewport().size(), ratio)
        self.view._paint_d2d()
        self.assertGreaterEqual(len(surface.created), 2)
        self.assertGreaterEqual(len(surface.drawn), 2)
        self.assertEqual(len(surface.filled), 1)
        self.assertEqual(len(surface.stroked), 1)
        created = len(surface.created)
        self.view._paint_d2d()
        self.assertEqual(len(surface.created), created)
        old_preview = self.view._d2d_previews[0][1]
        self.view.render_document(self.doc, [1], 1)
        self.assertTrue(old_preview.closed)
        self.assertNotIn(0, self.view._d2d_previews)
        self.view._d2d_surface = None
        self.view._d2d_previews.clear()
        self.view._d2d_tiles.clear()

    def test_supported_vector_page_skips_cpu_tiles_and_rasterizes_paths(self):
        from pdfeditor.gpu_raster import VectorPage, VectorPath

        scene = VectorPage(True, (VectorPath(
            (("move", 20, 20), ("line", 120, 20),
             ("line", 120, 100), ("close",)),
            fill_argb=0xff0080ff, stroke_argb=0xffff0000,
            stroke_width=2),))
        native_path = Mock(closed=False)
        surface = Mock()
        surface.create_path.return_value = native_path
        self.view._d2d_surface = surface
        ratio = max(1.0, self.view.viewport().devicePixelRatioF())
        self.view._d2d_size = (self.view.viewport().size(), ratio)
        self.view._d2d_requested = True
        self.view._vector_pages[0] = scene

        self.view._paint_d2d()
        surface.create_path.assert_called_once_with(
            scene.paths[0].commands, even_odd=False)
        surface.fill_path.assert_called_once_with(native_path, 0xff0080ff)
        surface.stroke_path.assert_called_once_with(native_path, 0xffff0000, 2)
        surface.create_bitmap_bgra.assert_not_called()
        self.view._plan_tiles()
        self.assertFalse(self.view._pending)

        self.view._d2d_surface = None
        self.view._d2d_vector_paths.clear()
        self.view._d2d_requested = False

    def test_stroked_clip_path_is_widened_then_pushed_on_gpu(self):
        from pdfeditor.gpu_raster import ClipPop, ClipStrokePush, VectorPage

        style = (1, 1, 1, 2, 10.0, 0.5, (1.5, 0.75))
        clip = ClipStrokePush(
            (("move", 20, 20), ("line", 120, 20)), 4.0, style)
        scene = VectorPage(True, items=(clip, ClipPop()))
        source = Mock(closed=False)
        native_style = Mock(closed=False)
        widened = Mock(closed=False)
        surface = Mock()
        surface.create_path.return_value = source
        surface.create_stroke_style.return_value = native_style
        surface.create_stroked_path.return_value = widened
        self.view._d2d_surface = surface
        ratio = max(1.0, self.view.viewport().devicePixelRatioF())
        self.view._d2d_size = (self.view.viewport().size(), ratio)
        self.view._d2d_requested = True
        self.view._vector_pages[0] = scene

        self.view._paint_d2d()
        surface.create_path.assert_called_once_with(clip.commands)
        surface.create_stroke_style.assert_called_once_with(style)
        surface.create_stroked_path.assert_called_once_with(
            source, 4.0, native_style)
        surface.push_clip_path.assert_called_once_with(widened)
        surface.pop_clip.assert_called_once_with()

        self.view._d2d_surface = None
        self.view._d2d_vector_paths.clear()
        self.view._d2d_requested = False

    def test_blended_scene_uses_explicit_composite_groups(self):
        from pdfeditor.gpu_raster import GroupPush, GroupPop, VectorPage
        scene = VectorPage(True, items=(
            GroupPush(1), GroupPush(.5, 9), GroupPop(),
            GroupPush(.5, 12), GroupPop(), GroupPush(.5, 13), GroupPop(),
            GroupPush(.5, 14), GroupPop(), GroupPush(.5, 15), GroupPop(), GroupPop()))
        surface = Mock()
        self.view._d2d_surface = surface
        ratio = max(1.0, self.view.viewport().devicePixelRatioF())
        self.view._d2d_size = (self.view.viewport().size(), ratio)
        self.view._d2d_requested = True
        self.view._vector_pages[0] = scene
        self.view._paint_d2d()
        self.assertEqual([call.args for call in
            surface.begin_composite_group.call_args_list],
            [(0, 1), (9, .5), (12, .5), (13, .5), (14, .5), (15, .5)])
        self.assertEqual(surface.end_composite_group.call_count, 6)
        surface.push_opacity_layer.assert_not_called()
        surface.create_bitmap_bgra.assert_not_called()
        self.view._d2d_surface = None
        self.view._d2d_vector_paths.clear()
        self.view._d2d_requested = False

    def test_blended_scene_routes_geometry_clips_through_backdrop_captures(self):
        from pdfeditor.gpu_raster import (ClipPush, ClipStrokePush, ClipPop,
                                         GroupPush, GroupPop, VectorPage)
        commands = (("move", 0, 0), ("line", 50, 0), ("line", 50, 50), ("close",))
        scene = VectorPage(True, items=(
            GroupPush(1), ClipPush(commands, transform=(1, 0, 0, 1, 10, 20)),
            GroupPush(.5, 9), ClipStrokePush(commands, 2.0), ClipPop(),
            GroupPop(), ClipPop(), GroupPop()))
        surface = Mock()
        self.view._d2d_surface = surface
        ratio = max(1.0, self.view.viewport().devicePixelRatioF())
        self.view._d2d_size = (self.view.viewport().size(), ratio)
        self.view._d2d_requested = True
        self.view._vector_pages[0] = scene
        try:
            self.view._paint_d2d()
            events = [call[0] for call in surface.mock_calls if call[0] in (
                "begin_clip_group", "end_clip_group", "begin_composite_group",
                "end_composite_group")]
            self.assertEqual(events, ["begin_composite_group", "begin_clip_group",
                "begin_composite_group", "begin_clip_group", "end_clip_group",
                "end_composite_group", "end_clip_group", "end_composite_group"])
            surface.create_stroked_path.assert_called_once()
            surface.push_clip_path.assert_not_called()
            surface.pop_clip.assert_not_called()
        finally:
            self.view._d2d_surface = None
            self.view._d2d_vector_paths.clear()
            self.view._d2d_requested = False

    def test_supported_image_scene_uploads_bitmap_and_preserves_transform(self):
        from pdfeditor.gpu_raster import VectorImage, VectorPage

        image = VectorImage(
            bytes((0, 0, 255, 255)) * 4, 2, 2, 8,
            (100, 0, 0, 80, 25, 35), .75)
        scene = VectorPage(True, items=(image,))
        bitmap = Mock(closed=False)
        surface = Mock()
        surface.create_bitmap_bgra.return_value = bitmap
        self.view._d2d_surface = surface
        ratio = max(1.0, self.view.viewport().devicePixelRatioF())
        self.view._d2d_size = (self.view.viewport().size(), ratio)
        self.view._d2d_requested = True
        self.view._vector_pages[0] = scene

        self.view._paint_d2d()
        surface.create_bitmap_bgra.assert_called_once_with(
            image.pixels, 2, 2, 8)
        surface.draw_bitmap.assert_called_once_with(
            bitmap, 0, 0, 1, 1, .75, interpolate=True)
        transform = surface.set_transform.call_args_list[-2].args
        page_transform = surface.set_transform.call_args_list[-1].args
        self.assertEqual(transform[:4], image.transform[:4])
        self.assertEqual(transform[4] - page_transform[4], image.transform[4])
        self.assertEqual(transform[5] - page_transform[5], image.transform[5])
        self.view._plan_tiles()
        self.assertFalse(self.view._pending)

        self.view._d2d_surface = None
        self.view._d2d_vector_paths.clear()
        self.view._d2d_requested = False

    def test_repeated_glyphs_share_geometry_and_one_realized_group(self):
        from pdfeditor.gpu_raster import VectorPage, VectorPath

        commands = (("move", 0, 0), ("line", 1, 0),
                    ("line", 1, 1), ("close",))
        glyphs = tuple(VectorPath(
            commands, fill_argb=0xff202020,
            transform=(12, 0, 0, 12, x, 40), groupable=True)
                       for x in (20, 40, 60))
        scene = VectorPage(True, glyphs, items=glyphs)
        path = Mock(closed=False)
        group = Mock(closed=False)
        surface = Mock()
        surface.create_path.return_value = path
        surface.create_geometry_group.return_value = group
        self.view._d2d_surface = surface
        self.view._d2d_requested = True
        self.view._vector_pages[0] = scene
        ratio = max(1.0, self.view.viewport().devicePixelRatioF())
        self.view._d2d_size = (self.view.viewport().size(), ratio)

        self.view._paint_d2d()
        surface.create_path.assert_called_once_with(commands, even_odd=False)
        surface.create_geometry_group.assert_called_once_with(
            [(path, glyph.transform) for glyph in glyphs], even_odd=False)
        surface.fill_path.assert_called_once_with(group, 0xff202020)
        self.assertEqual(surface.set_transform.call_args_list[-2].args[:4],
                         (1.0, 0.0, 0.0, 1.0))

        self.view._d2d_surface = None
        self.view._d2d_vector_paths.clear()
        self.view._d2d_requested = False

    def test_clip_scene_pushes_and_pops_native_layer_in_order(self):
        from pdfeditor.gpu_raster import (ClipPop, ClipPush, VectorPage,
                                          VectorPath)

        commands = (("move", 0, 0), ("line", 100, 0),
                    ("line", 100, 80), ("close",))
        clip = ClipPush(commands, transform=(1, 0, 0, 1, 20, 30))
        drawing = VectorPath(commands, fill_argb=0xff0080ff)
        scene = VectorPage(True, (drawing,),
                           items=(clip, drawing, ClipPop()))
        clip_path = Mock(closed=False)
        surface = Mock()
        surface.create_path.return_value = clip_path
        calls = []
        surface.push_clip_path.side_effect = \
            lambda path: calls.append(("push", path))
        surface.fill_path.side_effect = \
            lambda path, color: calls.append(("fill", path, color))
        surface.pop_clip.side_effect = lambda: calls.append(("pop",))
        self.view._d2d_surface = surface
        self.view._d2d_requested = True
        self.view._vector_pages[0] = scene
        ratio = max(1.0, self.view.viewport().devicePixelRatioF())
        self.view._d2d_size = (self.view.viewport().size(), ratio)

        self.view._paint_d2d()
        self.assertEqual(calls, [
            ("push", clip_path),
            ("fill", clip_path, 0xff0080ff),
            ("pop",),
        ])

        self.view._d2d_surface = None
        self.view._d2d_vector_paths.clear()
        self.view._d2d_requested = False

    def test_transparency_group_uses_opacity_layer_in_order(self):
        from pdfeditor.gpu_raster import (GroupPop, GroupPush, VectorPage,
                                          VectorPath)

        commands = (("move", 0, 0), ("line", 100, 0),
                    ("line", 100, 80), ("close",))
        drawing = VectorPath(commands, fill_argb=0xff0080ff)
        scene = VectorPage(
            True, (drawing,),
            items=(GroupPush(0.6), drawing, GroupPop()))
        path = Mock(closed=False)
        surface = Mock()
        surface.create_path.return_value = path
        calls = []
        surface.push_opacity_layer.side_effect = \
            lambda opacity: calls.append(("push-group", opacity))
        surface.fill_path.side_effect = \
            lambda resource, color: calls.append(("fill", resource, color))
        surface.pop_layer.side_effect = lambda: calls.append(("pop-group",))
        self.view._d2d_surface = surface
        self.view._d2d_requested = True
        self.view._vector_pages[0] = scene
        ratio = max(1.0, self.view.viewport().devicePixelRatioF())
        self.view._d2d_size = (self.view.viewport().size(), ratio)

        self.view._paint_d2d()
        self.assertEqual(calls, [
            ("push-group", 0.6),
            ("fill", path, 0xff0080ff),
            ("pop-group",),
        ])

        self.view._d2d_surface = None
        self.view._d2d_vector_paths.clear()
        self.view._d2d_requested = False

    def test_soft_mask_captures_then_applies_before_page_drawing(self):
        from pdfeditor.gpu_raster import (ClipPop, MaskBegin, MaskEnd,
                                          VectorPage, VectorPath)

        commands = (("move", 0, 0), ("line", 100, 0),
                    ("line", 100, 80), ("close",))
        mask_path = VectorPath(commands, fill_argb=0xffffffff)
        content = VectorPath(commands, fill_argb=0xffff0000)
        scene = VectorPage(
            True, (mask_path, content),
            items=(MaskBegin((0, 0, 100, 80), True, 0xff000000),
                   mask_path, MaskEnd(), content, ClipPop()),
            features=("soft-mask", "vector"))
        path = Mock(closed=False)
        surface = Mock()
        surface.create_path.return_value = path
        calls = []
        surface.begin_composite_mask.side_effect = lambda *args: calls.append(
            ("begin-mask", *args))
        surface.fill_path.side_effect = lambda resource, color: calls.append(
            ("fill", resource, color))
        surface.end_composite_mask.side_effect = lambda: calls.append(("end-mask",))
        surface.end_clip_group.side_effect = lambda: calls.append(("pop-mask",))
        self.view._d2d_surface = surface
        self.view._d2d_requested = True
        self.view._vector_pages[0] = scene
        ratio = max(1.0, self.view.viewport().devicePixelRatioF())
        self.view._d2d_size = (self.view.viewport().size(), ratio)

        self.view._paint_d2d()
        self.assertEqual(calls, [
            ("begin-mask", (0, 0, 100, 80), True, 0xff000000),
            ("fill", path, 0xffffffff),
            ("end-mask",),
            ("fill", path, 0xffff0000),
            ("pop-mask",),
        ])

        self.view._d2d_surface = None
        self.view._d2d_vector_paths.clear()
        self.view._d2d_requested = False

    def test_same_page_refresh_asks_document_for_invalidated_vector_scene(self):
        from pdfeditor.gpu_raster import VectorPage, VectorPath

        first = VectorPage(True, (VectorPath(
            (("move", 10, 10), ("line", 20, 20)),
            stroke_argb=0xff000000),))
        changed = VectorPage(False, reason="unsupported operation: fill-text")
        self.view._d2d_requested = True
        with patch.object(
                self.doc, "gpu_vector_page",
                side_effect=(first, changed)) as vector_page:
            self.view.render_document(self.doc, [0], 0)
            self.view.render_document(self.doc, [0], 0)
        self.assertEqual(vector_page.call_count, 2)
        self.assertIs(self.view._vector_pages[0], changed)
        self.view._d2d_requested = False

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

    def test_view_rotation_keeps_pdf_unchanged_and_reuses_previews(self):
        original = Path(self.doc.path).read_bytes()
        with patch.object(self.doc, "render", wraps=self.doc.render) as render:
            self.view.rotate_page_view(0, 90)
            render.assert_not_called()
            self.assertEqual(self.view.displayed_page_size(self.doc, 0), (840, 600))
            self.assertEqual(self.view.sceneRect().width(), 840)
            self.view.render_document(self.doc, [2], 2)
            self.view.render_document(self.doc, [0], 0)
        # Switching pages can make new previews; rotating alone does not.
        self.assertEqual(render.call_count, 2)
        self.assertEqual(self.view.page_rotation(0), 90)
        self.view.rotate_page_view(0, -90)
        self.assertEqual(self.view.page_rotation(0), 0)
        self.assertFalse(self.view._rotations)
        self.assertEqual(self.doc._doc[0].rotation, 0)
        self.assertFalse(self.doc._doc.is_dirty)
        self.assertEqual(Path(self.doc.path).read_bytes(), original)

    def test_all_view_rotations_align_tiles_pointer_zoom_and_overlays(self):
        from PyQt5.QtCore import QPointF, QRectF
        self.view.preview_zoom(3)
        point = QPointF(150, 200)
        for angle in (0, 90, 180, 270):
            self.view.rotate_page_view(0, angle - self.view.page_rotation(0))
            self.view.center_on_document_point(point)
            self.finish_tiles()
            cursor = self.view.mapFromScene(self.view._page_transforms[0].map(point))
            mapped = self.view.canvas._page_point(self.view.mapToScene(cursor))
            self.assertLess((mapped[1] - point).manhattanLength(), 1)
            before = self.view.viewport().grab().toImage().pixelColor(cursor)
            self.assertLess(abs(before.red() - 51), 3)
            self.assertLess(abs(before.green() - 153), 3)
            self.assertLess(abs(before.blue() - 204), 3)
            self.view.canvas.set_selection([QRectF(140, 190, 20, 20)])
            after = self.view.viewport().grab().toImage().pixelColor(cursor)
            self.assertNotEqual(before, after)
            self.view.canvas.set_selection([])
            self.view.preview_zoom(8, cursor)
            mapped_after = self.view.canvas._page_point(self.view.mapToScene(cursor))
            self.assertLess((mapped_after[1] - point).manhattanLength(), 1)
            self.view.preview_zoom(3)

    def test_rotated_two_page_selection_and_thumbnail_marker(self):
        from PyQt5.QtCore import QPointF, QRectF, Qt
        from PyQt5.QtTest import QTest
        self.view.render_document(self.doc, [0, 2], 2)
        self.view.rotate_page_view(2, 90)
        self.view.preview_zoom(0.4)
        first, second = [rect for _page, _pix, rect in self.view.canvas._pages]
        self.assertAlmostEqual(second.left(), first.right() + 16)
        self.assertEqual(second.width(), 840 * .4)
        point = QPointF(150, 200)
        cursor = self.view.mapFromScene(self.view._page_transforms[2].map(point))
        clicked = []
        self.view.canvas.ctrl_clicked.connect(clicked.append)
        QTest.mouseClick(self.view.viewport(), Qt.LeftButton, Qt.ControlModifier, cursor)
        self.assertEqual(len(clicked), 1)
        self.assertLess((clicked[0] - point).manhattanLength(), 1)
        self.view.preview_zoom(8)
        self.view.center_on_page_fraction(QPointF(.6, .7))
        marker = self.view.visible_page_rect()
        self.assertAlmostEqual(marker.center().x(), .6, delta=.001)
        self.assertAlmostEqual(marker.center().y(), .7, delta=.001)
        self.view.ensure_rect_visible(QRectF(100, 100, 10, 10))
        self.assertTrue(self.view._visible_scene_rect().contains(
            self.view._page_transforms[2].mapRect(QRectF(100, 100, 10, 10))))

    def test_view_rotation_retained_on_save_refresh_but_not_new_file(self):
        from pdfeditor.core import Document
        self.view.rotate_page_view(0, 90)
        refreshed = Document(self.doc.path, read_only=True)
        other_path = Path(self.directory.name) / "other.pdf"
        other_path.write_bytes(Path(self.doc.path).read_bytes())
        other = Document(str(other_path), read_only=True)
        try:
            self.view.render_document(refreshed, [0], 0)
            self.assertEqual(self.view.page_rotation(0), 90)
            self.view.render_document(other, [0], 0)
            self.assertEqual(self.view.page_rotation(0), 0)
        finally:
            self.view.clear()
            refreshed.close()
            other.close()


if __name__ == "__main__":
    unittest.main()

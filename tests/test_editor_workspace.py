import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec("PyQt5"), "PyQt5 required")
class EditorWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        cls.application = QApplication.instance() or QApplication([])
        cls.application.setQuitOnLastWindowClosed(False)

    def setUp(self):
        import fitz
        from pdfeditor import app, settings
        from pdfeditor.i18n import set_language
        set_language("en")
        self.module = app
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.path = root / "pages.pdf"
        with fitz.open() as pdf:
            for index in range(45):
                page = pdf.new_page(width=280, height=400)
                page.insert_text((35, 60), "Page %02d" % (index + 1), fontsize=20)
                page.draw_rect((35, 90, 240, 330), fill=(.8, .9, 1))
            pdf.save(self.path)
        self.original = self.path.read_bytes()
        self.patchers = [patch.object(settings, "PATH", str(root / "settings.json")),
                         patch.object(settings, "_OLD_PATH", str(root / "absent")),
                         patch.object(app, "_app_windows", [])]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        for window in list(self.module._app_windows):
            for index in range(window._tabs.count()):
                window._tabs.widget(index)._dirty = False
            window.close()
        self.settle()
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.directory.cleanup()

    def settle(self):
        for _ in range(6):
            self.application.processEvents()

    def open_editor(self):
        self.window = self.module.new_window(str(self.path), workspace_mode="editor")
        self.window.resize(1080, 800)
        self.settle()
        return self.window._tabs.currentWidget()

    def render_grid(self, tab):
        grid = tab._page_grid
        grid.stop_rendering()
        for _ in range(40):
            grid._render_visible_thumbnails()
            grid.stop_rendering()
            if all(grid.pages.item(row).data(256) for row in grid.pages.visible_rows()):
                break

    def test_editor_starts_with_wrapped_grid_without_full_page_raster(self):
        from pdfeditor.core import Document
        original_render = Document.render
        with patch.object(Document, "render", autospec=True, side_effect=original_render) as render:
            tab = self.open_editor()
            self.render_grid(tab)
        self.assertTrue(tab.is_editor_overview())
        self.assertFalse(tab._edit_mode)
        self.assertEqual(tab._page_grid.pages.count(), 45)
        self.assertEqual(tab._editor_stack.currentWidget(), tab._page_grid)
        self.assertFalse(tab._zoom_input.isVisible())
        self.assertTrue(render.call_count)
        self.assertTrue(all(call.args[2] < 1 for call in render.call_args_list))
        pages = tab._page_grid.pages
        self.assertTrue(pages.dragEnabled())
        self.assertTrue(pages.acceptDrops())
        first, second = pages.visualItemRect(pages.item(0)), pages.visualItemRect(pages.item(1))
        self.assertEqual(first.top(), second.top())
        self.assertGreater(second.left(), first.right())
        self.assertTrue(tab._detail_button.isVisible())

    def test_mouse_drag_starts_with_selected_page_payload(self):
        from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
        from PyQt5.QtGui import QMouseEvent
        from PyQt5.QtTest import QTest
        from pdfeditor.page_organizer import PAGE_MIME
        tab = self.open_editor()
        pages = tab._page_grid.pages
        point = pages.visualItemRect(pages.item(0)).center()
        with patch("pdfeditor.page_organizer.QDrag") as drag:
            QTest.mousePress(pages.viewport(), Qt.LeftButton, pos=point)
            for offset in (20, 60):
                move = QMouseEvent(QEvent.MouseMove, QPointF(point + QPoint(offset, 0)),
                                   Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
                self.application.sendEvent(pages.viewport(), move)
            QTest.mouseRelease(pages.viewport(), Qt.LeftButton, pos=point + QPoint(60, 0))
        drag.assert_called_once_with(pages)
        mime = drag.return_value.setMimeData.call_args.args[0]
        self.assertEqual(json.loads(bytes(mime.data(PAGE_MIME))), [0])
        drag.return_value.exec_.assert_called_once_with(Qt.MoveAction)

    def test_drop_reorders_selected_pages_with_shared_undo_and_save(self):
        from PyQt5.QtCore import QByteArray, QMimeData, QPointF, Qt
        from PyQt5.QtGui import QDropEvent
        from pdfeditor.page_organizer import PAGE_MIME
        tab = self.open_editor()
        pages = tab._page_grid.pages
        target = pages.visualItemRect(pages.item(3)).topRight()
        mime = QMimeData()
        mime.setData(PAGE_MIME, QByteArray(json.dumps([0, 1]).encode("ascii")))
        event = QDropEvent(QPointF(target), Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier)
        pages.dropEvent(event)
        self.assertTrue(event.isAccepted())
        self.assertTrue(tab._dirty)
        self.assertTrue(tab.is_editor_overview())
        self.assertIn("Page 03", tab.doc._doc[0].get_text())
        self.assertIn("Page 01", tab.doc._doc[2].get_text())
        self.assertEqual([pages.row(item) for item in pages.selectedItems()], [2, 3])
        self.assertEqual(self.path.read_bytes(), self.original)
        tab.undo()
        self.assertIn("Page 01", tab.doc._doc[0].get_text())
        tab.redo()
        self.assertIn("Page 03", tab.doc._doc[0].get_text())
        self.assertTrue(tab.save())
        import fitz
        with fitz.open(self.path) as saved:
            self.assertIn("Page 03", saved[0].get_text())

    def test_double_click_and_large_buttons_share_document_and_edits(self):
        from PyQt5.QtCore import Qt
        from PyQt5.QtTest import QTest
        tab = self.open_editor()
        document = tab.doc
        pages = tab._page_grid.pages
        point = pages.visualItemRect(pages.item(2)).center()
        QTest.mouseClick(pages.viewport(), Qt.LeftButton, pos=point)
        QTest.mouseDClick(pages.viewport(), Qt.LeftButton, pos=point)
        self.settle()
        self.assertFalse(tab.is_editor_overview())
        self.assertEqual(tab.page_index, 2)
        self.assertTrue(tab._edit_mode)
        self.assertIs(tab.doc, document)
        self.assertTrue(tab._perform_text_edit(lambda: tab.doc.add_text_box(2, (35, 365), "Kept edit")))
        tab._overview_button.click()
        self.assertTrue(tab.is_editor_overview())
        self.assertEqual(pages.currentRow(), 2)
        tab._detail_button.click()
        self.assertFalse(tab.is_editor_overview())
        self.assertIn("Kept edit", tab.doc._doc[2].get_text())
        tab.undo()
        self.assertNotIn("Kept edit", tab.doc._doc[2].get_text())

    def test_long_grid_renders_last_page_and_evicts_old_cards(self):
        tab = self.open_editor()
        self.render_grid(tab)
        grid = tab._page_grid
        self.assertTrue(grid.pages.item(0).data(256))
        grid.pages.scrollToBottom()
        self.settle()
        self.render_grid(tab)
        self.assertIn(44, grid.pages.visible_rows())
        self.assertTrue(grid.pages.item(44).data(256))
        self.assertTrue(grid.pages.item(0).icon().isNull())
        self.assertLess(len(grid._rendered_rows), 30)
        self.window.hide()
        self.assertFalse(grid._thumbnail_timer.isActive())

    def test_keyboard_edit_and_presentation_restore_controls(self):
        from PyQt5.QtCore import Qt
        from PyQt5.QtTest import QTest
        tab = self.open_editor()
        pages = tab._page_grid.pages
        pages.setCurrentRow(12)
        QTest.keyClick(pages, Qt.Key_Return)
        self.assertFalse(tab.is_editor_overview())
        self.assertEqual(tab.page_index, 12)
        tab._pages_act.trigger()
        self.assertTrue(tab.is_editor_overview())
        self.window.toggle_presentation()
        self.settle()
        self.assertFalse(tab.is_editor_overview())
        self.assertTrue(tab._workspace_header.isHidden())
        self.assertTrue(tab._interaction_toolbar.isHidden())
        self.window.toggle_presentation()
        self.settle()
        self.assertFalse(tab._workspace_header.isHidden())
        self.assertFalse(tab._interaction_toolbar.isHidden())
        tab._overview_button.click()
        self.assertTrue(tab.is_editor_overview())
        self.assertEqual(pages.currentRow(), 12)

    def test_reorder_failure_restores_document_and_history(self):
        tab = self.open_editor()
        def failure(_order):
            tab.doc._doc.delete_page(0)
            raise RuntimeError("test failed move")
        with patch.object(tab.doc, "reorder_pages", side_effect=failure), \
                patch("pdfeditor.document_tools.QMessageBox.warning"):
            self.assertFalse(tab._page_grid.move_pages([0], 3))
        self.assertEqual(tab.doc.page_count, 45)
        self.assertIn("Page 01", tab.doc._doc[0].get_text())
        self.assertEqual(tab._undo_stack, [])
        self.assertFalse(tab._dirty)

    def test_reader_prominent_button_and_embedded_behavior(self):
        reader = self.module.new_window(str(self.path), workspace_mode="reader")
        self.settle()
        reading = reader._tabs.currentWidget()
        button = reading._editor_mode_button
        self.assertEqual(button.text(), "Edit mode")
        self.assertTrue(button.property("accent"))
        self.assertGreaterEqual(button.height(), 40)
        self.assertTrue(reading._interaction_toolbar.isAncestorOf(button))
        self.assertIsNone(reading._workspace_header)
        button.click()
        self.settle()
        editor = next(window for window in self.module._app_windows if window.workspace_mode == "editor")
        self.assertTrue(editor._tabs.currentWidget().is_editor_overview())
        embedded = self.module.new_window(str(self.path))
        self.settle()
        tab = embedded._tabs.currentWidget()
        self.assertIsNone(tab._page_grid)
        self.assertIsNone(tab._workspace_header)
        with patch("pdfeditor.pages.PageOrganizerDialog") as dialog:
            tab.show_page_organizer()
        dialog.return_value.exec_.assert_called_once()


if __name__ == "__main__":
    unittest.main()

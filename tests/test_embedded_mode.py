import importlib.util
import os
import unittest
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


HAS_PYQT5 = importlib.util.find_spec("PyQt5") is not None


@unittest.skipUnless(HAS_PYQT5, "PyQt5가 설치된 환경에서 실행")
class EmbeddedModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        # Other localization tests intentionally switch the process-wide
        # catalog. Embedded-mode assertions use the international default.
        from pdfeditor.i18n import set_language
        set_language("en")

    @contextmanager
    def document_windows(self):
        import fitz
        from pdfeditor import app, settings

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "reader.pdf"
            with fitz.open() as pdf:
                page = pdf.new_page()
                page.insert_text((72, 72), "Read this sentence.")
                page.add_text_annot((100, 100), "Existing note")
                pdf.new_page()
                pdf.set_toc([[1, "Start", 1]])
                pdf.save(source)
            with patch.object(settings, "PATH", str(root / "settings.json")), \
                    patch.object(settings, "_OLD_PATH", str(root / "absent")), \
                    patch.object(app, "_app_windows", []):
                try:
                    yield app, source
                finally:
                    for window in list(app._app_windows):
                        for index in range(window._tabs.count()):
                            window._tabs.widget(index)._dirty = False
                        window.close()
                    for _ in range(4):
                        self.app.processEvents()

    def test_read_only_window_keeps_reading_and_blocks_all_edit_commands(self):
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QAction, QAbstractItemView

        with self.document_windows() as (module, source):
            window = module.new_window(read_only=True)
            tab = window.open_in_tab(str(source))
            for _ in range(4):
                self.app.processEvents()
            self.assertTrue(window.read_only)
            self.assertTrue(tab.read_only)
            self.assertTrue(tab.doc.read_only)
            self.assertFalse(window.updates_enabled)
            self.assertIsNone(window._update_service)
            self.assertIsNone(window._recovery_store)
            for action in (tab._save_act, tab._edit_act, tab._pages_act,
                           tab._undo_act, tab._redo_act, tab._rotate_cw_act):
                self.assertFalse(action.isVisible())
                self.assertFalse(action.isEnabled())
                action.trigger()
            for owner in (window, tab):
                for name in dir(type(owner)):
                    method = getattr(owner, name)
                    if callable(method) and getattr(method, "requires_editing", False):
                        with self.subTest(command=name):
                            self.assertFalse(method())
            tab.set_edit_mode(True)
            self.assertFalse(tab._edit_mode)
            self.assertFalse(tab._dirty)
            self.assertEqual(tab._undo_stack, [])
            self.assertIsNone(tab._ocr_worker)
            with self.assertRaises(PermissionError):
                tab.doc.rotate_page(0, 90)

            tree = tab.bookmarks
            self.assertEqual(tree.dragDropMode(), QAbstractItemView.NoDragDrop)
            self.assertFalse(tree.topLevelItem(0).flags() & Qt.ItemIsEditable)
            self.assertTrue(tab._print_act.isEnabled())
            self.assertTrue(tab._search_act.isEnabled())
            shortcuts = {action.shortcut().toString(): action
                         for action in tab.findChildren(QAction)}
            for shortcut in ("Ctrl+C", "Ctrl+A", "Ctrl+F", "Ctrl+P"):
                self.assertTrue(shortcuts[shortcut].isEnabled())
            tab.select_all()
            tab.copy_selection()
            self.assertIn("Read this sentence.", self.app.clipboard().text())
            tab.show_page(1)
            self.assertEqual(tab.page_index, 1)
            tab.set_zoom(1.25)
            self.assertEqual(tab.view.zoom, 1.25)
            note = tab.doc.annots(0)[0]
            with patch("pdfeditor.annots.QMessageBox.exec_"), patch(
                    "pdfeditor.annots.QInputDialog.getMultiLineText") as edit:
                tab.edit_annot(note)
                edit.assert_not_called()
            self.assertFalse(tab._dirty)

    def test_new_windows_inherit_policy_and_cannot_reuse_opposite_mode(self):
        with self.document_windows() as (module, source):
            editor = module.new_window()
            reader = module.new_window(read_only=True)
            self.assertIsNot(editor, reader)
            self.assertIs(module.new_window(read_only=False), editor)
            self.assertIs(module.new_window(read_only=True), reader)
            child = reader.new_window()
            self.assertIsNot(child, reader)
            self.assertTrue(child.read_only)
            self.assertFalse(child.updates_enabled)
            tab = editor.open_in_tab(str(source))
            for _ in range(4):
                self.app.processEvents()
            self.assertFalse(reader._adopt_tab(editor, tab, 0))
            self.assertEqual(editor._tabs.indexOf(tab), 0)
            self.assertEqual(reader._tabs.count(), 0)
            self.assertFalse(reader.open_snapshot_in_tab("missing.pdf", str(source)))

    def test_read_only_does_not_enable_self_updates_or_recovery(self):
        from pdfeditor.app import AppWindow
        with patch("pdfeditor.app.GitHubUpdateService") as updater:
            window = AppWindow(read_only=True)
            try:
                updater.assert_not_called()
                self.assertIsNone(window._recovery_store)
            finally:
                window.close()

    def test_annotation_mode_autosaves_and_restores_without_changing_pdf(self):
        from PyQt5.QtCore import QPointF
        from PyQt5.QtTest import QTest
        from PyQt5.QtWidgets import QAction
        from pdfeditor.core import Document

        with self.document_windows() as (module, source):
            original = source.read_bytes()
            window = module.new_window(read_only=True, annotations_enabled=True)
            tab = window.open_in_tab(str(source))
            for _ in range(4):
                self.app.processEvents()
            self.assertTrue(tab.annotations_enabled)
            self.assertTrue(tab._save_act.isEnabled())
            self.assertFalse(tab._edit_act.isVisible())
            self.assertFalse(tab._pages_act.isVisible())
            menu = [action.text() for action in tab.findChildren(QAction)]
            self.assertIn("Save PDF with annotations...", menu)
            tab._annotation_timer.setInterval(20)
            with patch("pdfeditor.annots.QInputDialog.getMultiLineText",
                       return_value=("New annotation", True)):
                tab._add_note_at(QPointF(80, 80))
            self.assertTrue(tab._dirty)
            self.assertTrue(tab._annotation_timer.isActive())
            self.assertTrue(tab._undo_act.isEnabled())
            QTest.qWait(60)
            self.assertFalse(tab._dirty)
            self.assertEqual(source.read_bytes(), original)
            tab.undo()
            self.assertEqual(len(tab.doc.annots(0)), 1)
            QTest.qWait(60)
            tab.redo()
            self.assertEqual(len(tab.doc.annots(0)), 2)
            # Closing immediately must flush the pending timer's changes.
            self.assertTrue(tab.maybe_save())
            self.assertFalse(tab._dirty)
            readback = Document(str(source), read_only=True, annotations_enabled=False)
            try:
                self.assertEqual(readback.annots(0)[-1]["text"], "New annotation")
            finally:
                readback.close()
            child = window.new_window()
            self.assertEqual(child.access_policy, window.access_policy)
            reader = module.new_window(read_only=True, annotations_enabled=False)
            manual = module.new_window(read_only=True, annotations_enabled=True,
                                       autosave_annotations=False)
            self.assertIsNot(reader, window)
            self.assertIsNot(manual, window)
            self.assertFalse(manual._adopt_tab(window, tab, 0))

    def test_annotation_autosave_off_requires_save_and_can_cancel_close(self):
        from PyQt5.QtCore import QPointF
        from PyQt5.QtWidgets import QMessageBox
        with self.document_windows() as (module, source):
            window = module.new_window(read_only=True, annotations_enabled=True,
                                       autosave_annotations=False)
            tab = window.open_in_tab(str(source))
            for _ in range(4):
                self.app.processEvents()
            with patch("pdfeditor.annots.QInputDialog.getMultiLineText",
                       return_value=("Manual annotation", True)):
                tab._add_note_at(QPointF(80, 80))
            self.assertFalse(tab._annotation_timer.isActive())
            sidecar = Path(str(source) + ".spdf-annotations.json")
            self.assertFalse(sidecar.exists())
            with patch("pdfeditor.annots.QMessageBox.exec_", return_value=QMessageBox.Cancel):
                self.assertFalse(tab.maybe_save())
            self.assertTrue(tab._dirty)
            self.assertTrue(tab.save())
            self.assertTrue(sidecar.exists())
            self.assertFalse(tab._dirty)

    def test_annotation_save_failure_keeps_pending_edits_and_cancelable_close(self):
        from PyQt5.QtCore import QPointF
        from PyQt5.QtWidgets import QMessageBox
        with self.document_windows() as (module, source):
            window = module.new_window(read_only=True, annotations_enabled=True)
            tab = window.open_in_tab(str(source))
            for _ in range(4):
                self.app.processEvents()
            with patch("pdfeditor.annots.QInputDialog.getMultiLineText",
                       return_value=("Do not lose this", True)):
                tab._add_note_at(QPointF(80, 80))
            with patch.object(tab.doc, "save_annotations", side_effect=OSError("disk full")):
                tab._autosave_annotations()
                self.assertTrue(tab._dirty)
                self.assertIn("could not be saved", tab.statusBar().currentMessage())
                with patch("pdfeditor.annots.QMessageBox.exec_", return_value=QMessageBox.Cancel):
                    self.assertFalse(tab.maybe_save())
                target = source.with_name("exported.pdf")
                with patch("pdfeditor.annotation_ui.QFileDialog.getSaveFileName",
                           return_value=(str(target), "PDF")):
                    self.assertTrue(tab.save_as_dialog())
                self.assertTrue(target.exists())
                self.assertEqual(tab.doc.path, str(source))
                self.assertTrue(tab._dirty)
            self.assertTrue(tab.save())

    def test_annotation_mode_can_edit_existing_note_and_delete_with_undo(self):
        with self.document_windows() as (module, source):
            window = module.new_window(read_only=True, annotations_enabled=True,
                                       autosave_annotations=False)
            tab = window.open_in_tab(str(source))
            for _ in range(4):
                self.app.processEvents()
            note = tab.doc.annots(0)[0]
            with patch("pdfeditor.annots.QInputDialog.getMultiLineText",
                       return_value=("Revised original note", True)):
                tab.edit_annot(note)
            self.assertEqual(tab.doc.annots(0)[0]["text"], "Revised original note")
            tab.delete_annot(tab.doc.annots(0)[0])
            self.assertEqual(tab.doc.annots(0), [])
            tab.undo()
            self.assertEqual(tab.doc.annots(0)[0]["text"], "Revised original note")
            tab.undo()
            self.assertEqual(tab.doc.annots(0)[0]["text"], "Existing note")

    def test_host_default_never_reuses_or_inherits_standalone_updater(self):
        with self.document_windows() as (module, source):
            with patch("pdfeditor.app.GitHubUpdateService"), patch(
                    "pdfeditor.app.settings.automatic_update_check_due", return_value=False):
                standalone = module.new_window(updates_enabled=True)
                embedded = module.new_window()
                self.assertIsNot(embedded, standalone)
                self.assertFalse(embedded.updates_enabled)
                self.assertIsNone(embedded._update_service)

    def test_internal_module_window_disables_all_update_entry_points(self):
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QAction, QStatusBar
        from pdfeditor.app import AppWindow

        with patch("pdfeditor.app.settings.ui_language", return_value="en"):
            window = AppWindow()
        menu_texts = [action.text() for action in window.findChildren(QAction)]

        self.assertFalse(window.updates_enabled)
        self.assertIsNone(window._update_service)
        self.assertIsNone(window._recovery_store)
        self.assertEqual(
            window.findChildren(
                QStatusBar, options=Qt.FindDirectChildrenOnly), [])
        self.assertFalse(window.check_for_updates(manual=True))
        self.assertNotIn("Check for Updates...", menu_texts)
        window.close()

    def test_standalone_window_keeps_update_feature(self):
        from PyQt5.QtWidgets import QAction
        from pdfeditor.app import AppWindow

        cleanup_flag = getattr(self.app, "_spdf_update_cleanup_started", None)
        if hasattr(self.app, "_spdf_update_cleanup_started"):
            del self.app._spdf_update_cleanup_started
        try:
            cleanup_patch = patch(
                "pdfeditor.app.GitHubUpdateService.cleanup_downloads")
            with patch("pdfeditor.app.settings.automatic_update_check_due",
                       return_value=False), patch(
                           "pdfeditor.app.settings.ui_language",
                           return_value="en"), cleanup_patch as cleanup:
                window = AppWindow(updates_enabled=True)
            cleanup.assert_called_once()
        finally:
            if cleanup_flag is None:
                if hasattr(self.app, "_spdf_update_cleanup_started"):
                    del self.app._spdf_update_cleanup_started
            else:
                self.app._spdf_update_cleanup_started = cleanup_flag
        menu_texts = [action.text() for action in window.findChildren(QAction)]

        self.assertTrue(window.updates_enabled)
        self.assertIsNotNone(window._update_service)
        self.assertIn("Check for Updates...", menu_texts)
        window.close()


if __name__ == "__main__":
    unittest.main()

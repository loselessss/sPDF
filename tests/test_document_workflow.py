import importlib.util
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch


HAS_QT = importlib.util.find_spec("PyQt5") is not None


def _write_recovery_then_exit(root):
    """Leave a real stale QLockFile behind, as a crashed process would."""
    from pdfeditor.recovery import RecoveryStore
    store = RecoveryStore(root)
    token = store.new_token()
    store.write(token, b"crash-copy", "source.pdf", {"page": 1})
    os._exit(0)


@unittest.skipUnless(HAS_QT, "PyQt5 is required")
class DocumentWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        # Every test closes its top-level window.  Keep the shared test
        # application alive between cases so the offscreen Windows backend
        # does not race QApplication shutdown with the next AppWindow setup.
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        import fitz
        from pdfeditor import settings
        from pdfeditor.app import AppWindow
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.settings_patch = patch.object(settings, "PATH", str(self.root / "settings.json"))
        self.settings_patch.start()
        self.old_patch = patch.object(settings, "_OLD_PATH", str(self.root / "absent.json"))
        self.old_patch.start()
        self.source = self.root / "source.pdf"
        raw = fitz.open()
        for i in range(4):
            page = raw.new_page(width=200, height=300)
            page.insert_text((40, 80), "Page %d" % i)
        raw.set_toc([[1, "Start", 1], [2, "Details", 2], [1, "End", 4]])
        raw.save(self.source)
        raw.close()
        self.window = AppWindow()
        self.window.show()
        self.tab = self.window.open_in_tab(str(self.source))
        self.events()

    def events(self):
        for _ in range(4):
            self.app.processEvents()

    def tearDown(self):
        for i in range(self.window._tabs.count()):
            self.window._tabs.widget(i)._dirty = False
        self.window.close()
        self.events()
        self.settings_patch.stop()
        self.old_patch.stop()
        self.temp.cleanup()

    def test_navigation_restores_page_zoom_and_scroll(self):
        tab = self.tab
        tab.set_zoom(5)
        self.events()
        bar = tab.view.verticalScrollBar()
        bar.setValue(round(bar.maximum() * 0.6))
        before = tab.capture_view_state()
        tab.show_page(2)
        tab.set_zoom(2)
        tab.navigate_history()
        self.events()
        self.assertEqual(tab.page_index, 0)
        self.assertEqual(tab.view.zoom, 5)
        self.assertAlmostEqual(tab.capture_view_state()["vertical"], before["vertical"], places=2)
        tab.navigate_history(False)
        self.events()
        self.assertEqual(tab.page_index, 2)
        self.assertEqual(tab.view.zoom, 2)

    def test_reopen_restores_reading_position(self):
        tab = self.tab
        tab.show_page(2)
        tab.set_zoom(2.5)
        tab.save_reading_position()
        self.window.close_tab(tab)
        self.events()
        self.tab = self.window.open_in_tab(str(self.source))
        self.events()
        self.assertEqual(self.tab.page_index, 2)
        self.assertEqual(self.tab.view.zoom, 2.5)
        self.assertFalse(self.tab._view_history.back)

    def test_bookmark_edit_undo_redo_preserves_hierarchy(self):
        tab = self.tab
        tab.rename_bookmark(1, "Renamed")
        self.assertEqual(tab.doc.bookmarks()[1][1], "Renamed")
        tab.undo()
        self.assertEqual(tab.doc.bookmarks()[1][1], "Details")
        tab.redo()
        self.assertEqual(tab.doc.bookmarks()[1][1], "Renamed")
        tab.reorder_bookmarks([(1, 2), (1, 0), (2, 1)])
        self.assertEqual([entry[1] for entry in tab.doc.bookmarks()],
                         ["End", "Start", "Renamed"])
        tab.apply_document_change(lambda: tab.doc.delete_bookmark(1))
        self.assertEqual(len(tab.doc.bookmarks()), 1)
        tab.undo()
        self.assertEqual(len(tab.doc.bookmarks()), 3)

    def test_inline_bookmark_rename_updates_pdf(self):
        self.tab.bookmarks.topLevelItem(0).setText(0, "Inline title")
        self.events()
        self.assertEqual(self.tab.doc.bookmarks()[0][1], "Inline title")

    def test_history_is_bounded_and_new_navigation_clears_forward(self):
        from pdfeditor.navigation import ViewHistory
        history = ViewHistory(limit=3)
        for page in range(6):
            history.record({"page": page})
        self.assertEqual(len(history.back), 3)
        self.assertEqual(history.move({"page": 6})["page"], 5)
        self.assertTrue(history.forward)
        history.record({"page": 5})
        self.assertFalse(history.forward)

    def test_crop_is_undoable_and_preserves_original_file(self):
        original = self.source.read_bytes()
        tab = self.tab
        self.assertTrue(tab.apply_document_change(
            lambda: tab.doc.crop_pages([0, 2], (0.1, 0.1, 0.9, 0.9))))
        self.assertEqual(tab.doc.page_size(0), (160, 240))
        self.assertEqual(tab.doc.page_size(1), (200, 300))
        tab.undo()
        self.assertEqual(tab.doc.page_size(0), (200, 300))
        tab.redo()
        self.assertEqual(tab.doc.page_size(0), (160, 240))
        self.assertEqual(self.source.read_bytes(), original)

    def test_crop_rotated_and_already_cropped_pages(self):
        import fitz
        doc = self.tab.doc
        for index, rotation in enumerate((0, 90, 180, 270)):
            doc._doc[index].set_cropbox(fitz.Rect(10, 20, 190, 280))
            doc._doc[index].set_rotation(rotation)
            w, h = doc.page_size(index)
            doc.crop_pages([index], (0.1, 0.2, 0.8, 0.9))
            new_w, new_h = doc.page_size(index)
            self.assertAlmostEqual(new_w, w * 0.7, places=3)
            self.assertAlmostEqual(new_h, h * 0.7, places=3)

    def test_crop_rejects_empty_or_out_of_range_page_selection(self):
        for pages in ([], [-1], [self.tab.doc.page_count]):
            with self.assertRaises(ValueError):
                self.tab.doc.crop_pages(pages, (0.1, 0.1, 0.9, 0.9))

    def test_crop_preview_selects_normalized_rectangle(self):
        from PyQt5.QtCore import QPoint, Qt
        from PyQt5.QtTest import QTest
        from pdfeditor.crop_dialog import CropDialog
        dialog = CropDialog(self.tab.doc, 0, self.window)
        dialog.show()
        self.events()
        preview = dialog.preview
        r = preview.image_rect()
        p1 = QPoint(round(r.x() + r.width() * 0.1), round(r.y() + r.height() * 0.2))
        p2 = QPoint(round(r.x() + r.width() * 0.9), round(r.y() + r.height() * 0.8))
        QTest.mousePress(preview, Qt.LeftButton, pos=p1)
        QTest.mouseRelease(preview, Qt.LeftButton, pos=p2)
        for actual, expected in zip(preview.fractions(), (0.1, 0.2, 0.9, 0.8)):
            self.assertAlmostEqual(actual, expected, places=2)
        dialog.close()

    def test_tab_recovery_clears_on_save_and_protects_recovered_original(self):
        from pdfeditor.recovery import RecoveryStore
        store = RecoveryStore(self.root / "recovery")
        tab = self.tab
        tab._recovery.store = store
        tab.apply_document_change(lambda: tab.doc.add_bookmark("New", 2))
        tab._recovery.checkpoint()
        tab._recovery.worker.join(5)
        self.assertEqual(len(list(store.session.glob("*.recovery"))), 1)
        self.assertTrue(tab.save())
        self.assertFalse(list(store.session.glob("*.recovery")))
        tab._recovered_unsaved = True
        with patch.object(tab, "save_as_dialog", return_value=False) as save_as:
            self.assertFalse(tab.save())
            save_as.assert_called_once()
        for lock in store._locks.values():
            lock.unlock()

    def test_recovery_dialog_restores_snapshot_without_touching_original(self):
        from PyQt5.QtWidgets import QDialog
        from pdfeditor.recovery import RecoveryStore
        from pdfeditor.recovery_ui import show_recovery_dialog
        original = self.source.read_bytes()
        self.tab.doc.add_bookmark("Recovered", 2)
        snapshot = self.tab.doc.snapshot()
        store = RecoveryStore(self.root / "recovery")
        token = store.new_token()
        store.write(token, snapshot, str(self.source), {"page": 2, "zoom": 1.5})
        store._locks[store.session].unlock()
        other = RecoveryStore(self.root / "recovery")
        self.window._recovery_store = other
        self.window.close_tab(self.tab)
        self.events()
        try:
            with patch.object(QDialog, "exec_", return_value=QDialog.Accepted):
                show_recovery_dialog(self.window)
            self.events()
            restored = self.window._tabs.currentWidget()
            self.assertTrue(restored._dirty)
            self.assertTrue(restored._recovered_unsaved)
            self.assertEqual(restored.page_index, 2)
            self.assertEqual(restored.doc.bookmarks()[-1][1], "Recovered")
            self.assertEqual(self.source.read_bytes(), original)
            self.assertEqual(other.available(), [])
        finally:
            for i in range(self.window._tabs.count()):
                tab = self.window._tabs.widget(i)
                tab._recovery.clear()
                tab._dirty = False
            for lock in other._locks.values():
                lock.unlock()

    def test_protected_pdf_is_not_written_as_plaintext_recovery(self):
        import fitz
        from pdfeditor.core import Document
        from pdfeditor.recovery import RecoveryStore
        path = self.root / "protected.pdf"
        raw = fitz.open(self.source)
        raw.save(path, encryption=fitz.PDF_ENCRYPT_AES_256,
                 owner_pw="owner", user_pw="reader", permissions=fitz.PDF_PERM_PRINT)
        raw.close()
        document = Document(str(path), "reader")
        self.tab.doc.close()
        self.tab.doc = document
        store = RecoveryStore(self.root / "recovery")
        self.tab._recovery.store = store
        try:
            self.tab.mark_dirty()
            self.tab._recovery.checkpoint()
            self.assertIsNone(self.tab._recovery.worker)
            self.assertFalse(list(store.session.glob("*.recovery")))
            with self.assertRaises(PermissionError):
                document.crop_pages([0], (0.1, 0.1, 0.9, 0.9))
        finally:
            for lock in store._locks.values():
                lock.unlock()


@unittest.skipUnless(HAS_QT, "PyQt5 is required")
class RecoveryStoreTests(unittest.TestCase):
    def setUp(self):
        from pdfeditor.recovery import RecoveryStore
        self.temp = tempfile.TemporaryDirectory()
        self.store = RecoveryStore(self.temp.name)
        self.stores = [self.store]

    def tearDown(self):
        for store in self.stores:
            for lock in store._locks.values():
                lock.unlock()
        self.temp.cleanup()

    def test_live_session_not_offered_but_crashed_session_can_be_restored(self):
        from pdfeditor.recovery import RecoveryStore
        token = self.store.new_token()
        self.store.write(token, b"pdf-data", "source.pdf", {"page": 3})
        other = RecoveryStore(self.temp.name)
        self.stores.append(other)
        self.assertEqual(other.available(), [])
        self.store._locks[self.store.session].unlock()  # simulate ended process
        entries = other.available()
        self.assertEqual(len(entries), 1)
        self.assertEqual(other.read(entries[0]), b"pdf-data")
        adopted = other.adopt(entries[0])
        self.assertEqual(other.available(), [])
        other.discard(adopted)
        self.assertFalse(Path(entries[0]["file"]).exists())

    def test_real_crashed_process_session_is_discovered(self):
        import multiprocessing
        process = multiprocessing.get_context("spawn").Process(
            target=_write_recovery_then_exit, args=(self.temp.name,))
        process.start()
        process.join(10)
        self.assertEqual(process.exitcode, 0)
        entries = self.store.available()
        self.assertEqual(len(entries), 1)
        self.assertEqual(self.store.read(entries[0]), b"crash-copy")

    def test_failed_write_preserves_previous_recovery_copy(self):
        token = self.store.new_token()
        self.store.write(token, b"old", "source.pdf", {})
        destination = self.store._active[token]
        original = destination.read_bytes()
        with patch("pdfeditor.recovery.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.store.write(token, b"new", "source.pdf", {})
        self.assertEqual(destination.read_bytes(), original)
        self.assertFalse(list(self.store.session.glob("*.tmp")))

    def test_close_during_background_write_cannot_resurrect_copy(self):
        token = self.store.new_token()
        started, resume = threading.Event(), threading.Event()

        def pause(_fd):
            started.set()
            resume.wait(5)

        with patch("pdfeditor.recovery.os.fsync", side_effect=pause):
            thread = threading.Thread(target=self.store.write,
                                      args=(token, b"data", "source.pdf", {}))
            thread.start()
            self.assertTrue(started.wait(5))
            self.store.discard(token)
            resume.set()
            thread.join(5)
        self.assertFalse(list(self.store.session.glob("*.recovery")))

    def test_path_outside_recovery_folder_is_rejected(self):
        with self.assertRaises(ValueError):
            self.store.read({"file": str(Path(self.temp.name) / "outside.pdf")})


if __name__ == "__main__":
    unittest.main()

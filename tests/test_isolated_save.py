import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import fitz

from pdfeditor.core import Document
from pdfeditor.document_snapshot import DocumentSnapshot, cleanup_snapshots, file_revision
from pdfeditor.save_transaction import destination_lock


class IsolatedSaveTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = str(Path(self.directory.name) / "source.pdf")
        with fitz.open() as pdf:
            pdf.new_page().insert_text((72, 72), "Original")
            pdf.save(self.path)
        self.original = Path(self.path).read_bytes()

    def document(self, **kwargs):
        document = Document(self.path, isolated=True, **kwargs)
        self.addCleanup(document.close)
        return document

    def test_stale_writer_cannot_overwrite_newer_save(self):
        first, second = self.document(), self.document()
        first.add_text_box(0, (72, 100), "First")
        second.add_text_box(0, (72, 120), "Second")
        first.save_as(self.path)
        saved = Path(self.path).read_bytes()
        with self.assertRaisesRegex(OSError, "another writer"):
            second.save_as(self.path)
        self.assertEqual(Path(self.path).read_bytes(), saved)
        self.assertIn("Second", second._doc[0].get_text())
        with fitz.open(self.path) as pdf:
            self.assertIn("First", pdf[0].get_text())
            self.assertNotIn("Second", pdf[0].get_text())

    @unittest.skipUnless(os.name == "nt", "Windows file sharing")
    def test_real_external_file_handle_blocks_replace_without_losing_edits(self):
        editor, reader = self.document(), self.document(read_only=True)
        editor.add_text_box(0, (72, 100), "Pending")
        with open(self.path, "rb") as external_handle:
            with self.assertRaises(PermissionError):
                editor.save_as(self.path)
            self.assertEqual(external_handle.read(), self.original)
        self.assertIn("Pending", editor._doc[0].get_text())
        self.assertNotIn("Pending", reader._doc[0].get_text())
        editor.save_as(self.path)
        self.assertTrue(reader.render(0, .2)[3])

    def test_backup_failure_preserves_original_previous_backup_and_edits(self):
        editor = self.document()
        backup = Path(self.path + ".bak")
        backup.write_bytes(b"previous backup")
        editor.add_text_box(0, (72, 100), "Pending")
        with patch("pdfeditor.save_transaction.shutil.copyfileobj", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                editor.save_as(self.path)
        self.assertEqual(Path(self.path).read_bytes(), self.original)
        self.assertEqual(backup.read_bytes(), b"previous backup")
        self.assertIn("Pending", editor._doc[0].get_text())

    def test_busy_writer_lock_fails_without_waiting(self):
        editor = self.document()
        with destination_lock(self.path):
            with self.assertRaises(OSError):
                editor.save_as(self.path)
        self.assertEqual(Path(self.path).read_bytes(), self.original)
        editor.save_as(self.path)

    def test_private_snapshot_preserves_encryption_and_cleans_up(self):
        protected = str(Path(self.directory.name) / "protected.pdf")
        with fitz.open(self.path) as pdf:
            pdf.save(protected, encryption=fitz.PDF_ENCRYPT_AES_256,
                     owner_pw="owner", user_pw="reader")
        doc = Document(protected, "owner", isolated=True)
        private = Path(doc._snapshot.path)
        with fitz.open(private) as pdf:
            self.assertTrue(pdf.needs_pass)
        doc.save_as(protected)
        with fitz.open(protected) as pdf:
            self.assertTrue(pdf.needs_pass)
        doc.close()
        self.assertFalse(private.exists())

    def test_failed_cleanup_is_retried_without_escaping_callback(self):
        copy = DocumentSnapshot(self.path)
        with patch.object(copy.directory, "cleanup", side_effect=PermissionError("busy")):
            copy.close()
        self.assertTrue(Path(copy.path).exists())
        cleanup_snapshots()
        self.assertFalse(Path(copy.path).exists())

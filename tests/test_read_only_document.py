import tempfile
import unittest
from pathlib import Path

import fitz

from pdfeditor.core import Document


class ReadOnlyDocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "source.pdf"
        with fitz.open() as pdf:
            pdf.new_page().insert_text((72, 72), "Read-only test")
            pdf.new_page()
            pdf.set_toc([[1, "Start", 1]])
            pdf.save(self.source)

    def test_reading_still_works(self):
        doc = Document(str(self.source), read_only=True)
        self.addCleanup(doc.close)
        self.assertTrue(doc.read_only)
        self.assertEqual(doc.page_count, 2)
        self.assertTrue(doc.words(0))
        self.assertTrue(doc.search(0, "test"))
        self.assertTrue(doc.render(0, 0.2)[3])
        self.assertEqual(doc.bookmarks(), [(1, "Start", 1)])
        snapshot = Document.from_snapshot(
            str(self.source), doc.snapshot(), read_only=True)
        self.addCleanup(snapshot.close)
        with self.assertRaises(PermissionError):
            snapshot.rotate_page(0, 90)

    def test_every_mutation_is_rejected_before_work_starts(self):
        original = self.source.read_bytes()
        doc = Document(str(self.source), read_only=True)
        self.addCleanup(doc.close)
        # Deliberately omit arguments: the access check must happen before
        # argument validation, PDF mutation, temporary files or output writes.
        commands = """
            add_bookmark rename_bookmark delete_bookmark reorder_bookmarks
            replace_bookmarks crop_pages add_watermark add_highlight add_note
            set_note_text delete_annot insert_ocr_text replace_span
            replace_scanned_text add_text_box rotate_page delete_page move_page
            reorder_pages delete_pages insert_pdf extract_pages restore save_as
            ensure_editable
        """.split()
        for name in commands:
            with self.subTest(command=name), self.assertRaises(PermissionError):
                getattr(doc, name)()
        self.assertFalse(doc._doc.is_dirty)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [self.source])

    def test_editing_is_on_by_default_and_when_explicitly_enabled(self):
        for options in ({}, {"read_only": False}):
            with self.subTest(options=options):
                doc = Document(str(self.source), **options)
                try:
                    self.assertFalse(doc.read_only)
                    doc.rotate_page(0, 90)
                    self.assertEqual(doc._doc[0].rotation, 90)
                    target = str(Path(self.temp.name) / "edited.pdf")
                    doc.save_as(target)
                    self.assertTrue(Path(target).is_file())
                finally:
                    doc.close()


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

import fitz

from pdfeditor.core import Document


def _make_pdf(path, labels):
    doc = fitz.open()
    try:
        for label in labels:
            page = doc.new_page()
            page.insert_text((72, 72), label, fontsize=18)
        doc.save(path)
    finally:
        doc.close()


def _page_texts(path):
    doc = fitz.open(path)
    try:
        return [page.get_text().strip() for page in doc]
    finally:
        doc.close()


class PdfPageOperationTests(unittest.TestCase):
    def test_snapshot_reopens_as_dirty_transfer_document_path(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.pdf"
            _make_pdf(source, ["before"])
            original = str(source)
            doc = Document(original)
            try:
                doc.rotate_page(0, 90)
                moved = Document.from_snapshot(original, doc.snapshot())
                try:
                    self.assertEqual(moved.path, original)
                    self.assertEqual(moved._doc[0].rotation, 90)
                finally:
                    moved.close()
            finally:
                doc.close()

    def test_insert_pdf_preserves_selected_file_order(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = root / "base.pdf"
            addition = root / "addition.pdf"
            _make_pdf(base, ["base-1", "base-2"])
            _make_pdf(addition, ["added-1", "added-2"])

            document = Document(str(base))
            try:
                count = document.insert_pdf(str(addition), at=1)
                self.assertEqual(count, 2)
                self.assertEqual(document.page_count, 4)
                merged = root / "merged.pdf"
                document.extract_pages(range(document.page_count), str(merged))
            finally:
                document.close()

            self.assertEqual(
                _page_texts(merged),
                ["base-1", "added-1", "added-2", "base-2"])

    def test_extract_pages_preserves_requested_order_and_cleans_temp_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.pdf"
            output = root / "split.pdf"
            _make_pdf(source, ["page-1", "page-2", "page-3"])

            document = Document(str(source))
            try:
                document.extract_pages([2, 0], str(output))
            finally:
                document.close()

            self.assertEqual(_page_texts(output), ["page-3", "page-1"])
            self.assertEqual(
                sorted(path.name for path in root.iterdir()),
                ["source.pdf", "split.pdf"])


if __name__ == "__main__":
    unittest.main()

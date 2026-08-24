import tempfile
import unittest
from pathlib import Path

import fitz

from pdfeditor.core import ANTIALIAS_LEVEL, Document, configure_antialiasing
from pdfeditor.compression_core import compress_pdf_bytes
from pdfeditor.pages import page_order_after_move


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
    def test_rendering_uses_highest_mupdf_antialiasing_level(self):
        class FakeTools:
            level = None

            def set_aa_level(self, level):
                self.level = level

        tools = FakeTools()
        configure_antialiasing(tools)
        self.assertEqual(ANTIALIAS_LEVEL, 8)
        self.assertEqual(tools.level, 8)

    def test_pdf_compatible_illustrator_file_opens_as_pdf(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.pdf"
            illustrator = Path(temp) / "drawing.ai"
            _make_pdf(source, ["Illustrator PDF data"])
            illustrator.write_bytes(source.read_bytes())
            document = Document(str(illustrator))
            try:
                self.assertEqual(document.page_count, 1)
                self.assertIn(
                    "Illustrator PDF data", document._doc[0].get_text())
            finally:
                document.close()

    def test_bookmarks_and_web_links_are_exposed_for_navigation(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "links.pdf"
            raw = fitz.open()
            try:
                raw.new_page()
                raw.new_page()
                page = raw[0]
                page.insert_text((72, 72), "OpenAI")
                page.insert_link({
                    "kind": fitz.LINK_URI,
                    "from": fitz.Rect(60, 50, 150, 85),
                    "uri": "https://openai.com/",
                })
                page.insert_link({
                    "kind": fitz.LINK_GOTO,
                    "from": fitz.Rect(60, 90, 150, 120),
                    "page": 1,
                    "to": fitz.Point(20, 30),
                })
                raw.set_toc([[1, "Introduction", 1]])
                raw.save(source)
            finally:
                raw.close()
            document = Document(str(source))
            try:
                self.assertEqual(
                    document.bookmarks(), [(1, "Introduction", 1)])
                link = document.link_at(0, 80, 65)
                self.assertEqual(link["kind"], "uri")
                self.assertEqual(link["uri"], "https://openai.com/")
                internal = document.link_at(0, 80, 100)
                self.assertEqual(internal["kind"], "goto")
                self.assertEqual(internal["page"], 1)
                self.assertIsNone(document.link_at(0, 300, 300))
            finally:
                document.close()

    def test_lossless_compression_writes_a_valid_pdf_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.pdf"
            output = Path(temp) / "compressed.pdf"
            _make_pdf(source, ["compression test"])
            result_size = compress_pdf_bytes(
                source.read_bytes(), str(output), "lossless")
            self.assertEqual(result_size, output.stat().st_size)
            self.assertEqual(_page_texts(output), ["compression test"])

    def test_unknown_compression_preset_is_rejected(self):
        with self.assertRaises(ValueError):
            compress_pdf_bytes(b"%PDF-1.7", "ignored.pdf", "unknown")

    def test_page_order_moves_single_page_between_pages(self):
        order, selected = page_order_after_move(5, [0], 4)
        self.assertEqual(order, [1, 2, 3, 0, 4])
        self.assertEqual(selected, [3])

    def test_page_order_moves_selected_pages_as_group(self):
        order, selected = page_order_after_move(6, [1, 3], 6)
        self.assertEqual(order, [0, 2, 4, 5, 1, 3])
        self.assertEqual(selected, [4, 5])

    def test_reorder_and_delete_pages(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.pdf"
            output = Path(temp) / "output.pdf"
            _make_pdf(source, ["one", "two", "three", "four"])
            document = Document(str(source))
            try:
                document.reorder_pages([2, 0, 3, 1])
                document.delete_pages([1, 3])
                document.extract_pages(range(document.page_count), str(output))
            finally:
                document.close()
            self.assertEqual(_page_texts(output), ["three", "four"])

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

import tempfile
import unittest
from pathlib import Path

import fitz

from pdfeditor.conversions import images_to_pdf, write_image_atomic
from pdfeditor.core import Document
from pdfeditor.outline_import import parse_outline_text


def _make_pdf(path, pages=2, width=144, height=72):
    document = fitz.open()
    try:
        for number in range(pages):
            page = document.new_page(width=width, height=height)
            page.insert_text((12, 30), "Page %d" % (number + 1))
        document.save(path)
    finally:
        document.close()


def _make_image(path, width, height, color):
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, width, height), False)
    pixmap.clear_with(color)
    pixmap.save(path)


class PdfToolTests(unittest.TestCase):
    def test_plain_text_outline_supports_page_first_title_first_and_nesting(self):
        entries = parse_outline_text(
            "1 | Introduction\n  Details | 2\n3 Results", 3)
        self.assertEqual(entries, [
            (1, "Introduction", 1),
            (2, "Details", 2),
            (1, "Results", 3),
        ])

    def test_plain_text_outline_rejects_bad_page_and_hierarchy(self):
        with self.assertRaises(ValueError):
            parse_outline_text("4 | Outside", 3)
        with self.assertRaises(ValueError):
            parse_outline_text("1 | Root\n    2 | Too deep", 3)

    def test_images_to_pdf_preserves_order_and_renders(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, second = root / "red.png", root / "green.png"
            output = root / "images.pdf"
            _make_image(first, 80, 40, 0xFF0000)
            _make_image(second, 40, 80, 0x00FF00)

            self.assertEqual(images_to_pdf([first, second], output), 2)
            converted = fitz.open(output)
            try:
                self.assertEqual(converted.page_count, 2)
                self.assertGreater(converted[0].rect.width, converted[0].rect.height)
                self.assertLess(converted[1].rect.width, converted[1].rect.height)
                self.assertGreater(converted[0].get_pixmap().width, 0)
            finally:
                converted.close()

    def test_pdf_to_png_and_jpeg_have_requested_resolution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.pdf"
            _make_pdf(source, pages=1)
            document = Document(str(source))
            try:
                png = document.page_image_bytes(0, "png", 144)
                jpeg = document.page_image_bytes(0, "jpeg", 72)
            finally:
                document.close()
            png_pixmap = fitz.Pixmap(png)
            jpeg_pixmap = fitz.Pixmap(jpeg)
            try:
                self.assertEqual((png_pixmap.width, png_pixmap.height),
                                 (288, 144))
                self.assertEqual((jpeg_pixmap.width, jpeg_pixmap.height),
                                 (144, 72))
            finally:
                del png_pixmap
                del jpeg_pixmap
            output = root / "page.png"
            write_image_atomic(png, output)
            self.assertEqual(output.read_bytes(), png)

    def test_watermark_and_outline_are_undo_snapshot_compatible(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.pdf"
            _make_pdf(source)
            document = Document(str(source))
            try:
                before = document.snapshot()
                document.replace_bookmarks([
                    (1, "Introduction", 1), (2, "Detail", 2)])
                document.add_watermark([0, 1], "DRAFT", 24, 0.3, -30)
                self.assertEqual(document.bookmarks()[1][:2], (2, "Detail"))
                self.assertIn("DRAFT", document._doc[0].get_text())
                rendered = document.render(0, 1)
                self.assertGreater(rendered[0] * rendered[1], 0)
                self.assertTrue(document._display_cache)
                document.invalidate_render(0)
                self.assertFalse(document._display_cache)
                document.restore(before)
                self.assertFalse(document.bookmarks())
                self.assertNotIn("DRAFT", document._doc[0].get_text())
            finally:
                document.close()


if __name__ == "__main__":
    unittest.main()

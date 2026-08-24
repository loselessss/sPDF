import unittest

from pdfeditor.filetypes import (
    is_illustrator_document, is_supported_document, suggested_pdf_path)


class DocumentFileTypeTests(unittest.TestCase):
    def test_pdf_and_illustrator_extensions_are_supported(self):
        self.assertTrue(is_supported_document("paper.pdf"))
        self.assertTrue(is_supported_document("drawing.AI"))
        self.assertFalse(is_supported_document("image.svg"))

    def test_illustrator_detection_is_case_insensitive(self):
        self.assertTrue(is_illustrator_document("drawing.AI"))
        self.assertFalse(is_illustrator_document("drawing.pdf"))

    def test_illustrator_save_destination_is_pdf(self):
        self.assertEqual(suggested_pdf_path("drawing.ai"), "drawing.pdf")
        self.assertEqual(suggested_pdf_path("drawing.AI"), "drawing.pdf")
        self.assertEqual(suggested_pdf_path("drawing"), "drawing.pdf")
        self.assertEqual(suggested_pdf_path("drawing.pdf"), "drawing.pdf")


if __name__ == "__main__":
    unittest.main()

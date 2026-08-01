"""Tests for the public text-selection transfer contract."""

import unittest

from pdfeditor.selection import payload_from_words


class SelectionPayloadTests(unittest.TestCase):
    def test_words_become_one_based_text_and_pdf_boxes(self):
        value = payload_from_words(
            [
                (20, 10, 30, 15, "world", 0, 0, 1),
                (1, 10, 10, 15, "hello", 0, 0, 0),
            ],
            pdf_page=3,
            document_id="paper-1",
            document_path="paper.pdf",
        )
        self.assertEqual(value.text, "hello world")
        self.assertEqual(value.pdf_page, 3)
        self.assertEqual(value.document_id, "paper-1")
        self.assertEqual(value.bounding_boxes[0], (1.0, 10.0, 10.0, 15.0))


if __name__ == "__main__":
    unittest.main()

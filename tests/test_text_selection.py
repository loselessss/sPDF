import importlib.util
import unittest


HAS_PYQT5 = importlib.util.find_spec("PyQt5") is not None


@unittest.skipUnless(HAS_PYQT5, "PyQt5가 설치된 환경에서 실행")
class TextFlowSelectionTests(unittest.TestCase):
    def setUp(self):
        from PyQt5.QtCore import QPointF

        self.QPointF = QPointF
        # x0, y0, x1, y1, text, block, line, word
        self.words = [
            (0, 0, 10, 10, "one", 0, 0, 0),
            (12, 0, 22, 10, "two", 0, 0, 1),
            (24, 0, 34, 10, "three", 0, 0, 2),
            (0, 12, 10, 22, "four", 0, 1, 0),
            (12, 12, 22, 22, "five", 0, 1, 1),
            (24, 12, 34, 22, "six", 0, 1, 2),
        ]

    def test_drag_selects_continuous_reading_flow_across_lines(self):
        from pdfeditor.textsel import words_in_text_flow

        selected = words_in_text_flow(
            self.words, self.QPointF(15, 5), self.QPointF(15, 17))

        self.assertEqual(
            [word[4] for word in selected],
            ["two", "three", "four", "five"])

    def test_reverse_drag_selects_the_same_text(self):
        from pdfeditor.textsel import words_in_text_flow

        selected = words_in_text_flow(
            self.words, self.QPointF(15, 17), self.QPointF(15, 5))

        self.assertEqual(
            [word[4] for word in selected],
            ["two", "three", "four", "five"])

    def test_drag_must_start_on_text(self):
        from pdfeditor.textsel import words_in_text_flow

        self.assertEqual(
            words_in_text_flow(
                self.words, self.QPointF(100, 100), self.QPointF(15, 5)),
            [])

    def test_copy_joins_visual_lines_but_keeps_paragraphs(self):
        from pdfeditor.textsel import words_to_text

        words = self.words + [
            (0, 30, 10, 40, "next", 1, 0, 0),
            (12, 30, 22, 40, "paragraph", 1, 0, 1),
        ]

        self.assertEqual(
            words_to_text(words),
            "one two three four five six\nnext paragraph")


if __name__ == "__main__":
    unittest.main()

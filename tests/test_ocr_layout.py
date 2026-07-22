import unittest

import numpy as np

from pdfeditor.ocr_subprocess import (
    _find_column_gutter, _merge_ocr_items, _recognize_tiled, _tile_starts,
)


def _document_image(two_columns):
    image = np.full((1200, 1800, 3), 255, dtype=np.uint8)
    for y in range(80, 1120, 36):
        if two_columns:
            image[y:y + 12, 100:800] = 0
            image[y:y + 12, 1000:1700] = 0
        else:
            image[y:y + 12, 100:1700] = 0
    return image


class _FakeEngine:
    def __init__(self):
        self.calls = []

    def recognize(self, image):
        self.calls.append(image.shape[:2])
        return [[10, 10, 80, 30, "테스트"]]


class OcrLayoutTests(unittest.TestCase):
    def test_detects_two_column_gutter(self):
        split = _find_column_gutter(
            _document_image(two_columns=True), min_width=400)
        self.assertIsNotNone(split)
        self.assertGreater(split, 800)
        self.assertLess(split, 1000)

    def test_does_not_split_single_column_lines(self):
        self.assertIsNone(_find_column_gutter(
            _document_image(two_columns=False), min_width=400))

    def test_tile_starts_cover_page_with_requested_overlap(self):
        starts = _tile_starts(5100, size=2200, overlap=200)
        self.assertEqual(starts[0], 0)
        self.assertEqual(starts[-1], 2900)
        for left, right in zip(starts, starts[1:]):
            self.assertLessEqual(right, left + 2000)

    def test_tiled_recognition_restores_vertical_offsets(self):
        image = np.full((5100, 1000, 3), 255, dtype=np.uint8)
        engine = _FakeEngine()
        items = _recognize_tiled(engine, image)
        starts = _tile_starts(5100)
        self.assertEqual(len(engine.calls), len(starts))
        self.assertEqual([round(item[1]) for item in items],
                         [start + 10 for start in starts])

    def test_two_columns_are_processed_left_before_right(self):
        engine = _FakeEngine()
        items = _recognize_tiled(engine, _document_image(two_columns=True))
        self.assertEqual(len(engine.calls), 2)
        self.assertLess(items[0][0], items[1][0])

    def test_overlapping_same_text_is_deduplicated(self):
        items = _merge_ocr_items([
            [10, 10, 100, 30, "같은 줄"],
            [12, 11, 105, 32, "같은  줄"],
            [10, 50, 100, 70, "다른 줄"],
        ])
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0][4], "같은  줄")


if __name__ == "__main__":
    unittest.main()

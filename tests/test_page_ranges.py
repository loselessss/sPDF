import unittest

from pdfeditor.page_ranges import page_group_label, parse_page_groups


class PageRangeTests(unittest.TestCase):
    def test_star_splits_every_page(self):
        self.assertEqual(parse_page_groups("*", 3), [[0], [1], [2]])

    def test_ranges_make_separate_output_groups(self):
        self.assertEqual(
            parse_page_groups("1-3; 4,6; 7-9", 9),
            [[0, 1, 2], [3, 5], [6, 7, 8]])

    def test_duplicate_page_is_kept_once_per_group(self):
        self.assertEqual(parse_page_groups("1-3,2", 3), [[0, 1, 2]])

    def test_invalid_or_out_of_bounds_ranges_are_rejected(self):
        for value in ("", "1;;2", "3-1", "0", "1-4", "one"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_page_groups(value, 3)

    def test_label_compacts_consecutive_pages(self):
        self.assertEqual(page_group_label([0, 1, 2, 4, 6, 7]), "p1-3_5_7-8")


if __name__ == "__main__":
    unittest.main()

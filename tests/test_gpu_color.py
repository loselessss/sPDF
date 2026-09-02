import unittest

import pymupdf

from pdfeditor.gpu_color import luminosity_lut, softmask_gray_samples


class GpuColorTests(unittest.TestCase):
    def test_lut_layout_matches_mupdf_gray_conversion(self):
        signature, edge, data = luminosity_lut()
        self.assertEqual(edge, 65)
        self.assertEqual(len(data), edge ** 3 * 4)
        self.assertEqual(len(signature), 3)
        for r, g, b in ((0, 0, 0), (64, 64, 64), (64, 0, 0),
                        (0, 64, 0), (0, 0, 64), (17, 31, 52)):
            rgb = bytes(round(v * 255 / (edge - 1)) for v in (r, g, b))
            source = pymupdf.Pixmap(pymupdf.csRGB, 1, 1, rgb, False)
            gray = softmask_gray_samples(source)[0]
            offset = ((r * edge + g) * edge + b) * 4
            self.assertEqual(data[offset:offset + 4], bytes((gray, gray, gray, 255)))
        self.assertIs(luminosity_lut()[2], data)

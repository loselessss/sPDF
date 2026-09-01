import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import fitz

from pdfeditor.core import Document


class GpuRasterSceneTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "gpu-scene.pdf"
        with fitz.open() as pdf:
            vector = pdf.new_page(width=300, height=240)
            shape = vector.new_shape()
            shape.draw_rect((20, 30, 150, 170))
            shape.draw_bezier((40, 50), (80, 10), (120, 210), (180, 90))
            shape.finish(color=(1, 0, 0), fill=(0, 0.5, 1), width=2)
            shape.commit()
            text = pdf.new_page(width=300, height=240)
            text.insert_text((30, 60), "GPU text", color=(0.2, 0.4, 0.8))
            image = pdf.new_page(width=300, height=240)
            pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 2, 2), 0)
            pixmap.clear_with(0x4080c0)
            image.insert_image((20, 20, 120, 120), pixmap=pixmap)
            pdf.save(self.path)
        self.document = Document(str(self.path), read_only=True)

    def tearDown(self):
        self.document.close()
        self.directory.cleanup()

    def test_simple_vector_page_becomes_direct2d_commands(self):
        scene = self.document.gpu_vector_page(0)
        self.assertTrue(scene.supported, scene.reason)
        self.assertEqual(len(scene.paths), 1)
        path = scene.paths[0]
        self.assertEqual(path.fill_argb, 0xff0080ff)
        self.assertEqual(path.stroke_argb, 0xffff0000)
        self.assertEqual(path.stroke_width, 2)
        kinds = [command[0] for command in path.commands]
        self.assertIn("move", kinds)
        self.assertIn("line", kinds)
        self.assertIn("cubic", kinds)
        self.assertIn("close", kinds)

    def test_text_page_uses_exact_glyph_outlines(self):
        scene = self.document.gpu_vector_page(1)
        self.assertTrue(scene.supported, scene.reason)
        self.assertEqual(len(scene.paths), 7)
        self.assertTrue(all(path.fill_argb == 0xff3366cc
                            for path in scene.paths))
        self.assertTrue(all(path.transform is not None for path in scene.paths))
        kinds = {command[0] for path in scene.paths
                 for command in path.commands}
        self.assertIn("move", kinds)
        self.assertIn("cubic", kinds)
        self.assertIn("close", kinds)

    def test_image_page_uses_decoded_bgra_bitmap_and_pdf_transform(self):
        from pdfeditor.gpu_raster import VectorImage

        scene = self.document.gpu_vector_page(2)
        self.assertTrue(scene.supported, scene.reason)
        self.assertEqual(len(scene.paths), 0)
        self.assertEqual(len(scene.drawables), 1)
        image = scene.drawables[0]
        self.assertIsInstance(image, VectorImage)
        self.assertEqual((image.width, image.height, image.stride), (2, 2, 8))
        self.assertEqual(image.pixels[:4], bytes((0xc0, 0xc0, 0xc0, 0xff)))
        self.assertEqual(image.transform, (100.0, 0.0, 0.0, 100.0, 20.0, 20.0))
        self.assertEqual(image.opacity, 1.0)

    def test_scene_is_cached_and_invalidated_with_render_data(self):
        first = self.document.gpu_vector_page(0)
        self.assertIs(first, self.document.gpu_vector_page(0))
        self.document.invalidate_render(0)
        self.assertIsNot(first, self.document.gpu_vector_page(0))

    def test_oversized_image_scene_uses_complete_cpu_fallback(self):
        self.document.invalidate_render(2)
        with patch("pdfeditor.gpu_raster.MAX_GPU_IMAGE_BYTES", 1):
            scene = self.document.gpu_vector_page(2)
        self.assertFalse(scene.supported)
        self.assertIn("GPU scene limit", scene.reason)


if __name__ == "__main__":
    unittest.main()

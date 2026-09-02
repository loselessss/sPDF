import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import fitz

from pdfeditor.core import Document


def image_mask_pdf_bytes():
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 240] "
        b"/Resources << /XObject << /Im1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length 44 >>\nstream\n"
        b"q 0 0 1 rg 100 0 0 100 20 20 cm /Im1 Do Q\nendstream",
        b"<< /Type /XObject /Subtype /Image /Width 8 /Height 8 "
        b"/ImageMask true /BitsPerComponent 1 /Decode [0 1] /Length 8 >>\n"
        b"stream\n\xf0\x90\x90\xf0\x90\x90\x90\x00\nendstream",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode())
        data.extend(obj)
        data.extend(b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    data.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode())
    return bytes(data)


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
            clipped = pdf.new_page(width=300, height=240)
            clipped.insert_text((30, 90), "CLIPPED TEXT", fontsize=24)
            xref = clipped.get_contents()[0]
            stream = pdf.xref_stream(xref)
            pdf.update_stream(
                xref, b"q 40 130 100 50 re W n\n" + stream + b"\nQ")
            nested = pdf.new_page(width=300, height=240)
            nested.insert_text((30, 90), "NESTED CLIP", fontsize=24)
            xref = nested.get_contents()[0]
            stream = pdf.xref_stream(xref)
            pdf.update_stream(
                xref,
                b"q 20 120 200 100 re W n q 40 130 100 50 re W n\n" +
                stream + b"\nQ Q")
            with fitz.open(stream=image_mask_pdf_bytes(), filetype="pdf") as mask:
                pdf.insert_pdf(mask)
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

    def test_path_clip_is_recorded_in_display_order(self):
        from pdfeditor.gpu_raster import ClipPop, ClipPush, VectorPath

        scene = self.document.gpu_vector_page(3)
        self.assertTrue(scene.supported, scene.reason)
        self.assertIsInstance(scene.drawables[0], ClipPush)
        self.assertTrue(all(isinstance(item, VectorPath)
                            for item in scene.drawables[1:-1]))
        self.assertIsInstance(scene.drawables[-1], ClipPop)
        clip = scene.drawables[0]
        self.assertEqual(clip.transform, (1.0, 0.0, 0.0, -1.0, 0.0, 240.0))
        self.assertIn("close", [command[0] for command in clip.commands])

    def test_nested_path_clips_are_balanced(self):
        from pdfeditor.gpu_raster import ClipPop, ClipPush

        scene = self.document.gpu_vector_page(4)
        self.assertTrue(scene.supported, scene.reason)
        self.assertEqual(sum(isinstance(item, ClipPush)
                             for item in scene.drawables), 2)
        self.assertEqual(sum(isinstance(item, ClipPop)
                             for item in scene.drawables), 2)
        self.assertIsInstance(scene.drawables[0], ClipPush)
        self.assertIsInstance(scene.drawables[1], ClipPush)
        self.assertIsInstance(scene.drawables[-2], ClipPop)
        self.assertIsInstance(scene.drawables[-1], ClipPop)

    def test_colored_image_mask_becomes_premultiplied_gpu_bitmap(self):
        from pdfeditor.gpu_raster import VectorImage

        scene = self.document.gpu_vector_page(5)
        self.assertTrue(scene.supported, scene.reason)
        self.assertEqual(len(scene.drawables), 1)
        image = scene.drawables[0]
        self.assertIsInstance(image, VectorImage)
        self.assertEqual((image.width, image.height, image.stride), (8, 8, 32))
        self.assertEqual(image.transform,
                         (100.0, 0.0, 0.0, 100.0, 20.0, 120.0))
        self.assertEqual(image.pixels[:4], bytes((0, 0, 0, 0)))
        self.assertEqual(image.pixels[4 * 4:4 * 5], bytes((255, 0, 0, 255)))

    def test_oversized_image_scene_uses_complete_cpu_fallback(self):
        self.document.invalidate_render(2)
        with patch("pdfeditor.gpu_raster.MAX_GPU_IMAGE_BYTES", 1):
            scene = self.document.gpu_vector_page(2)
        self.assertFalse(scene.supported)
        self.assertIn("GPU scene limit", scene.reason)


if __name__ == "__main__":
    unittest.main()

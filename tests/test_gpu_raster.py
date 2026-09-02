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


def linear_gradient_pdf_bytes():
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 240] "
        b"/Resources << /Shading << /Sh1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length 38 >>\nstream\n"
        b"q 20 20 260 200 re W n /Sh1 sh Q\nendstream",
        b"<< /ShadingType 2 /ColorSpace /DeviceRGB /Coords [20 20 280 20] "
        b"/Function << /FunctionType 2 /Domain [0 1] /C0 [1 0 0] "
        b"/C1 [0 0 1] /N 1 >> /Extend [true true] >>",
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


def isolated_group_pdf_bytes():
    page_content = b"q /GS1 gs /Fm1 Do Q\n"
    form_content = (
        b"1 0 0 rg 20 20 180 140 re f "
        b"0 0 1 rg 100 80 180 140 re f\n")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 240] "
        b"/Resources << /XObject << /Fm1 5 0 R >> "
        b"/ExtGState << /GS1 6 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(page_content)} >>\nstream\n".encode() +
        page_content + b"endstream",
        b"<< /Type /XObject /Subtype /Form /BBox [0 0 300 240] "
        b"/Resources << >> /Group << /S /Transparency /I true "
        b"/CS /DeviceRGB >> /Length " + str(len(form_content)).encode() +
        b" >>\nstream\n" + form_content + b"endstream",
        b"<< /Type /ExtGState /ca 0.5 /CA 0.5 >>",
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


def soft_mask_pdf_bytes():
    page_content = b"q /GS1 gs 1 0 0 rg 20 20 260 200 re f Q\n"
    mask_content = b"0.5 g 50 50 200 140 re f\n"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 240] "
        b"/Resources << /ExtGState << /GS1 6 0 R >> >> "
        b"/Contents 4 0 R >>",
        f"<< /Length {len(page_content)} >>\nstream\n".encode() +
        page_content + b"endstream",
        b"<< /Type /XObject /Subtype /Form /BBox [0 0 300 240] "
        b"/Resources << >> /Group << /S /Transparency /I true "
        b"/CS /DeviceGray >> /Length " + str(len(mask_content)).encode() +
        b" >>\nstream\n" + mask_content + b"endstream",
        b"<< /Type /ExtGState /SMask << /S /Luminosity /G 5 0 R "
        b"/BC [0] >> >>",
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
            text_clip = pdf.new_page(width=300, height=240)
            text_clip.insert_text((30, 90), "MASK", fontsize=48)
            xref = text_clip.get_contents()[0]
            stream = pdf.xref_stream(xref)
            stream = stream.replace(b"BT", b"BT\n7 Tr", 1)
            head, tail = stream.rsplit(b"Q", 1)
            pdf.update_stream(
                xref,
                head + b"0 0 1 rg 0 0 300 240 re f\nQ" + tail)
            with fitz.open(
                    stream=linear_gradient_pdf_bytes(),
                    filetype="pdf") as gradient:
                pdf.insert_pdf(gradient)
            with fitz.open(
                    stream=isolated_group_pdf_bytes(),
                    filetype="pdf") as group:
                pdf.insert_pdf(group)
            with fitz.open(
                    stream=soft_mask_pdf_bytes(),
                    filetype="pdf") as masked:
                pdf.insert_pdf(masked)
            stroked = pdf.new_page(width=300, height=240)
            stroked.insert_text((20, 20), "stroke source")
            pdf.update_stream(
                stroked.get_contents()[0],
                b"q 4 w 1 J 2 j [6 3] 2 d 1 0 0 RG "
                b"20 40 m 140 40 l 180 120 l S Q\n")
            stroked_text = pdf.new_page(width=300, height=240)
            stroked_text.insert_text(
                (30, 90), "OUTLINE", fontsize=36, render_mode=1,
                color=(0.8, 0.1, 0.1), border_width=1)
            clipped_stroke_text = pdf.new_page(width=300, height=240)
            clipped_stroke_text.insert_text(
                (30, 90), "CLIP", fontsize=42, render_mode=5,
                color=(0.1, 0.1, 0.8), border_width=1)
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

    def test_complex_stroke_style_stays_on_direct2d_path(self):
        scene = self.document.gpu_vector_page(10)
        self.assertTrue(scene.supported, scene.reason)
        self.assertIn("stroke-style", scene.features)
        path = scene.paths[0]
        self.assertEqual(path.stroke_width, 4)
        self.assertEqual(path.stroke_style[:4], (1, 1, 1, 2))
        self.assertEqual(path.stroke_style[4], 10)
        self.assertAlmostEqual(path.stroke_style[5], 0.5)
        self.assertEqual(path.stroke_style[6], (1.5, 0.75))

    def test_stroked_text_uses_page_space_gpu_outlines(self):
        scene = self.document.gpu_vector_page(11)
        self.assertTrue(scene.supported, scene.reason)
        self.assertIn("stroked-text", scene.features)
        self.assertTrue(scene.paths)
        self.assertTrue(all(path.stroke_argb is not None
                            for path in scene.paths))
        self.assertTrue(all(path.transform is None for path in scene.paths))

    def test_stroke_and_clip_text_mode_stays_on_gpu_path(self):
        from pdfeditor.gpu_raster import ClipPop, ClipPush

        scene = self.document.gpu_vector_page(12)
        self.assertTrue(scene.supported, scene.reason)
        self.assertIn("stroked-text", scene.features)
        self.assertIn("text-clip", scene.features)
        self.assertTrue(any(isinstance(item, ClipPush)
                            for item in scene.drawables))
        self.assertIsInstance(scene.drawables[-1], ClipPop)

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

    def test_text_clip_uses_combined_exact_glyph_outlines(self):
        from pdfeditor.gpu_raster import ClipPop, ClipPush, VectorPath

        scene = self.document.gpu_vector_page(6)
        self.assertTrue(scene.supported, scene.reason)
        self.assertIsInstance(scene.drawables[0], ClipPush)
        self.assertIsNone(scene.drawables[0].transform)
        self.assertTrue(any(command[0] == "cubic"
                            for command in scene.drawables[0].commands))
        self.assertTrue(any(isinstance(item, VectorPath)
                            for item in scene.drawables[1:-1]))
        self.assertIsInstance(scene.drawables[-1], ClipPop)

    def test_linear_gradient_keeps_gpu_scene_with_bounded_bitmap(self):
        from pdfeditor.gpu_raster import (ClipPop, ClipPush,
                                          SHADE_RASTER_SCALE, VectorImage)

        scene = self.document.gpu_vector_page(7)
        self.assertTrue(scene.supported, scene.reason)
        self.assertIn("shading", scene.features)
        self.assertIn("vector-clip", scene.features)
        self.assertIsInstance(scene.drawables[0], ClipPush)
        image = scene.drawables[1]
        self.assertIsInstance(image, VectorImage)
        self.assertEqual(
            (image.width, image.height),
            (round(300 * SHADE_RASTER_SCALE),
             round(240 * SHADE_RASTER_SCALE)))
        self.assertEqual(image.transform, (300.0, 0.0, 0.0, 240.0, 0.0, 0.0))
        self.assertEqual(image.pixels[:4], bytes((0, 0, 255, 255)))
        self.assertEqual(image.pixels[-4:], bytes((255, 0, 0, 255)))
        self.assertIsInstance(scene.drawables[-1], ClipPop)

    def test_oversized_gradient_scene_uses_complete_cpu_fallback(self):
        self.document.invalidate_render(7)
        with patch("pdfeditor.gpu_raster.MAX_GPU_IMAGE_BYTES", 1):
            scene = self.document.gpu_vector_page(7)
        self.assertFalse(scene.supported)
        self.assertIn("shading data exceeds GPU scene limit", scene.reason)

    def test_isolated_normal_transparency_group_uses_opacity_layer(self):
        from pdfeditor.gpu_raster import (ClipPop, ClipPush, GroupPop,
                                          GroupPush, VectorPath)

        scene = self.document.gpu_vector_page(8)
        self.assertTrue(scene.supported, scene.reason)
        self.assertIn("transparency-group", scene.features)
        self.assertIsInstance(scene.drawables[0], GroupPush)
        self.assertAlmostEqual(scene.drawables[0].opacity, 1.0)
        self.assertIsInstance(scene.drawables[1], GroupPush)
        self.assertAlmostEqual(scene.drawables[1].opacity, 0.5)
        self.assertIsInstance(scene.drawables[2], ClipPush)
        paths = [item for item in scene.drawables
                 if isinstance(item, VectorPath)]
        self.assertEqual(len(paths), 2)
        self.assertTrue(all((item.fill_argb >> 24) == 255 for item in paths))
        self.assertIsInstance(scene.drawables[-3], ClipPop)
        self.assertIsInstance(scene.drawables[-2], GroupPop)
        self.assertIsInstance(scene.drawables[-1], GroupPop)

    def test_luminosity_soft_mask_stays_in_gpu_scene(self):
        from pdfeditor.gpu_raster import (ClipPop, GroupPop, GroupPush,
                                          MaskBegin, MaskEnd, VectorPath)

        scene = self.document.gpu_vector_page(9)
        self.assertTrue(scene.supported, scene.reason)
        self.assertIn("soft-mask", scene.features)
        self.assertIsInstance(scene.drawables[0], MaskBegin)
        self.assertTrue(scene.drawables[0].luminosity)
        self.assertEqual(scene.drawables[0].area, (20.0, 20.0, 280.0, 220.0))
        self.assertIsInstance(scene.drawables[1], GroupPush)
        self.assertTrue(any(isinstance(item, VectorPath)
                            for item in scene.drawables[2:]))
        mask_end = next(index for index, item in enumerate(scene.drawables)
                        if isinstance(item, MaskEnd))
        self.assertIsInstance(scene.drawables[mask_end - 1], GroupPop)
        self.assertIsInstance(scene.drawables[-1], ClipPop)

    def test_oversized_image_scene_uses_complete_cpu_fallback(self):
        self.document.invalidate_render(2)
        with patch("pdfeditor.gpu_raster.MAX_GPU_IMAGE_BYTES", 1):
            scene = self.document.gpu_vector_page(2)
        self.assertFalse(scene.supported)
        self.assertIn("GPU scene limit", scene.reason)


if __name__ == "__main__":
    unittest.main()

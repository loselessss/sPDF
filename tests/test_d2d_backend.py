import ctypes
import math
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from pdfeditor.d2d_backend import (ABI_VERSION, D2DSurface, _NativeInfo,
                                  probe_d2d_backend)


class D2DBackendTests(unittest.TestCase):
    def test_native_structure_has_stable_abi_layout(self):
        self.assertEqual(ABI_VERSION, 10)
        self.assertEqual(_NativeInfo.adapter_name.offset, 20)
        if os.name == "nt":
            self.assertEqual(ctypes.sizeof(_NativeInfo), 276)

    def test_missing_library_is_a_safe_fallback(self):
        with patch("pdfeditor.d2d_backend.os.name", "nt"):
            result = probe_d2d_backend(Path("missing-spdf-renderer.dll"))
        self.assertFalse(result.available)
        self.assertEqual(result.reason, "native renderer is not built")

    @unittest.skipUnless(os.name == "nt", "Direct2D is Windows-only")
    def test_built_renderer_creates_d2d_and_directwrite_devices(self):
        library = Path(__file__).resolve().parents[1] / "native" / "bin" / \
            "spdf_d2d_renderer.dll"
        if not library.is_file():
            self.skipTest("native renderer is not built")
        result = probe_d2d_backend(library)
        self.assertTrue(result.available, result)
        self.assertIn(result.driver, ("hardware", "warp"))
        self.assertGreaterEqual(result.feature_level, 0xA000)
        self.assertTrue(result.adapter_name)

    @unittest.skipUnless(os.name == "nt", "Direct2D is Windows-only")
    def test_built_renderer_presents_and_resizes_hidden_hwnd(self):
        library = Path(__file__).resolve().parents[1] / "native" / "bin" / \
            "spdf_d2d_renderer.dll"
        if not library.is_file():
            self.skipTest("native renderer is not built")
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.CreateWindowExW.argtypes = [
            ctypes.c_uint32, ctypes.c_wchar_p, ctypes.c_wchar_p,
            ctypes.c_uint32, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_void_p]
        user32.CreateWindowExW.restype = ctypes.c_void_p
        user32.DestroyWindow.argtypes = [ctypes.c_void_p]
        user32.DestroyWindow.restype = ctypes.c_int
        hwnd = user32.CreateWindowExW(
            0, "STATIC", "sPDF D2D test", 0, 0, 0, 64, 64,
            None, None, None, None)
        self.assertTrue(hwnd, ctypes.get_last_error())
        try:
            with D2DSurface(hwnd, 64, 64, path=library) as surface:
                surface.clear(0xff1a73e8)
                pixels = bytes((
                    0x00, 0x00, 0xff, 0xff, 0x00, 0xff, 0x00, 0xff,
                    0xff, 0x00, 0x00, 0xff, 0xff, 0xff, 0xff, 0xff))
                bitmap = surface.create_bitmap_bgra(pixels, 2, 2)
                path = surface.create_path([
                    ("move", 6, 6), ("line", 58, 6),
                    ("line", 58, 58), ("line", 6, 58), ("close",)])
                group = surface.create_geometry_group([
                    (path, (0.5, 0, 0, 0.5, 4, 4)),
                    (path, (0.25, 0, 0, 0.25, 40, 40)),
                ])
                stroke_style = surface.create_stroke_style(
                    (1, 1, 1, 2, 10.0, 0.5, (1.5, 0.75)))
                stroked_path = surface.create_stroked_path(
                    path, 4.0, stroke_style)
                surface.begin_frame(0xff202020)
                surface.draw_bitmap(bitmap, 8, 8, 56, 56)
                surface.set_transform(1, 0, 0, 1, 0, 0)
                surface.fill_rect(4, 4, 20, 12, 0x600078d7)
                surface.stroke_rect(2, 2, 62, 62, 0xff00a05a, 1.0)
                surface.fill_path(path, 0x600078d7)
                surface.stroke_path(path, 0xff00a05a, 2.0)
                surface.stroke_path(path, 0xffff8000, 4.0, stroke_style)
                surface.push_clip_path(path)
                surface.push_clip_path(stroked_path)
                surface.push_clip_path(group)
                surface.push_opacity_layer(0.65)
                surface.fill_path(group, 0x800000ff)
                surface.pop_layer()
                surface.pop_clip()
                surface.pop_clip()
                surface.pop_clip()
                surface.set_transform(1, 0, 0, 1, 0, 0)
                surface.begin_mask((0, 0, 64, 64), True, 0xff000000)
                surface.fill_rect(8, 8, 56, 56, 0xffffffff)
                surface.end_mask()
                surface.fill_rect(0, 0, 64, 64, 0xffff0000)
                surface.pop_clip()
                surface.end_frame()
                # Verify all supported PDF blend modes in premultiplied pixels,
                # including a translucent backdrop and separate group opacity.
                def blend_value(mode, backdrop, source):
                    if mode == 1:
                        return backdrop * source
                    if mode == 2:
                        return backdrop + source - backdrop * source
                    if mode == 3:
                        return (2 * backdrop * source if backdrop <= .5 else
                                1 - 2 * (1 - backdrop) * (1 - source))
                    if mode == 4:
                        return min(backdrop, source)
                    if mode == 5:
                        return max(backdrop, source)
                    if mode == 6:
                        return min(1, backdrop / (1 - source))
                    if mode == 7:
                        return 1 - min(1, (1 - backdrop) / source)
                    if mode == 8:
                        return (2 * backdrop * source if source <= .5 else
                                1 - 2 * (1 - backdrop) * (1 - source))
                    if mode == 9:
                        if source <= .5:
                            return backdrop - (1 - 2 * source) * backdrop * (1 - backdrop)
                        curve = (((16 * backdrop - 12) * backdrop + 4) * backdrop
                                 if backdrop <= .25 else math.sqrt(backdrop))
                        return backdrop + (2 * source - 1) * (curve - backdrop)
                    if mode == 10:
                        return abs(backdrop - source)
                    return backdrop + source - 2 * backdrop * source

                for mode in range(1, 12):
                    with self.subTest(blend_mode=mode):
                        surface.begin_frame(0xffffffff)
                        surface.begin_composite_group(0, 1)
                        surface.fill_rect(0, 0, 64, 64, 0x804080c0)
                        surface.begin_composite_group(mode, .6)
                        surface.fill_rect(8, 8, 56, 56, 0xc0c04080)
                        surface.end_composite_group()
                        pixels = surface.read_pixels_bgra(64, 64)
                        offset = (32 * 64 + 32) * 4
                        actual = tuple(pixels[offset:offset + 4])
                        ad, af = 128 / 255, 192 / 255 * .6
                        expected = []
                        for cb, cf in zip((192, 128, 64), (128, 64, 192)):
                            cb, cf = cb / 255, cf / 255
                            expected.append(round(255 * (
                                blend_value(mode, cb, cf) * ad * af +
                                cf * af * (1 - ad) + cb * ad * (1 - af))))
                        expected.append(round(255 * (af + ad * (1 - af))))
                        for value, target in zip(actual, expected):
                            self.assertLessEqual(abs(value - target), 4,
                                (mode, actual, expected))
                        # Outside the source, preserve the existing backdrop.
                        self.assertEqual(tuple(pixels[:4]), (96, 64, 32, 128))
                        surface.end_composite_group()
                        surface.end_frame()
                # End-to-end: parse actual PDF blend groups, replay the native
                # scene, and compare interior pixels with MuPDF's CPU render.
                import pymupdf
                from pdfeditor.gpu_raster import (
                    ClipPush, ClipPop, GroupPush, GroupPop, VectorPath,
                    vector_page_from_pymupdf)
                from tests.test_gpu_raster import isolated_group_pdf_bytes
                for name in ("Multiply", "Screen", "Overlay", "Darken", "Lighten",
                             "ColorDodge", "ColorBurn", "HardLight", "SoftLight",
                             "Difference", "Exclusion"):
                    with self.subTest(pdf_blend=name), pymupdf.open(
                            stream=isolated_group_pdf_bytes(name, background=True),
                            filetype="pdf") as pdf:
                        scene = vector_page_from_pymupdf(pdf[0])
                        self.assertTrue(scene.supported, scene.reason)
                        reference = pdf[0].get_pixmap(matrix=pymupdf.Matrix(.2, .2))
                        surface.begin_frame(0xffffffff)
                        frame_paths = []
                        for item in scene.drawables:
                            if isinstance(item, GroupPush):
                                surface.begin_composite_group(item.blend_mode, item.opacity)
                            elif isinstance(item, GroupPop):
                                surface.end_composite_group()
                            elif isinstance(item, ClipPop):
                                surface.pop_clip()
                            elif isinstance(item, (VectorPath, ClipPush)):
                                matrix = item.transform or (1, 0, 0, 1, 0, 0)
                                surface.set_transform(*(value * .2 for value in matrix))
                                geometry = surface.create_path(
                                    item.commands, even_odd=item.even_odd)
                                frame_paths.append(geometry)
                                if isinstance(item, ClipPush):
                                    surface.push_clip_path(geometry)
                                else:
                                    if item.fill_argb is not None:
                                        surface.fill_path(geometry, item.fill_argb)
                                    if item.stroke_argb is not None:
                                        surface.stroke_path(geometry, item.stroke_argb,
                                                            item.stroke_width)
                        actual = surface.read_pixels_bgra(64, 64)
                        for x, y in ((2, 2), (10, 20), (25, 25), (50, 10)):
                            offset = (y * 64 + x) * 4
                            native_rgb = tuple(reversed(actual[offset:offset + 3]))
                            reference_rgb = reference.pixel(x, y)
                            self.assertTrue(all(abs(a - b) <= 3 for a, b in
                                zip(native_rgb, reference_rgb)),
                                (name, (x, y), native_rgb, reference_rgb))
                        surface.end_frame()
                        for geometry in frame_paths:
                            geometry.close()
                surface.resize(96, 80, 120.0)
                surface.begin_frame(0xff4080c0)
                surface.begin_composite_group(9, .6)
                surface.fill_rect(8, 8, 56, 56, 0xc0c04080)
                surface.end_composite_group()
                actual = surface.read_pixels_bgra(96, 80)
                # 120 DPI: eight DIPs start at ten physical pixels.
                outside = (20 * 96 + 8) * 4
                self.assertEqual(tuple(actual[outside:outside + 4]), (192, 128, 64, 255))
                inside = (20 * 96 + 12) * 4
                af = 192 / 255 * .6
                expected = [round(255 * (blend_value(9, cb / 255, cf / 255) * af +
                    cb / 255 * (1 - af))) for cb, cf in
                    zip((192, 128, 64), (128, 64, 192))]
                self.assertTrue(all(abs(a - b) <= 3 for a, b in
                    zip(actual[inside:inside + 3], expected)))
                surface.end_frame()
                surface.begin_frame()
                surface.push_clip_path(path)
                with self.assertRaises(OSError):
                    surface.begin_composite_group(9, 1)
                surface.pop_clip()
                surface.end_frame()
                surface.begin_frame()
                surface.begin_composite_group(9, 1)
                with self.assertRaises(OSError):
                    surface.end_frame()  # Reject and unwind an incomplete capture.
                surface.clear(0xfff7f7f7)
                self.assertFalse(surface.closed)
                bitmap.close()
                self.assertTrue(bitmap.closed)
                path.close()
                self.assertTrue(path.closed)
                group.close()
                self.assertTrue(group.closed)
                stroke_style.close()
                self.assertTrue(stroke_style.closed)
                stroked_path.close()
                self.assertTrue(stroked_path.closed)
            self.assertTrue(surface.closed)
        finally:
            user32.DestroyWindow(hwnd)


if __name__ == "__main__":
    unittest.main()

import ctypes
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from pdfeditor.d2d_backend import (ABI_VERSION, D2DSurface, _NativeInfo,
                                  probe_d2d_backend)


class D2DBackendTests(unittest.TestCase):
    def test_native_structure_has_stable_abi_layout(self):
        self.assertEqual(ABI_VERSION, 9)
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
                surface.resize(96, 80, 120.0)
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

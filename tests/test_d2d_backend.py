import ctypes
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from pdfeditor.d2d_backend import (ABI_VERSION, D2DSurface, _NativeInfo,
                                  probe_d2d_backend)


class D2DBackendTests(unittest.TestCase):
    def test_native_structure_has_stable_abi_layout(self):
        self.assertEqual(ABI_VERSION, 1)
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
                surface.begin_frame(0xff202020)
                surface.draw_bitmap(bitmap, 8, 8, 56, 56)
                surface.end_frame()
                surface.resize(96, 80, 120.0)
                surface.clear(0xfff7f7f7)
                self.assertFalse(surface.closed)
                bitmap.close()
                self.assertTrue(bitmap.closed)
            self.assertTrue(surface.closed)
        finally:
            user32.DestroyWindow(hwnd)


if __name__ == "__main__":
    unittest.main()

"""Optional Windows Direct2D backend probe.

The native module is isolated from document and Qt state. Loading or probing it
must never be required for the existing CPU/OpenGL display path.
"""

import ctypes
from ctypes import (CDLL, POINTER, Structure, byref, c_float, c_int32,
                    c_size_t, c_uint32, c_ubyte, c_void_p, c_wchar)
from dataclasses import dataclass
import os
from pathlib import Path
import sys


ABI_VERSION = 1
DRIVER_NAMES = {0: "none", 1: "hardware", 2: "warp"}


class _NativeInfo(Structure):
    _fields_ = [
        ("struct_size", c_uint32),
        ("abi_version", c_uint32),
        ("driver", c_uint32),
        ("feature_level", c_uint32),
        ("last_hresult", c_int32),
        ("adapter_name", c_wchar * 128),
    ]


@dataclass(frozen=True)
class D2DBackendInfo:
    available: bool
    driver: str = "none"
    feature_level: int = 0
    adapter_name: str = ""
    hresult: int = 0
    reason: str = ""


def _library_path():
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "native" / "spdf_d2d_renderer.dll"
    return Path(__file__).resolve().parents[1] / "native" / "bin" / \
        "spdf_d2d_renderer.dll"


def _load_library(path):
    library = CDLL(str(path))
    library.spdf_d2d_abi_version.argtypes = []
    library.spdf_d2d_abi_version.restype = c_uint32
    if library.spdf_d2d_abi_version() != ABI_VERSION:
        raise OSError("native renderer ABI mismatch")
    library.spdf_d2d_probe.argtypes = [POINTER(_NativeInfo)]
    library.spdf_d2d_probe.restype = c_int32
    library.spdf_d2d_create_surface.argtypes = [
        c_size_t, c_uint32, c_uint32, c_float, POINTER(_NativeInfo),
        POINTER(c_void_p)]
    library.spdf_d2d_create_surface.restype = c_int32
    library.spdf_d2d_resize_surface.argtypes = [
        c_void_p, c_uint32, c_uint32, c_float]
    library.spdf_d2d_resize_surface.restype = c_int32
    library.spdf_d2d_clear_surface.argtypes = [c_void_p, c_uint32]
    library.spdf_d2d_clear_surface.restype = c_int32
    library.spdf_d2d_begin_frame.argtypes = [c_void_p, c_uint32]
    library.spdf_d2d_begin_frame.restype = c_int32
    library.spdf_d2d_create_bitmap.argtypes = [
        c_void_p, c_void_p, c_uint32, c_uint32, c_uint32, POINTER(c_void_p)]
    library.spdf_d2d_create_bitmap.restype = c_int32
    library.spdf_d2d_draw_bitmap.argtypes = [
        c_void_p, c_void_p, c_float, c_float, c_float, c_float, c_float]
    library.spdf_d2d_draw_bitmap.restype = c_int32
    library.spdf_d2d_end_frame.argtypes = [c_void_p]
    library.spdf_d2d_end_frame.restype = c_int32
    library.spdf_d2d_destroy_bitmap.argtypes = [c_void_p]
    library.spdf_d2d_destroy_bitmap.restype = None
    library.spdf_d2d_destroy_surface.argtypes = [c_void_p]
    library.spdf_d2d_destroy_surface.restype = None
    return library


def _check_hresult(result, operation):
    if result < 0:
        raise OSError("%s failed: HRESULT 0x%08X" %
                      (operation, result & 0xffffffff))


class D2DSurface:
    """Own one native swap chain without owning the target HWND."""

    def __init__(self, hwnd, width, height, dpi=96.0, path=None):
        library_path = Path(path) if path is not None else _library_path()
        self._library = _load_library(library_path)
        self._handle = c_void_p()
        self._bitmaps = set()
        native = _NativeInfo()
        native.struct_size = ctypes.sizeof(_NativeInfo)
        result = self._library.spdf_d2d_create_surface(
            int(hwnd), max(1, int(width)), max(1, int(height)), float(dpi),
            byref(native), byref(self._handle))
        _check_hresult(result, "Direct2D surface creation")
        self.info = D2DBackendInfo(
            True,
            DRIVER_NAMES.get(native.driver, "unknown"),
            native.feature_level,
            native.adapter_name,
            native.last_hresult)

    @property
    def closed(self):
        return not bool(self._handle)

    def resize(self, width, height, dpi=96.0):
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        result = self._library.spdf_d2d_resize_surface(
            self._handle, max(1, int(width)), max(1, int(height)), float(dpi))
        _check_hresult(result, "Direct2D surface resize")

    def clear(self, argb):
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        result = self._library.spdf_d2d_clear_surface(
            self._handle, int(argb) & 0xffffffff)
        _check_hresult(result, "Direct2D frame presentation")

    def create_bitmap_bgra(self, pixels, width, height, stride=None):
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        width, height = int(width), int(height)
        stride = int(stride if stride is not None else width * 4)
        data = bytes(pixels)
        if width <= 0 or height <= 0 or stride < width * 4 or \
                len(data) < stride * height:
            raise ValueError("invalid BGRA bitmap dimensions or stride")
        buffer = (c_ubyte * len(data)).from_buffer_copy(data)
        handle = c_void_p()
        result = self._library.spdf_d2d_create_bitmap(
            self._handle, buffer, width, height, stride, byref(handle))
        _check_hresult(result, "Direct2D bitmap creation")
        bitmap = D2DBitmap(self, handle, width, height)
        self._bitmaps.add(bitmap)
        return bitmap

    def begin_frame(self, argb=0xffe8e8e8):
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        _check_hresult(
            self._library.spdf_d2d_begin_frame(
                self._handle, int(argb) & 0xffffffff),
            "Direct2D frame start")

    def draw_bitmap(self, bitmap, left, top, right, bottom, opacity=1.0):
        if bitmap.closed or bitmap._surface is not self:
            raise ValueError("bitmap does not belong to this Direct2D surface")
        _check_hresult(
            self._library.spdf_d2d_draw_bitmap(
                self._handle, bitmap._handle, float(left), float(top),
                float(right), float(bottom), float(opacity)),
            "Direct2D bitmap draw")

    def end_frame(self):
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        _check_hresult(
            self._library.spdf_d2d_end_frame(self._handle),
            "Direct2D frame presentation")

    def close(self):
        if not self.closed:
            for bitmap in tuple(self._bitmaps):
                bitmap.close()
            self._library.spdf_d2d_destroy_surface(self._handle)
            self._handle = c_void_p()

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        self.close()

    def __del__(self):
        try:
            self.close()
        except (AttributeError, OSError):
            pass


class D2DBitmap:
    def __init__(self, surface, handle, width, height):
        self._surface = surface
        self._handle = handle
        self.width = width
        self.height = height

    @property
    def closed(self):
        return not bool(self._handle)

    def close(self):
        if not self.closed:
            self._surface._library.spdf_d2d_destroy_bitmap(self._handle)
            self._handle = c_void_p()
            self._surface._bitmaps.discard(self)

    def __del__(self):
        try:
            self.close()
        except (AttributeError, OSError):
            pass


def probe_d2d_backend(path=None):
    """Return capabilities without changing the active rendering backend."""
    if os.name != "nt":
        return D2DBackendInfo(False, reason="Direct2D is available only on Windows")
    library_path = Path(path) if path is not None else _library_path()
    if not library_path.is_file():
        return D2DBackendInfo(False, reason="native renderer is not built")
    try:
        library = _load_library(library_path)
        native = _NativeInfo()
        native.struct_size = ctypes.sizeof(_NativeInfo)
        result = library.spdf_d2d_probe(byref(native))
    except (OSError, AttributeError) as error:
        return D2DBackendInfo(False, reason=str(error))
    return D2DBackendInfo(
        result >= 0,
        DRIVER_NAMES.get(native.driver, "unknown"),
        native.feature_level,
        native.adapter_name,
        native.last_hresult,
        "" if result >= 0 else "Direct2D device initialization failed",
    )

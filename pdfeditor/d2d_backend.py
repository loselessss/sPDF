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


ABI_VERSION = 11
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


class _PathCommand(Structure):
    _fields_ = [("type", c_uint32), ("points", c_float * 6)]


class _Transform(Structure):
    _fields_ = [
        ("m11", c_float), ("m12", c_float),
        ("m21", c_float), ("m22", c_float),
        ("dx", c_float), ("dy", c_float),
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
    library.spdf_d2d_set_transform.argtypes = [
        c_void_p, c_float, c_float, c_float, c_float, c_float, c_float]
    library.spdf_d2d_set_transform.restype = c_int32
    library.spdf_d2d_create_bitmap.argtypes = [
        c_void_p, c_void_p, c_uint32, c_uint32, c_uint32, POINTER(c_void_p)]
    library.spdf_d2d_create_bitmap.restype = c_int32
    library.spdf_d2d_create_path.argtypes = [
        c_void_p, POINTER(_PathCommand), c_uint32, c_uint32, POINTER(c_void_p)]
    library.spdf_d2d_create_path.restype = c_int32
    library.spdf_d2d_create_geometry_group.argtypes = [
        c_void_p, POINTER(c_void_p), POINTER(_Transform), c_uint32,
        c_uint32, POINTER(c_void_p)]
    library.spdf_d2d_create_geometry_group.restype = c_int32
    library.spdf_d2d_create_stroke_style.argtypes = [
        c_void_p, c_uint32, c_uint32, c_uint32, c_uint32, c_float, c_float,
        POINTER(c_float), c_uint32, POINTER(c_void_p)]
    library.spdf_d2d_create_stroke_style.restype = c_int32
    library.spdf_d2d_create_stroked_path.argtypes = [
        c_void_p, c_void_p, c_float, c_void_p, POINTER(c_void_p)]
    library.spdf_d2d_create_stroked_path.restype = c_int32
    library.spdf_d2d_push_clip_path.argtypes = [c_void_p, c_void_p]
    library.spdf_d2d_push_clip_path.restype = c_int32
    library.spdf_d2d_pop_clip.argtypes = [c_void_p]
    library.spdf_d2d_pop_clip.restype = c_int32
    library.spdf_d2d_push_opacity_layer.argtypes = [c_void_p, c_float]
    library.spdf_d2d_push_opacity_layer.restype = c_int32
    library.spdf_d2d_pop_layer.argtypes = [c_void_p]
    library.spdf_d2d_pop_layer.restype = c_int32
    library.spdf_d2d_begin_mask.argtypes = [
        c_void_p, c_float, c_float, c_float, c_float, c_uint32, c_uint32]
    library.spdf_d2d_begin_mask.restype = c_int32
    library.spdf_d2d_end_mask.argtypes = [c_void_p]
    library.spdf_d2d_end_mask.restype = c_int32
    library.spdf_d2d_begin_composite_group.argtypes = [c_void_p, c_uint32, c_float]
    library.spdf_d2d_begin_composite_group.restype = c_int32
    library.spdf_d2d_end_composite_group.argtypes = [c_void_p]
    library.spdf_d2d_end_composite_group.restype = c_int32
    library.spdf_d2d_read_pixels.argtypes = [c_void_p, c_void_p, c_size_t]
    library.spdf_d2d_read_pixels.restype = c_int32
    library.spdf_d2d_draw_bitmap.argtypes = [
        c_void_p, c_void_p, c_float, c_float, c_float, c_float, c_float]
    library.spdf_d2d_draw_bitmap.restype = c_int32
    library.spdf_d2d_fill_rect.argtypes = [
        c_void_p, c_float, c_float, c_float, c_float, c_uint32]
    library.spdf_d2d_fill_rect.restype = c_int32
    library.spdf_d2d_stroke_rect.argtypes = [
        c_void_p, c_float, c_float, c_float, c_float, c_uint32, c_float]
    library.spdf_d2d_stroke_rect.restype = c_int32
    library.spdf_d2d_fill_path.argtypes = [c_void_p, c_void_p, c_uint32]
    library.spdf_d2d_fill_path.restype = c_int32
    library.spdf_d2d_stroke_path.argtypes = [
        c_void_p, c_void_p, c_uint32, c_float]
    library.spdf_d2d_stroke_path.restype = c_int32
    library.spdf_d2d_stroke_path_styled.argtypes = [
        c_void_p, c_void_p, c_uint32, c_float, c_void_p]
    library.spdf_d2d_stroke_path_styled.restype = c_int32
    library.spdf_d2d_end_frame.argtypes = [c_void_p]
    library.spdf_d2d_end_frame.restype = c_int32
    library.spdf_d2d_destroy_bitmap.argtypes = [c_void_p]
    library.spdf_d2d_destroy_bitmap.restype = None
    library.spdf_d2d_destroy_path.argtypes = [c_void_p]
    library.spdf_d2d_destroy_path.restype = None
    library.spdf_d2d_destroy_stroke_style.argtypes = [c_void_p]
    library.spdf_d2d_destroy_stroke_style.restype = None
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
        self._paths = set()
        self._stroke_styles = set()
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

    def create_path(self, commands, *, even_odd=False):
        """Create an immutable Direct2D geometry from compact path commands.

        Commands are ``(kind, coordinates...)`` where kind is ``move``,
        ``line``, ``cubic``, or ``close``.
        """
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        kinds = {"move": 1, "line": 2, "cubic": 3, "close": 4}
        native_commands = []
        expected = {"move": 2, "line": 2, "cubic": 6, "close": 0}
        for command in commands:
            kind, values = command[0], command[1:]
            if kind not in kinds or len(values) != expected.get(kind):
                raise ValueError("invalid Direct2D path command")
            item = _PathCommand()
            item.type = kinds[kind]
            for index, value in enumerate(values):
                item.points[index] = float(value)
            native_commands.append(item)
        if not native_commands:
            raise ValueError("Direct2D path cannot be empty")
        array = (_PathCommand * len(native_commands))(*native_commands)
        handle = c_void_p()
        result = self._library.spdf_d2d_create_path(
            self._handle, array, len(native_commands), bool(even_odd),
            byref(handle))
        _check_hresult(result, "Direct2D path creation")
        path = D2DPath(self, handle)
        self._paths.add(path)
        return path

    def create_geometry_group(self, instances, *, even_odd=False):
        """Create one immutable geometry from transformed path instances."""
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        instances = tuple(instances)
        if not instances:
            raise ValueError("Direct2D geometry group cannot be empty")
        handles = (c_void_p * len(instances))()
        transforms = (_Transform * len(instances))()
        for index, (path, matrix) in enumerate(instances):
            if path.closed or path._surface is not self:
                raise ValueError("path does not belong to this Direct2D surface")
            if len(matrix) != 6:
                raise ValueError("invalid Direct2D geometry transform")
            handles[index] = path._handle
            transforms[index] = _Transform(*map(float, matrix))
        handle = c_void_p()
        result = self._library.spdf_d2d_create_geometry_group(
            self._handle, handles, transforms, len(instances), bool(even_odd),
            byref(handle))
        _check_hresult(result, "Direct2D geometry group creation")
        group = D2DPath(self, handle)
        self._paths.add(group)
        return group

    def create_stroke_style(self, style):
        """Create a Direct2D cap, join and custom-dash resource."""
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        start_cap, dash_cap, end_cap, line_join, miter_limit, dash_offset, \
            dash_values = style
        dash_values = tuple(float(value) for value in dash_values)
        dash_array = ((c_float * len(dash_values))(*dash_values)
                      if dash_values else None)
        handle = c_void_p()
        result = self._library.spdf_d2d_create_stroke_style(
            self._handle, int(start_cap), int(dash_cap), int(end_cap),
            int(line_join), float(miter_limit), float(dash_offset),
            dash_array, len(dash_values), byref(handle))
        _check_hresult(result, "Direct2D stroke style creation")
        created = D2DStrokeStyle(self, handle)
        self._stroke_styles.add(created)
        return created

    def create_stroked_path(self, path, width, style=None):
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        if path.closed or path._surface is not self:
            raise ValueError("path does not belong to this Direct2D surface")
        if style is not None and (style.closed or style._surface is not self):
            raise ValueError(
                "stroke style does not belong to this Direct2D surface")
        handle = c_void_p()
        result = self._library.spdf_d2d_create_stroked_path(
            self._handle, path._handle, float(width),
            None if style is None else style._handle, byref(handle))
        _check_hresult(result, "Direct2D stroked path creation")
        created = D2DPath(self, handle)
        self._paths.add(created)
        return created

    def begin_frame(self, argb=0xffe8e8e8):
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        _check_hresult(
            self._library.spdf_d2d_begin_frame(
                self._handle, int(argb) & 0xffffffff),
            "Direct2D frame start")

    def push_clip_path(self, path):
        if path.closed or path._surface is not self:
            raise ValueError("path does not belong to this Direct2D surface")
        _check_hresult(
            self._library.spdf_d2d_push_clip_path(
                self._handle, path._handle),
            "Direct2D clip push")

    def pop_clip(self):
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        _check_hresult(
            self._library.spdf_d2d_pop_clip(self._handle),
            "Direct2D clip pop")

    def push_opacity_layer(self, opacity):
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        _check_hresult(
            self._library.spdf_d2d_push_opacity_layer(
                self._handle, float(opacity)),
            "Direct2D opacity layer push")

    def pop_layer(self):
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        _check_hresult(
            self._library.spdf_d2d_pop_layer(self._handle),
            "Direct2D layer pop")

    def begin_mask(self, area, luminosity, background_argb):
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        left, top, right, bottom = area
        _check_hresult(
            self._library.spdf_d2d_begin_mask(
                self._handle, float(left), float(top), float(right),
                float(bottom), int(bool(luminosity)),
                int(background_argb) & 0xffffffff),
            "Direct2D mask capture start")

    def end_mask(self):
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        _check_hresult(
            self._library.spdf_d2d_end_mask(self._handle),
            "Direct2D mask capture end")

    def begin_composite_group(self, mode, opacity):
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        _check_hresult(self._library.spdf_d2d_begin_composite_group(
            self._handle, int(mode), float(opacity)), "Direct2D blend group start")

    def end_composite_group(self):
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        _check_hresult(self._library.spdf_d2d_end_composite_group(
            self._handle), "Direct2D blend group end")

    def read_pixels_bgra(self, width, height):
        """Explicit test/diagnostic readback, never part of ordinary repaint."""
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        size = int(width) * int(height) * 4
        if width <= 0 or height <= 0 or size > 256 * 1024 * 1024:
            raise ValueError("invalid readback size")
        pixels = (c_ubyte * size)()
        _check_hresult(self._library.spdf_d2d_read_pixels(
            self._handle, pixels, size), "Direct2D pixel readback")
        return bytes(pixels)

    def draw_bitmap(self, bitmap, left, top, right, bottom, opacity=1.0):
        if bitmap.closed or bitmap._surface is not self:
            raise ValueError("bitmap does not belong to this Direct2D surface")
        _check_hresult(
            self._library.spdf_d2d_draw_bitmap(
                self._handle, bitmap._handle, float(left), float(top),
                float(right), float(bottom), float(opacity)),
            "Direct2D bitmap draw")

    def set_transform(self, m11, m12, m21, m22, dx, dy):
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        _check_hresult(
            self._library.spdf_d2d_set_transform(
                self._handle, float(m11), float(m12), float(m21),
                float(m22), float(dx), float(dy)),
            "Direct2D transform")

    def fill_rect(self, left, top, right, bottom, argb):
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        _check_hresult(
            self._library.spdf_d2d_fill_rect(
                self._handle, float(left), float(top), float(right),
                float(bottom), int(argb) & 0xffffffff),
            "Direct2D rectangle fill")

    def stroke_rect(self, left, top, right, bottom, argb, width=1.0):
        if self.closed:
            raise RuntimeError("Direct2D surface is closed")
        _check_hresult(
            self._library.spdf_d2d_stroke_rect(
                self._handle, float(left), float(top), float(right),
                float(bottom), int(argb) & 0xffffffff, float(width)),
            "Direct2D rectangle stroke")

    def fill_path(self, path, argb):
        if path.closed or path._surface is not self:
            raise ValueError("path does not belong to this Direct2D surface")
        _check_hresult(
            self._library.spdf_d2d_fill_path(
                self._handle, path._handle, int(argb) & 0xffffffff),
            "Direct2D path fill")

    def stroke_path(self, path, argb, width=1.0, style=None):
        if path.closed or path._surface is not self:
            raise ValueError("path does not belong to this Direct2D surface")
        if style is None:
            result = self._library.spdf_d2d_stroke_path(
                self._handle, path._handle, int(argb) & 0xffffffff,
                float(width))
        else:
            if style.closed or style._surface is not self:
                raise ValueError(
                    "stroke style does not belong to this Direct2D surface")
            result = self._library.spdf_d2d_stroke_path_styled(
                self._handle, path._handle, int(argb) & 0xffffffff,
                float(width), style._handle)
        _check_hresult(result, "Direct2D path stroke")

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
            for path in tuple(self._paths):
                path.close()
            for style in tuple(self._stroke_styles):
                style.close()
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


class D2DPath:
    def __init__(self, surface, handle):
        self._surface = surface
        self._handle = handle

    @property
    def closed(self):
        return not bool(self._handle)

    def close(self):
        if not self.closed:
            self._surface._library.spdf_d2d_destroy_path(self._handle)
            self._handle = c_void_p()
            self._surface._paths.discard(self)

    def __del__(self):
        try:
            self.close()
        except (AttributeError, OSError):
            pass


class D2DStrokeStyle:
    def __init__(self, surface, handle):
        self._surface = surface
        self._handle = handle

    @property
    def closed(self):
        return not bool(self._handle)

    def close(self):
        if not self.closed:
            self._surface._library.spdf_d2d_destroy_stroke_style(self._handle)
            self._handle = c_void_p()
            self._surface._stroke_styles.discard(self)

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

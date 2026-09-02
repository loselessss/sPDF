"""Conservative MuPDF display-list to Direct2D scene conversion.

MuPDF remains the PDF parser and supplies exact glyph outlines and decoded
images. Direct2D rasterizes supported drawing commands. Any command that is not
represented exactly makes the whole page use the existing PyMuPDF tile path.
"""

from dataclasses import dataclass, replace

import pymupdf
from pymupdf import mupdf as _mupdf


MAX_GPU_IMAGE_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class VectorPath:
    commands: tuple
    even_odd: bool = False
    fill_argb: int = None
    stroke_argb: int = None
    stroke_width: float = 1.0
    transform: tuple = None
    groupable: bool = False


@dataclass(frozen=True)
class VectorImage:
    pixels: bytes
    width: int
    height: int
    stride: int
    transform: tuple
    opacity: float = 1.0


@dataclass(frozen=True)
class ClipPush:
    commands: tuple
    even_odd: bool = False
    transform: tuple = None


@dataclass(frozen=True)
class ClipPop:
    pass


@dataclass(frozen=True)
class VectorPage:
    supported: bool
    paths: tuple = ()
    reason: str = ""
    items: tuple = ()

    @property
    def drawables(self):
        return self.items or self.paths


class _PathWalker(_mupdf.FzPathWalker2):
    def __init__(self):
        super().__init__()
        self.use_virtual_moveto()
        self.use_virtual_lineto()
        self.use_virtual_curveto()
        self.use_virtual_closepath()
        self.commands = []

    def moveto(self, _context, x, y):
        self.commands.append(("move", float(x), float(y)))

    def lineto(self, _context, x, y):
        self.commands.append(("line", float(x), float(y)))

    def curveto(self, _context, x1, y1, x2, y2, x3, y3):
        self.commands.append((
            "cubic", float(x1), float(y1), float(x2), float(y2),
            float(x3), float(y3)))

    def closepath(self, _context):
        self.commands.append(("close",))


def _path_commands(path, *, allow_empty=False):
    walker = _PathWalker()
    if isinstance(path, _mupdf.FzPath):
        resource = path
    else:
        resource = _mupdf.FzPath(path)
        resource.thisown = False
    _mupdf.fz_walk_path(resource, walker, walker.m_internal)
    if not walker.commands and not allow_empty:
        raise ValueError("empty vector path")
    return tuple(walker.commands)


def _matrix(value):
    matrix = value if isinstance(value, _mupdf.FzMatrix) else _mupdf.FzMatrix(value)
    return (float(matrix.a), float(matrix.b), float(matrix.c),
            float(matrix.d), float(matrix.e), float(matrix.f))


def _argb(color, opacity):
    values = tuple(color)
    if len(values) < 3:
        raise ValueError("Direct2D scene requires RGB colors")
    alpha = max(0, min(255, round(float(opacity) * 255)))
    channels = [max(0, min(255, round(float(value) * 255)))
                for value in values[:3]]
    return (alpha << 24) | (channels[0] << 16) | (channels[1] << 8) | channels[2]


def _device_color(colorspace, color, opacity, color_params):
    source = _mupdf.FzColorspace(colorspace)
    # The callback lends this pointer; the temporary C++ wrapper must not drop
    # the page/global colorspace when Python releases it.
    source.thisown = False
    target = _mupdf.fz_device_rgb()
    target.thisown = False
    intermediate = _mupdf.FzColorspace()
    params = _mupdf.FzColorParams(color_params)
    source_values = [_mupdf.floats_getitem(color, index)
                     for index in range(source.fz_colorspace_n())]
    converted = _mupdf.fz_convert_color(
        source, source_values, target, intermediate, params)
    return _argb(converted, opacity)


class _DisplayListDevice(_mupdf.FzDevice2):
    """Record only operations with an exact Direct2D representation."""

    def __init__(self):
        super().__init__()
        for name in (
                "fill_path", "stroke_path", "clip_path", "pop_clip",
                "fill_text", "stroke_text", "clip_text", "clip_stroke_text",
                "clip_stroke_path", "fill_image", "fill_image_mask",
                "clip_image_mask", "fill_shade", "begin_mask", "end_mask",
                "begin_group", "end_group", "begin_tile", "end_tile"):
            getattr(self, "use_virtual_" + name)()
        self.items = []
        self.failure = ""
        self._glyphs = {}
        self._image_bytes = 0
        self._clip_depth = 0

    def _fail(self, operation):
        if not self.failure:
            self.failure = "unsupported operation: " + operation

    def fill_path(self, _context, path, even_odd, ctm, colorspace, color,
                  alpha, color_params):
        try:
            self.items.append(VectorPath(
                _path_commands(path), bool(even_odd),
                fill_argb=_device_color(
                    colorspace, color, alpha, color_params),
                transform=_matrix(ctm)))
        except Exception as error:
            self.failure = str(error)

    def stroke_path(self, _context, path, stroke, ctm, colorspace, color,
                    alpha, color_params):
        try:
            if stroke.dash_len or stroke.start_cap or stroke.dash_cap or \
                    stroke.end_cap or stroke.linejoin or \
                    abs(float(stroke.miterlimit) - 10.0) > 1e-5:
                raise ValueError("unsupported stroke style")
            commands = _path_commands(path)
            transform = _matrix(ctm)
            argb = _device_color(colorspace, color, alpha, color_params)
            width = float(stroke.linewidth)
            if self.items and isinstance(self.items[-1], VectorPath):
                previous = self.items[-1]
                if previous.commands == commands and \
                        previous.transform == transform and \
                        previous.stroke_argb is None:
                    self.items[-1] = replace(
                        previous, stroke_argb=argb, stroke_width=width)
                    return
            self.items.append(VectorPath(
                commands, stroke_argb=argb, stroke_width=width,
                transform=transform))
        except Exception as error:
            self.failure = str(error)

    def clip_path(self, _context, path, even_odd, ctm, _scissor):
        try:
            self.items.append(ClipPush(
                _path_commands(path), bool(even_odd), _matrix(ctm)))
            self._clip_depth += 1
        except Exception as error:
            self.failure = str(error)

    def pop_clip(self, _context):
        if self._clip_depth <= 0:
            self.failure = "unbalanced clip stack"
            return
        self.items.append(ClipPop())
        self._clip_depth -= 1

    def fill_text(self, _context, text, ctm, colorspace, color,
                  alpha, color_params):
        try:
            argb = _device_color(colorspace, color, alpha, color_params)
            span_ptr = text.head
            while span_ptr:
                next_span = span_ptr.next
                span = _mupdf.FzTextSpan(span_ptr)
                span.thisown = False
                font = span.font()
                base = span.trm()
                page_matrix = _mupdf.FzMatrix(ctm)
                for index in range(span.m_internal.len):
                    item = span.items(index)
                    if item.gid < 0:
                        raise ValueError("text glyph has no usable glyph id")
                    matrix = _mupdf.FzMatrix(
                        base.a, base.b, base.c, base.d, base.e, base.f)
                    matrix.e = item.x
                    matrix.f = item.y
                    matrix = _mupdf.fz_concat(matrix, page_matrix)
                    key = (font.m_internal_value(), item.gid)
                    commands = self._glyphs.get(key)
                    if commands is None:
                        outline = font.fz_outline_glyph(
                            item.gid, _mupdf.FzMatrix())
                        if not outline:
                            if chr(item.ucs).isspace():
                                self._glyphs[key] = ()
                                continue
                            raise ValueError("font glyph has no vector outline")
                        commands = _path_commands(outline, allow_empty=True)
                        if not commands and not chr(item.ucs).isspace():
                            raise ValueError("font glyph has no vector outline")
                        self._glyphs[key] = commands
                    if commands:
                        self.items.append(VectorPath(
                            commands, fill_argb=argb,
                            transform=_matrix(matrix), groupable=True))
                span_ptr = next_span
        except Exception as error:
            self.failure = str(error)

    def fill_image(self, _context, image, ctm, alpha, _color_params):
        try:
            source = _mupdf.FzImage(image)
            source.thisown = False
            estimated = int(source.w()) * int(source.h()) * 4
            if estimated > MAX_GPU_IMAGE_BYTES or \
                    self._image_bytes + estimated > MAX_GPU_IMAGE_BYTES:
                raise ValueError("page image data exceeds GPU scene limit")
            pixmap = pymupdf.Pixmap(
                source.fz_get_unscaled_pixmap_from_image())
            rgba = pixmap.samples
            cost = pixmap.width * pixmap.height * 4
            if pixmap.n != 4 or not pixmap.alpha or len(rgba) < cost:
                raise ValueError("decoded image is not RGBA")
            if cost > MAX_GPU_IMAGE_BYTES or \
                    self._image_bytes + cost > MAX_GPU_IMAGE_BYTES:
                raise ValueError("page image data exceeds GPU scene limit")
            bgra = bytearray(cost)
            for offset in range(0, cost, 4):
                red, green, blue, opacity = rgba[offset:offset + 4]
                if opacity != 255:
                    red = (red * opacity + 127) // 255
                    green = (green * opacity + 127) // 255
                    blue = (blue * opacity + 127) // 255
                bgra[offset:offset + 4] = blue, green, red, opacity
            self.items.append(VectorImage(
                bytes(bgra), pixmap.width, pixmap.height, pixmap.width * 4,
                _matrix(ctm), max(0.0, min(1.0, float(alpha)))))
            self._image_bytes += cost
        except Exception as error:
            self.failure = str(error)

    def stroke_text(self, *_args):
        self._fail("stroke-text")

    def clip_text(self, *_args):
        self._fail("clip-text")

    def clip_stroke_text(self, *_args):
        self._fail("clip-stroke-text")

    def clip_stroke_path(self, *_args):
        self._fail("clip-stroke-path")

    def fill_image_mask(self, _context, image, ctm, colorspace, color,
                        alpha, color_params):
        try:
            source = _mupdf.FzImage(image)
            source.thisown = False
            estimated = int(source.w()) * int(source.h()) * 4
            if estimated > MAX_GPU_IMAGE_BYTES or \
                    self._image_bytes + estimated > MAX_GPU_IMAGE_BYTES:
                raise ValueError("page image data exceeds GPU scene limit")
            pixmap = pymupdf.Pixmap(
                source.fz_get_unscaled_pixmap_from_image())
            if pixmap.n != 1 or not pixmap.alpha:
                raise ValueError("decoded stencil is not an alpha mask")
            argb = _device_color(
                colorspace, color, 1.0, color_params)
            red = (argb >> 16) & 0xff
            green = (argb >> 8) & 0xff
            blue = argb & 0xff
            bgra = bytearray(pixmap.width * pixmap.height * 4)
            for index, opacity in enumerate(pixmap.samples):
                offset = index * 4
                bgra[offset:offset + 4] = (
                    (blue * opacity + 127) // 255,
                    (green * opacity + 127) // 255,
                    (red * opacity + 127) // 255,
                    opacity)
            cost = len(bgra)
            self.items.append(VectorImage(
                bytes(bgra), pixmap.width, pixmap.height, pixmap.width * 4,
                _matrix(ctm), max(0.0, min(1.0, float(alpha)))))
            self._image_bytes += cost
        except Exception as error:
            self.failure = str(error)

    def clip_image_mask(self, *_args):
        self._fail("clip-image-mask")

    def fill_shade(self, *_args):
        self._fail("fill-shade")

    def begin_mask(self, *_args):
        self._fail("begin-mask")

    def end_mask(self, *_args):
        self._fail("end-mask")

    def begin_group(self, *_args):
        self._fail("begin-group")

    def end_group(self, *_args):
        self._fail("end-group")

    def begin_tile(self, *_args):
        self._fail("begin-tile")

    def end_tile(self, *_args):
        self._fail("end-tile")


def vector_page_from_pymupdf(page):
    """Return a complete GPU scene only when every operation is supported."""
    device = _DisplayListDevice()
    try:
        _mupdf.fz_run_page(
            page.this, device, _mupdf.FzMatrix(), _mupdf.FzCookie())
        if device._clip_depth:
            device.failure = "unbalanced clip stack"
    except Exception as error:
        device.failure = str(error)
    finally:
        _mupdf.fz_close_device(device)
    if device.failure:
        return VectorPage(False, reason=device.failure)
    items = tuple(device.items)
    paths = tuple(item for item in items if isinstance(item, VectorPath))
    return VectorPage(True, paths, items=items)

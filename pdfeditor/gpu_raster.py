"""Conservative MuPDF display-list to Direct2D scene conversion.

MuPDF remains the PDF parser and supplies exact glyph outlines and decoded
images. Direct2D rasterizes supported drawing commands. Any command that is not
represented exactly makes the whole page use the existing PyMuPDF tile path.
"""

from dataclasses import dataclass, replace
import math

import pymupdf
from pymupdf import mupdf as _mupdf


MAX_GPU_IMAGE_BYTES = 64 * 1024 * 1024
SHADE_RASTER_SCALE = 2.0


@dataclass(frozen=True)
class VectorPath:
    commands: tuple
    even_odd: bool = False
    fill_argb: int = None
    stroke_argb: int = None
    stroke_width: float = 1.0
    stroke_style: tuple = None
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
class ClipStrokePush:
    commands: tuple
    stroke_width: float
    stroke_style: tuple = None
    transform: tuple = None


@dataclass(frozen=True)
class ClipPop:
    pass


@dataclass(frozen=True)
class GroupPush:
    opacity: float
    blend_mode: int = 0
    isolated: bool = True


@dataclass(frozen=True)
class GroupPop:
    pass


@dataclass(frozen=True)
class MaskBegin:
    area: tuple
    luminosity: bool
    background_argb: int


@dataclass(frozen=True)
class MaskEnd:
    pass


@dataclass(frozen=True)
class VectorPage:
    supported: bool
    paths: tuple = ()
    reason: str = ""
    items: tuple = ()
    features: tuple = ()

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


def _transform_commands(commands, transform):
    a, b, c, d, e, f = transform

    def point(x, y):
        return (a * x + c * y + e, b * x + d * y + f)

    transformed = []
    for command in commands:
        kind = command[0]
        if kind == "close":
            transformed.append(command)
            continue
        if kind in ("move", "line"):
            transformed.append((kind, *point(command[1], command[2])))
            continue
        if kind == "cubic":
            transformed.append((
                kind,
                *point(command[1], command[2]),
                *point(command[3], command[4]),
                *point(command[5], command[6])))
            continue
        raise ValueError("unsupported vector path command")
    return tuple(transformed)


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


def _stroke_parameters(stroke):
    width = float(stroke.linewidth)
    dash_count = int(stroke.dash_len)
    dashes = tuple(float(_mupdf.floats_getitem(
        stroke.dash_list, index)) for index in range(dash_count))
    if any(not math.isfinite(value) or value < 0 for value in dashes):
        raise ValueError("invalid stroke dash pattern")
    if dashes and width <= 0:
        raise ValueError("dashed hairline stroke is not supported")
    dash_scale = width if dashes else 1.0
    style = (
        int(stroke.start_cap), int(stroke.dash_cap),
        int(stroke.end_cap), int(stroke.linejoin),
        float(stroke.miterlimit), float(stroke.dash_phase) / dash_scale,
        tuple(value / dash_scale for value in dashes))
    if style == (0, 0, 0, 0, 10.0, 0.0, ()):
        style = None
    return width, style


def _uniform_scale(matrix):
    a, b, c, d, _e, _f = _matrix(matrix)
    first = math.hypot(a, b)
    second = math.hypot(c, d)
    tolerance = max(1.0, first, second) * 1e-5
    dot_tolerance = max(1.0, first * second) * 1e-5
    if first <= 0 or abs(first - second) > tolerance or \
            abs(a * c + b * d) > dot_tolerance:
        raise ValueError("non-uniform stroked text transform")
    return first


class _DisplayListDevice(_mupdf.FzDevice2):
    """Record only operations with an exact Direct2D representation."""

    def __init__(self, page_rect):
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
        self._group_depth = 0
        self._mask_depth = 0
        self._page_rect = tuple(float(value) for value in page_rect)
        self._features = set()

    def _fail(self, operation):
        if not self.failure:
            self.failure = "unsupported operation: " + operation

    def fill_path(self, _context, path, even_odd, ctm, colorspace, color,
                  alpha, color_params):
        try:
            self._features.add("vector")
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
            self._features.add("vector")
            commands = _path_commands(path)
            transform = _matrix(ctm)
            argb = _device_color(colorspace, color, alpha, color_params)
            width, style = _stroke_parameters(stroke)
            if style is not None:
                self._features.add("stroke-style")
            if self.items and isinstance(self.items[-1], VectorPath):
                previous = self.items[-1]
                if previous.commands == commands and \
                        previous.transform == transform and \
                        previous.stroke_argb is None:
                    self.items[-1] = replace(
                        previous, stroke_argb=argb, stroke_width=width,
                        stroke_style=style)
                    return
            self.items.append(VectorPath(
                commands, stroke_argb=argb, stroke_width=width,
                stroke_style=style, transform=transform))
        except Exception as error:
            self.failure = str(error)

    def clip_path(self, _context, path, even_odd, ctm, _scissor):
        try:
            self._features.add("vector-clip")
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

    def _text_outlines(self, text, ctm):
        outlines = []
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
                    outlines.append((commands, _matrix(matrix)))
            span_ptr = next_span
        return outlines

    def fill_text(self, _context, text, ctm, colorspace, color,
                  alpha, color_params):
        try:
            self._features.add("text")
            argb = _device_color(colorspace, color, alpha, color_params)
            for commands, transform in self._text_outlines(text, ctm):
                self.items.append(VectorPath(
                    commands, fill_argb=argb,
                    transform=transform, groupable=True))
        except Exception as error:
            self.failure = str(error)

    def fill_image(self, _context, image, ctm, alpha, _color_params):
        try:
            self._features.add("image")
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

    def stroke_text(self, _context, text, stroke, ctm, colorspace, color,
                    alpha, color_params):
        try:
            self._features.add("stroked-text")
            width, style = _stroke_parameters(stroke)
            width *= _uniform_scale(ctm)
            argb = _device_color(colorspace, color, alpha, color_params)
            for commands, transform in self._text_outlines(text, ctm):
                self.items.append(VectorPath(
                    _transform_commands(commands, transform),
                    stroke_argb=argb, stroke_width=width,
                    stroke_style=style))
        except Exception as error:
            self.failure = str(error)

    def clip_text(self, _context, text, ctm, _scissor):
        try:
            self._features.add("text-clip")
            commands = []
            for outline, transform in self._text_outlines(text, ctm):
                commands.extend(_transform_commands(outline, transform))
            if not commands:
                raise ValueError("text clip has no vector outline")
            self.items.append(ClipPush(tuple(commands)))
            self._clip_depth += 1
        except Exception as error:
            self.failure = str(error)

    def clip_stroke_text(self, _context, text, stroke, ctm, _scissor):
        try:
            self._features.add("stroked-text-clip")
            width, style = _stroke_parameters(stroke)
            width *= _uniform_scale(ctm)
            commands = []
            for outline, transform in self._text_outlines(text, ctm):
                commands.extend(_transform_commands(outline, transform))
            if not commands:
                raise ValueError("stroked text clip has no vector outline")
            self.items.append(ClipStrokePush(
                tuple(commands), width, style))
            self._clip_depth += 1
        except Exception as error:
            self.failure = str(error)

    def clip_stroke_path(self, _context, path, stroke, ctm, _scissor):
        try:
            self._features.add("stroked-vector-clip")
            width, style = _stroke_parameters(stroke)
            self.items.append(ClipStrokePush(
                _path_commands(path), width, style, _matrix(ctm)))
            self._clip_depth += 1
        except Exception as error:
            self.failure = str(error)

    def fill_image_mask(self, _context, image, ctm, colorspace, color,
                        alpha, color_params):
        try:
            self._features.add("stencil")
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

    def clip_image_mask(self, _context, image, ctm, _scissor):
        try:
            source = _mupdf.FzImage(image)
            source.thisown = False
            estimated = int(source.w()) * int(source.h()) * 4
            if estimated > MAX_GPU_IMAGE_BYTES or \
                    self._image_bytes + estimated > MAX_GPU_IMAGE_BYTES:
                raise ValueError("page clip mask data exceeds GPU scene limit")
            pixmap = pymupdf.Pixmap(
                source.fz_get_unscaled_pixmap_from_image())
            if pixmap.n != 1 or not pixmap.alpha:
                raise ValueError("decoded clip mask is not an alpha mask")
            bgra = bytearray(pixmap.width * pixmap.height * 4)
            for index, opacity in enumerate(pixmap.samples):
                offset = index * 4
                bgra[offset:offset + 4] = opacity, opacity, opacity, opacity
            cost = len(bgra)
            self.items.extend((
                MaskBegin(self._page_rect, False, 0),
                VectorImage(
                    bytes(bgra), pixmap.width, pixmap.height,
                    pixmap.width * 4, _matrix(ctm)),
                MaskEnd()))
            self._clip_depth += 1
            self._image_bytes += cost
            self._features.add("clip-mask")
        except Exception as error:
            self.failure = str(error)

    def fill_shade(self, _context, shade_ptr, ctm, alpha, color_params):
        try:
            self._features.add("shading")
            shade = _mupdf.FzShade(shade_ptr)
            shade.thisown = False
            matrix = _mupdf.FzMatrix(ctm)
            bound = shade.fz_bound_shade(matrix)
            page_x0, page_y0, page_x1, page_y1 = self._page_rect
            values = (float(bound.x0), float(bound.y0),
                      float(bound.x1), float(bound.y1))
            if all(math.isfinite(value) for value in values):
                x0 = max(page_x0, values[0])
                y0 = max(page_y0, values[1])
                x1 = min(page_x1, values[2])
                y1 = min(page_y1, values[3])
            else:
                x0, y0, x1, y1 = self._page_rect
            if x1 <= x0 or y1 <= y0:
                return
            scale = SHADE_RASTER_SCALE
            left = math.floor(x0 * scale)
            top = math.floor(y0 * scale)
            right = math.ceil(x1 * scale)
            bottom = math.ceil(y1 * scale)
            width = right - left
            height = bottom - top
            estimated = width * height * 4
            if estimated > MAX_GPU_IMAGE_BYTES or \
                    self._image_bytes + estimated > MAX_GPU_IMAGE_BYTES:
                raise ValueError("page shading data exceeds GPU scene limit")
            target = _mupdf.fz_device_rgb()
            target.thisown = False
            bbox = _mupdf.FzIrect(left, top, right, bottom)
            pixmap = _mupdf.fz_new_pixmap_with_bbox(
                target, bbox, _mupdf.FzSeparations(), 1)
            _mupdf.fz_clear_pixmap(pixmap)
            render_matrix = _mupdf.fz_concat(
                matrix, _mupdf.FzMatrix(scale, 0, 0, scale, 0, 0))
            shade.fz_paint_shade(
                _mupdf.FzColorspace(), render_matrix, pixmap,
                _mupdf.FzColorParams(color_params), bbox,
                _mupdf.FzOverprint())
            image = pymupdf.Pixmap(pixmap)
            if image.n != 4 or not image.alpha:
                raise ValueError("rasterized shading is not RGBA")
            cost = width * height * 4
            rgba = image.samples
            if len(rgba) < cost:
                raise ValueError("rasterized shading data is incomplete")
            bgra = bytearray(cost)
            for offset in range(0, cost, 4):
                red, green, blue, opacity = rgba[offset:offset + 4]
                if opacity != 255:
                    red = (red * opacity + 127) // 255
                    green = (green * opacity + 127) // 255
                    blue = (blue * opacity + 127) // 255
                bgra[offset:offset + 4] = blue, green, red, opacity
            self.items.append(VectorImage(
                bytes(bgra), width, height, width * 4,
                (width / scale, 0.0, 0.0, height / scale,
                 left / scale, top / scale),
                max(0.0, min(1.0, float(alpha)))))
            self._image_bytes += cost
        except Exception as error:
            self.failure = str(error)

    def begin_mask(self, _context, area, luminosity, colorspace, background,
                   color_params):
        try:
            if luminosity:
                background_argb = _device_color(
                    colorspace, background, 1.0, color_params)
            else:
                background_argb = 0
            self.items.append(MaskBegin(
                (float(area.x0), float(area.y0),
                 float(area.x1), float(area.y1)),
                bool(luminosity), background_argb))
            self._mask_depth += 1
            self._features.add("soft-mask")
        except Exception as error:
            self.failure = str(error)

    def end_mask(self, _context, function):
        if self._mask_depth <= 0:
            if not self.failure:
                self.failure = "unbalanced soft mask stack"
            return
        if function:
            self._fail("soft-mask-transfer-function")
        self.items.append(MaskEnd())
        self._mask_depth -= 1
        self._clip_depth += 1

    def begin_group(self, _context, _area, colorspace, isolated, knockout,
                    blendmode, alpha):
        try:
            self._features.add("transparency-group")
            opacity = float(alpha)
            mode = int(blendmode)
            if knockout:
                raise ValueError("unsupported knockout transparency group")
            if not 0 <= mode <= 15:
                raise ValueError("unsupported blend mode: %s" % mode)
            if mode:
                self._features.add("blend-mode")
            if colorspace:
                source = _mupdf.FzColorspace(colorspace)
                source.thisown = False
                channels = source.fz_colorspace_n()
                valid_device_space = (
                    _mupdf.fz_colorspace_is_device(source) and
                    (channels == 3 or (self._mask_depth and channels == 1)))
                if not valid_device_space:
                    raise ValueError("unsupported transparency group colorspace")
            if not isolated and (mode or opacity < 1.0 - 1e-6):
                raise ValueError("unsupported non-isolated transparency group")
            if not math.isfinite(opacity) or opacity < 0.0 or opacity > 1.0:
                raise ValueError("invalid transparency group opacity")
            self.items.append(GroupPush(opacity, mode, bool(isolated)))
            self._group_depth += 1
        except Exception as error:
            self.failure = str(error)

    def end_group(self, _context):
        if self._group_depth <= 0:
            if not self.failure:
                self.failure = "unbalanced transparency group stack"
            return
        self.items.append(GroupPop())
        self._group_depth -= 1

    def begin_tile(self, *_args):
        self._fail("begin-tile")

    def end_tile(self, *_args):
        self._fail("end-tile")


def _validate_composite_context(items):
    """Geometry clips use explicit captures; soft masks still use layers."""
    clips = []
    mask_depth = 0
    for item in items:
        if isinstance(item, (ClipPush, ClipStrokePush)):
            if mask_depth or any(clips):
                return "unsupported clip group inside mask"
            clips.append(False)
        elif isinstance(item, ClipPop):
            if not clips:
                return "unbalanced composite clip stack"
            clips.pop()
        elif isinstance(item, MaskBegin):
            mask_depth += 1
        elif isinstance(item, MaskEnd):
            mask_depth -= 1
            clips.append(True)
        elif isinstance(item, GroupPush):
            if not item.isolated:
                return "unsupported non-isolated group in blended scene"
            if mask_depth or any(clips):
                return "unsupported blend group inside mask"
    return ""


def vector_page_from_pymupdf(page):
    """Return a complete GPU scene only when every operation is supported."""
    rect = page.rect
    device = _DisplayListDevice((rect.x0, rect.y0, rect.x1, rect.y1))
    try:
        _mupdf.fz_run_page(
            page.this, device, _mupdf.FzMatrix(), _mupdf.FzCookie())
        if device._clip_depth:
            device.failure = "unbalanced clip stack"
        if device._group_depth:
            device.failure = "unbalanced transparency group stack"
        if device._mask_depth:
            device.failure = "unbalanced soft mask stack"
        if not device.failure and "blend-mode" in device._features:
            device.failure = _validate_composite_context(device.items)
    except Exception as error:
        device.failure = str(error)
    finally:
        _mupdf.fz_close_device(device)
    if device.failure:
        return VectorPage(
            False, reason=device.failure,
            features=tuple(sorted(device._features)))
    items = tuple(device.items)
    paths = tuple(item for item in items if isinstance(item, VectorPath))
    return VectorPage(
        True, paths, items=items,
        features=tuple(sorted(device._features)))

"""Conservative MuPDF-display-list to Direct2D scene conversion.

MuPDF continues to parse PDF content and provide exact glyph outlines and
decoded images. Direct2D rasterizes the supported page scene. Shading, masks,
clips, transparency groups, or complex stroke styles keep the whole page on
the existing pixel-correct PyMuPDF tile renderer.
"""

from dataclasses import dataclass

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


@dataclass(frozen=True)
class VectorImage:
    pixels: bytes
    width: int
    height: int
    stride: int
    transform: tuple
    opacity: float = 1.0


@dataclass(frozen=True)
class VectorPage:
    supported: bool
    paths: tuple = ()
    reason: str = ""
    items: tuple = ()

    @property
    def drawables(self):
        return self.items or self.paths


class _GlyphOutlineWalker(_mupdf.FzPathWalker2):
    """Collect one already-transformed MuPDF glyph outline."""

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


class _DisplayListDevice(_mupdf.FzDevice2):
    """Extract exact glyph outlines and decoded images from MuPDF."""

    def __init__(self):
        super().__init__()
        self.use_virtual_fill_text()
        self.use_virtual_fill_image()
        self.outlines = []
        self.images = []
        self.failure = ""
        self._glyphs = {}
        self._image_bytes = 0

    def fill_text(self, _context, text, ctm, _colorspace, _color,
                  _alpha, _color_params):
        span_ptr = text.head
        while span_ptr:
            next_span = span_ptr.next
            span = _mupdf.FzTextSpan(span_ptr)
            font = span.font()
            base = span.trm()
            page_matrix = _mupdf.FzMatrix(ctm)
            glyphs = []
            for index in range(span.m_internal.len):
                item = span.items(index)
                if item.gid < 0:
                    self.failure = "text glyph has no usable glyph id"
                    return
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
                        # Spaces and other blank glyphs legitimately have no path.
                        if chr(item.ucs).isspace():
                            self._glyphs[key] = ()
                            continue
                        self.failure = "font glyph has no vector outline"
                        return
                    walker = _GlyphOutlineWalker()
                    _mupdf.fz_walk_path(
                        outline, walker, walker.m_internal)
                    commands = tuple(walker.commands)
                    self._glyphs[key] = commands
                if commands:
                    glyphs.append((commands, (
                        float(matrix.a), float(matrix.b), float(matrix.c),
                        float(matrix.d), float(matrix.e), float(matrix.f))))
            self.outlines.append(tuple(glyphs))
            span_ptr = next_span

    def fill_image(self, _context, image, ctm, alpha, _color_params):
        try:
            source = _mupdf.FzImage(image)
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
            for source in range(0, cost, 4):
                red, green, blue, opacity = rgba[source:source + 4]
                if opacity != 255:
                    red = (red * opacity + 127) // 255
                    green = (green * opacity + 127) // 255
                    blue = (blue * opacity + 127) // 255
                bgra[source:source + 4] = blue, green, red, opacity
            matrix = _mupdf.FzMatrix(ctm)
            self.images.append(VectorImage(
                bytes(bgra), pixmap.width, pixmap.height, pixmap.width * 4,
                (float(matrix.a), float(matrix.b), float(matrix.c),
                 float(matrix.d), float(matrix.e), float(matrix.f)),
                max(0.0, min(1.0, float(alpha)))))
            self._image_bytes += cost
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            self.failure = str(error)


def _display_resources(page):
    device = _DisplayListDevice()
    try:
        _mupdf.fz_run_page(
            page.this, device, _mupdf.FzMatrix(), _mupdf.FzCookie())
    finally:
        _mupdf.fz_close_device(device)
    if device.failure:
        raise ValueError(device.failure)
    return tuple(device.outlines), tuple(device.images)


def _argb(color, opacity):
    if color is None:
        return None
    values = tuple(color)
    if len(values) != 3:
        raise ValueError("Direct2D prototype requires RGB path colors")
    alpha = max(0, min(255, round(float(opacity) * 255)))
    channels = [max(0, min(255, round(float(value) * 255))) for value in values]
    return (alpha << 24) | (channels[0] << 16) | (channels[1] << 8) | channels[2]


def _point(value):
    return float(value[0]), float(value[1])


def _same(left, right):
    return left is not None and abs(left[0] - right[0]) < 1e-5 and \
        abs(left[1] - right[1]) < 1e-5


def _path_commands(items, close_path=False):
    commands = []
    current = None

    def move(point):
        nonlocal current
        if not _same(current, point):
            commands.append(("move", point[0], point[1]))
        current = point

    for item in items:
        kind = item[0]
        if kind == "re":
            rect = item[1]
            x0, y0, x1, y1 = map(float, rect)
            points = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            if len(item) > 2 and item[2] < 0:
                points.reverse()
            move(points[0])
            for point in points[1:]:
                commands.append(("line", point[0], point[1]))
            commands.append(("close",))
            current = points[0]
        elif kind == "l":
            start, end = _point(item[1]), _point(item[2])
            move(start)
            commands.append(("line", end[0], end[1]))
            current = end
        elif kind == "c":
            start = _point(item[1])
            control1, control2, end = map(_point, item[2:5])
            move(start)
            commands.append(("cubic", control1[0], control1[1],
                             control2[0], control2[1], end[0], end[1]))
            current = end
        elif kind == "qu":
            points = [_point(point) for point in item[1]]
            if len(points) != 4:
                raise ValueError("unsupported quadrilateral path")
            move(points[0])
            for point in points[1:]:
                commands.append(("line", point[0], point[1]))
            commands.append(("close",))
            current = points[0]
        else:
            raise ValueError("unsupported path operation: %s" % kind)
    if close_path and commands and commands[-1][0] != "close":
        commands.append(("close",))
    if not commands:
        raise ValueError("empty vector path")
    return tuple(commands)


def vector_page_from_pymupdf(page):
    """Return a complete GPU scene only when every page operation is supported."""
    try:
        bbox_log = page.get_bboxlog()
        unsupported = [entry[0] for entry in bbox_log
                       if entry[0] not in (
                           "fill-path", "stroke-path", "fill-text",
                           "fill-image")]
        if unsupported:
            return VectorPage(False, reason="unsupported operation: %s" % unsupported[0])
        result = []
        for drawing in page.get_cdrawings(extended=True):
            kind = drawing.get("type")
            if kind not in ("f", "s", "fs") or drawing.get("level", 0) != 0:
                return VectorPage(False, reason="unsupported path container")
            if "s" in kind:
                if tuple(drawing.get("lineCap", (0, 0, 0))) != (0, 0, 0) or \
                        float(drawing.get("lineJoin", 0)) != 0 or \
                        str(drawing.get("dashes", "[] 0")).strip() != "[] 0":
                    return VectorPage(False, reason="unsupported stroke style")
            commands = _path_commands(
                drawing.get("items", ()), drawing.get("closePath", False))
            result.append((drawing.get("seqno", 0), VectorPath(
                commands=commands,
                even_odd=bool(drawing.get("even_odd", False)),
                fill_argb=_argb(drawing.get("fill"),
                                drawing.get("fill_opacity", 1.0)) if "f" in kind else None,
                stroke_argb=_argb(drawing.get("color"),
                                  drawing.get("stroke_opacity", 1.0)) if "s" in kind else None,
                stroke_width=float(drawing.get("width", 1.0)))))
        traces = page.get_texttrace()
        outlines, images = _display_resources(page) if traces or any(
            entry[0] == "fill-image" for entry in bbox_log) else ((), ())
        if len(outlines) != len(traces):
            return VectorPage(False, reason="text outline count mismatch")
        for trace, glyphs in zip(traces, outlines):
            if trace.get("type") != 0:
                return VectorPage(False, reason="unsupported text rendering mode")
            color = _argb(trace.get("color"), trace.get("opacity", 1.0))
            for commands, transform in glyphs:
                result.append((trace.get("seqno", 0), VectorPath(
                    commands=commands,
                    fill_argb=color,
                    transform=transform)))
        image_seqnos = [index for index, entry in enumerate(bbox_log)
                        if entry[0] == "fill-image"]
        if len(images) != len(image_seqnos):
            return VectorPage(False, reason="image resource count mismatch")
        result.extend(zip(image_seqnos, images))
        result.sort(key=lambda item: item[0])
        items = tuple(item for _seqno, item in result)
        paths = tuple(item for item in items if isinstance(item, VectorPath))
        return VectorPage(True, paths, items=items)
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        return VectorPage(False, reason=str(error))

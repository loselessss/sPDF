"""Viewport-sized reader compositor with bounded, on-demand CPU PDF tiles.

OpenGL only composites already-rasterized images. MuPDF remains on the GUI
thread: it is not thread-safe. One small tile per timer tick yields between
tiles without sharing documents with workers or making tab close wait for one.
"""

from collections import OrderedDict
import math
import os

from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QMouseEvent, QPainter, QPixmap
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsView, QOpenGLWidget, QWidget

from .widgets import PageCanvas, qimage_from_render

TILE_PIXELS = 512
TILE_CACHE_BYTES = 64 * 1024 * 1024
PREVIEW_PIXELS = 1_000_000
VIEWPORT_PIXELS = 6_000_000
MAX_VISIBLE_TILES = 48


def opengl_allowed():
    return (os.name == "nt" and
            os.environ.get("QT_QPA_PLATFORM", "").lower() not in ("offscreen", "minimal") and
            os.environ.get("SPDF_DISABLE_GPU", "").lower() not in ("1", "true", "yes"))


class _ReaderCanvas(PageCanvas):
    """Reuse selection/link interaction state, not a page-sized native surface."""

    def __init__(self, owner):
        self.owner = owner
        super().__init__(owner)
        self.hide()

    def update(self, *args):
        self.owner.viewport().update()

    def setCursor(self, cursor):
        super().setCursor(cursor)
        self.owner.viewport().setCursor(cursor)

class ReaderPageView(QGraphicsView):
    zoom_changed = pyqtSignal(float)
    page_flip = pyqtSignal(int)
    viewport_changed = pyqtSignal()
    render_failed = pyqtSignal(str)
    ZOOM_MIN, ZOOM_MAX = 0.1, 8.0
    FLIP_THRESHOLD = 120

    def __init__(self, parent=None, *, use_opengl=None):
        super().__init__(parent)
        self.setObjectName("documentViewport")
        self.setScene(QGraphicsScene(self))
        self.setAlignment(Qt.AlignCenter)
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setResizeAnchor(QGraphicsView.NoAnchor)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.zoom = 1.0
        self._flip_accum = 0
        self._document = None
        self._page_sizes = {}
        self._previews = {}
        self._tiles = OrderedDict()
        self._tile_bytes = 0
        self._pending = []
        self._wanted = set()
        self._updating = False
        self._gpu_surface = None
        self._tile_timer = QTimer(self)
        self._tile_timer.setSingleShot(True)
        self._tile_timer.timeout.connect(self._render_next_tile)
        self._refine_timer = QTimer(self)
        self._refine_timer.setSingleShot(True)
        self._refine_timer.timeout.connect(self._plan_tiles)
        self.canvas = _ReaderCanvas(self)
        enable_opengl = opengl_allowed() if use_opengl is None else use_opengl
        if enable_opengl:
            try:
                self._gpu_surface = QOpenGLWidget()
                self.setViewport(self._gpu_surface)
            except (RuntimeError, ImportError):
                self._gpu_surface = None
                self.setViewport(QWidget())
        self.viewport().setObjectName("documentViewportSurface")
        self.setMouseTracking(True)
        self.canvas.refresh_cursor()
        self.canvas.pan_requested.connect(self._pan_canvas)
        self.horizontalScrollBar().valueChanged.connect(self._viewport_moved)
        self.verticalScrollBar().valueChanged.connect(self._viewport_moved)

    @property
    def composition_backend(self):
        return "opengl" if self._gpu_surface is not None and self._gpu_surface.isValid() else "cpu"

    def _verify_gpu(self):
        if self._gpu_surface is not None and not self._gpu_surface.isValid():
            # Keep document, image cache, scroll position and interaction state.
            self._gpu_surface = None
            self.setViewport(QWidget())
            self.viewport().setObjectName("documentViewportSurface")
            self.setMouseTracking(True)
            self.canvas.refresh_cursor()
            self.viewport().update()

    def render_document(self, document, pages, active_page):
        self.stop_rendering()
        changed = document is not self._document
        if changed:
            self._previews.clear()
            self._clear_tiles()
        self._document = document
        pages = list(pages)
        self._previews = {p: pix for p, pix in self._previews.items() if p in pages}
        self._page_sizes = {p: document.page_size(p) for p in pages}
        for page in pages:
            if page not in self._previews:
                w, h = self._page_sizes[page]
                scale = min(0.75, math.sqrt(PREVIEW_PIXELS / max(1, w * h)))
                image = qimage_from_render(*document.render(page, scale))
                self._previews[page] = QPixmap.fromImage(image)
        self.canvas._active_page = active_page
        self._layout_pages()
        self._schedule_refine()

    def _layout_pages(self):
        self._updating = True
        try:
            left, height = 0.0, 0.0
            self.canvas.zoom = self.zoom
            self.canvas._pages = []
            for page, (w, h) in self._page_sizes.items():
                rect = QRectF(left, 0, w * self.zoom, h * self.zoom)
                self.canvas._pages.append((page, self._previews[page], rect))
                left = rect.right() + 16
                height = max(height, rect.height())
            self.canvas._pix = next(iter(self._previews.values()), None)
            self.setSceneRect(QRectF(0, 0, max(0, left - 16), height))
        finally:
            self._updating = False
        self.viewport().update()
        self.viewport_changed.emit()

    def preview_zoom(self, zoom, position=None):
        if position is None:
            position = self.viewport().rect().center()
        anchor = self.canvas._page_point(self.mapToScene(position))
        self.zoom = max(self.ZOOM_MIN, min(self.ZOOM_MAX, zoom))
        self.stop_rendering()
        self._layout_pages()
        if anchor is not None:
            page, point = anchor
            for index, _pix, rect in self.canvas._pages:
                if index == page:
                    target = rect.topLeft() + point * self.zoom
                    actual = self.mapToScene(position)
                    self.horizontalScrollBar().setValue(
                        self.horizontalScrollBar().value() + round(target.x() - actual.x()))
                    self.verticalScrollBar().setValue(
                        self.verticalScrollBar().value() + round(target.y() - actual.y()))
                    break
        self._schedule_refine(90)
        self.viewport_changed.emit()

    def _visible_scene_rect(self):
        return self.mapToScene(self.viewport().rect()).boundingRect()

    def _schedule_refine(self, delay=40):
        self._tile_timer.stop()
        self._pending.clear()
        if self._document is not None and self.isVisible():
            self._refine_timer.start(delay)

    def _viewport_moved(self, *_args):
        if self._updating:
            return
        self.viewport().update()
        self.viewport_changed.emit()
        self._schedule_refine()

    def _plan_tiles(self):
        self._pending.clear()
        self._wanted.clear()
        if self._document is None or not self.isVisible():
            return
        exposed = self._visible_scene_rect()
        # Keep small text smooth at fit-page zoom without letting HiDPI or
        # oversized windows create unbounded raster requests.
        supersample = min(2.0, 2.0 / max(1.0, self.zoom))
        ratio = min(max(supersample, self.viewport().devicePixelRatioF()),
                    math.sqrt(VIEWPORT_PIXELS / max(1, exposed.width() * exposed.height())))
        scale = round(self.zoom * ratio, 6)
        requests = []
        for page, _pixmap, rect in self.canvas._pages:
            visible = rect.intersected(exposed)
            if visible.isEmpty():
                continue
            local = QRectF((visible.left() - rect.left()) * ratio,
                           (visible.top() - rect.top()) * ratio,
                           visible.width() * ratio, visible.height() * ratio)
            for y in range(max(0, math.floor(local.top() / TILE_PIXELS)),
                           math.ceil(local.bottom() / TILE_PIXELS)):
                for x in range(max(0, math.floor(local.left() / TILE_PIXELS)),
                               math.ceil(local.right() / TILE_PIXELS)):
                    key = (page, scale, x, y)
                    distance = ((x + 0.5) * TILE_PIXELS - local.center().x()) ** 2 + \
                               ((y + 0.5) * TILE_PIXELS - local.center().y()) ** 2
                    requests.append((distance, key))
        for _distance, key in sorted(requests)[:MAX_VISIBLE_TILES]:
            self._wanted.add(key)
            if key in self._tiles:
                self._tiles.move_to_end(key)
            else:
                self._pending.append(key)
        if self._pending:
            self._tile_timer.start(0)
        self.viewport().update()

    def _render_next_tile(self):
        if not self._pending or self._document is None or not self.isVisible():
            return
        key = self._pending.pop(0)
        page, scale, x, y = key
        if page not in self._page_sizes:
            return
        # One-pixel overlap prevents hairline gaps from rounded clip boundaries.
        clip = ((x * TILE_PIXELS - 1) / scale, (y * TILE_PIXELS - 1) / scale,
                ((x + 1) * TILE_PIXELS + 1) / scale,
                ((y + 1) * TILE_PIXELS + 1) / scale)
        try:
            px, py, w, h, stride, samples = self._document.render_region(page, scale, clip)
            pixmap = QPixmap.fromImage(qimage_from_render(w, h, stride, samples))
        except Exception as error:
            self._pending.clear()
            self.render_failed.emit(str(error))
            return
        tile = (pixmap, QRectF(px / scale, py / scale, w / scale, h / scale))
        cost = pixmap.width() * pixmap.height() * 4
        while self._tiles and self._tile_bytes + cost > TILE_CACHE_BYTES:
            _old_key, (old_pixmap, _rect) = self._tiles.popitem(last=False)
            self._tile_bytes -= old_pixmap.width() * old_pixmap.height() * 4
        self._tiles[key] = tile
        self._tile_bytes += cost
        self.viewport().update()
        if self._pending:
            self._tile_timer.start(1)

    def drawBackground(self, painter, exposed):
        painter.fillRect(exposed, QColor("#e8e8e8"))
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        for page, preview, rect in self.canvas._pages:
            if not rect.intersects(exposed):
                continue
            painter.drawPixmap(rect, preview, QRectF(preview.rect()))
            for key, (pixmap, region) in self._tiles.items():
                if key not in self._wanted or key[0] != page:
                    continue
                target = QRectF(rect.left() + region.x() * self.zoom,
                                 region.y() * self.zoom,
                                 region.width() * self.zoom, region.height() * self.zoom)
                if target.intersects(exposed):
                    painter.save()
                    painter.setClipRect(rect, Qt.IntersectClip)
                    painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
                    painter.restore()
        self.canvas.paint_overlays(painter)

    def _clear_tiles(self):
        self._tiles.clear()
        self._tile_bytes = 0
        self._wanted.clear()

    def stop_rendering(self):
        self._refine_timer.stop()
        self._tile_timer.stop()
        self._pending.clear()

    def clear(self):
        self.stop_rendering()
        self._document = None
        self._previews.clear()
        self._page_sizes.clear()
        self._clear_tiles()
        self.canvas.clear()
        self.setSceneRect(QRectF())
        self.viewport_changed.emit()

    def set_interaction_mode(self, mode):
        self.canvas.set_interaction_mode(mode)

    def _pan_canvas(self, delta):
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())

    def visible_page_rect(self):
        page = self.canvas.active_page_rect()
        visible = page.intersected(self._visible_scene_rect())
        if page.isEmpty() or visible.isEmpty() or visible == page:
            return None
        return QRectF((visible.x() - page.x()) / page.width(),
                      (visible.y() - page.y()) / page.height(),
                      visible.width() / page.width(), visible.height() / page.height())

    def center_on_page_fraction(self, point):
        page = self.canvas.active_page_rect()
        if not page.isEmpty():
            self.centerOn(page.left() + max(0, min(1, point.x())) * page.width(),
                          page.top() + max(0, min(1, point.y())) * page.height())
            self.viewport_changed.emit()

    def ensure_rect_visible(self, rect):
        page = self.canvas.active_page_rect()
        self.ensureVisible(QRectF(page.left() + rect.x() * self.zoom,
                                  page.top() + rect.y() * self.zoom,
                                  rect.width() * self.zoom, rect.height() * self.zoom), 40, 40)

    def _forward_mouse(self, name, event):
        point = self.mapToScene(event.pos())
        proxy = QMouseEvent(event.type(), point, QPointF(event.globalPos()),
                            event.button(), event.buttons(), event.modifiers())
        getattr(self.canvas, name)(proxy)
        event.accept()

    def mousePressEvent(self, event):
        self._forward_mouse("mousePressEvent", event)

    def mouseMoveEvent(self, event):
        self._forward_mouse("mouseMoveEvent", event)

    def mouseReleaseEvent(self, event):
        self._forward_mouse("mouseReleaseEvent", event)

    def mouseDoubleClickEvent(self, event):
        self._forward_mouse("mouseDoubleClickEvent", event)

    def contextMenuEvent(self, event):
        point = self.canvas._activate_at(self.mapToScene(event.pos()))
        if point is not None:
            self.canvas.context_requested.emit(point, event.globalPos())
        event.accept()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if not delta:
            super().wheelEvent(event)
            return
        if event.modifiers() & (Qt.ControlModifier | Qt.AltModifier):
            zoom = (self.zoom * (1.25 if delta > 0 else 0.8)
                    if event.modifiers() & Qt.ControlModifier else
                    round(self.zoom + (0.01 if delta > 0 else -0.01), 2))
            self.preview_zoom(zoom, event.pos())
            self.zoom_changed.emit(self.zoom)
            event.accept()
            return
        bar = self.verticalScrollBar()
        if (delta < 0 and bar.value() >= bar.maximum()) or \
                (delta > 0 and bar.value() <= bar.minimum()):
            self._flip_accum += delta
            if abs(self._flip_accum) >= self.FLIP_THRESHOLD:
                direction = 1 if self._flip_accum < 0 else -1
                self._flip_accum = 0
                self.page_flip.emit(direction)
            event.accept()
        else:
            self._flip_accum = 0
            super().wheelEvent(event)

    def reset_flip(self):
        self._flip_accum = 0

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._verify_gpu)
        self._schedule_refine()

    def hideEvent(self, event):
        self.stop_rendering()
        super().hideEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "canvas"):
            self._viewport_moved()

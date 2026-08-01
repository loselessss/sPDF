"""ViewerMixin — 썸네일/메인뷰/줌/페이지 이동.

렌더 캐시는 현재 페이지 ±2만 유지한다(설계 §3.1). 대용량 스캔본에서
전 페이지를 들고 있으면 RAM이 터지기 때문.
"""

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication

from . import settings
from .widgets import qimage_from_render

CACHE_RADIUS = 2  # 현재 페이지 기준 앞뒤로 유지할 페이지 수
MIN_RENDER_PIXEL_RATIO = 2.0  # 일반 화면도 2배 슈퍼샘플링해 초기 확대 품질 보장


def render_pixel_ratio(widget):
    """레이아웃 전에도 실제 화면 DPR을 반영하고 최소 2배로 렌더한다."""
    ratios = [MIN_RENDER_PIXEL_RATIO, float(widget.devicePixelRatioF())]
    window = widget.window().windowHandle() if widget.window() else None
    if window is not None and window.screen() is not None:
        ratios.append(float(window.screen().devicePixelRatio()))
    app = QApplication.instance()
    if app is not None and app.primaryScreen() is not None:
        ratios.append(float(app.primaryScreen().devicePixelRatio()))
    return max(ratios)


class ViewerMixin:
    def _init_viewer_state(self):
        self.doc = None
        self.page_index = 0
        self._cache = {}  # (page, zoom) -> QImage
        # 썸네일 스크롤 중 매번 렌더하면 버벅이므로 멈춘 뒤 한 번만 그린다.
        self._thumb_timer = QTimer(self)
        self._thumb_timer.setSingleShot(True)
        self._thumb_timer.setInterval(80)
        self._thumb_timer.timeout.connect(self._render_visible_thumbs)
        self._pending_thumbnail_width = None
        self._thumbnail_width_timer = QTimer(self)
        self._thumbnail_width_timer.setSingleShot(True)
        self._thumbnail_width_timer.setInterval(250)
        self._thumbnail_width_timer.timeout.connect(
            self._save_thumbnail_width)

    # --- 페이지 표시 -------------------------------------------------

    def show_page(self, index):
        if self.doc is None:
            return
        index = max(0, min(index, self.doc.page_count - 1))
        self.page_index = index
        self._render_current()
        self._trim_cache()
        if self.thumbs.currentRow() != index:
            self.thumbs.blockSignals(True)
            self.thumbs.setCurrentRow(index)
            self.thumbs.blockSignals(False)
        self._update_page_label()

    def _render_current(self):
        pixel_ratio = render_pixel_ratio(self.view)
        key = (
            self.page_index,
            round(self.view.zoom, 3),
            round(pixel_ratio, 2),
        )
        img = self._cache.get(key)
        if img is None:
            img = qimage_from_render(
                *self.doc.render(self.page_index, self.view.zoom * pixel_ratio),
                device_pixel_ratio=pixel_ratio,
            )
            self._cache[key] = img
        self.view.set_image(img)

    def _trim_cache(self):
        """현재 페이지에서 멀어진 렌더는 버린다 — 메모리 상한 유지."""
        lo, hi = self.page_index - CACHE_RADIUS, self.page_index + CACHE_RADIUS
        for key in [k for k in self._cache if not (lo <= k[0] <= hi)]:
            del self._cache[key]

    def on_zoom_changed(self, _zoom):
        if self.doc is None:
            return
        # 줌이 바뀌면 이전 배율 캐시는 쓸모없다.
        self._cache.clear()
        self._render_current()
        self._update_page_label()

    def set_zoom(self, zoom):
        zoom = round(max(self.view.ZOOM_MIN,
                         min(self.view.ZOOM_MAX, zoom)) * 100) / 100.0
        if zoom == self.view.zoom:
            self._update_page_label()
            return
        self.view.zoom = zoom
        self.on_zoom_changed(zoom)

    def zoom_in(self):
        self.set_zoom(self.view.zoom * 1.25)

    def zoom_out(self):
        self.set_zoom(self.view.zoom / 1.25)

    def zoom_in_fine(self):
        self.set_zoom(self.view.zoom + 0.01)

    def zoom_out_fine(self):
        self.set_zoom(self.view.zoom - 0.01)

    def _set_fit_zoom(self, index):
        """렌더 없이 줌 값만 창 너비에 맞춘다 — 문서를 열 때 이걸로 먼저
        배율을 정한 뒤 show_page를 부르면 첫 페이지를 한 번만 렌더한다
        (예전엔 zoom 1.0으로 그리고 fit으로 또 그려서 두 배로 느렸다)."""
        pw, _ = self.doc.page_size(index)
        avail = self.view.viewport().width() - 24  # 여백/스크롤바 몫
        if pw > 0 and avail > 0:
            self.view.zoom = max(self.view.ZOOM_MIN,
                                 min(self.view.ZOOM_MAX, avail / pw))

    def zoom_fit(self):
        """창 너비에 맞춘다."""
        if self.doc is None:
            return
        self._set_fit_zoom(self.page_index)
        self.on_zoom_changed(self.view.zoom)

    def finish_initial_layout(self, document):
        """창 배치가 끝난 실제 폭으로 맞춤 배율과 HiDPI 이미지를 확정한다."""
        if self.doc is not document or self.doc is None:
            return
        old_zoom = self.view.zoom
        self._set_fit_zoom(self.page_index)
        if self.view.zoom != old_zoom:
            self._cache.clear()
        self._render_current()
        self._update_page_label()
        self.update_thumbnail_viewport_marker()

    def refresh_page(self, index):
        """페이지 내용이 바뀌었을 때(주석 등) 렌더 캐시와 썸네일을 무효화."""
        for key in [k for k in self._cache if k[0] == index]:
            del self._cache[key]
        if index == self.page_index:
            self._render_current()
        self.thumbs.invalidate(index)
        self._schedule_thumbs()

    def next_page(self):
        self.show_page(self.page_index + 1)

    def prev_page(self):
        self.show_page(self.page_index - 1)

    # --- 썸네일 ------------------------------------------------------

    def _schedule_thumbs(self):
        self._thumb_timer.start()

    def _render_visible_thumbs(self):
        """보이는 항목 중 아직 안 그린 것만 렌더(레이지, 설계 §3.1)."""
        if self.doc is None:
            return
        width = self.thumbs.thumbnail_width()
        for row in self.thumbs.visible_rows():
            if self.thumbs.is_rendered(row, width):
                continue
            pw, _ = self.doc.page_size(row)
            zoom = width / pw if pw else 0.2
            pixel_ratio = render_pixel_ratio(self.thumbs)
            self.thumbs.set_thumb(
                row,
                qimage_from_render(
                    *self.doc.render(row, zoom * pixel_ratio),
                    device_pixel_ratio=pixel_ratio,
                ),
                rendered_width=width,
            )
        self.update_thumbnail_viewport_marker()

    def on_thumbnail_width_changed(self, _width):
        """기존 아이콘은 유지하고 리사이즈가 멈추면 새 폭으로 교체한다."""
        self._schedule_thumbs()

    def update_thumbnail_viewport_marker(self):
        if self.doc is None:
            self.thumbs.set_viewport_marker(-1, None)
            return
        self.thumbs.set_viewport_marker(
            self.page_index, self.view.visible_page_rect())

    def on_thumbnail_splitter_moved(self, _pos, index):
        """사용자가 놓은 썸네일 패널 너비를 잦은 디스크 쓰기 없이 기억한다."""
        if index != 1:
            return
        self._pending_thumbnail_width = self.thumbs.width()
        self._thumbnail_width_timer.start()

    def _save_thumbnail_width(self):
        if self._pending_thumbnail_width is None:
            return
        settings.set_thumbnail_width(self._pending_thumbnail_width)
        self._pending_thumbnail_width = None

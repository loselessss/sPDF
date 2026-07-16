"""ViewerMixin — 썸네일/메인뷰/줌/페이지 이동.

렌더 캐시는 현재 페이지 ±2만 유지한다(설계 §3.1). 대용량 스캔본에서
전 페이지를 들고 있으면 RAM이 터지기 때문.
"""

from PyQt5.QtCore import Qt, QTimer

from .widgets import THUMB_W, qimage_from_render

CACHE_RADIUS = 2  # 현재 페이지 기준 앞뒤로 유지할 페이지 수


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
        key = (self.page_index, round(self.view.zoom, 3))
        img = self._cache.get(key)
        if img is None:
            img = qimage_from_render(*self.doc.render(self.page_index, self.view.zoom))
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
        self.view.zoom = zoom
        self.on_zoom_changed(zoom)

    def zoom_in(self):
        self.set_zoom(min(self.view.ZOOM_MAX, self.view.zoom * 1.25))

    def zoom_out(self):
        self.set_zoom(max(self.view.ZOOM_MIN, self.view.zoom / 1.25))

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
        for row in self.thumbs.visible_rows():
            if self.thumbs.is_rendered(row):
                continue
            pw, _ = self.doc.page_size(row)
            zoom = THUMB_W / pw if pw else 0.2
            self.thumbs.set_thumb(row, qimage_from_render(*self.doc.render(row, zoom)))

"""TextSelectMixin — 텍스트 선택/복사(§3.2) + 검색(Ctrl+F). v0.2.

단어 좌표는 페이지당 한 번만 뽑아 캐시한다 — 드래그 중 매 이벤트마다
get_text를 부르면 큰 페이지에서 버벅인다.
"""

from PyQt5.QtCore import QRectF
from PyQt5.QtWidgets import QApplication


class TextSelectMixin:
    def _init_textsel_state(self):
        self._words_cache = {}   # page -> word 목록
        self._selected = []      # 현재 선택된 word 튜플들
        self._search_query = ""
        self._search_hits = []   # (page, QRectF) 목록
        self._search_pos = -1

    def _reset_textsel(self):
        self._words_cache.clear()
        self._selected = []
        self._search_query = ""
        self._search_hits = []
        self._search_pos = -1

    # --- 페이지 전환 훅 ------------------------------------------------

    def show_page(self, index):
        # MRO상 ViewerMixin.show_page가 실제 표시를 한 뒤, 이 페이지에
        # 해당하는 오버레이(선택은 초기화, 검색은 재적용)를 얹는다.
        super().show_page(index)
        self._clear_selection()
        self._apply_search_overlay()

    # --- 선택 ----------------------------------------------------------

    def _page_words(self, page):
        ws = self._words_cache.get(page)
        if ws is None:
            ws = self.doc.words(page) if self.doc else []
            self._words_cache[page] = ws
        return ws

    def on_drag_selected(self, start, end):
        """드래그 사각형과 교차하는 단어를 선택(설계 §3.2)."""
        if self.doc is None:
            return
        rect = QRectF(start, end).normalized()
        self._selected = [
            w for w in self._page_words(self.page_index)
            if rect.intersects(QRectF(w[0], w[1], w[2] - w[0], w[3] - w[1]))
        ]
        self._show_selection()

    def on_word_picked(self, pt):
        """더블클릭 — 그 지점의 단어 하나 선택."""
        if self.doc is None:
            return
        self._selected = [
            w for w in self._page_words(self.page_index)
            if w[0] <= pt.x() <= w[2] and w[1] <= pt.y() <= w[3]
        ]
        self._show_selection()

    def select_all(self):
        if self.doc is None:
            return
        self._selected = list(self._page_words(self.page_index))
        self._show_selection()

    def _show_selection(self):
        self.view.canvas.set_selection(
            [QRectF(w[0], w[1], w[2] - w[0], w[3] - w[1]) for w in self._selected])
        n = len(self._selected)
        if n:
            self.statusBar().showMessage("%d개 단어 선택 — Ctrl+C로 복사" % n, 3000)
        elif self.doc is not None and not self.doc.has_text(self.page_index):
            self.statusBar().showMessage(
                "이 페이지에는 텍스트 레이어가 없습니다 (스캔본) — OCR 필요", 3000)

    def _clear_selection(self):
        self._selected = []
        self.view.canvas.set_selection([])

    def copy_selection(self):
        if not self._selected:
            return
        # (block, line) 단위로 묶어 원문 줄바꿈을 복원한다. words()가
        # 읽기 순서로 오므로 정렬은 그 순서를 따른다.
        ws = sorted(self._selected, key=lambda w: (w[5], w[6], w[7]))
        lines, cur_key, cur = [], None, []
        for w in ws:
            key = (w[5], w[6])
            if key != cur_key and cur:
                lines.append(" ".join(cur))
                cur = []
            cur_key = key
            cur.append(w[4])
        if cur:
            lines.append(" ".join(cur))
        text = "\n".join(lines)
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage("복사됨 (%d자)" % len(text), 3000)

    # --- 검색 ----------------------------------------------------------

    def search_start(self, query):
        """새 검색 — 전체 페이지에서 일치 목록을 만들고 현재 페이지
        이후의 첫 결과로 이동. 같은 질의로 다시 부르면 다음 결과로."""
        query = query.strip()
        if not query or self.doc is None:
            return
        if query == self._search_query and self._search_hits:
            self.search_next()
            return
        self._search_query = query
        self._search_hits = []
        for p in range(self.doc.page_count):
            for x0, y0, x1, y1 in self.doc.search(p, query):
                self._search_hits.append((p, QRectF(x0, y0, x1 - x0, y1 - y0)))
        if not self._search_hits:
            self._search_pos = -1
            self._apply_search_overlay()
            self._update_search_count()
            self.statusBar().showMessage("검색 결과 없음: %s" % query, 3000)
            return
        # 현재 페이지 이후의 첫 결과부터 (없으면 처음으로 감기)
        self._search_pos = 0
        for i, (p, _r) in enumerate(self._search_hits):
            if p >= self.page_index:
                self._search_pos = i
                break
        self._goto_hit()

    def search_next(self):
        if self._search_hits:
            self._search_pos = (self._search_pos + 1) % len(self._search_hits)
            self._goto_hit()

    def search_prev(self):
        if self._search_hits:
            self._search_pos = (self._search_pos - 1) % len(self._search_hits)
            self._goto_hit()

    def search_clear(self):
        self._search_query = ""
        self._search_hits = []
        self._search_pos = -1
        self._apply_search_overlay()
        self._update_search_count()

    def _goto_hit(self):
        page, rect = self._search_hits[self._search_pos]
        if page != self.page_index:
            self.show_page(page)  # 안에서 _apply_search_overlay가 불린다
        else:
            self._apply_search_overlay()
        self.view.ensure_rect_visible(rect)
        self._update_search_count()

    def _apply_search_overlay(self):
        """현재 페이지의 검색 일치를 오버레이로 — 현재 항목은 다른 색."""
        rects = [r for p, r in self._search_hits if p == self.page_index]
        cur = None
        if 0 <= self._search_pos < len(self._search_hits):
            p, r = self._search_hits[self._search_pos]
            if p == self.page_index:
                cur = r
        self.view.canvas.set_search(rects, cur)

    def _update_search_count(self):
        # 검색바의 "n/N" 라벨 — app.py가 만들어둔다.
        if not self._search_hits:
            self._search_count.setText("0건")
        else:
            self._search_count.setText(
                "%d / %d" % (self._search_pos + 1, len(self._search_hits)))

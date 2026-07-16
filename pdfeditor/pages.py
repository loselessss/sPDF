"""PagesMixin — 페이지 회전/삭제/순서변경/병합/추출(설계 §3.5).

되돌리기는 EditMixin의 스냅샷 스택을 그대로 쓴다(_push_undo) — 구조
변경도 문서 전체 스냅샷이므로 같은 방식으로 되돌아간다.
"""

import os

from PyQt5.QtWidgets import QFileDialog, QMessageBox


class PagesMixin:
    # --- 회전 ----------------------------------------------------------

    def rotate_page_cw(self):
        self._rotate(90)

    def rotate_page_ccw(self):
        self._rotate(-90)

    def _rotate(self, deg):
        if self.doc is None:
            return
        self._push_undo()
        self.doc.rotate_page(self.page_index, deg)
        self._after_page_content_changed()
        self.mark_dirty()
        # 회전하면 페이지 비율이 바뀌므로 창 너비 맞춤을 다시 계산
        self.zoom_fit()

    # --- 삭제 ----------------------------------------------------------

    def delete_current_page(self):
        if self.doc is None:
            return
        if self.doc.page_count <= 1:
            QMessageBox.information(
                self, "삭제 불가", "마지막 한 페이지는 삭제할 수 없습니다.")
            return
        ret = QMessageBox.question(
            self, "페이지 삭제",
            "%d쪽을 삭제할까요? (Ctrl+Z로 되돌릴 수 있습니다)"
            % (self.page_index + 1))
        if ret != QMessageBox.Yes:
            return
        self._push_undo()
        self.doc.delete_page(self.page_index)
        self._after_structure_changed(keep_page=self.page_index)
        self.mark_dirty()

    # --- 순서 변경 (썸네일 드래그) ---------------------------------------

    def on_thumb_moved(self, src, dst):
        """썸네일을 드래그해 순서를 바꿨을 때 — 문서에 실제로 반영."""
        if self.doc is None or src == dst:
            return
        self._push_undo()
        self.doc.move_page(src, dst)
        self._after_structure_changed(keep_page=dst)
        self.mark_dirty()
        self.statusBar().showMessage(
            "%d쪽 → %d쪽으로 이동" % (src + 1, dst + 1), 3000)

    # --- 병합 / 추출 -----------------------------------------------------

    def merge_pdf(self):
        if self.doc is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "병합할 PDF 선택", "", "PDF 파일 (*.pdf)")
        if not path:
            return
        # 현재 페이지 '뒤'에 끼워넣는 게 직관적
        at = self.page_index + 1
        self._push_undo()
        try:
            n = self.doc.insert_pdf(path, at=at)
        except Exception as e:
            self._undo_stack.pop()  # 실패했으니 방금 찍은 스냅샷은 버린다
            QMessageBox.critical(
                self, "병합 실패", "PDF를 병합할 수 없습니다.\n\n%s" % e)
            return
        self._after_structure_changed(keep_page=at)
        self.mark_dirty()
        self.statusBar().showMessage(
            "%s — %d페이지 병합됨" % (os.path.basename(path), n), 5000)

    def extract_current_page(self):
        """현재 페이지만 새 PDF로 저장 — 원본은 그대로."""
        if self.doc is None:
            return
        base = os.path.splitext(os.path.basename(self.doc.path))[0]
        suggest = os.path.join(os.path.dirname(self.doc.path),
                               "%s_p%d.pdf" % (base, self.page_index + 1))
        path, _ = QFileDialog.getSaveFileName(
            self, "현재 페이지 추출", suggest, "PDF 파일 (*.pdf)")
        if not path:
            return
        try:
            self.doc.extract_pages([self.page_index], path)
        except Exception as e:
            QMessageBox.critical(
                self, "추출 실패", "저장할 수 없습니다.\n\n%s" % e)
            return
        self.statusBar().showMessage("추출됨: %s" % path, 5000)

    # --- 구조 변경 후 갱신 -------------------------------------------------

    def _after_structure_changed(self, keep_page=0):
        """페이지 수/순서가 바뀐 뒤 — 썸네일을 다시 만들고 위치를 보정한다.

        _after_page_content_changed(내용만 바뀜)와 달리 썸네일 목록 자체를
        새로 만들어야 한다.
        """
        self._cache.clear()
        self._words_cache.clear()
        if hasattr(self, "_annot_cache"):
            self._annot_cache.clear()
        # 검색 결과는 페이지 번호가 어긋나므로 버린다(좌표가 안 맞음)
        self.search_clear()

        count = self.doc.page_count
        self.thumbs.blockSignals(True)
        self.thumbs.reset_pages(count)
        self.thumbs.blockSignals(False)
        self.show_page(max(0, min(keep_page, count - 1)))
        self._schedule_thumbs()
        if hasattr(self, "_notes_dock") and self._notes_dock.isVisible():
            self._rebuild_notes_list()

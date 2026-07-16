"""재사용 위젯 — PageCanvas/PageView(메인 페이지 뷰), ThumbList(썸네일)."""

from PyQt5.QtCore import Qt, QPointF, QRectF, QSize, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QScrollArea, QWidget

THUMB_W = 120  # 썸네일 가로 픽셀

# 오버레이 색 — 선택은 파랑, 검색은 노랑, 현재 검색 항목은 주황
SEL_COLOR = QColor(0, 120, 215, 70)
SEARCH_COLOR = QColor(255, 200, 0, 80)
SEARCH_CUR_COLOR = QColor(255, 120, 0, 110)
EDIT_BOX_COLOR = QColor(0, 160, 90, 160)  # 편집 가능한 span 테두리(초록)


def qimage_from_render(w, h, stride, samples):
    """core.Document.render() 결과를 QImage로.

    copy()가 필요한 이유: samples는 PyMuPDF가 소유한 버퍼라 pixmap이
    해제되면 사라진다. QImage는 기본적으로 버퍼를 참조만 하므로 복사본을
    쥐고 있어야 나중에 그릴 때 깨지지 않는다.
    """
    return QImage(samples, w, h, stride, QImage.Format_RGB888).copy()


class PageCanvas(QWidget):
    """페이지 비트맵 + 선택/검색 하이라이트 오버레이.

    오버레이 좌표는 전부 PDF 좌표계(zoom=1)로 저장한다 — 줌이 바뀌어도
    그릴 때만 배율을 곱하면 되므로 하이라이트가 그대로 유지된다.
    """

    drag_selected = pyqtSignal(QPointF, QPointF)  # 드래그 시작/현재 (PDF 좌표)
    selection_cleared = pyqtSignal()
    word_picked = pyqtSignal(QPointF)   # 더블클릭 지점 (PDF 좌표)
    clicked = pyqtSignal(QPointF)       # 드래그 없는 단순 클릭 (메모 배치/열기)
    context_requested = pyqtSignal(QPointF, object)  # (PDF 좌표, 전역 좌표)
    hovered = pyqtSignal(QPointF, object)  # 마우스 이동 (메모 툴팁용)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pix = None
        self.zoom = 1.0
        self._sel_rects = []
        self._search_rects = []
        self._search_cur = None
        self._edit_boxes = []
        self._drag_start = None
        self._dragged = False
        self.setCursor(Qt.IBeamCursor)
        self.setMouseTracking(True)  # 버튼 안 눌러도 hovered가 오도록

    # --- 표시 내용 ----------------------------------------------------

    def set_image(self, img, zoom):
        self._pix = QPixmap.fromImage(img)
        self.zoom = zoom
        self.resize(self._pix.size())
        self.update()

    def clear(self):
        self._pix = None
        self._sel_rects = []
        self._search_rects = []
        self._search_cur = None
        self._edit_boxes = []
        self.resize(QSize(0, 0))
        self.update()

    def set_selection(self, rects):
        self._sel_rects = rects
        self.update()

    def set_search(self, rects, current=None):
        self._search_rects = rects
        self._search_cur = current
        self.update()

    def set_edit_boxes(self, rects):
        self._edit_boxes = rects
        self.update()

    def paintEvent(self, _ev):
        if self._pix is None:
            return
        p = QPainter(self)
        p.drawPixmap(0, 0, self._pix)
        p.setPen(Qt.NoPen)
        z = self.zoom
        for rects, color in ((self._search_rects, SEARCH_COLOR),
                             (self._sel_rects, SEL_COLOR)):
            p.setBrush(color)
            for r in rects:
                p.drawRect(QRectF(r.x() * z, r.y() * z, r.width() * z, r.height() * z))
        if self._search_cur is not None:
            r = self._search_cur
            p.setBrush(SEARCH_CUR_COLOR)
            p.drawRect(QRectF(r.x() * z, r.y() * z, r.width() * z, r.height() * z))
        # 편집 가능한 span은 채우지 않고 테두리만 그린다(글자를 가리지 않게)
        if self._edit_boxes:
            p.setBrush(Qt.NoBrush)
            p.setPen(EDIT_BOX_COLOR)
            for r in self._edit_boxes:
                p.drawRect(QRectF(r.x() * z, r.y() * z, r.width() * z, r.height() * z))
        p.end()

    # --- 마우스 → PDF 좌표 --------------------------------------------

    def _to_page(self, pos):
        return QPointF(pos.x() / self.zoom, pos.y() / self.zoom)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and self._pix is not None:
            self._drag_start = self._to_page(ev.pos())
            self._dragged = False
            self.selection_cleared.emit()

    def mouseMoveEvent(self, ev):
        if self._drag_start is not None:
            self._dragged = True
            self.drag_selected.emit(self._drag_start, self._to_page(ev.pos()))
        elif self._pix is not None:
            self.hovered.emit(self._to_page(ev.pos()), ev.globalPos())

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            # 드래그 없이 눌렀다 뗀 것만 '클릭' — 선택 드래그와 구분한다.
            if self._drag_start is not None and not self._dragged:
                self.clicked.emit(self._to_page(ev.pos()))
            self._drag_start = None

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.LeftButton and self._pix is not None:
            self.word_picked.emit(self._to_page(ev.pos()))

    def contextMenuEvent(self, ev):
        if self._pix is not None:
            self.context_requested.emit(self._to_page(ev.pos()), ev.globalPos())


class PageView(QScrollArea):
    """PageCanvas를 감싸는 스크롤 영역. 줌은 Ctrl+휠.

    setWidgetResizable(False)여야 한다 — True면 스크롤 영역이 캔버스
    크기를 뷰포트에 맞춰버려서, 확대 시 이미지가 잘리고 스크롤바가 안
    생긴다. 크기는 캔버스가 이미지에 맞춰 스스로 정한다.
    """

    zoom_changed = pyqtSignal(float)
    page_flip = pyqtSignal(int)  # +1 다음 장, -1 이전 장

    ZOOM_MIN, ZOOM_MAX = 0.1, 8.0
    # 마우스 휠 한 칸 = 120. 트랙패드는 잘게 쪼개 보내므로 누적해서 이 값을
    # 넘을 때만 페이지를 넘긴다(안 그러면 트랙패드에서 몇 장씩 훌쩍 넘어감).
    FLIP_THRESHOLD = 120

    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = PageCanvas()
        self.setWidget(self.canvas)
        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignCenter)
        self.zoom = 1.0
        self._flip_accum = 0

    def set_image(self, img):
        self.canvas.set_image(img, self.zoom)

    def clear(self):
        self.canvas.clear()

    def ensure_rect_visible(self, rect):
        """PDF 좌표 rect가 보이도록 스크롤."""
        z = self.zoom
        cx = int((rect.x() + rect.width() / 2) * z)
        cy = int((rect.y() + rect.height() / 2) * z)
        self.ensureVisible(cx, cy, 120, 120)

    def wheelEvent(self, ev):
        # Ctrl+휠은 줌.
        if ev.modifiers() & Qt.ControlModifier:
            step = 1.25 if ev.angleDelta().y() > 0 else 1 / 1.25
            new = max(self.ZOOM_MIN, min(self.ZOOM_MAX, self.zoom * step))
            if new != self.zoom:
                self.zoom = new
                self.zoom_changed.emit(new)
            ev.accept()
            return

        dy = ev.angleDelta().y()
        bar = self.verticalScrollBar()
        at_top = bar.value() <= bar.minimum()
        at_bottom = bar.value() >= bar.maximum()

        # 페이지가 스크롤 여지가 있으면(확대 상태) 먼저 그 방향으로 스크롤하고,
        # 끝(위/아래)에 닿아 있을 때만 페이지를 넘긴다. 확대 안 된 상태는
        # min==max라 at_top·at_bottom이 둘 다 참이므로 바로 넘어간다.
        if (dy < 0 and at_bottom) or (dy > 0 and at_top):
            # dy<0(아래로) → 다음 장, dy>0(위로) → 이전 장. 부호대로 누적.
            self._flip_accum += dy
            if self._flip_accum <= -self.FLIP_THRESHOLD:
                self.page_flip.emit(1)
                self._flip_accum = 0
            elif self._flip_accum >= self.FLIP_THRESHOLD:
                self.page_flip.emit(-1)
                self._flip_accum = 0
            ev.accept()
        else:
            self._flip_accum = 0  # 도중에 방향을 틀면 누적 초기화
            super().wheelEvent(ev)

    def reset_flip(self):
        """페이지가 바뀌면 누적 초기화 — 다음 장에서 곧바로 또 넘어가지 않게."""
        self._flip_accum = 0


class ThumbList(QListWidget):
    """썸네일 사이드바. 렌더는 하지 않고 자리만 잡아둔다 — 실제 그림은
    ViewerMixin이 화면에 보이는 항목만 채운다(레이지 렌더, 설계 §3.1).

    드래그로 순서 변경 가능 — 실제 문서 반영은 page_moved 시그널을 받은
    PagesMixin이 한다."""

    page_selected = pyqtSignal(int)
    page_moved = pyqtSignal(int, int)  # (원래 행, 옮긴 행)

    # 뷰포트 크기를 모를 때(레이아웃 전) 렌더할 최대 항목 수 — 여기서
    # count-1까지 그려버리면 대용량 PDF에서 전 페이지를 렌더하게 된다.
    FALLBACK_WINDOW = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(THUMB_W + 40)
        self.setIconSize(QSize(THUMB_W, int(THUMB_W * 1.5)))
        self.setSpacing(4)
        self.setDragDropMode(QListWidget.InternalMove)
        self.currentRowChanged.connect(self._on_row)
        self._drag_src = None

    def _on_row(self, row):
        if row >= 0:
            self.page_selected.emit(row)

    def dropEvent(self, ev):
        # 드롭 전 현재 행을 기억했다가, Qt가 항목을 옮긴 뒤 새 위치를 읽어
        # page_moved를 쏜다. 실제 재정렬은 문서를 바꾼 뒤 reset_pages로
        # 다시 그리므로, 여기서 Qt가 만든 시각적 이동은 임시로만 쓴다.
        # 시그널 방출은 이 dropEvent가 끝난 다음으로 미룬다 — 핸들러가
        # reset_pages로 이 위젯을 재구성하는데 그걸 드롭 처리 도중에 하면
        # Qt 내부 상태와 충돌한다.
        src = self.currentRow()
        super().dropEvent(ev)
        dst = self.currentRow()
        if src >= 0 and dst >= 0 and src != dst:
            QTimer.singleShot(0, lambda: self.page_moved.emit(src, dst))

    def reset_pages(self, count):
        """페이지 수만큼 빈 항목 생성 — 아이콘은 나중에 채워진다."""
        self.clear()
        for i in range(count):
            it = QListWidgetItem("%d" % (i + 1))
            it.setTextAlignment(Qt.AlignHCenter | Qt.AlignBottom)
            it.setData(Qt.UserRole, False)  # 렌더 완료 여부
            self.addItem(it)

    def visible_rows(self):
        """현재 화면에 보이는 항목 행 번호 — 이 범위만 렌더하면 된다."""
        if self.count() == 0:
            return []
        top = self.indexAt(self.viewport().rect().topLeft()).row()
        bot = self.indexAt(self.viewport().rect().bottomLeft()).row()
        if top < 0:
            top = 0
        if bot < 0:
            # 레이아웃 전이라 판단 불가 — 상한을 두지 않으면 전 페이지 렌더.
            bot = min(top + self.FALLBACK_WINDOW, self.count() - 1)
        return list(range(top, min(bot + 2, self.count())))

    def set_thumb(self, row, img):
        it = self.item(row)
        if it is not None:
            it.setIcon(QIcon(QPixmap.fromImage(img)))
            it.setData(Qt.UserRole, True)

    def is_rendered(self, row):
        it = self.item(row)
        return bool(it and it.data(Qt.UserRole))

    def invalidate(self, row):
        """페이지 내용이 바뀌었을 때(주석 추가 등) 다시 그리게 표시."""
        it = self.item(row)
        if it is not None:
            it.setData(Qt.UserRole, False)

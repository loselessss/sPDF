"""편집 시작 화면과 별도 대화상자에서 재사용하는 페이지 구성 패널.

현재 문서의 페이지를 여러 장 선택해 한 묶음으로 옮기거나, 드래그한 한
장만 옮길 수 있다. 외부 PDF/PDF 호환 Illustrator 파일은 목록의 원하는
위치에 드롭해 삽입한다.
썸네일은 화면에 보이는 항목만 렌더해 큰 문서에서도 메모리를 제한한다.
"""

import json
from PyQt5.QtCore import (
    QByteArray, QItemSelectionModel, QMimeData, QPoint, QSize, Qt, QTimer, pyqtSignal,
)
from PyQt5.QtGui import QColor, QDrag, QIcon, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView, QButtonGroup, QDialog, QFileDialog, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QRadioButton, QVBoxLayout, QWidget,
)

from .i18n import localize, tr

from .widgets import qimage_from_render
from .icons import fluent_icon
from .filetypes import DOCUMENT_OPEN_FILTER, is_supported_document


PAGE_MIME = "application/x-spdf-page-indices"
THUMB_WIDTH = 150


class PageOrganizerList(QListWidget):
    FALLBACK_WINDOW = 10

    def __init__(self, dialog, *, grid=False):
        super().__init__(dialog)
        self.dialog = dialog
        self.grid = grid
        self._drop_at = None
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setIconSize(QSize(THUMB_WIDTH, int(THUMB_WIDTH * 1.42)))
        self.setSpacing(6)
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        if grid:
            self.setObjectName("pageOverviewList")
            self.setViewMode(QListWidget.IconMode)
            self.setFlow(QListWidget.LeftToRight)
            self.setWrapping(True)
            self.setResizeMode(QListWidget.Adjust)
            self.setMovement(QListWidget.Static)
            # Static keeps the cards aligned, but also disables dragging in Qt.
            # Re-enable our document-order drag handler after setting movement.
            self.setDragEnabled(True)
            self.setAcceptDrops(True)
            self.setGridSize(QSize(190, 260))
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.setStyleSheet(
                "QListWidget#pageOverviewList { background: #f2f5f8; border: 0; }"
                "QListWidget#pageOverviewList::item { border-radius: 6px; }"
                "QListWidget#pageOverviewList::item:selected {"
                " background: #dcecf9; border: 2px solid #0078d4; color: #202020; }")

    def reset_pages(self, count):
        """페이지 수만큼 크기가 고정된 빈 썸네일 항목을 만든다."""
        self.clear()
        item_size = QSize(
            THUMB_WIDTH + 20,
            self.iconSize().height() + 30,
        )
        for index in range(count):
            item = QListWidgetItem(tr("%d페이지" % (index + 1)))
            item.setTextAlignment(Qt.AlignHCenter)
            item.setSizeHint(item_size)
            item.setData(Qt.UserRole, False)
            self.addItem(item)

    def visible_rows(self):
        """여백을 제외하고 실제 뷰포트에 걸친 썸네일 행을 반환한다."""
        if self.count() == 0:
            return []
        if self.grid:
            # Sample viewport cells, not all document pages. Include one nearby
            # grid row so partially visible cards and spacing are covered.
            rect = self.viewport().rect()
            dx, dy = self.gridSize().width() // 2, self.gridSize().height() // 2
            rows = set()
            for y in [*range(0, rect.height(), max(1, dy)), rect.bottom()]:
                for x in [*range(0, rect.width(), max(1, dx)), rect.right()]:
                    row = self.indexAt(QPoint(x, y)).row()
                    if row >= 0:
                        rows.add(row)
            if not rows:
                return []
            columns = max(1, rect.width() // self.gridSize().width())
            return list(range(max(0, min(rows) - columns),
                              min(self.count(), max(rows) + columns + 1)))
        top = self._row_near_viewport_edge(True)
        bottom = self._row_near_viewport_edge(False)
        if top < 0:
            top = 0
        if bottom < 0:
            bottom = min(top + self.FALLBACK_WINDOW - 1, self.count() - 1)
        return list(range(top, min(bottom + 2, self.count())))

    def _row_near_viewport_edge(self, from_top):
        """x=0의 좌우 여백을 피해 중앙에서 가장자리의 행을 찾는다."""
        rect = self.viewport().rect()
        x = rect.center().x()
        positions = (
            range(rect.top(), rect.bottom() + 1)
            if from_top else
            range(rect.bottom(), rect.top() - 1, -1)
        )
        for y in positions:
            row = self.indexAt(QPoint(x, y)).row()
            if row >= 0:
                return row
        return -1

    def _request_visible_thumbnails(self):
        if self.dialog is not None:
            self.dialog._schedule_thumbnails()

    def showEvent(self, event):
        super().showEvent(event)
        self._request_visible_thumbnails()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._request_visible_thumbnails()

    def startDrag(self, _actions):
        row = self.currentRow()
        if row < 0:
            return
        if self.dialog.group_mode.isChecked():
            rows = sorted(self.row(item) for item in self.selectedItems())
            if row not in rows:
                rows = [row]
        else:
            rows = [row]
        mime = QMimeData()
        mime.setData(PAGE_MIME, QByteArray(json.dumps(rows).encode("ascii")))
        drag = QDrag(self)
        drag.setMimeData(mime)
        item = self.item(row)
        if item and not item.icon().isNull():
            drag.setPixmap(item.icon().pixmap(self.iconSize()))
        drag.exec_(Qt.MoveAction)

    @staticmethod
    def _pdf_paths(mime):
        if not mime.hasUrls():
            return []
        paths = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
        return [path for path in paths if is_supported_document(path)]

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(PAGE_MIME) or self._pdf_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(PAGE_MIME) or self._pdf_paths(event.mimeData()):
            self._drop_at = self._insertion_index(event.pos())
            self.viewport().update()
            event.acceptProposedAction()
        else:
            event.ignore()

    def _insertion_index(self, pos):
        item = self.itemAt(pos)
        if item is None:
            if self.grid:
                # Grid gaps belong to the adjacent card, not always the end.
                for row in self.visible_rows():
                    rect = self.visualItemRect(self.item(row))
                    if rect.top() <= pos.y() <= rect.bottom():
                        if pos.x() < rect.center().x():
                            return row
                        if pos.x() <= rect.right() + self.spacing():
                            return row + 1
            return self.count()
        row = self.row(item)
        rect = self.visualItemRect(item)
        if (pos.x() > rect.center().x() if self.grid else pos.y() > rect.center().y()):
            row += 1
        return row

    def dragLeaveEvent(self, event):
        self._drop_at = None
        self.viewport().update()
        super().dragLeaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.grid or self._drop_at is None or not self.count():
            return
        row = min(self._drop_at, self.count() - 1)
        rect = self.visualItemRect(self.item(row))
        x = rect.right() + 3 if self._drop_at == self.count() else rect.left() - 3
        painter = QPainter(self.viewport())
        painter.setPen(QPen(QColor("#0078d4"), 3))
        painter.drawLine(x, rect.top(), x, rect.bottom())
        painter.end()

    def keyPressEvent(self, event):
        if self.grid and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.dialog.open_selected_page()
            event.accept()
            return
        super().keyPressEvent(event)

    def dropEvent(self, event):
        self._drop_at = None
        self.viewport().update()
        at = self._insertion_index(event.pos())
        mime = event.mimeData()
        if mime.hasFormat(PAGE_MIME):
            if event.source() is not None and event.source() is not self:
                event.ignore()
                return
            try:
                rows = json.loads(bytes(mime.data(PAGE_MIME)).decode("ascii"))
            except (ValueError, UnicodeDecodeError):
                event.ignore()
                return
            if not isinstance(rows, list) or not all(type(row) is int for row in rows):
                event.ignore()
                return
            if self.dialog.move_pages(rows, at):
                event.setDropAction(Qt.MoveAction)
                event.accept()
            else:
                event.ignore()
            return
        paths = self._pdf_paths(mime)
        if paths and self.dialog.insert_pdfs(paths, at):
            event.acceptProposedAction()
        else:
            event.ignore()


class PageOrganizerPanel(QWidget):
    page_activated = pyqtSignal(int)
    close_requested = pyqtSignal()

    def __init__(self, host, *, grid=False):
        super().__init__(host)
        self.host = host
        self.grid = grid
        self._rendered_rows = set()
        self._thumbnail_timer = QTimer(self)
        self._thumbnail_timer.setSingleShot(True)
        self._thumbnail_timer.timeout.connect(self._render_visible_thumbnails)

        layout = QVBoxLayout(self)
        description = QLabel(localize(
            "Drag pages to reorder. Double-click a page to edit it. Drop PDFs to insert.",
            "페이지를 끌어 순서를 바꾸고, 두 번 눌러 상세 편집하세요. 외부 PDF도 끌어 넣을 수 있습니다.")
            if grid else tr("페이지를 선택해 끌어 놓으세요. 외부 PDF를 목록에 놓으면 해당 위치에 자동으로 삽입됩니다."))
        description.setWordWrap(True)
        layout.addWidget(description)

        modes = QHBoxLayout()
        modes.addWidget(QLabel("여러 페이지 선택 시:"))
        self.group_mode = QRadioButton("선택 페이지를 한 묶음으로 이동")
        self.single_mode = QRadioButton("드래그한 한 페이지만 이동")
        self.group_mode.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.group_mode)
        group.addButton(self.single_mode)
        modes.addWidget(self.group_mode)
        modes.addWidget(self.single_mode)
        modes.addStretch(1)
        layout.addLayout(modes)

        self.pages = PageOrganizerList(self, grid=grid)
        if grid:
            self.pages.itemDoubleClicked.connect(
                lambda item: self.page_activated.emit(self.pages.row(item)))
        self.pages.verticalScrollBar().valueChanged.connect(
            lambda _value: self._schedule_thumbnails())
        layout.addWidget(self.pages, 1)

        buttons = QHBoxLayout()
        add_button = QPushButton("PDF 추가...")
        add_button.setIcon(fluent_icon("add_file"))
        delete_button = QPushButton("선택 페이지 삭제")
        delete_button.setProperty("danger", True)
        delete_button.setIcon(fluent_icon("delete", "#c42b1c"))
        close_button = QPushButton(localize("Edit selected page", "선택 쪽 편집") if grid else tr("닫기"))
        close_button.setIcon(fluent_icon("edit" if grid else "close"))
        add_button.clicked.connect(self.choose_pdfs)
        delete_button.clicked.connect(self.delete_selected)
        close_button.clicked.connect(
            self.open_selected_page if grid else lambda: self.close_requested.emit())
        buttons.addWidget(add_button)
        buttons.addWidget(delete_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        self.refresh(host.page_index)

    def refresh(self, current=0, selected=None):
        self.stop_rendering()
        self._rendered_rows.clear()
        count = self.host.doc.page_count if self.host.doc else 0
        self.pages.blockSignals(True)
        self.pages.reset_pages(count)
        current = max(0, min(current, count - 1))
        self.pages.setCurrentRow(current)
        if selected:
            self.pages.clearSelection()
            for row in selected:
                item = self.pages.item(row)
                if item:
                    item.setSelected(True)
            if selected:
                self.pages.setCurrentRow(selected[0], QItemSelectionModel.NoUpdate)
        self.pages.blockSignals(False)
        if count:
            self.pages.scrollToItem(self.pages.item(current))
        self._schedule_thumbnails()

    def _schedule_thumbnails(self):
        if self.isVisible() and not self._thumbnail_timer.isActive():
            self._thumbnail_timer.start(20)

    def stop_rendering(self):
        self._thumbnail_timer.stop()

    def hideEvent(self, event):
        self.stop_rendering()
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._schedule_thumbnails()

    def open_selected_page(self):
        row = self.pages.currentRow()
        if row >= 0:
            self.page_activated.emit(row)

    def _render_visible_thumbnails(self):
        if (not self.isVisible() or not self.host.doc or self.pages.count() == 0 or
                getattr(self.host, "_closing_doc", False)):
            return
        visible = set(self.pages.visible_rows())
        for row in self._rendered_rows - visible:
            item = self.pages.item(row)
            if item is not None:
                item.setIcon(QIcon())
                item.setData(Qt.UserRole, False)
        self._rendered_rows.intersection_update(visible)
        rendered = 0
        for row in sorted(visible):
            item = self.pages.item(row)
            if item is None or item.data(Qt.UserRole):
                continue
            if rendered >= 2:
                self._thumbnail_timer.start(1)
                break
            try:
                width, height = self.host.doc.page_size(row)
                ratio = min(2.0, max(1.0, self.devicePixelRatioF()))
                zoom = min(THUMB_WIDTH / max(1.0, width),
                           self.pages.iconSize().height() / max(1.0, height))
                image = qimage_from_render(*self.host.doc.render(row, zoom * ratio),
                                           device_pixel_ratio=ratio)
                item.setIcon(QIcon(QPixmap.fromImage(image)))
            except Exception as error:
                item.setToolTip(str(error))
            item.setData(Qt.UserRole, True)
            self._rendered_rows.add(row)
            rendered += 1

    def move_pages(self, rows, at):
        new_rows = self.host.organizer_move_pages(rows, at)
        if new_rows is None:
            return False
        self.refresh(new_rows[0], new_rows)
        return True

    def insert_pdfs(self, paths, at):
        count = self.host.organizer_insert_pdfs(paths, at)
        if count <= 0:
            return False
        self.refresh(at, range(at, at + count))
        return True

    def choose_pdfs(self):
        paths, _filter = QFileDialog.getOpenFileNames(
            self, "추가할 PDF/Illustrator 파일 선택", "",
            tr(DOCUMENT_OPEN_FILTER))
        if not paths:
            return
        selected = sorted(self.pages.row(item) for item in self.pages.selectedItems())
        at = selected[-1] + 1 if selected else self.pages.count()
        self.insert_pdfs(paths, at)

    def delete_selected(self):
        rows = sorted(self.pages.row(item) for item in self.pages.selectedItems())
        if not rows:
            QMessageBox.information(self, "페이지 삭제", "삭제할 페이지를 선택하세요.")
            return
        if len(rows) >= self.pages.count():
            QMessageBox.information(
                self, "삭제 불가", "문서에는 최소 한 페이지가 남아 있어야 합니다.")
            return
        answer = QMessageBox.question(
            self, "페이지 삭제",
            "선택한 %d개 페이지를 삭제할까요?\n(Ctrl+Z로 되돌릴 수 있습니다.)"
            % len(rows))
        if answer != QMessageBox.Yes:
            return
        keep = self.host.organizer_delete_pages(rows)
        self.refresh(keep)


class PageOrganizerDialog(QDialog):
    """Keep the existing modal organizer for non-workspace embedded editors."""

    def __init__(self, host):
        super().__init__(host)
        self.setWindowTitle(tr("페이지 구성"))
        self.resize(620, 760)
        layout = QVBoxLayout(self)
        self.panel = PageOrganizerPanel(host)
        self.panel.close_requested.connect(self.accept)
        layout.addWidget(self.panel)

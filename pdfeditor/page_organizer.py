"""별도 페이지 구성 창.

현재 문서의 페이지를 여러 장 선택해 한 묶음으로 옮기거나, 드래그한 한
장만 옮길 수 있다. 외부 PDF 파일은 목록의 원하는 위치에 드롭해 삽입한다.
썸네일은 화면에 보이는 항목만 렌더해 큰 문서에서도 메모리를 제한한다.
"""

import json
from PyQt5.QtCore import (
    QByteArray, QItemSelectionModel, QMimeData, QSize, Qt, QTimer,
)
from PyQt5.QtGui import QDrag, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView, QButtonGroup, QDialog, QFileDialog, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QRadioButton, QVBoxLayout,
)

from .widgets import qimage_from_render


PAGE_MIME = "application/x-spdf-page-indices"
THUMB_WIDTH = 150


class PageOrganizerList(QListWidget):
    def __init__(self, dialog):
        super().__init__(dialog)
        self.dialog = dialog
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setIconSize(QSize(THUMB_WIDTH, int(THUMB_WIDTH * 1.42)))
        self.setSpacing(6)

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
        return [path for path in paths if path.lower().endswith(".pdf")]

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(PAGE_MIME) or self._pdf_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(PAGE_MIME) or self._pdf_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _insertion_index(self, pos):
        item = self.itemAt(pos)
        if item is None:
            return self.count()
        row = self.row(item)
        if pos.y() > self.visualItemRect(item).center().y():
            row += 1
        return row

    def dropEvent(self, event):
        at = self._insertion_index(event.pos())
        mime = event.mimeData()
        if mime.hasFormat(PAGE_MIME):
            try:
                rows = json.loads(bytes(mime.data(PAGE_MIME)).decode("ascii"))
            except (ValueError, UnicodeDecodeError):
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


class PageOrganizerDialog(QDialog):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.setWindowTitle("페이지 구성")
        self.resize(620, 760)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "페이지를 선택해 끌어 놓으세요. 외부 PDF를 목록에 놓으면 해당 "
            "위치에 자동으로 삽입됩니다."))

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

        self.pages = PageOrganizerList(self)
        self.pages.verticalScrollBar().valueChanged.connect(
            lambda _value: self._schedule_thumbnails())
        layout.addWidget(self.pages, 1)

        buttons = QHBoxLayout()
        add_button = QPushButton("PDF 추가...")
        delete_button = QPushButton("선택 페이지 삭제")
        close_button = QPushButton("닫기")
        add_button.clicked.connect(self.choose_pdfs)
        delete_button.clicked.connect(self.delete_selected)
        close_button.clicked.connect(self.accept)
        buttons.addWidget(add_button)
        buttons.addWidget(delete_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        self.refresh(host.page_index)

    def refresh(self, current=0, selected=None):
        self.pages.clear()
        count = self.host.doc.page_count
        for index in range(count):
            item = QListWidgetItem("%d페이지" % (index + 1))
            item.setTextAlignment(Qt.AlignHCenter)
            item.setData(Qt.UserRole, False)
            self.pages.addItem(item)
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
        self.pages.scrollToItem(self.pages.item(current))
        self._schedule_thumbnails()

    def _schedule_thumbnails(self):
        QTimer.singleShot(0, self._render_visible_thumbnails)

    def _render_visible_thumbnails(self):
        if not self.host.doc or self.pages.count() == 0:
            return
        top = self.pages.indexAt(self.pages.viewport().rect().topLeft()).row()
        bottom = self.pages.indexAt(self.pages.viewport().rect().bottomLeft()).row()
        top = max(0, top)
        bottom = min(self.pages.count() - 1, bottom if bottom >= 0 else top + 8)
        for row in range(top, bottom + 2):
            item = self.pages.item(row)
            if item is None or item.data(Qt.UserRole):
                continue
            width, _height = self.host.doc.page_size(row)
            zoom = THUMB_WIDTH / max(1.0, width)
            image = qimage_from_render(*self.host.doc.render(row, zoom))
            item.setIcon(QIcon(QPixmap.fromImage(image)))
            item.setData(Qt.UserRole, True)

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
            self, "추가할 PDF 선택", "", "PDF 파일 (*.pdf)")
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

"""Single-page drag preview for non-destructive margin cropping."""

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from .i18n import localize, tr
from .icons import fluent_icon
from .page_ranges import parse_page_groups
from .widgets import qimage_from_render


class CropPreview(QWidget):
    def __init__(self, image, parent=None):
        super().__init__(parent)
        self.pixmap = QPixmap.fromImage(image)
        self.selection = QRectF(0, 0, 1, 1)
        self._start = None
        self.setMinimumSize(250, 250)
        self.setCursor(Qt.CrossCursor)

    def image_rect(self):
        size = self.pixmap.size()
        scale = min((self.width() - 16) / size.width(),
                    (self.height() - 16) / size.height())
        w, h = size.width() * scale, size.height() * scale
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def _point(self, position):
        rect = self.image_rect()
        return QPointF(max(0, min(1, (position.x() - rect.x()) / rect.width())),
                       max(0, min(1, (position.y() - rect.y()) / rect.height())))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.image_rect().contains(
                QPointF(event.pos())):
            self._start = self._point(event.pos())

    def mouseMoveEvent(self, event):
        if self._start is not None:
            self.selection = QRectF(self._start, self._point(event.pos())).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._start is not None:
            self.selection = QRectF(self._start, self._point(event.pos())).normalized()
            self._start = None
            if self.selection.width() < 0.01 or self.selection.height() < 0.01:
                self.reset_selection()
            self.update()

    def reset_selection(self):
        self.selection = QRectF(0, 0, 1, 1)
        self.update()

    def fractions(self):
        return (self.selection.left(), self.selection.top(),
                self.selection.right(), self.selection.bottom())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#e9e9e9"))
        rect = self.image_rect()
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(rect, self.pixmap, QRectF(self.pixmap.rect()))
        selected = QRectF(
            rect.x() + self.selection.x() * rect.width(),
            rect.y() + self.selection.y() * rect.height(),
            self.selection.width() * rect.width(),
            self.selection.height() * rect.height())
        painter.setPen(QPen(QColor("#0f6cbd"), 2))
        painter.setBrush(QColor(15, 108, 189, 35))
        painter.drawRect(selected)


class CropDialog(QDialog):
    def __init__(self, document, page, parent=None):
        super().__init__(parent)
        self.document, self.page = document, page
        self.pages = [page]
        self.setWindowTitle(tr("페이지 여백 자르기"))
        self.resize(680, 760)
        layout = QVBoxLayout(self)
        label = QLabel(localize(
            "Drag the area to keep. Other pages use the same relative margins.\n"
            "This changes the visible area, not the underlying content. Ctrl+Z undoes it.",
            "남길 영역을 드래그하세요. 다른 페이지에는 같은 비율의 여백을 적용합니다.\n"
            "내용을 삭제하지 않고 표시 영역만 바꿉니다. Ctrl+Z로 되돌릴 수 있습니다."))
        label.setWordWrap(True)
        layout.addWidget(label)
        w, h = document.page_size(page)
        zoom = min(1200 / w, 1400 / h, 2)
        self.preview = CropPreview(qimage_from_render(*document.render(page, zoom)))
        layout.addWidget(self.preview, 1)
        row = QHBoxLayout()
        self.scope = QComboBox()
        for text in ("현재 페이지", "지정한 페이지", "전체 페이지"):
            self.scope.addItem(tr(text))
        self.range_edit = QLineEdit(str(page + 1))
        self.range_edit.setPlaceholderText("1-3, 5, 8-10")
        self.range_edit.setEnabled(False)
        self.scope.currentIndexChanged.connect(
            lambda index: self.range_edit.setEnabled(index == 1))
        reset = QPushButton(fluent_icon("undo"), tr("선택 초기화"))
        reset.clicked.connect(self.preview.reset_selection)
        row.addWidget(self.scope)
        row.addWidget(self.range_edit)
        row.addWidget(reset)
        layout.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        try:
            if self.scope.currentIndex() == 0:
                self.pages = [self.page]
            elif self.scope.currentIndex() == 2:
                self.pages = list(range(self.document.page_count))
            else:
                groups = parse_page_groups(self.range_edit.text(), self.document.page_count)
                self.pages = sorted({page for group in groups for page in group})
        except ValueError as error:
            QMessageBox.warning(self, tr("페이지 범위"), tr(str(error)))
            return
        super().accept()

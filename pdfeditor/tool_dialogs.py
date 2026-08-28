"""Compact option dialogs for watermarking and page image export."""

from PyQt5.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QSpinBox, QVBoxLayout,
)

from .i18n import localize, tr
from .page_ranges import parse_page_groups


class _PageScopeMixin:
    def _add_scope(self, form, current_page):
        self.current_page = current_page
        self.scope = QComboBox()
        for text in ("현재 페이지", "지정한 페이지", "전체 페이지"):
            self.scope.addItem(tr(text))
        self.range_edit = QLineEdit(str(current_page + 1))
        self.range_edit.setPlaceholderText("1-3, 5, 8-10")
        self.range_edit.setEnabled(False)
        self.scope.currentIndexChanged.connect(
            lambda index: self.range_edit.setEnabled(index == 1))
        row = QHBoxLayout()
        row.addWidget(self.scope)
        row.addWidget(self.range_edit, 1)
        form.addRow(tr("적용 범위:"), row)

    def selected_pages(self, page_count):
        if self.scope.currentIndex() == 0:
            return [self.current_page]
        if self.scope.currentIndex() == 2:
            return list(range(page_count))
        groups = parse_page_groups(self.range_edit.text(), page_count)
        return sorted({page for group in groups for page in group})


class WatermarkDialog(QDialog, _PageScopeMixin):
    def __init__(self, current_page, page_count, parent=None):
        super().__init__(parent)
        self.page_count = page_count
        self.pages = [current_page]
        self.setWindowTitle(tr("워터마크 추가"))
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        help_label = QLabel(localize(
            "Add centered text over the selected pages. Ctrl+Z undoes it.",
            "선택한 페이지 중앙에 글자를 올립니다. Ctrl+Z로 되돌립니다."))
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        form = QFormLayout()
        self.text = QLineEdit(localize("CONFIDENTIAL", "대외비"))
        form.addRow(tr("워터마크 문구:"), self.text)
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 240)
        self.font_size.setValue(42)
        self.font_size.setSuffix(" pt")
        form.addRow(tr("글자 크기:"), self.font_size)
        self.opacity = QSpinBox()
        self.opacity.setRange(1, 100)
        self.opacity.setValue(20)
        self.opacity.setSuffix("%")
        form.addRow(tr("투명도:"), self.opacity)
        self.angle = QSpinBox()
        self.angle.setRange(-180, 180)
        self.angle.setValue(-35)
        self.angle.setSuffix("°")
        form.addRow(tr("기울기:"), self.angle)
        self._add_scope(form, current_page)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        try:
            if not self.text.text().strip():
                raise ValueError(localize(
                    "Enter watermark text.", "워터마크 문구를 입력하세요."))
            self.pages = self.selected_pages(self.page_count)
        except ValueError as error:
            QMessageBox.warning(self, tr("워터마크 추가"), str(error))
            return
        super().accept()


class ExportImagesDialog(QDialog, _PageScopeMixin):
    def __init__(self, current_page, page_count, parent=None):
        super().__init__(parent)
        self.page_count = page_count
        self.pages = [current_page]
        self.setWindowTitle(tr("PDF를 이미지로"))
        self.setMinimumWidth(430)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.format = QComboBox()
        self.format.addItem("PNG", "png")
        self.format.addItem("JPEG", "jpeg")
        form.addRow(tr("이미지 형식:"), self.format)
        self.dpi = QSpinBox()
        self.dpi.setRange(72, 600)
        self.dpi.setValue(150)
        self.dpi.setSuffix(" DPI")
        form.addRow(tr("해상도:"), self.dpi)
        self._add_scope(form, current_page)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        try:
            self.pages = self.selected_pages(self.page_count)
        except ValueError as error:
            QMessageBox.warning(self, tr("PDF를 이미지로"), str(error))
            return
        super().accept()

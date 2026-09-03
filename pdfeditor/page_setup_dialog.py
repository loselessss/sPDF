"""Small page setup dialogs for editor canvas and bleed boxes."""

from PyQt5.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QLabel, QVBoxLayout,
)

from .i18n import localize


PT_PER_MM = 72.0 / 25.4


def pt_to_mm(value):
    return float(value) / PT_PER_MM


def mm_to_pt(value):
    return float(value) * PT_PER_MM


def _spin(value=0.0, maximum=5000.0, suffix=" mm"):
    widget = QDoubleSpinBox()
    widget.setRange(0.0, maximum)
    widget.setDecimals(2)
    widget.setSingleStep(1.0)
    widget.setSuffix(suffix)
    widget.setValue(float(value))
    return widget


class CanvasSizeDialog(QDialog):
    def __init__(self, parent=None, *, width_pt=0.0, height_pt=0.0):
        super().__init__(parent)
        self.setWindowTitle(localize("Canvas size", "캔버스 크기"))
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.width_input = _spin(pt_to_mm(width_pt), 5000.0)
        self.height_input = _spin(pt_to_mm(height_pt), 5000.0)
        form.addRow(localize("Width", "너비"), self.width_input)
        form.addRow(localize("Height", "높이"), self.height_input)
        layout.addLayout(form)
        note = QLabel(localize(
            "Changes the current page canvas. Existing page contents are not "
            "scaled.",
            "현재 쪽의 캔버스 크기를 바꿉니다. 기존 내용은 확대·축소하지 "
            "않습니다."))
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(localize("Apply", "적용"))
        buttons.button(QDialogButtonBox.Cancel).setText(localize("Cancel", "취소"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return mm_to_pt(self.width_input.value()), mm_to_pt(self.height_input.value())


class BleedDialog(QDialog):
    def __init__(self, parent=None, *, margins_pt=(0.0, 0.0, 0.0, 0.0)):
        super().__init__(parent)
        self.setWindowTitle(localize("Bleed", "도련"))
        layout = QVBoxLayout(self)
        form = QFormLayout()
        left, top, right, bottom = [pt_to_mm(value) for value in margins_pt]
        self.linked = QCheckBox(localize("Use same value on all sides",
                                         "상하좌우 같은 값 사용"))
        self.linked.setChecked(True)
        self.left_input = _spin(left, 254.0)
        self.top_input = _spin(top, 254.0)
        self.right_input = _spin(right, 254.0)
        self.bottom_input = _spin(bottom, 254.0)
        for widget in (self.left_input, self.top_input,
                       self.right_input, self.bottom_input):
            widget.valueChanged.connect(
                lambda value, source=widget: self._linked_changed(source, value))
        form.addRow(localize("Left", "왼쪽"), self.left_input)
        form.addRow(localize("Top", "위"), self.top_input)
        form.addRow(localize("Right", "오른쪽"), self.right_input)
        form.addRow(localize("Bottom", "아래"), self.bottom_input)
        layout.addLayout(form)
        row = QHBoxLayout()
        row.addWidget(self.linked)
        row.addStretch(1)
        layout.addLayout(row)
        note = QLabel(localize(
            "Sets TrimBox and BleedBox for the current page. Page artwork is "
            "moved to keep the trimmed page view in place.",
            "현재 쪽의 TrimBox와 BleedBox를 설정합니다. 재단 기준 화면 위치가 "
            "유지되도록 기존 내용만 이동합니다."))
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(localize("Apply", "적용"))
        buttons.button(QDialogButtonBox.Cancel).setText(localize("Cancel", "취소"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _linked_changed(self, source, value):
        if not self.linked.isChecked():
            return
        for widget in (self.left_input, self.top_input,
                       self.right_input, self.bottom_input):
            if widget is source:
                continue
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)

    def values(self):
        return tuple(mm_to_pt(widget.value()) for widget in (
            self.left_input, self.top_input, self.right_input,
            self.bottom_input))

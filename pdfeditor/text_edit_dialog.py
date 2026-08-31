"""Text replacement controls shared by ordinary and scanned PDF editing."""

from PyQt5.QtGui import QColor, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QColorDialog, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from .i18n import localize


class TextEditDialog(QDialog):
    def __init__(self, parent=None, *, text="", size=11, color=(0, 0, 0),
                 replacing=False):
        super().__init__(parent)
        self.setWindowTitle(localize("Edit text", "텍스트 편집") if replacing
                            else localize("Add text", "텍스트 추가"))
        self.resize(470, 310)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(localize("Text", "내용")))
        self.text_input = QPlainTextEdit(text)
        self.text_input.setAccessibleName(localize("Text", "내용"))
        layout.addWidget(self.text_input)
        form = QFormLayout()
        self.size_input = QDoubleSpinBox()
        self.size_input.setRange(1, max(1000, size))
        self.size_input.setDecimals(1)
        self.size_input.setSuffix(" pt")
        self.size_input.setValue(size)
        form.addRow(localize("Font size", "글자 크기"), self.size_input)
        self._color = QColor.fromRgbF(*color)
        self.color_button = QPushButton()
        self.color_button.clicked.connect(self.choose_color)
        self._update_color_label()
        form.addRow(localize("Text color", "글자 색상"), self.color_button)
        layout.addLayout(form)
        note = QLabel(localize(
            "Replacement fonts can look different. Text does not reflow; "
            "long replacements may be reduced to fit the original line.",
            "대체 글꼴로 모양이 달라질 수 있습니다. 문단은 재배치되지 않으며, "
            "긴 내용은 원래 줄 폭에 맞게 글자 크기가 줄어들 수 있습니다."))
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(localize("Apply", "적용"))
        buttons.button(QDialogButtonBox.Cancel).setText(localize("Cancel", "취소"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.text_input.setFocus()

    def _update_color_label(self):
        self.color_button.setText(self._color.name().upper())
        swatch = QPixmap(16, 16)
        swatch.fill(self._color)
        self.color_button.setIcon(QIcon(swatch))

    def choose_color(self):
        color = QColorDialog.getColor(self._color, self,
                                      localize("Text color", "글자 색상"))
        if color.isValid():
            self._color = color
            self._update_color_label()

    def values(self):
        return (self.text_input.toPlainText(), self.size_input.value(),
                (self._color.redF(), self._color.greenF(), self._color.blueF()))

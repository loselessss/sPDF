"""논문 자동 정리 설정과 구조화된 라이브러리 화면."""

import html
import os
import time

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QSplitter, QTextBrowser, QVBoxLayout, QWidget,
)

from . import settings
from .core import discover_input_pdfs, load_library, process_paper


class PaperSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("논문 자동 정리 설정")
        self.resize(680, 220)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.input_edit = self._folder_row(
            form, "입력 폴더", settings.paper_input_dir())
        self.organized_edit = self._folder_row(
            form, "정리 폴더", settings.paper_organized_dir())
        self.model_edit = QLineEdit(settings.paper_model())
        self.model_edit.setPlaceholderText("예: qwen3:8b")
        form.addRow("Ollama 모델", self.model_edit)
        self.auto_check = QCheckBox("앱 실행 중 input 폴더를 자동으로 확인")
        self.auto_check.setChecked(settings.paper_auto_enabled())
        form.addRow("자동 처리", self.auto_check)
        root.addLayout(form)
        note = QLabel(
            "논문 내용은 http://127.0.0.1:11434의 로컬 Ollama로만 전송됩니다. "
            "분석이 성공한 PDF만 정리 폴더로 이동합니다.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #666;")
        root.addWidget(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _folder_row(self, form, label, value):
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit(value)
        button = QPushButton("찾아보기...")
        button.clicked.connect(lambda _c=False, e=edit: self._browse(e))
        layout.addWidget(edit, 1)
        layout.addWidget(button)
        form.addRow(label, box)
        return edit

    def _browse(self, edit):
        start = edit.text().strip() or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "폴더 선택", start)
        if path:
            edit.setText(path)

    def _save(self):
        input_dir = self.input_edit.text().strip()
        organized_dir = self.organized_edit.text().strip()
        model = self.model_edit.text().strip()
        if not input_dir or not organized_dir:
            QMessageBox.warning(self, "설정 필요", "입력 폴더와 정리 폴더를 모두 지정하세요.")
            return
        if os.path.normcase(os.path.abspath(input_dir)) == \
                os.path.normcase(os.path.abspath(organized_dir)):
            QMessageBox.warning(self, "폴더 확인", "입력 폴더와 정리 폴더는 달라야 합니다.")
            return
        try:
            os.makedirs(input_dir, exist_ok=True)
            os.makedirs(organized_dir, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "폴더 오류", "폴더를 만들 수 없습니다:\n%s" % exc)
            return
        settings.set_paper_settings(
            input_dir, organized_dir, model, self.auto_check.isChecked())
        self.accept()


class PaperWorker(QThread):
    processing = pyqtSignal(str)
    processed = pyqtSignal(str, str)
    failed = pyqtSignal(str, str)

    def __init__(self, paths, organized_dir, model, parent=None):
        super().__init__(parent)
        self.paths = list(paths)
        self.organized_dir = organized_dir
        self.model = model

    def run(self):
        for path in self.paths:
            self.processing.emit(path)
            try:
                _record, destination = process_paper(
                    path, self.organized_dir, self.model)
                self.processed.emit(path, destination)
            except Exception as exc:
                self.failed.emit(path, str(exc))


class PaperLibraryPage(QWidget):
    open_pdf = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._records = []
        self._worker = None
        self._last_errors = []
        self._failed_unchanged = {}
        self._notify_errors = False

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        header = QHBoxLayout()
        title = QLabel("논문 라이브러리")
        font = title.font(); font.setPointSize(18); font.setBold(True)
        title.setFont(font)
        settings_btn = QPushButton("설정...")
        settings_btn.clicked.connect(self.show_settings)
        scan_btn = QPushButton("지금 분석")
        scan_btn.clicked.connect(lambda _c=False: self.scan_now(manual=True))
        refresh_btn = QPushButton("새로 고침")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(title)
        header.addStretch(1)
        for widget in (settings_btn, scan_btn, refresh_btn):
            header.addWidget(widget)
        root.addLayout(header)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #555;")
        root.addWidget(self.status)

        splitter = QSplitter(Qt.Horizontal)
        self.categories = QListWidget()
        self.categories.setMinimumWidth(170)
        self.categories.currentItemChanged.connect(
            lambda _current, _previous: self._populate_papers())
        self.papers = QListWidget()
        self.papers.setMinimumWidth(320)
        self.papers.currentItemChanged.connect(self._show_record)
        self.papers.itemDoubleClicked.connect(self._open_item)
        self.detail = QTextBrowser()
        self.detail.setOpenExternalLinks(False)
        splitter.addWidget(self.categories)
        splitter.addWidget(self.papers)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 2)
        root.addWidget(splitter, 1)

        self._timer = QTimer(self)
        self._timer.setInterval(30000)
        self._timer.timeout.connect(self._auto_scan)
        self._timer.start()
        self.refresh()
        QTimer.singleShot(1000, self._auto_scan)

    def show_settings(self):
        if PaperSettingsDialog(self).exec_() == QDialog.Accepted:
            self._failed_unchanged.clear()
            self.refresh()
            self._auto_scan()

    def is_processing(self):
        return self._worker is not None and self._worker.isRunning()

    def closeEvent(self, event):
        if self.is_processing():
            QMessageBox.information(
                self, "논문 분석 중",
                "논문 분석이 끝난 뒤 종료하세요. 원본 보호를 위해 처리 중에는 "
                "프로그램을 닫지 않습니다.")
            event.ignore()
            return
        super().closeEvent(event)

    def refresh(self):
        organized = settings.paper_organized_dir()
        self._records = load_library(organized) if organized else []
        selected = self.categories.currentItem().text() \
            if self.categories.currentItem() else "전체"
        categories = sorted({r.get("category") or "Review" for r in self._records})
        self.categories.clear()
        self.categories.addItem("전체")
        for category in categories:
            self.categories.addItem(category)
        matches = self.categories.findItems(selected, Qt.MatchExactly)
        self.categories.setCurrentItem(matches[0] if matches else self.categories.item(0))
        self._populate_papers()
        if self._worker is None:
            input_dir = settings.paper_input_dir()
            pending = len(discover_input_pdfs(input_dir, 0)) if input_dir else 0
            self.status.setText("정리된 논문 %d편 · input 대기 %d편" % (
                len(self._records), pending))

    def _populate_papers(self):
        item = self.categories.currentItem()
        category = item.text() if item else "전체"
        self.papers.clear()
        for record in self._records:
            if category != "전체" and (record.get("category") or "Review") != category:
                continue
            title = record.get("title") or record.get("source_name") or "제목 없음"
            sub = record.get("subcategory") or record.get("category") or ""
            year = record.get("year") or ""
            row = QListWidgetItem("%s\n%s  %s" % (title, year, sub))
            row.setData(Qt.UserRole, record)
            row.setToolTip(record.get("_pdf_file", ""))
            self.papers.addItem(row)
        if self.papers.count():
            self.papers.setCurrentRow(0)
        else:
            self.detail.setHtml("<p style='color:#777'>표시할 논문이 없습니다.</p>")

    def _show_record(self, current, _previous=None):
        if current is None:
            return
        r = current.data(Qt.UserRole) or {}
        esc = lambda value: html.escape(str(value or ""))
        bullets = lambda values: "".join("<li>%s</li>" % esc(v) for v in values or [])
        confidence = float(r.get("confidence", 0)) * 100
        self.detail.setHtml(
            "<h2>%s</h2>"
            "<p><b>저자</b> %s<br><b>연도</b> %s<br>"
            "<b>분류</b> %s / %s<br><b>신뢰도</b> %.0f%%<br>"
            "<b>키워드</b> %s</p>"
            "<h3>요약</h3><p>%s</p>"
            "<h3>핵심 기여</h3><ul>%s</ul>"
            "<h3>한계</h3><ul>%s</ul>"
            "<p style='color:#777'>모델: %s</p>" % (
                esc(r.get("title")), esc(", ".join(r.get("authors") or [])),
                esc(r.get("year")), esc(r.get("category")),
                esc(r.get("subcategory")), confidence,
                esc(", ".join(r.get("keywords") or [])),
                esc(r.get("summary_ko")), bullets(r.get("contributions")),
                bullets(r.get("limitations")), esc(r.get("model"))))

    def _open_item(self, item):
        record = item.data(Qt.UserRole) or {}
        path = record.get("_pdf_file", "")
        if os.path.isfile(path):
            self.open_pdf.emit(path)

    def _auto_scan(self):
        if settings.paper_auto_enabled():
            self.scan_now(manual=False)

    def scan_now(self, manual=False):
        if self._worker is not None:
            if manual:
                self.status.setText("이미 논문을 분석하고 있습니다.")
            return
        input_dir = settings.paper_input_dir()
        organized = settings.paper_organized_dir()
        if not input_dir or not organized:
            if manual:
                self.show_settings()
            return
        paths = discover_input_pdfs(input_dir)
        if not manual:
            paths = [p for p in paths if not self._recent_unchanged_failure(p)]
        if not paths:
            if manual:
                self.status.setText("동기화가 완료된 새 PDF가 없습니다.")
            return
        self._last_errors = []
        self._notify_errors = manual
        self._worker = PaperWorker(paths, organized, settings.paper_model(), self)
        self._worker.processing.connect(
            lambda p: self.status.setText("분석 중: %s" % os.path.basename(p)))
        self._worker.processed.connect(self._on_processed)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_failed(self, path, message):
        self._last_errors.append("%s: %s" % (os.path.basename(path), message))
        self._failed_unchanged[path] = (self._mtime(path), time.time())
        self.status.setText("분석 실패: %s" % os.path.basename(path))

    def _on_processed(self, source, destination):
        self._failed_unchanged.pop(source, None)
        self.status.setText("정리 완료: %s" % os.path.basename(destination))

    def _recent_unchanged_failure(self, path):
        previous = self._failed_unchanged.get(path)
        if previous is None:
            return False
        mtime, attempted_at = previous
        return mtime == self._mtime(path) and time.time() - attempted_at < 300

    @staticmethod
    def _mtime(path):
        try:
            return os.path.getmtime(path)
        except OSError:
            return None

    def _on_finished(self):
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        self.refresh()
        if self._last_errors:
            self.status.setText(
                "%d편 분석 실패 · 원본은 input에 그대로 있습니다." %
                len(self._last_errors))
            if self._notify_errors:
                QMessageBox.warning(
                    self, "일부 논문 분석 실패",
                    "원본은 input 폴더에 그대로 남아 있습니다.\n\n" +
                    "\n".join(self._last_errors[:8]))

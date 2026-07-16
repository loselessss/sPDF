"""MainWindow — 믹스인 조립(설계 §4)."""

import os

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QAction, QDockWidget, QFileDialog, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QListWidget, QMainWindow, QMessageBox, QPushButton,
    QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

from . import settings
from .annots import AnnotMixin
from .editing import EditMixin
from .meta import APP_NAME, APP_VERSION
from .ocr import OcrMixin
from .pages import PagesMixin
from .startpage import StartPage
from .textsel import TextSelectMixin
from .viewer import ViewerMixin
from .widgets import PageView, ThumbList


# 열린 창들 — 파이썬이 참조를 안 들고 있으면 창이 GC로 사라진다.
# 닫힐 때 closeEvent에서 스스로 빠진다.
_windows = []


def new_window(path=None):
    """새 창을 띄운다. path가 있으면 그 문서를 연다."""
    win = MainWindow()
    _windows.append(win)
    # 창이 겹쳐서 안 보이는 일이 없게 살짝 어긋나게 배치
    if len(_windows) > 1:
        prev = _windows[-2]
        win.move(prev.x() + 30, prev.y() + 30)
    win.show()
    if path:
        # 레이아웃이 끝난 뒤에 열어야 '창 너비 맞춤' 배율이 정확하다.
        QTimer.singleShot(0, lambda: win.open_path(path))
    return win


def _window_showing(path):
    """이미 그 파일을 열어둔 창이 있으면 반환 — 같은 파일을 두 창에서
    편집하면 서로의 저장을 덮어쓰므로 중복을 막는다."""
    target = os.path.normcase(os.path.abspath(path))
    for w in _windows:
        if w.doc is not None and \
                os.path.normcase(os.path.abspath(w.doc.path)) == target:
            return w
    return None


# MRO 주의: TextSelectMixin이 ViewerMixin보다 앞이어야 show_page 훅
# (페이지 전환 시 선택 초기화/검색 오버레이 재적용)이 동작한다.
class MainWindow(QMainWindow, EditMixin, PagesMixin, OcrMixin, AnnotMixin,
                 TextSelectMixin, ViewerMixin):
    def __init__(self, path=None):
        super().__init__()
        self._init_viewer_state()
        self._init_textsel_state()
        self._init_annot_state()
        self._init_ocr_state()
        self._init_edit_state()
        self._build_ui()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 800)
        self.setAcceptDrops(True)
        if path:
            self.open_path(path)

    def _build_ui(self):
        viewer = QWidget()
        lay = QHBoxLayout(viewer)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.thumbs = ThumbList()
        self.view = PageView()

        right = QWidget()
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.setSpacing(0)
        rlay.addWidget(self._build_search_bar())
        rlay.addWidget(self.view, 1)

        lay.addWidget(self.thumbs)
        lay.addWidget(right, 1)

        # 시작 페이지 ↔ 뷰어 전환 (문서 유무에 따라)
        self._start_page = StartPage()
        self._start_page.open_file.connect(self.open_in_window)
        self._start_page.browse.connect(self.open_dialog)
        self._start_page.back_to_doc.connect(self.back_to_doc)
        self._stack = QStackedWidget()
        self._stack.addWidget(self._start_page)  # index 0
        self._stack.addWidget(viewer)            # index 1
        self.setCentralWidget(self._stack)
        self._start_page.refresh()

        self.thumbs.page_selected.connect(self.show_page)
        self.thumbs.page_moved.connect(self.on_thumb_moved)
        self.thumbs.verticalScrollBar().valueChanged.connect(
            lambda _v: self._schedule_thumbs())
        self.view.zoom_changed.connect(self.on_zoom_changed)
        self.view.page_flip.connect(self.on_wheel_flip)
        self.view.canvas.drag_selected.connect(self.on_drag_selected)
        self.view.canvas.selection_cleared.connect(self._clear_selection)
        self.view.canvas.word_picked.connect(self.on_word_picked)
        self.view.canvas.clicked.connect(self._dispatch_click)
        self.view.canvas.context_requested.connect(self.on_context_menu)
        self.view.canvas.hovered.connect(self.on_canvas_hover)

        # 메모 모아보기 독 (기본 숨김)
        self._notes_list = QListWidget()
        self._notes_list.itemClicked.connect(self.on_note_item_clicked)
        self._notes_list.itemDoubleClicked.connect(self.on_note_item_double)
        self._notes_dock = QDockWidget("메모 모아보기", self)
        self._notes_dock.setWidget(self._notes_list)
        self.addDockWidget(Qt.RightDockWidgetArea, self._notes_dock)
        self._notes_dock.hide()

        self._page_label = QLabel("")
        self.statusBar().addPermanentWidget(self._page_label)

        self._build_menus()

    def _build_search_bar(self):
        bar = QWidget()
        h = QHBoxLayout(bar)
        h.setContentsMargins(6, 4, 6, 4)
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("검색어 입력 후 Enter (F3 다음 / Shift+F3 이전)")
        self._search_edit.returnPressed.connect(
            lambda: self.search_start(self._search_edit.text()))
        self._search_count = QLabel("")
        prev_btn = QToolButton(); prev_btn.setText("▲")
        next_btn = QToolButton(); next_btn.setText("▼")
        prev_btn.clicked.connect(lambda _c=False: self.search_prev())
        next_btn.clicked.connect(lambda _c=False: self.search_next())
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(lambda _c=False: self.hide_search())
        for w in (self._search_edit, self._search_count, prev_btn, next_btn, close_btn):
            h.addWidget(w)
        h.setStretch(0, 1)
        bar.hide()
        self._search_bar = bar
        return bar

    def show_search(self):
        self._search_bar.show()
        self._search_edit.setFocus()
        self._search_edit.selectAll()

    def hide_search(self):
        self._search_bar.hide()
        self.search_clear()

    def _build_menus(self):
        m = self.menuBar().addMenu("파일(&F)")
        self._home_act = self._act(m, "홈으로", "Alt+Home", self.go_home)
        self._home_act.setEnabled(False)  # 문서를 열어야 의미가 있다
        self._act(m, "열기...", "Ctrl+O", self.open_dialog)
        self._act(m, "새 창", "Ctrl+N", lambda: new_window())
        self._recent_menu = m.addMenu("최근 파일")
        self._recent_menu.setToolTipsVisible(True)  # 마우스 올리면 전체 경로
        self._recent_menu.aboutToShow.connect(self._rebuild_recent_menu)
        self._fav_menu = m.addMenu("즐겨찾기")
        self._fav_menu.setToolTipsVisible(True)
        self._fav_menu.aboutToShow.connect(self._rebuild_fav_menu)
        m.addSeparator()
        self._act(m, "저장", "Ctrl+S", self.save)
        self._act(m, "다른 이름으로 저장...", "Ctrl+Shift+S", self.save_as_dialog)
        m.addSeparator()
        self._act(m, "닫기", "Ctrl+W", self.request_close_doc)
        self._act(m, "종료", "Ctrl+Q", self.close)

        e = self.menuBar().addMenu("편집(&E)")
        self._undo_act = self._act(e, "실행 취소", "Ctrl+Z", self.undo)
        self._redo_act = self._act(e, "다시 실행", "Ctrl+Y", self.redo)
        self._undo_act.setEnabled(False)
        self._redo_act.setEnabled(False)
        e.addSeparator()
        self._act(e, "복사", "Ctrl+C", self.copy_selection)
        self._act(e, "현재 페이지 모두 선택", "Ctrl+A", self.select_all)
        e.addSeparator()
        self._edit_act = self._act(e, "텍스트 편집 모드", "Ctrl+E",
                                   self.toggle_edit_mode)
        self._edit_act.setCheckable(True)
        e.addSeparator()
        self._act(e, "찾기...", "Ctrl+F", self.show_search)
        self._act(e, "다음 찾기", "F3", self.search_next)
        self._act(e, "이전 찾기", "Shift+F3", self.search_prev)

        a = self.menuBar().addMenu("주석(&A)")
        self._act(a, "선택 영역 형광펜", "Ctrl+H", self.highlight_selection)
        self._act(a, "메모 추가 (위치 클릭)", "Ctrl+M", self.start_note_mode)
        a.addSeparator()
        self._act(a, "메모 모아보기", "Ctrl+Shift+M", self.toggle_notes_panel)

        pg = self.menuBar().addMenu("페이지(&P)")
        self._act(pg, "오른쪽으로 회전", "Ctrl+]", self.rotate_page_cw)
        self._act(pg, "왼쪽으로 회전", "Ctrl+[", self.rotate_page_ccw)
        pg.addSeparator()
        self._act(pg, "현재 페이지 삭제", "Ctrl+Delete", self.delete_current_page)
        self._act(pg, "다른 PDF 병합...", None, self.merge_pdf)
        self._act(pg, "현재 페이지 추출...", None, self.extract_current_page)

        o = self.menuBar().addMenu("OCR(&O)")
        self._act(o, "현재 페이지 OCR", "Ctrl+R", self.ocr_current_page)
        self._act(o, "전체 문서 OCR (텍스트 없는 페이지만)", "Ctrl+Shift+R",
                  self.ocr_document)
        o.addSeparator()
        self._act(o, "AI 고품질 OCR 설정...", None, self.show_ocr_engine_dialog)

        v = self.menuBar().addMenu("보기(&V)")
        self._act(v, "확대", "Ctrl++", self.zoom_in)
        self._act(v, "축소", "Ctrl+-", self.zoom_out)
        self._act(v, "창 너비에 맞춤", "Ctrl+0", self.zoom_fit)
        v.addSeparator()
        self._act(v, "다음 페이지", "PgDown", self.next_page)
        self._act(v, "이전 페이지", "PgUp", self.prev_page)

        h = self.menuBar().addMenu("도움말(&H)")
        self._act(h, "사용법", "F1", self.show_help)
        self._act(h, "PDF 기본 프로그램 확인...", None, self.check_default_app)
        self._act(h, "오픈소스 라이선스", None, self.show_licenses)
        self._act(h, "정보", None, self.show_about)

    def on_wheel_flip(self, direction):
        """휠로 페이지 끝에 닿았을 때 다음/이전 장으로.

        넘어간 뒤 스크롤 위치를 진행 방향에 맞춘다 — 다음 장은 위에서,
        이전 장은 아래 끝에서 시작해야 계속 같은 방향으로 읽힌다.
        """
        if self.doc is None:
            return
        if direction > 0 and self.page_index < self.doc.page_count - 1:
            self.show_page(self.page_index + 1)
            self.view.verticalScrollBar().setValue(
                self.view.verticalScrollBar().minimum())
        elif direction < 0 and self.page_index > 0:
            self.show_page(self.page_index - 1)
            self.view.verticalScrollBar().setValue(
                self.view.verticalScrollBar().maximum())
        self.view.reset_flip()

    def _dispatch_click(self, pt):
        """canvas 클릭 라우팅 — 편집 모드면 편집, 아니면 기존(메모 열기 등)."""
        if self._edit_mode:
            self.edit_span_at(pt)
        else:
            self.on_canvas_clicked(pt)

    def _act(self, menu, text, shortcut, slot):
        """QAction 연결 — triggered가 넘기는 checked 인자가 슬롯의 첫
        인자에 잘못 꽂히지 않도록 항상 람다로 감싼다."""
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(shortcut)
        a.triggered.connect(lambda _checked=False, s=slot: s())
        menu.addAction(a)
        return a

    # --- 홈 ------------------------------------------------------------

    def go_home(self):
        """시작 페이지로 — 문서는 열어둔 채 화면만 전환(닫기와 다르다).

        홈에서 '문서로 돌아가기'로 복귀할 수 있다.
        """
        if self.doc is None:
            return
        self._start_page.refresh()
        self._start_page.set_current_doc(os.path.basename(self.doc.path))
        self._stack.setCurrentIndex(0)

    def back_to_doc(self):
        if self.doc is not None:
            self._stack.setCurrentIndex(1)

    # --- 최근 파일 ----------------------------------------------------

    def _rebuild_recent_menu(self):
        self._recent_menu.clear()
        paths = settings.recent_files()
        if not paths:
            act = self._recent_menu.addAction("(비어 있음)")
            act.setEnabled(False)
            return
        for p in paths:
            # 어디 있는 파일인지 보이도록 전체 경로를 표시하되, 지나치게
            # 길면 가운데를 접는다(넉넉하게 100자).
            label = "%s  —  %s" % (os.path.basename(p), os.path.dirname(p))
            if len(label) > 100:
                label = label[:60] + "…" + label[-39:]
            act = self._recent_menu.addAction(label)
            act.setToolTip(p)
            act.triggered.connect(lambda _c=False, p=p: self._open_recent(p))
        self._recent_menu.addSeparator()
        self._recent_menu.addAction(
            "목록 지우기", lambda _c=False: settings.clear_recent())

    def _open_recent(self, path):
        if not os.path.exists(path):
            QMessageBox.warning(self, "파일 없음",
                                "파일이 이동되었거나 삭제되었습니다:\n%s" % path)
            settings.remove_recent(path)
            return
        self.open_in_window(path)

    # --- 즐겨찾기 ------------------------------------------------------

    def _rebuild_fav_menu(self):
        self._fav_menu.clear()
        if self.doc is not None:
            if settings.is_favorite(self.doc.path):
                self._fav_menu.addAction(
                    "현재 파일을 즐겨찾기에서 제거",
                    lambda _c=False: self._toggle_favorite())
            else:
                self._fav_menu.addAction(
                    "★ 현재 파일을 즐겨찾기에 추가",
                    lambda _c=False: self._toggle_favorite())
            self._fav_menu.addSeparator()
        favs = list(reversed(settings.favorites()))
        if not favs:
            act = self._fav_menu.addAction("(비어 있음)")
            act.setEnabled(False)
            return
        for p in favs:
            label = "%s  —  %s" % (os.path.basename(p), os.path.dirname(p))
            if len(label) > 100:
                label = label[:60] + "…" + label[-39:]
            act = self._fav_menu.addAction(label)
            act.setToolTip(p)
            act.triggered.connect(lambda _c=False, p=p: self._open_recent(p))

    def _toggle_favorite(self):
        if self.doc is None:
            return
        if settings.is_favorite(self.doc.path):
            settings.remove_favorite(self.doc.path)
            self.statusBar().showMessage("즐겨찾기에서 제거됨", 3000)
        else:
            settings.add_favorite(self.doc.path)
            self.statusBar().showMessage("즐겨찾기에 추가됨", 3000)
        self._start_page.refresh()

    # --- 파일 열기 ---------------------------------------------------

    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "PDF 열기", "", "PDF 파일 (*.pdf)")
        if path:
            self.open_in_window(path)

    def open_in_window(self, path):
        """사용자가 파일을 여는 모든 경로(메뉴/최근/즐겨찾기/홈/드롭)의 창구.

        - 이미 그 파일을 연 창이 있으면 그 창을 앞으로
        - 이 창이 비어 있으면(홈 상태) 여기서 연다
        - 이미 다른 문서를 보고 있으면 새 창으로 — 기존 문서를 잃지 않는다
        """
        existing = _window_showing(path)
        if existing is not None:
            existing.raise_()
            existing.activateWindow()
            return existing
        if self.doc is None:
            self.open_path(path)
            return self
        return new_window(path)

    def open_path(self, path):
        # 지연 임포트 — core가 물고 오는 MuPDF DLL(콜드 스타트 때 수 초)을
        # 창이 뜬 다음으로 미룬다. 빈 창이라도 즉시 보이는 게 체감상 낫다.
        from .core import Document, PasswordRequired
        if not self.maybe_save():
            return
        password = None
        while True:
            try:
                doc = Document(path, password)
                break
            except PasswordRequired:
                password, ok = QInputDialog.getText(
                    self, "암호 필요",
                    "이 PDF는 암호가 걸려 있습니다.\n비밀번호를 입력하세요:",
                    QLineEdit.Password)
                if not ok:
                    return
            except Exception as e:
                QMessageBox.critical(self, "열기 실패", "파일을 열 수 없습니다.\n\n%s" % e)
                return

        self.close_doc()
        self.doc = doc
        self.page_index = 0
        self.thumbs.reset_pages(doc.page_count)
        self._update_title()
        settings.push_recent(path)
        self._stack.setCurrentIndex(1)  # 시작 페이지 → 뷰어
        self._home_act.setEnabled(True)
        self._set_fit_zoom(0)   # 배율부터 정해서 첫 렌더를 한 번으로
        self.show_page(0)
        self._schedule_thumbs()
        self._notes_changed()   # 모아보기 패널이 열려 있으면 새 문서로 갱신
        if not doc.has_text(0):
            self.statusBar().showMessage(
                "텍스트 레이어가 없는 문서입니다 (스캔본) — 복사/검색은 OCR 후 가능", 6000)

    def request_close_doc(self):
        """메뉴의 '닫기' — 저장 확인을 거친다. 내부 정리는 close_doc."""
        if self.maybe_save():
            self.close_doc()

    def close_doc(self):
        if self.doc is not None:
            self.doc.close()
            self.doc = None
        self._cache.clear()
        self._reset_textsel()
        self._reset_annots()
        self._reset_edit()
        self._edit_act.setChecked(False)
        self._update_edit_actions()
        self.hide_search()
        self.thumbs.clear()
        self.view.clear()
        self._update_title()
        self._update_page_label()
        self._start_page.refresh()
        self._start_page.set_current_doc(None)  # 닫았으니 '돌아가기' 숨김
        self._home_act.setEnabled(False)
        self._stack.setCurrentIndex(0)  # 뷰어 → 시작 페이지

    def closeEvent(self, ev):
        if not self.maybe_save():
            ev.ignore()
            return
        self.close_doc()
        if self in _windows:
            _windows.remove(self)  # 참조를 놓아줘야 창이 실제로 해제된다
        super().closeEvent(ev)

    # --- 드래그&드롭 -------------------------------------------------

    def dragEnterEvent(self, ev):
        urls = ev.mimeData().urls()
        if urls and urls[0].toLocalFile().lower().endswith(".pdf"):
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        self.open_in_window(ev.mimeData().urls()[0].toLocalFile())

    # --- 상태 표시 ---------------------------------------------------

    def _update_title(self):
        if self.doc is None:
            self.setWindowTitle(APP_NAME)
        else:
            star = "*" if self._dirty else ""
            self.setWindowTitle("%s%s — %s" % (
                star, os.path.basename(self.doc.path), APP_NAME))

    def _update_page_label(self):
        if self.doc is None:
            self._page_label.setText("")
        else:
            self._page_label.setText("%d / %d   %d%%" % (
                self.page_index + 1, self.doc.page_count, round(self.view.zoom * 100)))

    def show_help(self):
        from .help import show_help
        show_help(self)

    def check_default_app(self):
        from .defaultapp import (friendly_handler_name, is_spdf_default,
                                 open_default_apps_settings)
        current = friendly_handler_name()
        if is_spdf_default():
            QMessageBox.information(
                self, "PDF 기본 프로그램",
                "PDF 파일의 기본 프로그램이 이미 sPDF로 설정되어 있습니다.\n\n"
                "현재: %s" % current)
            return
        box = QMessageBox(self)
        box.setWindowTitle("PDF 기본 프로그램")
        box.setIcon(QMessageBox.Question)
        box.setText("현재 PDF 기본 프로그램: %s\n\n"
                    "sPDF로 바꾸려면 Windows '기본 앱' 설정에서 .pdf 항목을\n"
                    "sPDF로 선택하세요. (보안상 프로그램이 자동으로 바꿀 수는\n"
                    "없습니다.)\n\n설정 화면을 열까요?" % current)
        box.setStandardButtons(QMessageBox.Open | QMessageBox.Cancel)
        box.button(QMessageBox.Open).setText("설정 열기")
        box.button(QMessageBox.Cancel).setText("닫기")
        if box.exec_() == QMessageBox.Open:
            if not open_default_apps_settings():
                QMessageBox.warning(
                    self, "설정 열기 실패",
                    "설정 화면을 열지 못했습니다.\n"
                    "Windows 설정 → 앱 → 기본 앱에서 직접 변경하세요.")

    def show_about(self):
        QMessageBox.about(self, "정보", "%s %s" % (APP_NAME, APP_VERSION))

    def show_ocr_engine_dialog(self):
        """OCR 엔진 선택 — 기본(RapidOCR) vs AI 고품질(VL).

        VL은 아직 뼈대 단계라 미설치 상태에서 켜면 실제 OCR 때 명확한
        안내가 뜬다(조용히 실패하지 않음). 여기서는 선택 저장 + 현재 상태
        (가속기/모델 설치)만 보여준다.
        """
        from . import settings, vl
        kind, desc = vl.runtime_summary()
        installed = vl.vl_installed()
        cur = settings.ocr_engine()

        box = QMessageBox(self)
        box.setWindowTitle("AI 고품질 OCR 설정")
        box.setIcon(QMessageBox.Question)
        box.setText(
            "OCR 엔진을 선택하세요.\n\n"
            "• 기본(RapidOCR): 가볍고 빠름, 한글+영문. CPU에서 잘 동작.\n"
            "• AI 고품질(VL): 저품질 스캔·복잡한 레이아웃에 강함. 모델 수 GB,\n"
            "  GPU 권장.\n\n"
            "현재 가속기: %s\n"
            "VL 모델 설치: %s\n"
            "현재 선택: %s"
            % (desc, "설치됨" if installed else "미설치",
               "AI 고품질(VL)" if cur == "vl" else "기본(RapidOCR)"))
        b_basic = box.addButton("기본으로", QMessageBox.AcceptRole)
        b_vl = box.addButton("AI 고품질로", QMessageBox.AcceptRole)
        box.addButton("취소", QMessageBox.RejectRole)
        box.exec_()
        clicked = box.clickedButton()
        if clicked is b_basic:
            settings.set_ocr_engine("rapidocr")
            self.statusBar().showMessage("OCR 엔진: 기본(RapidOCR)", 4000)
        elif clicked is b_vl:
            settings.set_ocr_engine("vl")
            if not installed:
                QMessageBox.information(
                    self, "VL 모델 필요",
                    "AI 고품질(VL) 엔진을 선택했지만 모델이 아직 설치되지 "
                    "않았습니다.\n\nVL은 현재 준비 중입니다. 모델이 연결되면 "
                    "여기서 다운로드할 수 있게 됩니다. 그전까지 OCR은 기본 "
                    "엔진으로 동작합니다.")
            else:
                self.statusBar().showMessage("OCR 엔진: AI 고품질(VL)", 4000)

    def show_licenses(self):
        QMessageBox.information(self, "오픈소스 라이선스", (
            "%s는 아래 오픈소스 소프트웨어로 만들어졌습니다.\n\n"
            "• PyQt5 — GPL v3 (Riverbank Computing)\n"
            "• PyMuPDF / MuPDF — AGPL 3.0 (Artifex Software)\n"
            "• RapidOCR — Apache 2.0 (RapidAI)\n"
            "• PaddleOCR 인식 모델 — Apache 2.0 (PaddlePaddle)\n"
            "• ONNX Runtime — MIT (Microsoft)\n"
            "• NumPy — BSD 3-Clause\n\n"
            "자세한 내용은 프로그램 폴더의 LICENSES.md 참고.\n"
            "개인 사용은 제약이 없으며, 이 프로그램을 외부에 배포할 경우\n"
            "PyQt5(GPL)와 PyMuPDF(AGPL) 조건에 따라 소스 공개 의무가\n"
            "생기는 점에 유의하세요.") % APP_NAME)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape and self._note_mode:
            self.cancel_note_mode()
        elif ev.key() == Qt.Key_Escape and self._search_bar.isVisible():
            self.hide_search()
        elif ev.key() in (Qt.Key_Down, Qt.Key_Right):
            self.next_page()
        elif ev.key() in (Qt.Key_Up, Qt.Key_Left):
            self.prev_page()
        else:
            super().keyPressEvent(ev)

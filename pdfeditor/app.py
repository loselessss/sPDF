"""AppWindow(셸) + DocumentTab — 탭 기반 다중 문서/창.

구조: 문서 하나 = DocumentTab(QMainWindow, 믹스인 전부). 바깥 AppWindow가
탭들을 QTabWidget에 담고, 활성 탭의 메뉴바를 자기 창에 reparent한다(믹스인은
여전히 자기 탭의 statusBar/QAction/docks를 쓰므로 거의 수정이 없다).
문서가 하나도 없으면 시작 페이지를 보여준다.
"""

import json
import os
import subprocess
import tempfile
import uuid

from PyQt5.QtCore import QMimeData, QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QDrag
from PyQt5.QtWidgets import (
    QAction, QActionGroup, QApplication, QCheckBox, QDialog, QDialogButtonBox,
    QDockWidget, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QMainWindow, QMenuBar, QMessageBox, QProgressDialog, QPushButton,
    QSpinBox, QSplitter, QStackedWidget, QTabBar, QTabWidget, QToolBar,
    QToolButton, QVBoxLayout, QWidget,
)

from . import settings
from .annots import AnnotMixin
from .editing import EditMixin
from .icons import fluent_icon
from .meta import APP_NAME, APP_VERSION
from .ocr import OcrMixin
from .pages import PagesMixin
from .startpage import StartPage
from .textsel import TextSelectMixin
from .update_dialog import UpdateCheckWorker, UpdateDialog
from .update_service import GitHubUpdateService, UpdateError
from .viewer import ViewerMixin
from .widgets import PageView, ThumbList


def _make_action(parent, text, shortcut, slot, icon_name=None):
    """QAction 생성 — triggered의 checked 인자가 슬롯 첫 인자에 잘못 꽂히지
    않게 항상 람다로 감싼다."""
    a = QAction(text, parent)
    if icon_name:
        a.setIcon(fluent_icon(icon_name))
    if shortcut:
        a.setShortcut(shortcut)
    a.triggered.connect(lambda _checked=False, s=slot: s())
    return a


def _show_default_app_settings(parent):
    from .defaultapp import (
        browser_external_pdf_enabled, friendly_handler_name, is_spdf_default,
        open_default_apps_settings, set_browser_external_pdf,
    )
    dialog = QDialog(parent)
    dialog.setWindowTitle("PDF 기본 프로그램 및 브라우저 설정")
    dialog.setMinimumWidth(500)
    layout = QVBoxLayout(dialog)

    current = friendly_handler_name()
    spdf_default = is_spdf_default()
    default_label = QLabel("Windows PDF 기본 앱: <b>%s</b>" % current)
    default_label.setTextFormat(Qt.RichText)
    layout.addWidget(default_label)
    if not spdf_default:
        warning = QLabel(
            "아래 옵션을 켜도 현재 기본 PDF 앱으로 열립니다. 먼저 Windows "
            "기본 앱에서 sPDF를 선택하세요.")
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #b45309;")
        layout.addWidget(warning)

    defaults = QPushButton("Windows 기본 앱 설정 열기")
    defaults.setIcon(fluent_icon("settings"))
    layout.addWidget(defaults)
    layout.addSpacing(8)

    labels = {
        "edge": "Microsoft Edge에서 PDF를 sPDF로 열기",
        "chrome": "Google Chrome에서 PDF를 sPDF로 열기",
        "firefox": "Mozilla Firefox에서 PDF를 sPDF로 열기",
    }
    states = {}
    checks = {}
    for browser, label in labels.items():
        states[browser] = browser_external_pdf_enabled(browser)
        check = QCheckBox(label)
        check.setChecked(states[browser])
        checks[browser] = check
        layout.addWidget(check)

    note = QLabel(
        "브라우저의 내장 PDF 뷰어 대신 Windows 기본 앱을 사용합니다. "
        "적용 후 브라우저를 완전히 종료했다 다시 실행하세요. Firefox는 "
        "웹페이지에 삽입된 PDF를 계속 브라우저에 표시할 수 있습니다.\n\n"
        "이 설정은 사용자별 브라우저 정책을 사용하므로 브라우저에 "
        "'조직에서 관리'가 표시될 수 있습니다.")
    note.setWordWrap(True)
    layout.addSpacing(6)
    layout.addWidget(note)

    buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Close)
    buttons.button(QDialogButtonBox.Save).setText("적용")
    buttons.button(QDialogButtonBox.Save).setIcon(fluent_icon("save"))
    buttons.button(QDialogButtonBox.Close).setText("닫기")
    buttons.button(QDialogButtonBox.Close).setIcon(fluent_icon("close"))
    layout.addWidget(buttons)

    def _open_defaults():
        if not open_default_apps_settings():
            QMessageBox.warning(
                dialog, "설정 열기 실패",
                "설정 화면을 열지 못했습니다.\n"
                "Windows 설정 → 앱 → 기본 앱에서 직접 변경하세요.")

    def _apply_browser_settings():
        changed = []
        applied = []
        try:
            for browser, check in checks.items():
                enabled = check.isChecked()
                if enabled != states[browser]:
                    set_browser_external_pdf(browser, enabled)
                    applied.append(browser)
                    changed.append(labels[browser].split("에서", 1)[0])
        except (OSError, ValueError) as e:
            # 일부 브라우저만 바뀐 채 남지 않도록 이번 적용분을 되돌린다.
            for browser in reversed(applied):
                try:
                    set_browser_external_pdf(browser, states[browser])
                except OSError:
                    pass
            QMessageBox.critical(
                dialog, "브라우저 설정 실패",
                "PDF 열기 설정을 변경하지 못했습니다.\n\n%s" % e)
            return
        if changed:
            QMessageBox.information(
                dialog, "브라우저 설정 완료",
                "%s 설정을 변경했습니다.\n"
                "브라우저를 완전히 종료한 뒤 다시 실행하세요."
                % ", ".join(changed))
        dialog.accept()

    defaults.clicked.connect(lambda _checked=False: _open_defaults())
    buttons.button(QDialogButtonBox.Save).clicked.connect(
        lambda _checked=False: _apply_browser_settings())
    buttons.rejected.connect(dialog.reject)
    dialog.exec_()


_TAB_MIME = "application/x-spdf-tab"
_dragged_tabs = {}


def _decode_tab_drag(mime):
    if not mime.hasFormat(_TAB_MIME):
        return None
    try:
        return json.loads(bytes(mime.data(_TAB_MIME)).decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError):
        return None


class TransferTabBar(QTabBar):
    """창 안 재정렬은 Qt에 맡기고, 탭 막대 밖으로 나가면 창 간 드래그한다."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._pressed_tab = None

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            i = self.tabAt(ev.pos())
            self._pressed_tab = self.parentWidget().widget(i) if i >= 0 else None
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        super().mouseReleaseEvent(ev)
        self._pressed_tab = None

    def mouseMoveEvent(self, ev):
        tab = self._pressed_tab
        if tab is not None and ev.buttons() & Qt.LeftButton and \
                not self.rect().adjusted(-10, -10, 10, 10).contains(ev.pos()):
            self._pressed_tab = None
            self._start_transfer(tab)
            return
        super().mouseMoveEvent(ev)

    def _start_transfer(self, tab):
        shell = self.window()
        if not isinstance(shell, AppWindow) or shell._tabs.indexOf(tab) < 0 or \
                tab.doc is None:
            return

        token = uuid.uuid4().hex
        snapshot_path = None
        if tab._dirty:
            try:
                fd, snapshot_path = tempfile.mkstemp(
                    prefix="spdf-tab-", suffix=".pdf")
                with os.fdopen(fd, "wb") as stream:
                    stream.write(tab.doc.snapshot())
            except Exception as e:
                if snapshot_path and os.path.exists(snapshot_path):
                    os.remove(snapshot_path)
                tab.statusBar().showMessage(
                    "탭 이동용 임시 저장에 실패했습니다: %s" % e, 5000)
                return

        payload = {
            "pid": os.getpid(),
            "token": token,
            "path": tab.doc.path,
            "dirty": bool(tab._dirty),
            "snapshot": snapshot_path,
        }
        mime = QMimeData()
        mime.setData(_TAB_MIME, json.dumps(payload).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        i = shell._tabs.indexOf(tab)
        if i >= 0:
            drag.setPixmap(self.grab(self.tabRect(i)))

        _dragged_tabs[token] = (shell, tab)
        try:
            result = drag.exec_(Qt.MoveAction)
        finally:
            _dragged_tabs.pop(token, None)

        # 같은 프로세스면 dropEvent에서 이미 위젯을 떼어 대상 창에 붙인다.
        # 아직 원래 창에 남아 있으면 다른 sPDF 프로세스가 경로를 받은 경우다.
        moved_to_external_process = result == Qt.MoveAction and \
            shell._tabs.indexOf(tab) >= 0
        if moved_to_external_process:
            shell._finish_external_tab_move(tab)
        elif snapshot_path and os.path.exists(snapshot_path):
            # 같은 프로세스 이동이나 취소에서는 임시본을 받을 프로세스가 없다.
            os.remove(snapshot_path)

    def dragEnterEvent(self, ev):
        if self._can_accept(ev.mimeData()):
            ev.setDropAction(Qt.MoveAction)
            ev.accept()
        else:
            ev.ignore()

    def dragMoveEvent(self, ev):
        if self._can_accept(ev.mimeData()):
            ev.setDropAction(Qt.MoveAction)
            ev.accept()
        else:
            ev.ignore()

    def dropEvent(self, ev):
        payload = _decode_tab_drag(ev.mimeData())
        if payload is None:
            ev.ignore()
            return

        index = self.tabAt(ev.pos())
        if index < 0:
            index = self.count()
        elif ev.pos().x() > self.tabRect(index).center().x():
            index += 1

        if self.window()._receive_tab_drop(payload, index):
            ev.setDropAction(Qt.MoveAction)
            ev.accept()
        else:
            ev.ignore()

    def _can_accept(self, mime):
        payload = _decode_tab_drag(mime)
        if not payload or not payload.get("path"):
            return False
        if payload.get("pid") == os.getpid():
            entry = _dragged_tabs.get(payload.get("token"))
            return entry is not None and entry[0] is not self.window()
        if not os.path.isfile(payload["path"]):
            return False
        if not payload.get("dirty"):
            return True
        snapshot = payload.get("snapshot")
        if not snapshot or not self._is_transfer_snapshot(snapshot):
            return False
        return self.window()._find_open_tab(payload["path"]) is None

    @staticmethod
    def _is_transfer_snapshot(path):
        try:
            full = os.path.abspath(path)
            return os.path.dirname(full) == os.path.abspath(tempfile.gettempdir()) \
                and os.path.basename(full).startswith("spdf-tab-") \
                and full.lower().endswith(".pdf") and os.path.isfile(full)
        except (TypeError, ValueError):
            return False


# ======================================================================
# DocumentTab — 문서 한 개의 뷰어/편집기 (믹스인 조립)
# ======================================================================

# MRO 주의: TextSelectMixin이 ViewerMixin보다 앞이어야 show_page 훅
# (페이지 전환 시 선택 초기화/검색 오버레이 재적용)이 동작한다.
class DocumentTab(QMainWindow, EditMixin, PagesMixin, OcrMixin, AnnotMixin,
                  TextSelectMixin, ViewerMixin):

    title_changed = pyqtSignal()  # 탭 라벨/창 제목 갱신 신호(셸이 받는다)
    selection_changed = pyqtSignal(object)

    def __init__(self, shell):
        super().__init__()
        self._shell = shell
        self._init_viewer_state()
        self._init_textsel_state()
        self._init_annot_state()
        self._init_ocr_state()
        self._init_edit_state()
        self._build_ui()
        self._menubar = self.menuBar()  # 활성화 시 셸로 reparent (참조 보관)

    # --- UI 구성 -------------------------------------------------------

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

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.thumbs)
        splitter.addWidget(right)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([settings.thumbnail_width(), 900])
        splitter.splitterMoved.connect(self.on_thumbnail_splitter_moved)
        lay.addWidget(splitter)
        self._viewer_splitter = splitter
        self.setCentralWidget(viewer)

        self.thumbs.page_selected.connect(self.show_page)
        self.thumbs.page_position_requested.connect(
            self.navigate_from_thumbnail)
        self.thumbs.page_moved.connect(self.on_thumb_moved)
        self.thumbs.verticalScrollBar().valueChanged.connect(
            lambda _v: self._schedule_thumbs())
        self.thumbs.thumbnail_width_changed.connect(
            self.on_thumbnail_width_changed)
        self.view.zoom_changed.connect(self.on_zoom_changed)
        self.view.viewport_changed.connect(
            self.update_thumbnail_viewport_marker)
        self.view.page_flip.connect(self.on_wheel_flip)
        self.view.canvas.drag_selected.connect(self.on_drag_selected)
        self.view.canvas.selection_cleared.connect(self._clear_selection)
        self.view.canvas.word_picked.connect(self.on_word_picked)
        self.view.canvas.clicked.connect(self._dispatch_click)
        self.view.canvas.context_requested.connect(self.on_context_menu)
        self.view.canvas.hovered.connect(self.on_canvas_hover)

        # 메모 모아보기 독 (기본 숨김) — 탭마다 독립
        self._notes_list = QListWidget()
        self._notes_list.itemClicked.connect(self.on_note_item_clicked)
        self._notes_list.itemDoubleClicked.connect(self.on_note_item_double)
        self._notes_dock = QDockWidget("메모 모아보기", self)
        self._notes_dock.setWidget(self._notes_list)
        self.addDockWidget(Qt.RightDockWidgetArea, self._notes_dock)
        self._notes_dock.hide()

        self._page_label = QLabel("")
        self.statusBar().addPermanentWidget(self._page_label)
        self._zoom_input = QSpinBox()
        self._zoom_input.setRange(
            round(self.view.ZOOM_MIN * 100), round(self.view.ZOOM_MAX * 100))
        self._zoom_input.setSingleStep(1)
        self._zoom_input.setSuffix("%")
        self._zoom_input.setKeyboardTracking(False)
        self._zoom_input.setValue(100)
        self._zoom_input.setToolTip("10~800% 범위를 1% 단위로 입력")
        self._zoom_input.valueChanged.connect(
            lambda value: self.set_zoom(value / 100.0))
        self.statusBar().addPermanentWidget(self._zoom_input)

        self._build_menus()

    def _build_search_bar(self):
        bar = QWidget()
        bar.setObjectName("searchBar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(6, 4, 6, 4)
        self._search_edit = QLineEdit()
        self._search_edit.addAction(
            fluent_icon("search", size=16), QLineEdit.LeadingPosition)
        self._search_edit.setPlaceholderText("검색어 입력 후 Enter (F3 다음 / Shift+F3 이전)")
        self._search_edit.returnPressed.connect(
            lambda: self.search_start(self._search_edit.text()))
        self._search_count = QLabel("")
        prev_btn = QToolButton(); prev_btn.setIcon(fluent_icon("chevron_up", size=16))
        next_btn = QToolButton(); next_btn.setIcon(fluent_icon("chevron_down", size=16))
        prev_btn.setToolTip("이전 검색 결과 (Shift+F3)")
        next_btn.setToolTip("다음 검색 결과 (F3)")
        prev_btn.clicked.connect(lambda _c=False: self.search_prev())
        next_btn.clicked.connect(lambda _c=False: self.search_next())
        close_btn = QPushButton("닫기")
        close_btn.setIcon(fluent_icon("close", size=16))
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

    def _act(self, menu, text, shortcut, slot, icon_name=None):
        a = _make_action(self, text, shortcut, slot, icon_name)
        menu.addAction(a)
        return a

    def _build_menus(self):
        m = self.menuBar().addMenu("파일(&F)")
        self._open_act = self._act(
            m, "열기...", "Ctrl+O", lambda: self._shell.open_dialog(), "open")
        self._act(m, "새 탭", "Ctrl+T", lambda: self._shell.open_dialog(),
                  "new_tab")
        self._act(m, "새 창", "Ctrl+Shift+N",
                  lambda: new_window(force_new=True), "new_window")
        self._recent_menu = m.addMenu("최근 파일")
        self._recent_menu.setIcon(fluent_icon("recent"))
        self._recent_menu.setToolTipsVisible(True)
        self._recent_menu.aboutToShow.connect(self._rebuild_recent_menu)
        self._fav_menu = m.addMenu("즐겨찾기")
        self._fav_menu.setIcon(fluent_icon("star"))
        self._fav_menu.setToolTipsVisible(True)
        self._fav_menu.aboutToShow.connect(self._rebuild_fav_menu)
        m.addSeparator()
        self._save_act = self._act(m, "저장", "Ctrl+S", self.save, "save")
        self._act(m, "다른 이름으로 저장...", "Ctrl+Shift+S",
                  self.save_as_dialog, "save_as")
        self._act(m, "탐색기에서 현재 위치 열기", None,
                  self.open_current_location, "external")
        m.addSeparator()
        self._act(m, "탭 닫기", "Ctrl+W",
                  lambda: self._shell.close_tab(self), "close")
        self._act(m, "종료", "Ctrl+Q", lambda: self._shell.close(), "power")

        e = self.menuBar().addMenu("편집(&E)")
        self._undo_act = self._act(
            e, "실행 취소", "Ctrl+Z", self.undo, "undo")
        self._redo_act = self._act(
            e, "다시 실행", "Ctrl+Y", self.redo, "redo")
        self._undo_act.setEnabled(False)
        self._redo_act.setEnabled(False)
        e.addSeparator()
        self._act(e, "복사", "Ctrl+C", self.copy_selection, "copy")
        self._act(e, "현재 페이지 모두 선택", "Ctrl+A", self.select_all,
                  "select_all")
        e.addSeparator()
        self._edit_act = self._act(e, "텍스트 편집 모드", "Ctrl+E",
                                   self.toggle_edit_mode, "edit")
        self._edit_act.setCheckable(True)
        e.addSeparator()
        self._search_act = self._act(
            e, "찾기...", "Ctrl+F", self.show_search, "search")
        self._act(e, "다음 찾기", "F3", self.search_next, "chevron_down")
        self._act(e, "이전 찾기", "Shift+F3", self.search_prev, "chevron_up")

        p = self.menuBar().addMenu("페이지(&P)")
        self._pages_act = self._act(
            p, "페이지 구성...", "Ctrl+Shift+P",
            self.show_page_organizer, "pages")
        p.addSeparator()
        self._act(p, "오른쪽으로 회전", "Ctrl+]", self.rotate_page_cw,
                  "rotate_cw")
        self._act(p, "왼쪽으로 회전", "Ctrl+[", self.rotate_page_ccw,
                  "rotate_ccw")
        self._act(p, "현재 페이지 삭제", "Ctrl+Delete",
                  self.delete_current_page, "delete")
        p.addSeparator()
        self._act(p, "PDF 병합...", None, self.merge_pdf, "merge")
        self._act(p, "PDF 분리...", None, self.split_pdf, "split")
        self._act(p, "현재 페이지 추출...", None,
                  self.extract_current_page, "extract")

        a = self.menuBar().addMenu("주석(&A)")
        self._act(a, "선택 영역 형광펜", "Ctrl+H",
                  self.highlight_selection, "highlight")
        self._act(a, "메모 추가 (위치 클릭)", "Ctrl+M",
                  self.start_note_mode, "note")
        a.addSeparator()
        self._act(a, "메모 모아보기", "Ctrl+Shift+M",
                  self.toggle_notes_panel, "notes")

        o = self.menuBar().addMenu("OCR(&O)")
        self._act(o, "현재 페이지 OCR", "Ctrl+R", self.ocr_current_page,
                  "ocr")
        self._act(o, "전체 문서 OCR (텍스트 없는 페이지만)", "Ctrl+Shift+R",
                  self.ocr_document, "ocr")
        o.addSeparator()
        self._act(o, "AI 고품질 OCR 설정...", None,
                  self.show_ocr_engine_dialog, "ai")

        v = self.menuBar().addMenu("보기(&V)")
        self._zoom_in_act = self._act(
            v, "확대", "Ctrl++", self.zoom_in, "zoom_in")
        self._zoom_out_act = self._act(
            v, "축소", "Ctrl+-", self.zoom_out, "zoom_out")
        self._act(v, "1% 확대", "Alt++", self.zoom_in_fine, "zoom_in")
        self._act(v, "1% 축소", "Alt+-", self.zoom_out_fine, "zoom_out")
        self._fit_width_act = self._act(
            v, "폭 맞춤", "Ctrl+0", self.zoom_fit, "fit_width")
        self._fit_page_act = self._act(
            v, "쪽 맞춤", None, self.zoom_page_fit, "fit_page")
        v.addSeparator()
        self._act(v, "다음 페이지", "PgDown", self.next_page,
                  "chevron_down")
        self._act(v, "이전 페이지", "PgUp", self.prev_page, "chevron_up")
        v.addSeparator()
        self._interaction_group = QActionGroup(self)
        self._interaction_group.setExclusive(True)
        self._select_tool_act = self._act(
            v, "텍스트 선택 도구", None,
            lambda: self.set_interaction_mode("select"), "text_select")
        self._hand_tool_act = self._act(
            v, "손 도구", None,
            lambda: self.set_interaction_mode("hand"), "hand")
        for action in (self._select_tool_act, self._hand_tool_act):
            action.setCheckable(True)
            self._interaction_group.addAction(action)
        self._select_tool_act.setChecked(True)
        self._favorite_act = _make_action(
            self, "즐겨찾기 추가", None, self._toggle_favorite, "star")
        self._favorite_act.setEnabled(False)

        tool_bar = QToolBar("명령 모음", self)
        tool_bar.setObjectName("command_bar")
        tool_bar.setMovable(False)
        tool_bar.setFloatable(False)
        tool_bar.setIconSize(QSize(20, 20))
        tool_bar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        tool_bar.addAction(self._open_act)
        tool_bar.addAction(self._save_act)
        tool_bar.addSeparator()
        tool_bar.addAction(self._undo_act)
        tool_bar.addAction(self._redo_act)
        tool_bar.addSeparator()
        tool_bar.addAction(self._hand_tool_act)
        tool_bar.addAction(self._select_tool_act)
        tool_bar.addSeparator()
        tool_bar.addAction(self._pages_act)
        tool_bar.addAction(self._search_act)
        tool_bar.addSeparator()
        tool_bar.addAction(self._favorite_act)
        tool_bar.addSeparator()
        tool_bar.addAction(self._zoom_in_act)
        tool_bar.addAction(self._zoom_out_act)
        tool_bar.addAction(self._fit_width_act)
        tool_bar.addAction(self._fit_page_act)
        self.addToolBar(Qt.TopToolBarArea, tool_bar)
        self._interaction_toolbar = tool_bar

        h = self.menuBar().addMenu("도움말(&H)")
        self._act(h, "사용법", "F1", self.show_help, "help")
        self._act(h, "업데이트 확인...", None,
                  lambda: self._shell.check_for_updates(True), "update")
        self._act(h, "PDF 기본 프로그램 / 브라우저 설정...", None,
                  self.check_default_app, "settings")
        self._act(h, "오픈소스 라이선스", None, self.show_licenses,
                  "license")
        self._act(h, "정보", None, self.show_about, "info")

    # --- 페이지 넘김/클릭 ---------------------------------------------

    def set_interaction_mode(self, mode, announce=True):
        if mode == "hand":
            if self._edit_mode:
                self.set_edit_mode(False)
            if self._note_mode:
                self.cancel_note_mode()
        self.view.set_interaction_mode(mode)
        self._hand_tool_act.setChecked(mode == "hand")
        self._select_tool_act.setChecked(mode == "select")
        if announce:
            message = (
                "손 도구 — PDF를 클릭한 채 드래그해 이동합니다"
                if mode == "hand" else
                "텍스트 선택 도구 — 글자를 드래그해 선택합니다"
            )
            self.statusBar().showMessage(message, 3000)

    def on_wheel_flip(self, direction):
        """휠로 페이지 끝에 닿았을 때 다음/이전 장으로."""
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

    # --- 최근 파일 / 즐겨찾기 (열기는 셸의 탭으로) ---------------------

    def _rebuild_recent_menu(self):
        self._recent_menu.clear()
        paths = settings.recent_files()
        if not paths:
            act = self._recent_menu.addAction("(비어 있음)")
            act.setEnabled(False)
            return
        for p in paths:
            label = "%s  —  %s" % (os.path.basename(p), os.path.dirname(p))
            if len(label) > 100:
                label = label[:60] + "…" + label[-39:]
            act = self._recent_menu.addAction(label)
            act.setIcon(fluent_icon("open"))
            act.setToolTip(p)
            act.triggered.connect(lambda _c=False, p=p: self._shell.open_recent(p))
        self._recent_menu.addSeparator()
        clear_action = self._recent_menu.addAction(
            "목록 지우기", lambda _c=False: settings.clear_recent())
        clear_action.setIcon(fluent_icon("delete"))

    def _rebuild_fav_menu(self):
        self._fav_menu.clear()
        self._sync_favorite_action()
        if self.doc is not None:
            if settings.is_favorite(self.doc.path):
                action = self._fav_menu.addAction(
                    "현재 파일을 즐겨찾기에서 제거",
                    lambda _c=False: self._toggle_favorite())
                action.setIcon(fluent_icon("star_filled", "#0f6cbd"))
            else:
                action = self._fav_menu.addAction(
                    "★ 현재 파일을 즐겨찾기에 추가",
                    lambda _c=False: self._toggle_favorite())
                action.setIcon(fluent_icon("star"))
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
            act.setIcon(fluent_icon("open"))
            act.setToolTip(p)
            act.triggered.connect(lambda _c=False, p=p: self._shell.open_recent(p))

    def _sync_favorite_action(self):
        """현재 문서의 즐겨찾기 여부를 도구 모음에 반영한다."""
        if self.doc is None or not self.doc.path:
            self._favorite_act.setText("즐겨찾기 추가")
            self._favorite_act.setIcon(fluent_icon("star"))
            self._favorite_act.setToolTip("PDF를 연 뒤 즐겨찾기에 추가할 수 있습니다")
            self._favorite_act.setEnabled(False)
            return
        favorite = settings.is_favorite(self.doc.path)
        self._favorite_act.setEnabled(True)
        self._favorite_act.setText(
            "즐겨찾기 해제" if favorite else "즐겨찾기 추가")
        self._favorite_act.setIcon(fluent_icon(
            "star_filled" if favorite else "star",
            "#0f6cbd" if favorite else "#424242"))
        self._favorite_act.setToolTip(
            "현재 PDF를 즐겨찾기에서 제거합니다" if favorite else
            "현재 PDF를 즐겨찾기에 추가합니다")

    def _toggle_favorite(self):
        if self.doc is None:
            return
        if settings.is_favorite(self.doc.path):
            settings.remove_favorite(self.doc.path)
            self.statusBar().showMessage("즐겨찾기에서 제거됨", 3000)
        else:
            settings.add_favorite(self.doc.path)
            self.statusBar().showMessage("즐겨찾기에 추가됨", 3000)
        self._sync_favorite_action()
        self._shell.refresh_start_page()

    # --- 문서 로드/정리 ------------------------------------------------

    def open_path(self, path):
        """이 탭에 문서를 연다(탭 생성 직후 한 번). 실패하면 doc=None으로 둔다."""
        from .core import Document, PasswordRequired
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

        self._set_document(doc, path)

    def open_snapshot(self, data, original_path):
        """다른 실행 창의 미저장 스냅샷을 원래 파일의 dirty 탭으로 연다."""
        from .core import Document
        try:
            doc = Document.from_snapshot(original_path, data)
        except Exception as e:
            QMessageBox.critical(
                self, "탭 이동 실패", "편집 중인 문서를 옮길 수 없습니다.\n\n%s" % e)
            return False
        self._set_document(doc, original_path)
        self._dirty = True
        self._update_title()
        return True

    def _set_document(self, doc, path):
        """파일/전송 스냅샷에 공통인 문서 탭 초기화를 한곳에서 수행한다."""
        self.doc = doc
        self.page_index = 0
        self._sync_favorite_action()
        self.thumbs.reset_pages(doc.page_count)
        self._update_title()
        settings.push_recent(path)
        self._set_fit_zoom(0)
        self.show_page(0)
        # 탭이 실제 화면에 배치된 뒤 확정된 폭과 모니터 DPR로 다시 맞춘다.
        QTimer.singleShot(0, lambda d=doc: self.finish_initial_layout(d))
        self._schedule_thumbs()
        self._notes_changed()
        if not doc.has_text(0):
            self.statusBar().showMessage(
                "텍스트 레이어가 없는 문서입니다 (스캔본) — 복사/검색은 OCR 후 가능", 6000)

    def close_doc(self):
        """탭이 닫힐 때 자원 정리. OCR 워커가 돌면 취소하고 문서를 닫는다."""
        self._save_thumbnail_width()
        w = getattr(self, "_ocr_worker", None)
        if w is not None:
            try:
                w.cancel()
                if not w.wait(2000):
                    w.kill_process()
                    w.wait(1000)
            except Exception:
                pass
        if self.doc is not None:
            self.doc.close()
            self.doc = None
        self._sync_favorite_action()
        self._cache.clear()
        self._reset_textsel()
        self._reset_annots()
        self._reset_edit()

    # --- 제목/상태 ----------------------------------------------------

    def tab_title(self):
        if self.doc is None:
            return "(빈 탭)"
        return ("*" if self._dirty else "") + os.path.basename(self.doc.path)

    def _update_title(self):
        # 탭은 자식 창이라 setWindowTitle은 안 보이지만, 셸이 라벨/제목을
        # 갱신하도록 신호를 쏜다.
        self.title_changed.emit()

    def _update_page_label(self):
        if self.doc is None:
            self._page_label.setText("")
        else:
            self._page_label.setText("%d / %d" % (
                self.page_index + 1, self.doc.page_count))
            if hasattr(self, "_zoom_input"):
                self._zoom_input.blockSignals(True)
                self._zoom_input.setValue(round(self.view.zoom * 100))
                self._zoom_input.blockSignals(False)

    def open_current_location(self):
        """현재 PDF를 선택한 상태로 Windows 탐색기를 연다."""
        if self.doc is None:
            return
        path = os.path.abspath(self.doc.path)
        if not os.path.exists(path):
            QMessageBox.warning(
                self, "파일 위치 열기", "현재 파일을 찾을 수 없습니다.\n%s" % path)
            return
        try:
            subprocess.Popen(["explorer.exe", "/select,", os.path.normpath(path)])
        except OSError as error:
            QMessageBox.warning(
                self, "파일 위치 열기",
                "Windows 탐색기를 열 수 없습니다.\n\n%s" % error)

    # --- 도움말/정보/OCR 설정 (탭 메뉴에서 호출) -----------------------

    def show_help(self):
        from .help import show_help
        show_help(self)

    def check_default_app(self):
        _show_default_app_settings(self)

    def show_about(self):
        QMessageBox.about(self, "정보", "%s %s" % (APP_NAME, APP_VERSION))

    def show_licenses(self):
        show_licenses(self)

    def show_ocr_engine_dialog(self):
        from . import settings, vl
        _kind, desc = vl.runtime_summary()
        installed = vl.vl_installed()
        cur = settings.ocr_engine()

        box = QMessageBox(self)
        box.setWindowTitle("AI 고품질 OCR 설정")
        box.setIcon(QMessageBox.Question)
        box.setText(
            "OCR 엔진을 선택하세요.\n\n"
            "• RapidOCR: 가볍고 빠름, 한글+영문. CPU에서 잘 동작.\n"
            "• AI 고품질(VL): 저품질 스캔·복잡한 레이아웃에 강함.\n"
            "  실행에 torch+transformers(수 GB) + 모델(약 2GB) 필요, GPU 권장.\n\n"
            "현재 가속기: %s\n"
            "VL 상태: %s\n"
            "현재 선택: %s"
            % (desc, vl.install_hint(),
               "AI 고품질(VL)" if cur == "vl" else "RapidOCR"))
        b_basic = box.addButton("RapidOCR로", QMessageBox.AcceptRole)
        b_basic.setIcon(fluent_icon("ocr"))
        b_vl = box.addButton("AI 고품질로", QMessageBox.AcceptRole)
        b_vl.setIcon(fluent_icon("ai"))
        b_cancel = box.addButton("취소", QMessageBox.RejectRole)
        b_cancel.setIcon(fluent_icon("close"))
        box.exec_()
        clicked = box.clickedButton()
        if clicked is b_basic:
            settings.set_ocr_engine("rapidocr")
            self.statusBar().showMessage("OCR 엔진: RapidOCR", 4000)
        elif clicked is b_vl:
            level, _specs, reason = vl.vl_suitability()
            if level in ("poor", "marginal"):
                ret = QMessageBox.question(
                    self, "VL 사양 확인",
                    "%s\n\n그래도 AI 고품질(VL)로 설정할까요?" % reason,
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if ret != QMessageBox.Yes:
                    self.statusBar().showMessage("RapidOCR 유지", 4000)
                    return
            settings.set_ocr_engine("vl")
            if installed:
                self.statusBar().showMessage("OCR 엔진: AI 고품질(VL)", 4000)
            elif vl.runtime_present() and vl.can_download():
                ret = QMessageBox.question(
                    self, "VL 모델 다운로드",
                    "AI 고품질(VL)을 선택했습니다.\n"
                    "모델(약 2GB)을 지금 다운로드할까요?\n\n"
                    "다운로드 전까지 OCR은 RapidOCR로 동작합니다.",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if ret == QMessageBox.Yes:
                    self._download_vl_models()
            else:
                QMessageBox.information(
                    self, "VL 준비 필요",
                    "AI 고품질(VL)을 선택했습니다(사양 확인됨).\n"
                    "빠진 것: %s\n\n"
                    "구성요소가 설치될 때까지 OCR은 RapidOCR로 "
                    "동작합니다.\n\n설치 방법:\n"
                    "1) 명령 프롬프트에서\n"
                    "   pip install torch torchvision transformers "
                    "huggingface_hub\n"
                    "   (GPU 사용 시 CUDA 지원 torch 빌드)\n"
                    "2) 이 대화상자를 다시 열어 'AI 고품질로'를 선택하면\n"
                    "   모델 다운로드를 안내합니다." % vl.install_hint())

    def _download_vl_models(self):
        from . import vl

        class _Dl(QThread):
            failed = pyqtSignal(str)

            def run(self):
                try:
                    vl.download_models()
                except Exception as e:
                    self.failed.emit(str(e))

        dlg = QProgressDialog(
            "VL 모델 다운로드 중... (약 2GB, 네트워크에 따라 수 분)",
            None, 0, 0, self)
        dlg.setWindowTitle("VL 모델 다운로드")
        dlg.setCancelButton(None)
        dlg.setMinimumDuration(0)

        th = _Dl(self)
        self._vl_dl_error = None

        def _on_fail(msg):
            self._vl_dl_error = msg

        def _on_done():
            dlg.close()
            th.deleteLater()
            if self._vl_dl_error:
                QMessageBox.critical(
                    self, "다운로드 실패",
                    "VL 모델 다운로드에 실패했습니다.\n\n%s" % self._vl_dl_error)
            elif vl.vl_installed():
                self.statusBar().showMessage(
                    "VL 모델 설치 완료 — OCR 엔진: AI 고품질(VL)", 6000)
            else:
                QMessageBox.warning(
                    self, "다운로드 미완료",
                    "다운로드가 끝났지만 모델 확인에 실패했습니다.\n"
                    "다시 시도해 주세요.")

        th.failed.connect(_on_fail)
        th.finished.connect(_on_done)
        th.start()
        dlg.exec_()

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


def show_licenses(parent):
    QMessageBox.information(parent, "오픈소스 라이선스", (
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


# ======================================================================
# AppWindow — 탭들을 담는 셸
# ======================================================================

class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 800)
        self.setAcceptDrops(True)
        self._update_service = GitHubUpdateService(APP_VERSION)
        self._update_worker = None
        self._available_update = None

        self._start_page = StartPage()
        self._start_page.open_file.connect(self.open_in_tab)
        self._start_page.browse.connect(self.open_dialog)
        self._start_page.back_to_doc.connect(self._show_tabs_if_any)

        self._tabs = QTabWidget()
        self._tabs.setTabBar(TransferTabBar(self._tabs))
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.setDocumentMode(True)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs.tabCloseRequested.connect(
            lambda i: self.close_tab(self._tabs.widget(i)))

        self._stack = QStackedWidget()
        self._stack.addWidget(self._start_page)  # 0
        self._stack.addWidget(self._tabs)        # 1
        self.setCentralWidget(self._stack)

        # 시작 페이지(탭 없음)일 때 쓰는 최소 메뉴바. 탭이 활성화되면 그 탭의
        # 메뉴바로 교체(reparent)한다.
        self._shell_menubar = self._build_shell_menu()
        self.setMenuBar(self._shell_menubar)
        self._show_start()
        if not any(getattr(window, "_auto_update_started", False)
                   for window in _app_windows):
            self._auto_update_started = True
            QTimer.singleShot(5000, lambda: self.check_for_updates(False))

        self._fluent_backdrop_attempted = False
        self._fluent_backdrop_applied = False

    def showEvent(self, event):
        super().showEvent(event)
        if not self._fluent_backdrop_attempted:
            from .windows_integration import apply_fluent_window_backdrop

            self._fluent_backdrop_attempted = True
            self._fluent_backdrop_applied = apply_fluent_window_backdrop(self)

    def _build_shell_menu(self):
        mb = QMenuBar(self)
        m = mb.addMenu("파일(&F)")
        m.addAction(_make_action(
            self, "열기...", "Ctrl+O", self.open_dialog, "open"))
        m.addAction(_make_action(
            self, "새 탭", "Ctrl+T", self.open_dialog, "new_tab"))
        m.addAction(_make_action(
            self, "새 창", "Ctrl+Shift+N", lambda: new_window(force_new=True),
            "new_window"))
        m.addSeparator()
        m.addAction(_make_action(
            self, "종료", "Ctrl+Q", self.close, "power"))
        h = mb.addMenu("도움말(&H)")
        h.addAction(_make_action(
            self, "사용법", "F1", self._shell_help, "help"))
        h.addAction(_make_action(
            self, "업데이트 확인...", None,
            lambda: self.check_for_updates(True), "update"))
        h.addAction(_make_action(
            self, "PDF 기본 프로그램 / 브라우저 설정...", None,
            lambda: _show_default_app_settings(self), "settings"))
        h.addAction(_make_action(self, "오픈소스 라이선스", None,
                                 lambda: show_licenses(self), "license"))
        h.addAction(_make_action(
            self, "정보", None, self._shell_about, "info"))
        return mb

    def _shell_help(self):
        from .help import show_help
        show_help(self)

    def _shell_about(self):
        QMessageBox.about(self, "정보", "%s %s" % (APP_NAME, APP_VERSION))

    # --- GitHub Releases 업데이트 ------------------------------------

    def check_for_updates(self, manual=True):
        if self._update_worker is not None and self._update_worker.isRunning():
            if manual:
                self.statusBar().showMessage(
                    "업데이트를 확인하고 있습니다…", 3000)
            return
        if manual:
            self.statusBar().showMessage(
                "GitHub에서 최신 버전을 확인하는 중입니다…")
        worker = UpdateCheckWorker(self._update_service, self)
        worker.completed.connect(
            lambda update: self._update_check_completed(update, manual))
        worker.failed.connect(
            lambda message: self._update_check_failed(message, manual))
        worker.finished.connect(self._update_check_finished)
        self._update_worker = worker
        worker.start()

    def _update_check_completed(self, update, manual):
        self.statusBar().clearMessage()
        if update is None:
            if manual:
                QMessageBox.information(
                    self, "업데이트 확인",
                    "현재 sPDF %s가 최신 버전입니다." % APP_VERSION)
            return
        self._available_update = update
        if manual:
            self._show_available_update()
        else:
            answer = QMessageBox.question(
                self, "sPDF 업데이트",
                "sPDF %s 업데이트가 있습니다.\n자세히 볼까요?"
                % update.version)
            if answer == QMessageBox.Yes:
                self._show_available_update()

    def _update_check_failed(self, message, manual):
        self.statusBar().clearMessage()
        if manual:
            QMessageBox.warning(self, "업데이트 확인 실패", message)

    def _update_check_finished(self):
        worker = self._update_worker
        self._update_worker = None
        if worker is not None:
            worker.deleteLater()

    def _show_available_update(self):
        update = self._available_update
        if update is None:
            return
        self._available_update = None
        dialog = UpdateDialog(self._update_service, update, self)
        dialog.install_requested.connect(self._launch_update_installer)
        dialog.exec_()

    def _launch_update_installer(self, path):
        answer = QMessageBox.question(
            self, "업데이트 설치",
            "설치 프로그램을 실행합니다.\n"
            "저장하지 않은 문서를 확인한 뒤 sPDF를 종료합니다. 계속할까요?")
        if answer != QMessageBox.Yes:
            return
        for window in list(_app_windows):
            for index in range(window._tabs.count()):
                if not window._tabs.widget(index).maybe_save():
                    return
        try:
            self._update_service.launch_installer(path)
        except UpdateError as error:
            QMessageBox.warning(self, "업데이트 실행 실패", str(error))
            return
        QApplication.instance().quit()

    # --- 화면 전환 -----------------------------------------------------

    def _show_start(self):
        self.setMenuBar(self._shell_menubar)
        self._start_page.refresh()
        self._start_page.set_current_doc(None)
        self._stack.setCurrentIndex(0)
        self.setWindowTitle(APP_NAME)

    def _show_tabs(self):
        self._stack.setCurrentIndex(1)

    def _show_tabs_if_any(self):
        if self._tabs.count() > 0:
            self._show_tabs()

    def refresh_start_page(self):
        self._start_page.refresh()

    # --- 파일 열기 (탭으로) --------------------------------------------

    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "PDF 열기", "", "PDF 파일 (*.pdf)")
        if path:
            self.open_in_tab(path)

    def open_recent(self, path):
        if not os.path.exists(path):
            QMessageBox.warning(self, "파일 없음",
                                "파일이 이동되었거나 삭제되었습니다:\n%s" % path)
            settings.remove_recent(path)
            self.refresh_start_page()
            return
        self.open_in_tab(path)

    def open_in_tab(self, path):
        """파일을 탭으로 연다. 이미 열려 있으면 그 탭으로 전환(중복 방지)."""
        existing = self._find_open_tab(path)
        if existing is not None:
            self._tabs.setCurrentWidget(existing)
            self._show_tabs()
            return existing
        tab = DocumentTab(self)
        self._connect_tab(tab)
        idx = self._tabs.addTab(tab, "불러오는 중...")
        self._tabs.setCurrentIndex(idx)
        self._show_tabs()
        # 레이아웃이 끝난 뒤 열어야 '창 너비 맞춤' 배율이 정확하다.
        QTimer.singleShot(0, lambda: self._load_into(tab, path))
        return tab

    def _find_open_tab(self, path):
        target = os.path.normcase(os.path.abspath(path))
        for i in range(self._tabs.count()):
            tab = self._tabs.widget(i)
            if tab.doc is not None and \
                    os.path.normcase(os.path.abspath(tab.doc.path)) == target:
                return tab
        return None

    def open_snapshot_in_tab(self, snapshot_path, original_path):
        """별도 sPDF 프로세스가 넘긴 미저장 PDF를 읽고 임시 파일을 회수한다."""
        if self._find_open_tab(original_path) is not None:
            return False
        try:
            with open(snapshot_path, "rb") as stream:
                data = stream.read()
            os.remove(snapshot_path)
        except OSError as e:
            QMessageBox.critical(
                self, "탭 이동 실패", "임시 문서를 읽을 수 없습니다.\n\n%s" % e)
            return False

        tab = DocumentTab(self)
        self._connect_tab(tab)
        index = self._tabs.addTab(tab, "옮기는 중...")
        self._tabs.setCurrentIndex(index)
        self._show_tabs()
        if not tab.open_snapshot(data, original_path):
            self._remove_tab(tab)
            return False
        self._sync_tab_title(tab)
        return True

    def _load_into(self, tab, path):
        tab.open_path(path)
        if tab.doc is None:
            self._remove_tab(tab)  # 열기 실패/취소 → 빈 탭 제거
        else:
            self._sync_tab_title(tab)

    # --- 탭 제목/전환/닫기 ---------------------------------------------

    def _connect_tab(self, tab):
        """이동 전 창에 남은 제목 신호를 끊고 현재 셸에 다시 연결한다."""
        old_slot = getattr(tab, "_shell_title_slot", None)
        if old_slot is not None:
            try:
                tab.title_changed.disconnect(old_slot)
            except TypeError:
                pass
        tab._shell = self
        slot = lambda t=tab, shell=self: shell._sync_tab_title(t)
        tab._shell_title_slot = slot
        tab.title_changed.connect(slot)

    def _adopt_tab(self, source, tab, index):
        """같은 프로세스의 다른 창에서 문서 위젯과 편집 상태를 그대로 받는다."""
        source_index = source._tabs.indexOf(tab)
        if source_index < 0:
            return
        title = tab.tab_title()
        tooltip = tab.doc.path if tab.doc else ""
        source._tabs.removeTab(source_index)

        self._connect_tab(tab)
        index = max(0, min(index, self._tabs.count()))
        new_index = self._tabs.insertTab(index, tab, title)
        self._tabs.setTabToolTip(new_index, tooltip)
        self._tabs.setCurrentIndex(new_index)
        self._show_tabs()
        self.show()
        self.raise_()
        self.activateWindow()
        source._close_if_empty_after_move()

    def _receive_tab_drop(self, payload, index):
        """탭 막대와 빈 창 시작 화면이 함께 쓰는 창 간 이동 처리."""
        if not payload or not payload.get("path"):
            return False
        entry = _dragged_tabs.get(payload.get("token")) \
            if payload.get("pid") == os.getpid() else None
        if entry is not None:
            source, tab = entry
            if source is self:
                return False
            self._adopt_tab(source, tab, index)
            return True
        if payload.get("dirty"):
            # 프로세스 경계를 넘으면 QWidget 대신 현재 PDF 스냅샷을 복원한다.
            return self.open_snapshot_in_tab(
                payload.get("snapshot"), payload.get("path"))
        self.open_in_tab(payload.get("path"))
        return True

    def _finish_external_tab_move(self, tab):
        """다른 프로세스가 저장된 파일을 받은 뒤 원본 탭 자원을 정리한다."""
        self._remove_tab(tab)
        self._close_if_empty_after_move()

    def _close_if_empty_after_move(self):
        if self._tabs.count() == 0:
            # 드롭 이벤트/QDrag 중에 창을 파괴하면 Qt가 소스 객체를 다시
            # 참조할 수 있으므로 이벤트 루프로 돌아간 뒤 닫는다.
            QTimer.singleShot(0, self.close)

    def _sync_tab_title(self, tab):
        i = self._tabs.indexOf(tab)
        if i < 0:
            return
        name = tab.tab_title()
        self._tabs.setTabText(i, name)
        self._tabs.setTabToolTip(i, tab.doc.path if tab.doc else "")
        if self._tabs.currentWidget() is tab:
            self.setWindowTitle(
                "%s — %s" % (name, APP_NAME) if tab.doc else APP_NAME)

    def _on_tab_changed(self, i):
        if i < 0:
            self._show_start()
            return
        tab = self._tabs.widget(i)
        self.setMenuBar(tab._menubar)  # 활성 탭 메뉴바를 셸에 붙인다
        self._sync_tab_title(tab)

    def close_tab(self, tab):
        if tab is None or not tab.maybe_save():
            return
        self._remove_tab(tab)

    def _remove_tab(self, tab):
        i = self._tabs.indexOf(tab)
        if i >= 0:
            self._tabs.removeTab(i)
        mb = getattr(tab, "_menubar", None)
        tab.close_doc()
        if mb is not None:
            mb.setParent(None)
            mb.deleteLater()  # 셸로 reparent됐을 수 있어 탭과 함께 안 지워진다
        tab.deleteLater()
        if self._tabs.count() == 0:
            self._show_start()

    # --- 종료/드롭 -----------------------------------------------------

    def closeEvent(self, ev):
        for i in range(self._tabs.count()):
            tab = self._tabs.widget(i)
            self._tabs.setCurrentIndex(i)
            if not tab.maybe_save():
                ev.ignore()
                return
        # 창의 X 버튼으로 종료할 때도 탭 닫기와 같은 경로를 거쳐 OCR 자식
        # 프로세스와 열린 문서를 확실히 정리한다.
        for i in range(self._tabs.count()):
            self._tabs.widget(i).close_doc()
        super().closeEvent(ev)
        if ev.isAccepted() and self._update_worker is not None and \
                self._update_worker.isRunning():
            self._update_worker.requestInterruption()
            self._update_worker.wait(1000)
        if ev.isAccepted() and self in _app_windows:
            _app_windows.remove(self)

    def dragEnterEvent(self, ev):
        if self._tabs.tabBar()._can_accept(ev.mimeData()):
            ev.setDropAction(Qt.MoveAction)
            ev.accept()
            return
        urls = ev.mimeData().urls()
        if urls and urls[0].toLocalFile().lower().endswith(".pdf"):
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        payload = _decode_tab_drag(ev.mimeData())
        if payload is not None:
            if self._receive_tab_drop(payload, self._tabs.count()):
                ev.setDropAction(Qt.MoveAction)
                ev.accept()
            else:
                ev.ignore()
            return
        for url in ev.mimeData().urls():
            p = url.toLocalFile()
            if p.lower().endswith(".pdf"):
                self.open_in_tab(p)


# ======================================================================
# 진입점 — 여러 AppWindow가 탭을 서로 주고받을 수 있다
# ======================================================================

_app_windows = []


def new_window(path=None, force_new=False):
    """기본 창을 재사용하되, 요청하면 탭을 받을 새 창을 만든다."""
    if force_new or not _app_windows:
        window = AppWindow()
        if _app_windows:
            previous = _app_windows[-1]
            window.move(previous.x() + 30, previous.y() + 30)
        _app_windows.append(window)
        window.show()
    else:
        window = _app_windows[0]
        window.raise_()
        window.activateWindow()
    if path:
        QTimer.singleShot(0, lambda: window.open_in_tab(path))
    return window

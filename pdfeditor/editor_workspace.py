"""Grid-first standalone editing; share one document and undo history."""

from PyQt5.QtCore import QItemSelectionModel
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from .i18n import localize
from .icons import fluent_icon
from .page_organizer import PageOrganizerPanel


class EditorWorkspaceMixin:
    def _init_editor_workspace(self, viewer):
        self._page_grid = None
        self._workspace_header = None
        self._editor_overview = self._shell.workspace_mode == "editor"
        if not self._editor_overview:
            return viewer
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._workspace_header = QWidget()
        header = QHBoxLayout(self._workspace_header)
        header.setContentsMargins(16, 8, 16, 8)
        self._workspace_label = QLabel(localize("Edit mode · Page overview", "편집 모드 · 페이지 구성"))
        self._workspace_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        header.addWidget(self._workspace_label)
        header.addStretch(1)
        layout.addWidget(self._workspace_header)
        self._overview_button = self._mode_button(localize("Page overview", "페이지 구성"), "pages")
        self._detail_button = self._mode_button(localize("Edit page", "상세 편집"), "edit", accent=True)
        self._overview_button.clicked.connect(self.show_editor_overview)
        self._detail_button.clicked.connect(lambda: self.open_page_editor())
        header.addWidget(self._overview_button)
        header.addWidget(self._detail_button)
        self._grid_document = None
        self._page_grid = PageOrganizerPanel(self, grid=True)
        self._page_grid.page_activated.connect(self.open_page_editor)
        self._page_grid.pages.currentRowChanged.connect(self._select_overview_page)
        self._editor_stack = QStackedWidget()
        self._editor_stack.addWidget(self._page_grid)
        self._editor_stack.addWidget(viewer)
        layout.addWidget(self._editor_stack, 1)
        return container

    def add_editor_mode_button(self, tool_bar):
        self._editor_mode_button = self._mode_button(
            localize("Edit mode", "편집 모드"), "edit", accent=True)
        self._editor_mode_button.setObjectName("openEditorModeButton")
        self._editor_mode_button.setToolTip(localize(
            "Open the page organizer in an editor window (Ctrl+E)",
            "편집 창의 페이지 구성으로 열기 (Ctrl+E)"))
        self._editor_mode_button.clicked.connect(lambda: self._shell.open_editor(self))
        tool_bar.addWidget(self._editor_mode_button)
        tool_bar.addSeparator()

    @staticmethod
    def _mode_button(text, icon, *, accent=False):
        button = QPushButton(text)
        button.setMinimumSize(145, 40)
        button.setProperty("accent", accent)
        button.setStyleSheet("font-size: 14px; font-weight: 600;")
        button.setIcon(fluent_icon(icon, "#ffffff" if accent else "#242424"))
        return button

    def is_editor_overview(self):
        return getattr(self, "_editor_overview", False)

    def _select_overview_page(self, row):
        if not self.is_editor_overview() or self.doc is None or row < 0:
            return
        self.page_index = row
        self._update_page_label()
        self.schedule_reading_position()

    def refresh_editor_overview(self, *, reset=False):
        grid = self._page_grid
        if grid is None or self.doc is None:
            return
        if reset:
            self._grid_document = None
        if not self.is_editor_overview():
            return
        if self._grid_document is not self.doc or grid.pages.count() != self.doc.page_count:
            self._grid_document = self.doc
            grid.refresh(self.page_index)
        elif grid.pages.currentRow() != self.page_index:
            grid.pages.setCurrentRow(self.page_index, QItemSelectionModel.ClearAndSelect)
        self._sync_editor_workspace_actions()

    def show_editor_overview(self):
        if self._page_grid is None or self.doc is None:
            return
        self.set_edit_mode(False)
        self.cancel_note_mode()
        self.hide_search()
        self._notes_dock.hide()
        self._zoom_render_timer.stop()
        self._thumb_timer.stop()
        self._editor_overview = True
        self._editor_stack.setCurrentWidget(self._page_grid)
        self.refresh_editor_overview(reset=True)
        self._page_grid.pages.setFocus()
        self.statusBar().showMessage(localize(
            "Drag pages to reorder; double-click a page to edit. Ctrl+Z undoes changes.",
            "페이지를 끌어 순서를 바꾸고, 두 번 눌러 상세 편집하세요. Ctrl+Z로 되돌릴 수 있습니다."))

    def open_page_editor(self, page=None, *, edit_text=True):
        if self._page_grid is None or self.doc is None:
            return
        page = self.page_index if page is None else int(page)
        page = max(0, min(page, self.doc.page_count - 1))
        self._editor_overview = False
        self._page_grid.stop_rendering()
        self._editor_stack.setCurrentIndex(1)
        self._two_page_mode = False
        self._two_page_act.setChecked(False)
        self._set_fit_zoom(page)
        self.show_page(page)
        self.set_edit_mode(edit_text)
        self._sync_editor_workspace_actions()
        self._schedule_thumbs()
        self.view.setFocus()

    def _sync_editor_workspace_actions(self):
        if self._page_grid is not None:
            self._workspace_label.setText(localize(
                "Edit mode · Page overview" if self.is_editor_overview() else "Edit mode · Page editing",
                "편집 모드 · 페이지 구성" if self.is_editor_overview() else "편집 모드 · 상세 편집"))
            self._overview_button.setEnabled(not self.is_editor_overview())
            self._detail_button.setEnabled(self.is_editor_overview())
        if hasattr(self, "_pages_act"):
            self._pages_act.setCheckable(True)
            self._pages_act.setChecked(self.is_editor_overview())
            self._pages_act.setToolTip(localize(
                "Page overview — reorder pages or return from detailed editing (Ctrl+Shift+P)",
                "페이지 구성 — 순서 조정 / 상세 편집에서 돌아가기 (Ctrl+Shift+P)"))
        if hasattr(self, "_zoom_input"):
            self._zoom_input.setVisible(not self.is_editor_overview())

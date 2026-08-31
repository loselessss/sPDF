"""Offline license texts and an explicit, version-matched source link."""

from html import escape
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QTabWidget, QTextBrowser, QVBoxLayout,
)

from .i18n import localize, tr
from .icons import fluent_icon
from .meta import APP_NAME, APP_VERSION
from .paths import resource


def source_url():
    return "https://github.com/loselessss/sPDF/releases/tag/v" + APP_VERSION


def summary_html():
    return localize(
        "<h2>{name} {version}</h2><p>Copyright (c) 2026 loselessss and contributors.</p>"
        "<p>Licensed under <b>GNU AGPL v3 only (AGPL-3.0-only)</b>. You may "
        "redistribute and modify sPDF under those terms.</p>"
        "<p>WITHOUT ANY WARRANTY, including merchantability or fitness for a "
        "particular purpose. Read the full license in the AGPL v3 tab.</p>"
        "<p><a href='{url}'>Source code for this version</a>: download the source "
        "ZIP and dependency source guide alongside the installer.</p>"
        "<p>Third-party components keep their own licenses. Previous MIT "
        "permissions remain valid for the earlier code they cover.</p>",
        "<h2>{name} {version}</h2><p>Copyright (c) 2026 loselessss and contributors.</p>"
        "<p><b>GNU AGPL v3만 적용(AGPL-3.0-only)</b>하며, 그 조건에 따라 "
        "sPDF를 재배포·수정할 수 있습니다.</p>"
        "<p>상품성·특정 목적 적합성을 포함하여 어떠한 보증도 제공하지 않습니다. "
        "전체 조건은 AGPL v3 탭에서 읽을 수 있습니다.</p>"
        "<p><a href='{url}'>이 버전의 소스 코드</a>: 설치 파일 옆의 소스 ZIP과 "
        "의존성 소스 안내를 함께 받으세요.</p>"
        "<p>외부 구성요소의 라이선스는 그대로 유지하며, 이전 MIT 코드에 "
        "이미 부여된 권한도 유지됩니다.</p>",
    ).format(name=escape(APP_NAME), version=escape(APP_VERSION), url=source_url())


class LicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("오픈소스 라이선스"))
        self.resize(760, 580)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)
        summary = QTextBrowser(self)
        summary.setOpenExternalLinks(True)  # Only an explicit click opens a URL.
        summary.setHtml(summary_html())
        self.tabs.addTab(summary, localize("License / Source code", "라이선스 / 소스 코드"))
        for label, relative in (
            ("AGPL v3", "LICENSE"),
            (localize("Third-party notices", "외부 구성요소 고지"), "LICENSES.md"),
            ("GPL v3", "licenses/GPL-3.0.txt"),
            ("LGPL v3", "licenses/LGPL-3.0.txt"),
            ("Apache 2.0", "licenses/Apache-2.0.txt"),
            (localize("Previous MIT notice", "기존 MIT 고지"), "licenses/MIT-sPDF-legacy.txt"),
            (localize("Source guide", "소스 제공 안내"), "SOURCE_CODE.md"),
        ):
            browser = QTextBrowser(self)
            # Plain text keeps local license documents offline and inert.
            try:
                content = Path(resource(*relative.split("/"))).read_text(encoding="utf-8")
            except OSError:
                content = localize("License file is missing: ", "라이선스 파일이 없습니다: ") + relative
            browser.setPlainText(content)
            self.tabs.addTab(browser, label)
        self.tabs.setUsesScrollButtons(True)
        buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        buttons.button(QDialogButtonBox.Close).setText(localize("Close", "닫기"))
        buttons.button(QDialogButtonBox.Close).setIcon(fluent_icon("close"))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


def show_licenses(parent):
    LicenseDialog(parent).exec_()

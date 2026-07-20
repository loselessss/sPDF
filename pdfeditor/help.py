"""사용법 다이얼로그 — 기능과 단축키를 한눈에.

기능이 늘 때마다 여기도 같이 갱신할 것(안 그러면 금방 낡는다).
"""

from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QScrollArea, QLabel, QVBoxLayout, QWidget,
)

from .meta import APP_NAME, APP_VERSION

HELP_HTML = """
<h2>{name} 사용법</h2>
<p style="color:gray;">v{ver} · 가벼운 PDF 보기 · 주석 · OCR · 편집 도구</p>

<h3>📂 파일</h3>
<table cellpadding="4">
<tr><td><b>Ctrl+O</b> / <b>Ctrl+T</b></td><td>PDF 열기 — 새 <b>탭</b>으로</td></tr>
<tr><td>도움말 메뉴</td><td><b>PDF 기본 프로그램 확인</b> — 현재 연결 확인 / 설정 열기</td></tr>
<tr><td><b>Ctrl+S</b></td><td>저장 (원본은 <code>.bak</code>으로 자동 백업)</td></tr>
<tr><td><b>Ctrl+Shift+S</b></td><td>다른 이름으로 저장</td></tr>
<tr><td><b>Ctrl+W</b></td><td>탭 닫기</td></tr>
</table>
<p>여러 PDF를 <b>탭</b>으로 엽니다. 각 탭은 페이지·편집·검색 상태를 따로
가집니다. 이미 열어둔 파일을 또 열면 새 탭 대신 <b>그 탭으로</b> 이동합니다
— 같은 파일을 두 곳에서 고치다 저장이 덮어써지는 걸 막기 위해서입니다.
탭은 드래그로 순서를 바꿀 수 있습니다.</p>
<p>탭을 모두 닫으면 <b>시작 페이지</b>가 나오고, 여기서 <b>즐겨찾기 / 최근
파일</b>을 바로 열 수 있습니다. 파일을 창으로 <b>드래그&드롭</b>해도 새 탭으로
열립니다. 암호가 걸린 PDF는 열 때 비밀번호를 물어봅니다.</p>

<h3>🔍 보기 · 이동</h3>
<table cellpadding="4">
<tr><td><b>Ctrl + 마우스휠</b></td><td>확대/축소</td></tr>
<tr><td><b>Ctrl++ / Ctrl+-</b></td><td>확대 / 축소</td></tr>
<tr><td><b>Ctrl+0</b></td><td>창 너비에 맞춤</td></tr>
<tr><td><b>PgUp / PgDown</b></td><td>이전 / 다음 페이지</td></tr>
<tr><td>왼쪽 <b>썸네일</b> 클릭</td><td>해당 페이지로 이동</td></tr>
<tr><td><b>마우스 휠</b></td><td>스크롤 — 페이지 끝에 닿으면 다음/이전 장으로</td></tr>
</table>

<h3>✂️ 텍스트 선택 · 복사 · 검색</h3>
<table cellpadding="4">
<tr><td><b>드래그</b></td><td>텍스트 선택</td></tr>
<tr><td><b>더블클릭</b></td><td>단어 하나 선택</td></tr>
<tr><td><b>Ctrl+A</b></td><td>현재 페이지 전체 선택</td></tr>
<tr><td><b>Ctrl+C</b></td><td>선택 텍스트 복사 (줄바꿈 유지)</td></tr>
<tr><td><b>Ctrl+F</b></td><td>찾기 (Enter로 검색)</td></tr>
<tr><td><b>F3 / Shift+F3</b></td><td>다음 / 이전 검색 결과</td></tr>
</table>
<p>스캔본(텍스트 레이어 없는 PDF)은 먼저 <b>OCR</b>을 해야 선택·검색이
됩니다.</p>

<h3>🖍️ 주석 (형광펜 · 메모)</h3>
<table cellpadding="4">
<tr><td><b>Ctrl+H</b></td><td>선택 영역에 형광펜</td></tr>
<tr><td><b>Ctrl+M</b></td><td>메모 추가 (그 다음 위치 클릭)</td></tr>
<tr><td><b>Ctrl+Shift+M</b></td><td>메모 모아보기 패널 열기/닫기</td></tr>
</table>
<p>메모 아이콘에 <b>마우스를 올리면</b> 내용이 뜨고, <b>클릭</b>하면
편집됩니다. 우클릭 메뉴로 형광펜/메모/삭제도 됩니다. 모아보기 패널에서
항목을 클릭하면 해당 위치로 이동합니다. <b>주석은 저장해야 파일에
남습니다.</b></p>

<h3>🔤 OCR (문자 인식)</h3>
<table cellpadding="4">
<tr><td><b>Ctrl+R</b></td><td>현재 페이지 OCR</td></tr>
<tr><td><b>Ctrl+Shift+R</b></td><td>전체 문서 OCR (텍스트 없는 페이지만)</td></tr>
</table>
<p>스캔본에 보이지 않는 텍스트 층을 입혀 <b>검색·복사가 가능</b>해집니다
(외관은 그대로). 한국어+영어. 첫 실행 때 인식 모델을 자동 내려받습니다.
저장하면 '검색 가능한 PDF'로 반영됩니다.</p>

<h3>✏️ 텍스트 편집</h3>
<table cellpadding="4">
<tr><td><b>Ctrl+E</b></td><td>편집 모드 켜기/끄기</td></tr>
<tr><td><b>Ctrl+Z / Ctrl+Y</b></td><td>실행 취소 / 다시 실행</td></tr>
</table>
<p>편집 모드에서 <b>초록 테두리</b>로 표시된 글자 토막을 클릭해 내용을
고칩니다. <b>빈 곳을 클릭</b>하면 그 자리에 새 글자를 얹습니다.</p>
<p><b>스캔본도 편집됩니다</b> — 먼저 OCR(Ctrl+R)을 돌리면 글자를 클릭할 수
있게 되고, 고치면 주변 종이색을 자동으로 떠서 원래 글자를 덮은 뒤 새 글자를
씁니다. 배경이 깨끗한 문서는 티가 잘 안 나고, 얼룩·무늬가 있는 스캔은 덮은
자리가 보일 수 있습니다.</p>
<p><span style="color:#b00;">한계</span>: 원본 글꼴이 파일에 없으면
기본 글꼴로 다시 써져 <b>모양이 달라질 수 있고</b>, 글자가 길어져도 다음
줄로 밀리지 않습니다(그 줄 안에서만 교체). 내용 수정용입니다.</p>

<h3>📑 페이지 조작</h3>
<table cellpadding="4">
<tr><td><b>Ctrl+] / Ctrl+[</b></td><td>오른쪽 / 왼쪽으로 회전</td></tr>
<tr><td><b>Ctrl+Delete</b></td><td>현재 페이지 삭제</td></tr>
<tr><td>썸네일 <b>드래그</b></td><td>페이지 순서 변경</td></tr>
<tr><td>페이지 메뉴</td><td>다른 PDF 병합 / 현재 페이지 추출</td></tr>
</table>
<p>회전·삭제·순서변경·병합은 모두 <b>Ctrl+Z</b>로 되돌릴 수 있습니다.</p>

<p style="color:gray;">도움말 → 오픈소스 라이선스에서 사용된 오픈소스
목록을 볼 수 있습니다.</p>
"""


def show_help(parent):
    dlg = QDialog(parent)
    dlg.setWindowTitle("%s 사용법" % APP_NAME)
    dlg.resize(560, 640)
    lay = QVBoxLayout(dlg)

    body = QLabel(HELP_HTML.format(name=APP_NAME, ver=APP_VERSION))
    body.setWordWrap(True)
    body.setTextFormat(1)  # Qt.RichText
    inner = QWidget()
    il = QVBoxLayout(inner)
    il.addWidget(body)
    il.addStretch(1)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(inner)
    lay.addWidget(scroll, 1)

    btns = QDialogButtonBox(QDialogButtonBox.Close)
    btns.rejected.connect(dlg.reject)
    btns.accepted.connect(dlg.accept)
    lay.addWidget(btns)
    dlg.exec_()

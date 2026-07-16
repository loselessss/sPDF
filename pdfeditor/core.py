"""PyMuPDF 래핑 — 문서 열기/저장/렌더/텍스트 추출.

Qt에 의존하지 않는다(설계 계획서 §4). GUI 없이 단독 테스트가 가능해야
하므로 이 모듈에서는 PyQt를 import 하지 말 것.
"""
import os
import shutil

import fitz


class PasswordRequired(Exception):
    """암호가 걸린 PDF — 호출부가 비밀번호를 받아 다시 시도해야 한다."""


class Document:
    """열린 PDF 한 건. 페이지 렌더와 텍스트 추출의 단일 창구."""

    def __init__(self, path, password=None):
        self.path = path
        # 같은 경로로 저장할 때 핸들을 닫았다가 다시 열어야 해서(save_as 참고)
        # 비밀번호를 들고 있어야 한다.
        self._password = password
        self._doc = self._open(path, password)

    @staticmethod
    def _open(path, password):
        doc = fitz.open(path)
        if doc.needs_pass:
            if password is None or not doc.authenticate(password):
                doc.close()
                raise PasswordRequired(path)
        return doc

    # --- 수명 주기 ---------------------------------------------------

    def close(self):
        if self._doc is not None:
            self._doc.close()
            self._doc = None

    @property
    def page_count(self):
        return self._doc.page_count

    # --- 렌더 -------------------------------------------------------

    def render(self, index, zoom=1.0):
        """페이지를 RGB888 픽셀로 렌더. (width, height, stride, bytes) 반환.

        Qt 타입(QImage)을 여기서 만들지 않는 건 이 모듈을 Qt 비의존으로
        유지하기 위해서다 — 조립은 widgets.py가 한다.
        """
        page = self._doc[index]
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pix.width, pix.height, pix.stride, pix.samples

    def page_size(self, index):
        r = self._doc[index].rect
        return r.width, r.height

    # --- 텍스트 -----------------------------------------------------

    def words(self, index):
        """단어별 (x0, y0, x1, y1, text, block, line, word_no) 목록 —
        PDF 좌표계(zoom=1 기준).

        선택/복사(§3.2)가 이 좌표를 쓴다. 화면 좌표 변환은 보는 쪽이
        zoom을 곱해서 처리. block/line 번호는 복사할 때 줄바꿈을 복원하는
        용도.
        """
        return list(self._doc[index].get_text("words"))

    def search(self, index, needle):
        """페이지 안에서 문자열 검색 — 일치 영역 (x0,y0,x1,y1) 목록."""
        return [(r.x0, r.y0, r.x1, r.y1)
                for r in self._doc[index].search_for(needle)]

    def has_text(self, index):
        """텍스트 레이어 유무 — 스캔본이면 False(→ OCR 필요)."""
        return bool(self._doc[index].get_text("text").strip())

    def spans(self, index):
        """편집 단위(span = 같은 글꼴/크기로 이어진 한 토막) 목록.

        편집은 이 단위로 한다 — PDF는 글자를 좌표에 찍어놓은 포맷이라
        '문단'이라는 개념이 없기 때문(설계 §3.4).
        """
        out = []
        for block in self._doc[index].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for sp in line.get("spans", []):
                    if not sp["text"].strip():
                        continue
                    c = sp["color"]
                    out.append({
                        "bbox": tuple(sp["bbox"]),
                        "origin": tuple(sp["origin"]),  # 글자 baseline 시작점
                        "text": sp["text"],
                        "size": sp["size"],
                        "flags": sp["flags"],
                        "font": sp["font"],
                        # PyMuPDF는 색을 int로 준다 → RGB 0~1 튜플로
                        "rgb": (((c >> 16) & 255) / 255.0,
                                ((c >> 8) & 255) / 255.0,
                                (c & 255) / 255.0),
                    })
        return out

    # --- 주석 (형광펜/메모) -------------------------------------------

    # 주의: 아래 메서드들은 page 객체를 지역변수로 반드시 붙들어야 한다.
    # self._doc[index].add_...() 처럼 임시로 쓰면 그 줄이 끝날 때 page가
    # GC되면서 annot이 "not bound to any page"로 죽는다(PyMuPDF 특성).

    def add_highlight(self, index, rects):
        """형광펜 — rects는 (x0,y0,x1,y1) 목록(줄 단위 권장)."""
        page = self._doc[index]
        annot = page.add_highlight_annot([fitz.Rect(*r) for r in rects])
        annot.update()
        return annot.xref

    def add_note(self, index, x, y, text):
        """스티키 노트 — 아이콘이 (x, y)에 붙는다."""
        page = self._doc[index]
        annot = page.add_text_annot(fitz.Point(x, y), text)
        annot.update()
        return annot.xref

    def annots(self, index):
        """페이지의 주석 목록 — 우클릭 히트테스트/편집용."""
        page = self._doc[index]
        out = []
        for a in page.annots():
            r = a.rect
            out.append({"xref": a.xref, "kind": a.type[1],
                        "rect": (r.x0, r.y0, r.x1, r.y1),
                        "text": a.info.get("content", "")})
        return out

    def set_note_text(self, index, xref, text):
        page = self._doc[index]
        for a in page.annots():
            if a.xref == xref:
                a.set_info(content=text)
                a.update()
                return

    def delete_annot(self, index, xref):
        page = self._doc[index]
        for a in page.annots():
            if a.xref == xref:
                page.delete_annot(a)
                return

    # --- OCR --------------------------------------------------------

    def insert_ocr_text(self, index, items):
        """OCR 결과를 보이지 않는 텍스트 레이어로 삽입(설계 §3.3).

        items: (x0, y0, x1, y1, text) 목록, PDF 좌표계.
        render_mode=3이 '그리지 않는 텍스트' — 화면 외관은 그대로 두고
        검색/선택만 가능하게 만든다. 폰트는 PyMuPDF 내장 CJK("korea")로
        한글+영문을 모두 커버한다(임베드 파일 불필요).
        """
        page = self._doc[index]
        n = 0
        for x0, y0, x1, y1, text in items:
            if not text.strip():
                continue
            h = y1 - y0
            # 베이스라인은 박스 바닥에서 살짝 위 — 선택 영역이 원문과
            # 대충 겹치기만 하면 된다(어차피 안 보이는 글자).
            page.insert_text((x0, y1 - h * 0.18), text,
                             fontsize=max(4.0, h * 0.85),
                             fontname="korea", render_mode=3)
            n += 1
        return n

    # --- 텍스트 편집 (설계 §3.4) --------------------------------------

    def replace_span(self, index, bbox, origin, new_text, size, rgb):
        """한 span의 글자를 지우고(redaction) 같은 baseline에 다시 쓴다.

        한계(설계 §3.4): 원본 폰트를 그대로 못 쓰는 경우가 많아 CJK 내장
        폰트("korea")로 다시 쓴다 → 한글+영문은 커버되지만 글자 모양이
        미묘하게 달라질 수 있다. 리플로우는 없다 — 길어져도 그 자리에서만
        교체(넘치면 폭에 맞춰 자간이 아니라 폰트 크기를 줄인다).

        fill=None: 배경을 칠하지 않고 글자만 지운다. 흰 배경이면 티가 안
        나고, 배경색이 있으면 그 자리가 지워질 수 있다(§3.4 한계).
        """
        page = self._doc[index]
        rect = fitz.Rect(*bbox)
        page.add_redact_annot(rect, fill=None)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

        page = self._doc[index]  # apply_redactions 후 페이지 재취득
        fontsize = self._fit_fontsize(new_text, size, rect.width)
        page.insert_text((origin[0], origin[1]), new_text,
                         fontsize=fontsize, fontname="korea", color=rgb)

    def _fit_fontsize(self, text, size, max_width):
        """새 글자가 원래 폭을 넘으면 폰트 크기를 줄여 한 줄에 맞춘다.
        리플로우가 없으므로(그 줄 안에서만 교체) 최소한의 안전장치."""
        if max_width <= 0:
            return size
        font = fitz.Font("cjk")
        width = font.text_length(text, fontsize=size)
        if width <= max_width:
            return size
        return max(4.0, size * max_width / width)

    # --- 스캔본 편집 (설계 §3.4) ----------------------------------------

    def is_scanned_area(self, index, bbox):
        """그 자리에 이미지가 깔려 있나 — 스캔본이면 글자가 이미지 픽셀이라
        리댁션만으로는 안 지워지고 배경색으로 덮어칠해야 한다."""
        page = self._doc[index]
        r = fitz.Rect(bbox)
        for img in page.get_images():
            for ir in page.get_image_rects(img[0]):
                if ir.intersects(r):
                    return True
        return False

    def sample_bg_fg(self, index, bbox, pad=4):
        """bbox 주변에서 배경색(종이)과 전경색(글자)을 추출 → (bg, fg) RGB 0~1.

        작은 영역만 렌더하므로 큰 페이지에서도 부담이 없다. numpy가 없으면
        흰 배경/검은 글자로 가정.
        """
        page = self._doc[index]
        r = fitz.Rect(bbox)
        outer = fitz.Rect(r.x0 - pad, r.y0 - pad, r.x1 + pad, r.y1 + pad)
        outer = outer & page.rect
        if outer.is_empty:
            return (1, 1, 1), (0, 0, 0)
        pix = page.get_pixmap(clip=outer, matrix=fitz.Matrix(2, 2), alpha=False)
        try:
            import numpy as np
        except ImportError:
            return (1, 1, 1), (0, 0, 0)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, 3)
        lum = arr.mean(axis=2)
        # 밝기 중간값으로 종이/글자를 가른다. 고정 퍼센타일로 나누면 배경이
        # 대부분인 영역에서 '어두운 15%'가 글자 획이 아니라 안티앨리어싱
        # 가장자리라 글자색이 흐릿한 회색으로 잡혔다.
        lo, hi = float(lum.min()), float(lum.max())
        thresh = (lo + hi) / 2.0
        bright = arr[lum >= thresh]
        dark = arr[lum < thresh]
        bg = tuple(np.median(bright, axis=0) / 255.0) if len(bright) else (1, 1, 1)
        if len(dark):
            fg = tuple(np.median(dark, axis=0) / 255.0)
        else:
            fg = (0, 0, 0)
        # 대비가 거의 없는 영역(글자가 없거나 흐린 스캔)에서 뽑힌 연한 색으로
        # 쓰면 읽을 수 없다 — 그럴 땐 검정으로.
        if sum(fg) / 3.0 > 0.55:
            fg = (0, 0, 0)
        return bg, fg

    def replace_scanned_text(self, index, bbox, origin, new_text, size,
                             bg=None, fg=None):
        """스캔본 글자 교체 — 배경색으로 덮고 그 자리에 새 글자를 쓴다.

        기존 OCR 텍스트 레이어(보이지 않는 글자)도 함께 지운다 — 안 그러면
        검색이 옛 글자를 계속 찾아낸다.
        """
        if bg is None or fg is None:
            sbg, sfg = self.sample_bg_fg(index, bbox)
            bg = bg or sbg
            fg = fg or sfg
        page = self._doc[index]
        rect = fitz.Rect(bbox)
        # 1) 그 자리의 텍스트(OCR 레이어)만 제거 — 이미지는 보존
        page.add_redact_annot(rect, fill=None)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        page = self._doc[index]
        # 2) 이미지에 찍혀 있는 원래 글자를 배경색으로 덮기
        #    가장자리 1px 여유 — 글자 획이 bbox를 살짝 삐져나오는 경우가 있다
        page.draw_rect(fitz.Rect(rect.x0 - 1, rect.y0 - 1,
                                 rect.x1 + 1, rect.y1 + 1),
                       color=None, fill=bg, width=0)
        # 3) 새 글자 쓰기
        if new_text.strip():
            page.insert_text(origin, new_text, fontsize=size,
                             fontname="korea", color=fg)

    def add_text_box(self, index, point, text, size=11, bg=None, fg=(0, 0, 0)):
        """임의 위치에 텍스트 박스 — OCR 없이도 스캔본에 글자를 얹는 자유 편집.

        bg가 있으면 글자 뒤에 배경 사각형을 깔아 밑에 있는 내용을 가린다.
        """
        page = self._doc[index]
        if bg is not None:
            w = fitz.get_text_length(text, fontname="korea", fontsize=size)
            rect = fitz.Rect(point[0] - 1, point[1] - size,
                             point[0] + w + 2, point[1] + size * 0.3)
            page.draw_rect(rect, color=None, fill=bg, width=0)
        page.insert_text(point, text, fontsize=size, fontname="korea", color=fg)

    # --- 페이지 조작 ---------------------------------------------------

    def rotate_page(self, index, degrees):
        """페이지 회전 — 기존 각도에 상대적으로 더한다(0/90/180/270로 정규화)."""
        page = self._doc[index]
        page.set_rotation((page.rotation + degrees) % 360)

    def delete_page(self, index):
        self._doc.delete_page(index)

    def move_page(self, src, dst):
        """src 페이지를 dst 위치로 이동."""
        if src == dst:
            return
        # PyMuPDF의 move_page(to=)는 '그 위치 앞에 끼운다' 의미라, 뒤로
        # 옮길 때 한 칸 밀린다 — 사용자가 기대하는 최종 인덱스로 맞춘다.
        self._doc.move_page(src, dst + 1 if dst > src else dst)

    def insert_pdf(self, path, at=None, password=None):
        """다른 PDF를 통째로 끼워넣는다(병합). at=None이면 맨 뒤.

        반환: 삽입된 페이지 수.
        """
        other = self._open(path, password)
        try:
            n = other.page_count
            self._doc.insert_pdf(other, start_at=at)
            return n
        finally:
            other.close()

    def extract_pages(self, indices, out_path):
        """선택한 페이지만 새 PDF로 저장(분할). 원본은 그대로 둔다."""
        new = fitz.open()
        try:
            for i in indices:
                new.insert_pdf(self._doc, from_page=i, to_page=i)
            new.save(out_path, garbage=3, deflate=True)
        finally:
            new.close()

    def snapshot(self):
        """현재 문서 전체를 바이트로 — 되돌리기 스택용(설계: 저널링 대신).

        PyMuPDF 1.28의 내장 저널링은 텍스트 삽입과 함께 쓰면 깨져서
        (연산 중 폰트 등록 불가) 스냅샷 방식을 쓴다. 텍스트 편집은 보통
        용량이 크지 않은 문서에서 일어나므로 감당 가능.
        """
        return self._doc.tobytes(garbage=0, deflate=True)

    def restore(self, data):
        """스냅샷으로 되돌린다 — 내부 문서를 통째로 교체."""
        self._doc.close()
        self._doc = fitz.open("pdf", data)

    # --- 저장 -------------------------------------------------------

    def save_as(self, out_path, backup=True):
        """항상 새 파일로 쓴 뒤 교체한다(설계 §4) — 저장 중 죽어도 원본이 남는다.

        incremental save는 쓰지 않는다: 원본 파일에 직접 덧쓰기 때문에
        실패 시 파손 위험이 있다.

        Windows 주의: 열려 있는 원본과 같은 경로로 교체하려면 먼저 그
        핸들을 닫아야 한다(os.replace가 WinError 5로 거부됨). 그래서
        임시 파일에 저장 → 원본 핸들 닫기 → 교체 → 결과를 다시 여는
        순서로 처리한다.
        """
        tmp = out_path + ".tmp"
        self._doc.save(tmp, garbage=3, deflate=True)

        same_path = os.path.normcase(os.path.abspath(out_path)) == \
            os.path.normcase(os.path.abspath(self.path))
        if same_path:
            self._doc.close()
            self._doc = None
        if backup and os.path.exists(out_path):
            shutil.copy2(out_path, out_path + ".bak")
        os.replace(tmp, out_path)
        if same_path:
            # 방금 저장한 파일을 다시 연다 — 이후 편집/렌더가 계속 가능하도록.
            self._doc = self._open(out_path, self._password)
            self.path = out_path

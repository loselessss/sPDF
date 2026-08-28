"""Plain-text outline parser for importing PDF bookmarks."""

from pathlib import Path
import re


_PAGE_FIRST = re.compile(r"^(\d+)\s*(?:\||\t)\s*(.+?)\s*$")
_TITLE_FIRST = re.compile(r"^(.+?)\s*(?:\||\t)\s*(\d+)\s*$")
_PAGE_SPACE_TITLE = re.compile(r"^(\d+)\s+(.+?)\s*$")


def parse_outline_text(text, page_count):
    """Return ``(level, title, one-based page)`` entries.

    Lines accept ``page | title``, ``title | page``, or ``page title``.
    Every two leading spaces (or one tab) adds one hierarchy level.
    """
    if page_count < 1:
        raise ValueError("책갈피를 넣을 페이지가 없습니다.")
    entries = []
    previous_level = 0
    for line_number, raw in enumerate(str(text).splitlines(), start=1):
        if not raw.strip():
            continue
        prefix = re.match(r"^[ \t]*", raw).group(0)
        indent = len(prefix.expandtabs(2))
        if indent % 2:
            raise ValueError(
                "%d번 줄의 들여쓰기는 2칸 단위여야 합니다." % line_number)
        body = raw[len(prefix):].strip()
        match = _PAGE_FIRST.fullmatch(body)
        if match:
            page, title = int(match.group(1)), match.group(2).strip()
        else:
            match = _TITLE_FIRST.fullmatch(body)
            if match:
                title, page = match.group(1).strip(), int(match.group(2))
            else:
                match = _PAGE_SPACE_TITLE.fullmatch(body)
                if not match:
                    raise ValueError(
                        "%d번 줄을 '페이지 | 제목' 형식으로 읽을 수 없습니다."
                        % line_number)
                page, title = int(match.group(1)), match.group(2).strip()
        if not title:
            raise ValueError("%d번 줄의 제목이 비어 있습니다." % line_number)
        if not 1 <= page <= page_count:
            raise ValueError(
                "%d번 줄의 페이지는 1-%d 사이여야 합니다."
                % (line_number, page_count))
        level = indent // 2 + 1
        if not entries and level != 1:
            raise ValueError("첫 책갈피는 들여쓰기 없이 작성하세요.")
        if entries and level > previous_level + 1:
            raise ValueError(
                "%d번 줄의 책갈피 단계가 한 번에 너무 많이 깊어졌습니다."
                % line_number)
        entries.append((level, title, page))
        previous_level = level
    if not entries:
        raise ValueError("가져올 책갈피가 없습니다.")
    return entries


def read_outline_file(path):
    data = Path(path).read_bytes()
    encodings = ("utf-16",) if data.startswith((b"\xff\xfe", b"\xfe\xff")) \
        else ("utf-8-sig", "cp949")
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("TXT 파일 인코딩을 읽을 수 없습니다.")

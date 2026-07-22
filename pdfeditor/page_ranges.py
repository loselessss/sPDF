"""PDF 분리용 페이지 범위 해석 도구.

UI와 분리해 두어 Qt 없이도 범위 규칙을 테스트할 수 있다. 사용자에게는
1부터 시작하는 페이지 번호를 받고, 코어에는 0부터 시작하는 인덱스를 넘긴다.
"""

import re


_RANGE_RE = re.compile(r"^(\d+)(?:\s*-\s*(\d+))?$")


def parse_page_groups(text, page_count):
    """분리 범위를 0 기반 페이지 인덱스 그룹으로 변환한다.

    ``*``는 모든 페이지를 각각의 PDF로 분리한다. 세미콜론은 출력 PDF를,
    쉼표는 같은 PDF에 넣을 범위를 구분한다. 예: ``1-3;4,6;7-9``.
    """
    if page_count < 1:
        raise ValueError("분리할 페이지가 없습니다.")

    value = text.strip()
    if value == "*":
        return [[index] for index in range(page_count)]
    if not value:
        raise ValueError("페이지 범위를 입력하세요.")

    groups = []
    for group_number, group_text in enumerate(value.split(";"), start=1):
        group_text = group_text.strip()
        if not group_text:
            raise ValueError("%d번째 출력 범위가 비어 있습니다." % group_number)

        pages = []
        seen = set()
        for token in group_text.split(","):
            token = token.strip()
            match = _RANGE_RE.match(token)
            if match is None:
                raise ValueError("올바르지 않은 페이지 범위: %s" % (token or "(빈 값)"))

            start = int(match.group(1))
            end = int(match.group(2) or start)
            if start > end:
                raise ValueError("페이지 범위의 시작이 끝보다 큽니다: %s" % token)
            if start < 1 or end > page_count:
                raise ValueError(
                    "페이지 범위는 1-%d 사이여야 합니다: %s" % (page_count, token))

            for page_number in range(start, end + 1):
                index = page_number - 1
                if index not in seen:
                    pages.append(index)
                    seen.add(index)
        groups.append(pages)
    return groups


def page_group_label(indices):
    """파일명에 쓸 간결한 1 기반 페이지 범위 라벨을 만든다."""
    if not indices:
        raise ValueError("페이지 그룹이 비어 있습니다.")

    numbers = [index + 1 for index in indices]
    parts = []
    run_start = numbers[0]
    run_end = numbers[0]
    for number in numbers[1:]:
        if number == run_end + 1:
            run_end = number
            continue
        parts.append(_format_run(run_start, run_end))
        run_start = run_end = number
    parts.append(_format_run(run_start, run_end))
    return "p" + "_".join(parts)


def _format_run(start, end):
    return str(start) if start == end else "%d-%d" % (start, end)

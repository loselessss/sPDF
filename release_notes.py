"""CHANGELOG.md에서 지정한 버전의 GitHub 릴리스 본문을 추출한다."""

import argparse
import re
from pathlib import Path


_RELEASE_HEADING_RE = re.compile(
    r"^## (?P<version>\d+\.\d+\.\d+) - (?P<date>\d{4}-\d{2}-\d{2})\s*$",
    re.MULTILINE)


def extract_release_notes(changelog, version):
    """버전 제목 다음부터 다음 버전 제목 전까지의 Markdown을 반환한다."""
    matches = list(_RELEASE_HEADING_RE.finditer(changelog))
    selected = [item for item in matches if item.group("version") == version]
    if len(selected) != 1:
        raise ValueError(
            "CHANGELOG.md에서 %s 버전 항목을 하나만 찾을 수 있어야 합니다."
            % version)
    match = selected[0]
    index = matches.index(match)
    end = matches[index + 1].start() if index + 1 < len(matches) \
        else len(changelog)
    notes = changelog[match.end():end].strip()
    if not notes:
        raise ValueError("%s 버전의 변경 내용이 비어 있습니다." % version)
    return notes + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--changelog", default="CHANGELOG.md")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    changelog = Path(args.changelog).read_text(encoding="utf-8")
    notes = extract_release_notes(changelog, args.version)
    Path(args.output).write_text(notes, encoding="utf-8")


if __name__ == "__main__":
    main()

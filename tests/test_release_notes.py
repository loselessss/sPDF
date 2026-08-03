import tempfile
import unittest
from pathlib import Path

from release_notes import extract_release_notes, main


SAMPLE = """# 변경 이력

## 1.7.2 - 2026-08-03

### 개선

- 프로세스 표시를 정리했습니다.

### 버그 수정

- 종료 처리를 보강했습니다.

## 1.7.1 - 2026-08-01

### 개선

- 선택 기능을 개선했습니다.
"""


class ReleaseNotesTests(unittest.TestCase):
    def test_extracts_only_requested_version_body(self):
        notes = extract_release_notes(SAMPLE, "1.7.2")
        self.assertIn("### 개선", notes)
        self.assertIn("종료 처리를 보강", notes)
        self.assertNotIn("1.7.1", notes)
        self.assertNotIn("선택 기능", notes)

    def test_missing_version_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "1.8.0"):
            extract_release_notes(SAMPLE, "1.8.0")

    def test_cli_writes_utf8_markdown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            changelog = root / "CHANGELOG.md"
            output = root / "notes.md"
            changelog.write_text(SAMPLE, encoding="utf-8")
            main(["--version", "1.7.2", "--changelog", str(changelog),
                  "--output", str(output)])
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                extract_release_notes(SAMPLE, "1.7.2"))


if __name__ == "__main__":
    unittest.main()

import re
import unittest
from pathlib import Path

from pdfeditor.meta import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class ReleasePackagingTests(unittest.TestCase):
    def test_application_and_installer_versions_match(self):
        installer = (ROOT / "installer.iss").read_text(encoding="utf-8")
        match = re.search(
            r'^#define MyAppVersion "([^"]+)"$', installer, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), APP_VERSION)

    def test_version_tag_builds_github_release(self):
        workflow = (
            ROOT / ".github" / "workflows" / "release.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('      - "v*.*.*"', workflow)
        self.assertIn("cmd /c build_exe.bat", workflow)
        self.assertIn("cmd /c build_installer.bat", workflow)
        self.assertIn("Get-FileHash -Algorithm SHA256", workflow)
        self.assertIn("sPDF_Setup_latest.exe", workflow)
        self.assertIn("gh release create", workflow)
        self.assertIn("contents: write", workflow)


if __name__ == "__main__":
    unittest.main()

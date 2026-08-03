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
        self.assertIn("python release_notes.py", workflow)
        self.assertIn("--notes-file release-notes.md", workflow)
        self.assertNotIn("--generate-notes", workflow)
        self.assertIn("contents: write", workflow)

    def test_both_executables_have_windows_version_resources(self):
        spec = (ROOT / "spdf.spec").read_text(encoding="utf-8")
        self.assertIn("version=gui_version_info", spec)
        self.assertIn("version=ocr_version_info", spec)
        self.assertGreaterEqual(spec.count('icon="assets/spdf.ico"'), 2)

    def test_installer_shortcuts_use_same_app_id_as_runtime(self):
        installer = (ROOT / "installer.iss").read_text(encoding="utf-8")
        integration = (
            ROOT / "pdfeditor" / "windows_integration.py"
        ).read_text(encoding="utf-8")
        app_id = re.search(
            r'^#define MyAppUserModelId "([^"]+)"$',
            installer, re.MULTILINE).group(1)
        runtime_app_id = re.search(
            r'^APP_USER_MODEL_ID = ["\']([^"\']+)["\']$',
            integration, re.MULTILINE).group(1)
        self.assertEqual(runtime_app_id, app_id)
        self.assertEqual(installer.count('AppUserModelID: "{#MyAppUserModelId}"'), 2)
        worker = (ROOT / "ocr_worker_main.py").read_text(encoding="utf-8")
        self.assertIn("set_current_process_app_id()", worker)


if __name__ == "__main__":
    unittest.main()

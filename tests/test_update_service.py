import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pdfeditor.update_service import GitHubUpdateService, UpdateError


class FakeResponse:
    def __init__(self, payload):
        self.stream = io.BytesIO(payload)

    def __enter__(self):
        return self

    def __exit__(self, _kind, _error, _traceback):
        return False

    def read(self, size=-1):
        return self.stream.read(size)


def release_payload(tag="v1.6.1", content=b"installer", url=None):
    version = tag.lstrip("v")
    download = url or (
        "https://github.com/loselessss/sPDF/releases/download/%s/"
        "sPDF_Setup_%s.exe" % (tag, version))
    return json.dumps({
        "tag_name": tag,
        "name": "sPDF %s" % version,
        "body": "변경 내용",
        "html_url": (
            "https://github.com/loselessss/sPDF/releases/tag/%s" % tag),
        "assets": [{
            "name": "sPDF_Setup_%s.exe" % version,
            "browser_download_url": download,
            "size": len(content),
            "digest": "sha256:%s" % hashlib.sha256(content).hexdigest(),
        }],
    }).encode("utf-8")


class UpdateServiceTests(unittest.TestCase):
    def test_newer_release_selects_exact_versioned_installer(self):
        service = GitHubUpdateService(
            "1.6.0", opener=lambda _request, timeout: FakeResponse(
                release_payload()))
        update = service.check()
        self.assertEqual(update.version, "1.6.1")
        self.assertEqual(update.asset.name, "sPDF_Setup_1.6.1.exe")
        self.assertEqual(len(update.asset.sha256), 64)

    def test_same_release_is_current(self):
        service = GitHubUpdateService(
            "1.6.0", opener=lambda _request, timeout: FakeResponse(
                release_payload("v1.6.0")))
        self.assertIsNone(service.check())

    def test_untrusted_asset_is_rejected(self):
        service = GitHubUpdateService(
            "1.6.0", opener=lambda _request, timeout: FakeResponse(
                release_payload(url="https://example.com/setup.exe")))
        with self.assertRaisesRegex(UpdateError, "안전하지"):
            service.check()

    def test_download_verifies_hash_and_reports_progress(self):
        content = b"verified installer"
        calls = [release_payload(content=content), content]

        def opener(_request, timeout):
            return FakeResponse(calls.pop(0))

        with tempfile.TemporaryDirectory() as temp:
            service = GitHubUpdateService(
                "1.6.0", opener=opener, download_root=Path(temp))
            update = service.check()
            progress = []
            result = service.download(update, progress=progress.append)
            self.assertEqual(result.read_bytes(), content)
            self.assertEqual(progress[-1].completed_bytes, len(content))

    def test_installer_launch_does_not_use_shell(self):
        with tempfile.TemporaryDirectory() as temp:
            installer = Path(temp) / "sPDF_Setup_1.6.1.exe"
            installer.write_bytes(b"MZ")
            service = GitHubUpdateService("1.6.0")
            with patch("pdfeditor.update_service.subprocess.Popen") as popen:
                service.launch_installer(installer)
            self.assertEqual(popen.call_args.args[0][0], str(installer.resolve()))
            self.assertNotIn("shell", popen.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()

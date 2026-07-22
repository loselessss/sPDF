import sys
import types
import unittest
from unittest.mock import patch

from pdfeditor import defaultapp


class _RegistryKey:
    def __init__(self, registry, path):
        self.registry = registry
        self.path = path

    def __enter__(self):
        return self

    def __exit__(self, _kind, _value, _traceback):
        return False


class _FakeWinreg(types.ModuleType):
    HKEY_CURRENT_USER = object()
    REG_DWORD = 4
    KEY_SET_VALUE = 2

    def __init__(self):
        super().__init__("winreg")
        self.values = {}

    def CreateKey(self, _root, path):
        self.values.setdefault(path, {})
        return _RegistryKey(self, path)

    def OpenKey(self, _root, path, *_args):
        if path not in self.values:
            raise FileNotFoundError(path)
        return _RegistryKey(self, path)

    def QueryValueEx(self, key, name):
        try:
            return self.values[key.path][name]
        except KeyError:
            raise FileNotFoundError(name)

    def SetValueEx(self, key, name, _reserved, kind, value):
        self.values[key.path][name] = (value, kind)

    def DeleteValue(self, key, name):
        try:
            del self.values[key.path][name]
        except KeyError:
            raise FileNotFoundError(name)


class EdgeExternalPdfSettingTests(unittest.TestCase):
    def setUp(self):
        self.winreg = _FakeWinreg()
        self.platform = patch.object(sys, "platform", "win32")
        self.modules = patch.dict(sys.modules, {"winreg": self.winreg})
        self.platform.start()
        self.modules.start()

    def tearDown(self):
        self.modules.stop()
        self.platform.stop()

    def test_enable_and_disable_current_user_edge_policy(self):
        self.assertFalse(defaultapp.edge_external_pdf_enabled())

        defaultapp.set_edge_external_pdf(True)
        self.assertTrue(defaultapp.edge_external_pdf_enabled())

        defaultapp.set_edge_external_pdf(False)
        self.assertFalse(defaultapp.edge_external_pdf_enabled())

    def test_disabling_missing_policy_is_safe(self):
        defaultapp.set_edge_external_pdf(False)
        self.assertFalse(defaultapp.edge_external_pdf_enabled())


if __name__ == "__main__":
    unittest.main()

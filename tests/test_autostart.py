import types

import pytest

from spinespy_win import autostart


class FakeReg:
    """Minimal in-memory stand-in for winreg."""

    HKEY_CURRENT_USER = "HKCU"
    KEY_SET_VALUE = 2
    KEY_READ = 1
    REG_SZ = 1

    def __init__(self):
        self.values = {}

    def OpenKey(self, root, subkey, reserved=0, access=0):
        return types.SimpleNamespace()

    def SetValueEx(self, key, name, reserved, type_, value):
        self.values[name] = value

    def DeleteValue(self, key, name):
        self.values.pop(name)

    def QueryValueEx(self, key, name):
        if name not in self.values:
            raise FileNotFoundError
        return (self.values[name], self.REG_SZ)

    def CloseKey(self, key):
        pass


@pytest.fixture
def fake_winreg(monkeypatch):
    reg = FakeReg()
    monkeypatch.setattr(autostart, "winreg", reg, raising=False)
    monkeypatch.setattr(autostart, "_exe_path", lambda: r"C:\App\SpineSpy.exe")
    return reg


def test_enable_then_query(fake_winreg):
    autostart.set_autostart(True)
    assert fake_winreg.values[autostart.RUN_VALUE_NAME] == r"C:\App\SpineSpy.exe"
    assert autostart.is_autostart_enabled() is True


def test_disable(fake_winreg):
    autostart.set_autostart(True)
    autostart.set_autostart(False)
    assert autostart.RUN_VALUE_NAME not in fake_winreg.values
    assert autostart.is_autostart_enabled() is False

"""Manage the HKCU Run key so SpineSpy starts at login. Never fatal."""

from __future__ import annotations

import sys

try:
    import winreg  # type: ignore
except ImportError:  # non-Windows authoring/test env
    winreg = None  # type: ignore

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "SpineSpy"


def _exe_path():
    """Path used to relaunch at login (the frozen exe, or python+script in dev)."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return f'"{sys.executable}" -m spinespy_win.main'


def set_autostart(enabled):
    if winreg is None:
        return
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        )
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, _exe_path())
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except OSError as exc:
        print(f"[autostart] could not set Run key: {exc}")


def is_autostart_enabled():
    if winreg is None:
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ
        )
        try:
            winreg.QueryValueEx(key, RUN_VALUE_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except OSError:
        return False

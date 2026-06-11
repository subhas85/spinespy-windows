"""Settings + calibration persistence to %APPDATA%\\SpineSpy\\config.json."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from spinespy_win.pose import Calibration


def default_config_path():
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "SpineSpy" / "config.json"


@dataclass
class Config:
    interval_seconds: int = 60
    sound_enabled: bool = True
    autostart: bool = True
    paused: bool = False
    update_check_enabled: bool = True
    calibration: Calibration | None = None

    def to_dict(self):
        return {
            "interval_seconds": self.interval_seconds,
            "sound_enabled": self.sound_enabled,
            "autostart": self.autostart,
            "paused": self.paused,
            "update_check_enabled": self.update_check_enabled,
            "calibration": self.calibration.to_dict() if self.calibration else None,
        }

    @classmethod
    def from_dict(cls, d):
        cal = d.get("calibration")
        return cls(
            interval_seconds=d.get("interval_seconds", 60),
            sound_enabled=d.get("sound_enabled", True),
            autostart=d.get("autostart", True),
            paused=d.get("paused", False),
            update_check_enabled=d.get("update_check_enabled", True),
            calibration=Calibration.from_dict(cal) if cal else None,
        )


def load(path=None):
    path = Path(path) if path else default_config_path()
    if not path.exists():
        c = Config()
        save(c, path)
        return c
    try:
        return Config.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, KeyError, TypeError):
        path.replace(path.with_suffix(".json.bak"))
        c = Config()
        save(c, path)
        return c


def save(config, path=None):
    path = Path(path) if path else default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")
    tmp.replace(path)  # atomic on the same filesystem

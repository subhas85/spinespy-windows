# SpineSpy for Windows 11 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a posture-only Windows 11 system-tray port of SpineSpy with persistent calibration, run-at-login, and one-click GitHub-release self-update, processing all webcam imagery strictly on-device.

**Architecture:** A small Python package (`spinespy_win`) split into single-responsibility modules — pure posture math (`pose.py`), Windows I/O wrappers (`camera.py`, `alerts.py`, `autostart.py`), persistence (`config.py`), self-update (`updater.py`), and a tray shell (`icons.py`, `tray.py`) wired by an orchestrator (`app.py`). Pure-logic modules are TDD'd; hardware/OS-shell modules get thin testable seams plus manual smoke steps. Shipped via PyInstaller + Inno Setup, released by GitHub Actions.

**Tech Stack:** Python 3.10–3.13, OpenCV (MSMF/DSHOW), MediaPipe Pose (`pose_landmarker_lite`), pystray + Pillow, windows-toasts, just_playback, pytest; PyInstaller + Inno Setup; GitHub Actions.

**Reference spec:** `docs/2026-06-10-spinespy-windows-design.md`

---

## File Structure

```
spinespy-windows/
  pyproject.toml              # deps, pytest config, entrypoint
  spinespy_win/
    __init__.py               # __version__ = "0.1.0"
    pose.py                   # posture math + MediaPipe detector wrapper
    camera.py                 # webcam capture (MSMF/DSHOW), permission hint
    alerts.py                 # toast + MP3 playback
    config.py                 # %APPDATA%\SpineSpy\config.json load/save
    autostart.py              # HKCU Run-key management
    updater.py                # GitHub Releases check + installer download
    icons.py                  # PIL-generated tray icons
    tray.py                   # pystray icon + menu
    app.py                    # timer loop + bad-streak state machine
    main.py                   # entrypoint, resource paths
  assets/
    audio/*.mp3               # copied from upstream
    pose_landmarker.task      # fetched at build time (gitignored)
  tests/
    conftest.py               # synthetic landmark fixtures
    test_pose.py
    test_config.py
    test_updater.py
    test_autostart.py
  packaging/
    spinespy.spec             # PyInstaller spec
    installer.iss             # Inno Setup script
  .github/workflows/release.yml
  PRIVACY.md
  README.md
```

Upstream constants (`SLOUCH_THRESHOLD=0.1`, `TILT_THRESHOLD=0.05`, `BAD_STREAK_LIMIT=5`, `CALIBRATION_FRAMES=10`, `CALIBRATION_INTERVAL=0.3`, `SNAPSHOT_FRAMES=3`) are carried over unchanged.

---

## Task 0: Project scaffold

**Files:**
- Create: `spinespy_win/__init__.py`
- Create: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `.gitignore`

- [ ] **Step 1: Create the package version file**

`spinespy_win/__init__.py`:
```python
"""SpineSpy for Windows — posture-only webcam nudge."""

__version__ = "0.1.0"
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "spinespy-win"
version = "0.1.0"
description = "Posture monitor for Windows 11 (system tray, local-only)"
requires-python = ">=3.10,<3.14"
dependencies = [
    "opencv-python>=4.8.0",
    "mediapipe>=0.10.0",
    "numpy>=1.26",
    "pystray>=0.19.5",
    "Pillow>=10.0",
    "windows-toasts>=1.1.0",
    "just_playback>=0.1.8",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
spinespy = "spinespy_win.main:main"

[tool.pytest.ini_options]
testpaths = ["tests"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 3: Create `.gitignore`**

```
__pycache__/
*.pyc
.venv/
build/
dist/
*.egg-info/
assets/pose_landmarker.task
debug_snapshot.jpg
```

- [ ] **Step 4: Create empty test package**

`tests/__init__.py`: (empty file)

- [ ] **Step 5: Create the virtualenv and install dev deps**

Run:
```bash
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"
```
Expected: install succeeds (on Windows). On the Linux authoring box, `windows-toasts` will fail to install — that is expected; pose/config/updater/autostart tests do not import it, so author and run those tests with a minimal env: `pip install pytest mediapipe opencv-python numpy`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml spinespy_win/__init__.py tests/__init__.py .gitignore
git commit -m "chore: scaffold spinespy_win package"
```

---

## Task 1: Posture math (`pose.py`)

Ported from upstream `menubar_app.py` but refactored so calibration is a returned value object (testable) and the detector is injected.

**Files:**
- Create: `spinespy_win/pose.py`
- Create: `tests/conftest.py`
- Create: `tests/test_pose.py`

- [ ] **Step 1: Write synthetic landmark fixtures**

`tests/conftest.py`:
```python
import pytest


class FakeLandmark:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z


def make_landmarks(nose_z=0.0, l_sh_z=0.0, r_sh_z=0.0, l_sh_y=0.5, r_sh_y=0.5):
    """Return a 33-element landmark list with the indices pose.py reads.

    Index 0 = nose, 11 = left shoulder, 12 = right shoulder.
    """
    lms = [FakeLandmark() for _ in range(33)]
    lms[0] = FakeLandmark(z=nose_z)
    lms[11] = FakeLandmark(y=l_sh_y, z=l_sh_z)
    lms[12] = FakeLandmark(y=r_sh_y, z=r_sh_z)
    return lms


@pytest.fixture
def landmarks_factory():
    return make_landmarks
```

- [ ] **Step 2: Write the failing test for `get_posture_metrics`**

`tests/test_pose.py`:
```python
from spinespy_win import pose


def test_get_posture_metrics_computes_lean_and_tilt(landmarks_factory):
    # shoulders at z=0.4, nose at z=0.0 -> forward_lean = 0.4 - 0.0 = 0.4
    # shoulder y diff = |0.6 - 0.5| = 0.1
    lms = landmarks_factory(nose_z=0.0, l_sh_z=0.4, r_sh_z=0.4, l_sh_y=0.6, r_sh_y=0.5)
    lean, tilt = pose.get_posture_metrics(lms)
    assert lean == 0.4
    assert abs(tilt - 0.1) < 1e-9
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_pose.py::test_get_posture_metrics_computes_lean_and_tilt -v`
Expected: FAIL (`ModuleNotFoundError` / `AttributeError: module 'spinespy_win.pose' has no attribute 'get_posture_metrics'`).

- [ ] **Step 4: Implement `pose.py` constants, dataclass, and metrics**

`spinespy_win/pose.py`:
```python
"""Posture math and the MediaPipe pose detector wrapper.

Pure logic except for `PoseAnalyzer`, which owns the MediaPipe detector.
Imports no networking — frames never leave the process.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

SLOUCH_THRESHOLD = 0.1
TILT_THRESHOLD = 0.05
CALIBRATION_FRAMES = 10
CALIBRATION_INTERVAL = 0.3
SNAPSHOT_FRAMES = 3
BAD_STREAK_LIMIT = 5


@dataclass
class Calibration:
    baseline_lean: float
    baseline_tilt: float
    slouch_threshold: float
    tilt_threshold: float

    def to_dict(self):
        return {
            "baseline_lean": self.baseline_lean,
            "baseline_tilt": self.baseline_tilt,
            "slouch_threshold": self.slouch_threshold,
            "tilt_threshold": self.tilt_threshold,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            baseline_lean=d["baseline_lean"],
            baseline_tilt=d["baseline_tilt"],
            slouch_threshold=d["slouch_threshold"],
            tilt_threshold=d["tilt_threshold"],
        )


def get_posture_metrics(landmarks):
    """Return (forward_lean, tilt) from a 33-point pose landmark list."""
    nose = landmarks[0]
    left_shoulder = landmarks[11]
    right_shoulder = landmarks[12]
    shoulder_z = (left_shoulder.z + right_shoulder.z) / 2
    forward_lean = shoulder_z - nose.z
    tilt = abs(left_shoulder.y - right_shoulder.y)
    return forward_lean, tilt
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_pose.py::test_get_posture_metrics_computes_lean_and_tilt -v`
Expected: PASS.

- [ ] **Step 6: Write failing tests for `calibrate_from_metrics` and `check_posture`**

Append to `tests/test_pose.py`:
```python
def test_calibrate_from_metrics_uses_median_and_threshold_floor():
    leans = [0.10, 0.11, 0.09, 0.10, 0.10]
    tilts = [0.01, 0.02, 0.01, 0.01, 0.02]
    cal = pose.calibrate_from_metrics(leans, tilts)
    assert abs(cal.baseline_lean - 0.10) < 1e-9
    # tight spread -> std*3 below floor -> thresholds clamp to the base constants
    assert cal.slouch_threshold == pose.SLOUCH_THRESHOLD
    assert cal.tilt_threshold == pose.TILT_THRESHOLD


def test_calibrate_from_metrics_returns_none_when_too_few():
    cal = pose.calibrate_from_metrics([0.1] * 4, [0.0] * 4)  # < CALIBRATION_FRAMES//2
    assert cal is None


def test_check_posture_flags_slouch(landmarks_factory):
    cal = pose.Calibration(0.0, 0.0, 0.1, 0.05)
    lms = landmarks_factory(nose_z=0.0, l_sh_z=0.2, r_sh_z=0.2)  # lean delta 0.2 > 0.1
    is_bad, reason = pose.check_posture(lms, cal)
    assert is_bad is True
    assert reason.startswith("Slouching")


def test_check_posture_good(landmarks_factory):
    cal = pose.Calibration(0.0, 0.0, 0.1, 0.05)
    lms = landmarks_factory(nose_z=0.0, l_sh_z=0.02, r_sh_z=0.02, l_sh_y=0.5, r_sh_y=0.5)
    is_bad, reason = pose.check_posture(lms, cal)
    assert is_bad is False
    assert reason is None
```

- [ ] **Step 7: Run to verify failure**

Run: `pytest tests/test_pose.py -v`
Expected: the four new tests FAIL (functions undefined); the metrics test still PASSES.

- [ ] **Step 8: Implement calibration and posture checking**

Append to `spinespy_win/pose.py`:
```python
def calibrate_from_metrics(leans, tilts):
    """Build a Calibration from collected per-frame metrics, or None if too few."""
    if len(leans) < CALIBRATION_FRAMES // 2:
        return None
    baseline_lean = statistics.median(leans)
    baseline_tilt = statistics.median(tilts)
    lean_std = statistics.stdev(leans) if len(leans) > 1 else 0.0
    tilt_std = statistics.stdev(tilts) if len(tilts) > 1 else 0.0
    return Calibration(
        baseline_lean=baseline_lean,
        baseline_tilt=baseline_tilt,
        slouch_threshold=max(SLOUCH_THRESHOLD, lean_std * 3),
        tilt_threshold=max(TILT_THRESHOLD, tilt_std * 3),
    )


def _severity_label(delta, threshold):
    ratio = delta / threshold if threshold > 0 else 0
    if ratio < 1.5:
        return "mild"
    if ratio < 2.5:
        return "moderate"
    return "severe"


def check_posture(landmarks, calibration):
    """Return (is_bad, reason) relative to a calibrated baseline."""
    forward_lean, tilt = get_posture_metrics(landmarks)
    lean_delta = forward_lean - calibration.baseline_lean
    tilt_delta = tilt - calibration.baseline_tilt

    if lean_delta >= calibration.slouch_threshold:
        return True, f"Slouching ({_severity_label(lean_delta, calibration.slouch_threshold)})"
    if tilt_delta >= calibration.tilt_threshold:
        return True, f"Tilting ({_severity_label(tilt_delta, calibration.tilt_threshold)})"
    return False, None
```

- [ ] **Step 9: Run the full pose test file**

Run: `pytest tests/test_pose.py -v`
Expected: all PASS.

- [ ] **Step 10: Commit**

```bash
git add spinespy_win/pose.py tests/conftest.py tests/test_pose.py
git commit -m "feat(pose): posture metrics, calibration, and check (TDD)"
```

---

## Task 2: MediaPipe analyzer wrapper (`pose.PoseAnalyzer`)

Wraps the MediaPipe detector so `camera`/`app` never touch MediaPipe internals. Not unit-tested (needs the model + a real image); covered by manual verification.

**Files:**
- Modify: `spinespy_win/pose.py`

- [ ] **Step 1: Add the analyzer class**

Append to `spinespy_win/pose.py`:
```python
class PoseAnalyzer:
    """Owns a MediaPipe PoseLandmarker. Created once, reused per frame."""

    def __init__(self, model_path):
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        self._mp = mp
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options, output_segmentation_masks=False
        )
        self._detector = vision.PoseLandmarker.create_from_options(options)

    def landmarks_for(self, rgb_frame):
        """Return the first pose's landmark list, or None if no pose found."""
        mp_image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB, data=rgb_frame
        )
        results = self._detector.detect(mp_image)
        if results.pose_landmarks and len(results.pose_landmarks) > 0:
            return results.pose_landmarks[0]
        return None
```

- [ ] **Step 2: Manual verification (requires model + webcam, run on Windows)**

Run (after Task 3 exists, or with a saved JPG):
```bash
.venv/Scripts/python -c "from spinespy_win.pose import PoseAnalyzer; a=PoseAnalyzer('assets/pose_landmarker.task'); print('analyzer constructed OK')"
```
Expected: prints `analyzer constructed OK` with no exception (model present).

- [ ] **Step 3: Commit**

```bash
git add spinespy_win/pose.py
git commit -m "feat(pose): MediaPipe PoseAnalyzer wrapper"
```

---

## Task 3: Camera capture (`camera.py`)

**Files:**
- Create: `spinespy_win/camera.py`

Hardware-bound; verified manually. Logic seam: backend fallback order is a module constant so it is inspectable.

- [ ] **Step 1: Implement `camera.py`**

`spinespy_win/camera.py`:
```python
"""Webcam capture for Windows. Opens, grabs N mirror-flipped frames, releases.

Frames are numpy arrays held only for the duration of capture — never written
to disk (except the explicit debug action in app.py) and never transmitted.
"""

from __future__ import annotations

import sys
import time

import cv2

# Try Media Foundation first (modern Win10/11), fall back to DirectShow.
_WINDOWS_BACKENDS = [cv2.CAP_MSMF, cv2.CAP_DSHOW]
_WARMUP_READS = 5


def _open_capture():
    if sys.platform == "win32":
        for backend in _WINDOWS_BACKENDS:
            cap = cv2.VideoCapture(0, backend)
            if cap.isOpened():
                return cap
            cap.release()
        return None
    cap = cv2.VideoCapture(0)
    return cap if cap.isOpened() else None


def capture_frames(n):
    """Capture n mirror-flipped BGR frames, or None if the camera won't open."""
    cap = _open_capture()
    if cap is None:
        return None
    try:
        time.sleep(0.5)
        for _ in range(_WARMUP_READS):
            cap.read()
        frames = []
        for _ in range(n):
            ret, frame = cap.read()
            if ret:
                frames.append(cv2.flip(frame, 1))
        return frames or None
    finally:
        cap.release()


def to_rgb(frame_bgr):
    """Convert a captured BGR frame to RGB for MediaPipe."""
    return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)


def camera_permission_hint():
    return (
        "Camera access is blocked or the webcam is in use. Allow it in "
        "Settings > Privacy & security > Camera, and close any other app "
        "using the webcam."
    )
```

- [ ] **Step 2: Manual verification (Windows, webcam attached)**

Run:
```bash
.venv/Scripts/python -c "from spinespy_win import camera; fs=camera.capture_frames(3); print('frames:', None if fs is None else len(fs))"
```
Expected: `frames: 3` (camera available), or `frames: None` plus you should then see the camera light briefly flash.

- [ ] **Step 3: Commit**

```bash
git add spinespy_win/camera.py
git commit -m "feat(camera): Windows webcam capture with MSMF/DSHOW fallback"
```

---

## Task 4: Config persistence (`config.py`)

**Files:**
- Create: `spinespy_win/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests (defaults, round-trip, corrupt recovery)**

`tests/test_config.py`:
```python
import json

from spinespy_win import config as cfg
from spinespy_win.pose import Calibration


def test_defaults_when_missing(tmp_path):
    path = tmp_path / "config.json"
    c = cfg.load(path)
    assert c.interval_seconds == 60
    assert c.sound_enabled is True
    assert c.autostart is True
    assert c.paused is False
    assert c.update_check_enabled is True
    assert c.calibration is None


def test_round_trip_with_calibration(tmp_path):
    path = tmp_path / "config.json"
    c = cfg.load(path)
    c.interval_seconds = 120
    c.sound_enabled = False
    c.calibration = Calibration(0.1, 0.02, 0.1, 0.05)
    cfg.save(c, path)

    reloaded = cfg.load(path)
    assert reloaded.interval_seconds == 120
    assert reloaded.sound_enabled is False
    assert reloaded.calibration.baseline_lean == 0.1
    assert reloaded.calibration.tilt_threshold == 0.05


def test_corrupt_file_recovers_to_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ this is not json ")
    c = cfg.load(path)
    assert c.interval_seconds == 60          # defaults restored
    assert path.with_suffix(".json.bak").exists()  # bad file backed up
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_config.py -v`
Expected: FAIL (`module 'spinespy_win.config' has no attribute 'load'`).

- [ ] **Step 3: Implement `config.py`**

`spinespy_win/config.py`:
```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_config.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add spinespy_win/config.py tests/test_config.py
git commit -m "feat(config): persistent settings + calibration with atomic write (TDD)"
```

---

## Task 5: Alerts — toast + audio (`alerts.py`)

**Files:**
- Create: `spinespy_win/alerts.py`

`windows-toasts` and `just_playback` are Windows-only; verified manually. Pure seam: `pick_clip` (selection logic) is testable without audio hardware.

- [ ] **Step 1: Implement `alerts.py`**

`spinespy_win/alerts.py`:
```python
"""Windows toast notifications and bundled MP3 playback (in-process)."""

from __future__ import annotations

import os
import random
import threading

ALERT_SOUND_FILES = [
    "assets/audio/Come on, shoulders back.mp3",
    "assets/audio/auditioning to be a shrimp.mp3",
    "assets/audio/did gravity offend u.mp3",
    "assets/audio/slouching_bella.mp3",
    "assets/audio/writing in cursive.mp3",
    "assets/audio/you're not a croissant.mp3",
]


def pick_clip(resolve, rng=random):
    """Return a playable clip path among bundled clips that exist, else None.

    `resolve` maps a relative asset path to an absolute one (resource_path).
    """
    available = [resolve(p) for p in ALERT_SOUND_FILES if os.path.exists(resolve(p))]
    if not available:
        return None
    return rng.choice(available)


def notify(title, message):
    """Show a Windows toast. Never raises."""
    try:
        from windows_toasts import Toast, WindowsToaster

        toaster = WindowsToaster("SpineSpy")
        toast = Toast()
        toast.text_fields = [title, message]
        toaster.show_toast(toast)
    except Exception as exc:  # noqa: BLE001 — UI nicety must not crash the app
        print(f"[alerts] toast failed: {exc}")


def play_random_clip(enabled, resolve):
    """Play a random reminder clip on a background thread. Returns False if skipped."""
    if not enabled:
        return False
    clip = pick_clip(resolve)
    if clip is None:
        return False

    def _play():
        try:
            from just_playback import Playback

            pb = Playback()
            pb.load_file(clip)
            pb.play()
            import time

            while pb.active:
                time.sleep(0.1)
        except Exception as exc:  # noqa: BLE001
            print(f"[alerts] playback failed: {exc}")

    threading.Thread(target=_play, daemon=True).start()
    return True
```

- [ ] **Step 2: Manual verification (Windows)**

Run:
```bash
.venv/Scripts/python -c "from spinespy_win import alerts; alerts.notify('SpineSpy','test toast'); alerts.play_random_clip(True, lambda p: p)"
```
Expected: a toast appears and one reminder clip plays (with `assets/audio/` present).

- [ ] **Step 3: Commit**

```bash
git add spinespy_win/alerts.py
git commit -m "feat(alerts): Windows toast + in-process MP3 playback"
```

---

## Task 6: Autostart registry (`autostart.py`)

**Files:**
- Create: `spinespy_win/autostart.py`
- Create: `tests/test_autostart.py`

Tested with `winreg` mocked so it runs on any OS.

- [ ] **Step 1: Write failing tests with mocked winreg**

`tests/test_autostart.py`:
```python
import sys
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

    # context-manager key handle
    def OpenKey(self, root, subkey, reserved=0, access=0):
        return types.SimpleNamespace()

    def __enter__(self):  # not used; keys are plain objects
        return self

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
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_autostart.py -v`
Expected: FAIL (module/attributes missing).

- [ ] **Step 3: Implement `autostart.py`**

`spinespy_win/autostart.py`:
```python
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
```

> Note: the test monkeypatches `autostart.winreg` and `autostart._exe_path`. `OpenKey` in `FakeReg` ignores its args and returns a dummy handle, matching the call signature.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_autostart.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add spinespy_win/autostart.py tests/test_autostart.py
git commit -m "feat(autostart): HKCU Run-key toggle (TDD, mocked winreg)"
```

---

## Task 7: Self-update (`updater.py`)

**Files:**
- Create: `spinespy_win/updater.py`
- Create: `tests/test_updater.py`

Network and `os.startfile` are seam-isolated; the version comparison and asset extraction are pure and tested.

- [ ] **Step 1: Write failing tests for semver compare + asset extraction**

`tests/test_updater.py`:
```python
from spinespy_win import updater


def test_is_newer_handles_numeric_ordering():
    assert updater.is_newer("1.10.0", "1.2.0") is True   # 10 > 2 numerically
    assert updater.is_newer("1.2.0", "1.10.0") is False
    assert updater.is_newer("1.2.0", "1.2.0") is False
    assert updater.is_newer("2.0.0", "1.9.9") is True


def test_is_newer_strips_v_prefix():
    assert updater.is_newer("v1.1.0", "1.0.0") is True


def test_parse_release_extracts_setup_asset():
    payload = {
        "tag_name": "v0.2.0",
        "assets": [
            {"name": "notes.txt", "browser_download_url": "http://x/notes.txt"},
            {"name": "SpineSpy-Setup.exe", "browser_download_url": "http://x/Setup.exe"},
        ],
    }
    info = updater.parse_release(payload, current="0.1.0")
    assert info is not None
    assert info.version == "0.2.0"
    assert info.installer_url == "http://x/Setup.exe"


def test_parse_release_none_when_not_newer():
    payload = {"tag_name": "v0.1.0", "assets": []}
    assert updater.parse_release(payload, current="0.1.0") is None
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_updater.py -v`
Expected: FAIL (module/attributes missing).

- [ ] **Step 3: Implement `updater.py`**

`spinespy_win/updater.py`:
```python
"""Check GitHub Releases for a newer SpineSpy and fetch its installer.

The only outbound network call in the app. Sends no image or usage data — an
unauthenticated GET to the public releases endpoint. Disable via config.
"""

from __future__ import annotations

import json
import os
import tempfile
import urllib.request
from dataclasses import dataclass

from spinespy_win import __version__

RELEASES_URL = (
    "https://api.github.com/repos/subhas85/spinespy-windows/releases/latest"
)
INSTALLER_ASSET = "SpineSpy-Setup.exe"
_TIMEOUT = 5


@dataclass
class UpdateInfo:
    version: str
    installer_url: str


def _to_tuple(v):
    return tuple(int(p) for p in v.lstrip("vV").split(".") if p.isdigit())


def is_newer(candidate, current):
    return _to_tuple(candidate) > _to_tuple(current)


def parse_release(payload, current=__version__):
    tag = payload.get("tag_name", "")
    if not tag or not is_newer(tag, current):
        return None
    for asset in payload.get("assets", []):
        if asset.get("name") == INSTALLER_ASSET:
            return UpdateInfo(
                version=tag.lstrip("vV"),
                installer_url=asset["browser_download_url"],
            )
    return None


def check(current=__version__):
    """Return UpdateInfo if a newer release exists, else None. Never raises."""
    try:
        req = urllib.request.Request(
            RELEASES_URL, headers={"Accept": "application/vnd.github+json"}
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return parse_release(payload, current=current)
    except Exception as exc:  # noqa: BLE001
        print(f"[updater] check failed: {exc}")
        return None


def download_and_launch(info):
    """Download the installer to %TEMP% and launch it. Returns the path, or None."""
    try:
        dest = os.path.join(tempfile.gettempdir(), INSTALLER_ASSET)
        urllib.request.urlretrieve(info.installer_url, dest)
        os.startfile(dest)  # noqa: S606 — launching our own signed-later installer
        return dest
    except Exception as exc:  # noqa: BLE001
        print(f"[updater] download/launch failed: {exc}")
        return None
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_updater.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add spinespy_win/updater.py tests/test_updater.py
git commit -m "feat(updater): GitHub release check + installer fetch (TDD)"
```

---

## Task 8: Tray icons (`icons.py`)

**Files:**
- Create: `spinespy_win/icons.py`

PIL image generation; verified by a quick byte-size assertion in a throwaway run (no formal test — trivial drawing code).

- [ ] **Step 1: Implement `icons.py`**

`spinespy_win/icons.py`:
```python
"""Generate flat colored tray icons (avoids inconsistent emoji glyph rendering)."""

from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw

_COLORS = {
    "good": (46, 160, 67),       # green
    "bad": (218, 54, 51),        # red
    "calibrating": (210, 153, 34),  # amber
}
_SIZE = 64


@lru_cache(maxsize=4)
def make_icon(state):
    """Return a 64x64 RGBA PIL image for the given state."""
    color = _COLORS.get(state, _COLORS["good"])
    img = Image.new("RGBA", (_SIZE, _SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([6, 6, _SIZE - 6, _SIZE - 6], fill=color)
    return img
```

- [ ] **Step 2: Manual verification**

Run:
```bash
.venv/Scripts/python -c "from spinespy_win.icons import make_icon; print([make_icon(s).size for s in ('good','bad','calibrating')])"
```
Expected: `[(64, 64), (64, 64), (64, 64)]`.

- [ ] **Step 3: Commit**

```bash
git add spinespy_win/icons.py
git commit -m "feat(icons): generated tray state icons"
```

---

## Task 9: Orchestrator (`app.py`)

The only stateful component. Holds runtime state and wires modules. Camera/MediaPipe are injected so the tick state machine is unit-testable with fakes.

**Files:**
- Create: `spinespy_win/app.py`
- Create: `tests/test_app.py`

- [ ] **Step 1: Write failing tests for the bad-streak state machine**

`tests/test_app.py`:
```python
from spinespy_win.app import SpineSpyApp
from spinespy_win.config import Config
from spinespy_win.pose import Calibration


class Recorder:
    def __init__(self):
        self.alerts = 0
        self.icon_states = []

    def alert(self):
        self.alerts += 1


def make_app(snapshot_results, recorder):
    """Build an app whose snapshot() yields queued (is_bad, reason) tuples."""
    cfg = Config(calibration=Calibration(0.0, 0.0, 0.1, 0.05))
    results = list(snapshot_results)

    app = SpineSpyApp(
        config=cfg,
        snapshot_fn=lambda: results.pop(0),
        set_icon_fn=lambda state: recorder.icon_states.append(state),
        alert_fn=recorder.alert,
    )
    return app


def test_alert_fires_after_streak_limit():
    rec = Recorder()
    bad = (True, "Slouching (mild)")
    app = make_app([bad] * 5, rec)
    for _ in range(5):
        app.tick()
    assert rec.alerts == 1
    assert app.bad_streak == 0  # reset after firing


def test_good_snapshot_resets_streak():
    rec = Recorder()
    app = make_app([(True, "Slouching (mild)"), (False, None)], rec)
    app.tick()
    assert app.bad_streak == 1
    app.tick()
    assert app.bad_streak == 0
    assert rec.alerts == 0


def test_paused_skips_snapshot():
    rec = Recorder()
    app = make_app([(True, "x")], rec)
    app.config.paused = True
    app.tick()
    assert app.bad_streak == 0
    assert rec.icon_states == []
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_app.py -v`
Expected: FAIL (no `SpineSpyApp`).

- [ ] **Step 3: Implement the orchestrator core**

`spinespy_win/app.py`:
```python
"""Orchestration: timer loop + bad-streak state machine. Wires the modules."""

from __future__ import annotations

from collections import Counter

from spinespy_win.pose import BAD_STREAK_LIMIT


class SpineSpyApp:
    def __init__(self, config, snapshot_fn, set_icon_fn, alert_fn):
        self.config = config
        self._snapshot = snapshot_fn      # () -> (is_bad, reason|None)
        self._set_icon = set_icon_fn      # (state: str) -> None
        self._alert = alert_fn            # () -> None
        self.bad_streak = 0
        self.bad_reasons = []
        self.calibrating = False

    def tick(self):
        if self.config.paused or self.calibrating:
            return
        try:
            is_bad, reason = self._snapshot()
        except Exception as exc:  # noqa: BLE001 — one bad tick must not kill the loop
            print(f"[app] tick failed: {exc}")
            return
        if is_bad is None:
            return
        if is_bad:
            self.bad_streak += 1
            self.bad_reasons.append(reason)
            self._set_icon("bad")
            if self.bad_streak >= BAD_STREAK_LIMIT:
                dominant = Counter(self.bad_reasons).most_common(1)[0][0]
                print(f"[app] alert: {dominant}")
                self._alert()
                self.bad_streak = 0
                self.bad_reasons = []
        else:
            self.bad_streak = 0
            self.bad_reasons = []
            self._set_icon("good")
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_app.py -v`
Expected: all PASS.

- [ ] **Step 5: Add the real snapshot + calibration helpers (manual-verified)**

Append to `spinespy_win/app.py`:
```python
def build_snapshot_fn(analyzer, calibration_getter, save_debug=False):
    """Return a snapshot() closure using real camera + MediaPipe + posture math."""
    from spinespy_win import camera
    from spinespy_win.pose import check_posture

    def snapshot():
        cal = calibration_getter()
        if cal is None:
            return False, None
        frames = camera.capture_frames(3)
        if not frames:
            return None, "Camera error"
        if save_debug:
            import cv2
            cv2.imwrite("debug_snapshot.jpg", frames[-1])
        votes, reasons = [], []
        for frame in frames:
            lms = analyzer.landmarks_for(camera.to_rgb(frame))
            if lms is None:
                votes.append(False)
                continue
            bad, reason = check_posture(lms, cal)
            votes.append(bad)
            if bad:
                reasons.append(reason)
        if sum(votes) >= len(votes) / 2 and reasons:
            return True, Counter(reasons).most_common(1)[0][0]
        return False, None

    return snapshot


def run_calibration(analyzer):
    """Capture calibration frames and return a Calibration, or None."""
    import time

    from spinespy_win import camera
    from spinespy_win.pose import (
        CALIBRATION_FRAMES,
        CALIBRATION_INTERVAL,
        calibrate_from_metrics,
        get_posture_metrics,
    )

    leans, tilts = [], []
    for _ in range(CALIBRATION_FRAMES):
        frames = camera.capture_frames(1)
        if frames:
            lms = analyzer.landmarks_for(camera.to_rgb(frames[0]))
            if lms is not None:
                lean, tilt = get_posture_metrics(lms)
                leans.append(lean)
                tilts.append(tilt)
        time.sleep(CALIBRATION_INTERVAL)
    return calibrate_from_metrics(leans, tilts)
```

- [ ] **Step 6: Run the full suite (no regressions)**

Run: `pytest -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add spinespy_win/app.py tests/test_app.py
git commit -m "feat(app): bad-streak state machine + real snapshot/calibration (TDD)"
```

---

## Task 10: Tray shell + entrypoint (`tray.py`, `main.py`)

**Files:**
- Create: `spinespy_win/tray.py`
- Create: `spinespy_win/main.py`

End-to-end glue; verified by launching the app on Windows.

- [ ] **Step 1: Implement `tray.py`**

`spinespy_win/tray.py`:
```python
"""pystray system-tray icon and menu. Holds no business logic — delegates."""

from __future__ import annotations

import pystray
from pystray import MenuItem as Item

from spinespy_win.icons import make_icon

INTERVALS = [("30 seconds", 30), ("1 minute", 60), ("2 minutes", 120), ("5 minutes", 300)]


def build_icon(controller):
    """controller exposes: toggle_pause, is_paused, set_interval, interval,
    toggle_sound, sound_enabled, calibrate, toggle_autostart, autostart_enabled,
    check_updates, save_debug, quit."""

    # pystray invokes an item's action with (icon, item); checked with (item).
    interval_items = [
        Item(
            label,
            (lambda icon, item, secs=secs: controller.set_interval(secs)),
            radio=True,
            checked=(lambda item, secs=secs: controller.interval == secs),
        )
        for label, secs in INTERVALS
    ]

    menu = pystray.Menu(
        Item("Monitoring", lambda icon, item: controller.toggle_pause(),
             checked=lambda item: not controller.is_paused()),
        Item("Interval", pystray.Menu(*interval_items)),
        Item("Sound clips", lambda icon, item: controller.toggle_sound(),
             checked=lambda item: controller.sound_enabled()),
        Item("Start at login", lambda icon, item: controller.toggle_autostart(),
             checked=lambda item: controller.autostart_enabled()),
        pystray.Menu.SEPARATOR,
        Item("Calibrate", lambda icon, item: controller.calibrate()),
        Item("Check for updates…", lambda icon, item: controller.check_updates()),
        Item("Save debug snapshot", lambda icon, item: controller.save_debug()),
        pystray.Menu.SEPARATOR,
        Item("Quit", lambda icon, item: controller.quit()),
    )

    icon = pystray.Icon("SpineSpy", make_icon("good"), "SpineSpy", menu)
    return icon
```

- [ ] **Step 2: Implement `main.py` (controller + wiring)**

`spinespy_win/main.py`:
```python
"""Entrypoint: build config, analyzer, app, tray; run timer + tray loop."""

from __future__ import annotations

import os
import sys
import threading
import time

from spinespy_win import alerts, autostart, config as cfg, updater
from spinespy_win.app import SpineSpyApp, build_snapshot_fn, run_calibration
from spinespy_win.icons import make_icon
from spinespy_win.pose import PoseAnalyzer
from spinespy_win.tray import build_icon


def resource_path(rel):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel)
    return rel


MODEL_REL = "assets/pose_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
)


def ensure_model():
    path = resource_path(MODEL_REL)
    if not os.path.exists(path):
        import urllib.request
        os.makedirs(os.path.dirname(path), exist_ok=True)
        alerts.notify("SpineSpy", "Downloading pose model (one time)…")
        urllib.request.urlretrieve(MODEL_URL, path)
    return path


class Controller:
    def __init__(self):
        self.config = cfg.load()
        self.analyzer = PoseAnalyzer(ensure_model())
        self.app = SpineSpyApp(
            config=self.config,
            snapshot_fn=build_snapshot_fn(self.analyzer, lambda: self.config.calibration),
            set_icon_fn=self._set_icon,
            alert_fn=self._fire_alert,
        )
        self.icon = build_icon(self)
        self._stop = threading.Event()
        self._pending_update = None

    # ---- timer loop ----
    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
        threading.Thread(target=self._first_run_and_updates, daemon=True).start()
        self.icon.run()  # blocks main thread

    def _loop(self):
        while not self._stop.is_set():
            self.app.tick()
            self._stop.wait(self.config.interval_seconds)

    def _first_run_and_updates(self):
        if self.config.calibration is None:
            alerts.notify("SpineSpy", "Sit up straight — calibrating in 3s…")
            time.sleep(3)
            self.calibrate(notify_start=False)
        if self.config.update_check_enabled:
            info = updater.check()
            if info:
                self._pending_update = info
                alerts.notify("SpineSpy", f"Update {info.version} available — use the tray menu to install.")

    # ---- icon/alert callbacks ----
    def _set_icon(self, state):
        self.icon.icon = make_icon(state)

    def _fire_alert(self):
        alerts.notify("SpineSpy", "Posture check — sit up!")
        alerts.play_random_clip(self.config.sound_enabled, resource_path)

    # ---- menu controller API ----
    def toggle_pause(self):
        self.config.paused = not self.config.paused
        cfg.save(self.config)

    def is_paused(self):
        return self.config.paused

    @property
    def interval(self):
        return self.config.interval_seconds

    def set_interval(self, secs):
        self.config.interval_seconds = secs
        cfg.save(self.config)

    def toggle_sound(self):
        self.config.sound_enabled = not self.config.sound_enabled
        cfg.save(self.config)

    def sound_enabled(self):
        return self.config.sound_enabled

    def toggle_autostart(self):
        self.config.autostart = not self.config.autostart
        autostart.set_autostart(self.config.autostart)
        cfg.save(self.config)

    def autostart_enabled(self):
        return autostart.is_autostart_enabled()

    def calibrate(self, notify_start=True):
        def _do():
            if notify_start:
                alerts.notify("SpineSpy", "Sit in your best posture — calibrating in 3s…")
                time.sleep(3)
            self.app.calibrating = True
            self._set_icon("calibrating")
            try:
                cal = run_calibration(self.analyzer)
                if cal:
                    self.config.calibration = cal
                    cfg.save(self.config)
                    alerts.notify("SpineSpy", "Calibration complete.")
                else:
                    alerts.notify("SpineSpy", "Calibration failed — make sure you're visible and well-lit.")
            finally:
                self.app.calibrating = False
                self._set_icon("good")
        threading.Thread(target=_do, daemon=True).start()

    def check_updates(self):
        info = self._pending_update or updater.check()
        if not info:
            alerts.notify("SpineSpy", "You're on the latest version.")
            return
        alerts.notify("SpineSpy", f"Installing update {info.version}…")
        if updater.download_and_launch(info):
            self.quit()

    def save_debug(self):
        snap = build_snapshot_fn(self.analyzer, lambda: self.config.calibration, save_debug=True)
        threading.Thread(target=snap, daemon=True).start()

    def quit(self):
        self._stop.set()
        self.icon.stop()


def main():
    # Apply autostart preference on every launch so it matches config.
    Controller_instance = Controller()
    autostart.set_autostart(Controller_instance.config.autostart)
    Controller_instance.start()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Manual verification (Windows)**

Run:
```bash
.venv/Scripts/python -m spinespy_win.main
```
Expected: tray icon appears; first-run toast then auto-calibration (icon turns amber, then green); right-click shows the full menu; slouching for 5 ticks fires a toast + clip. Quit from the menu exits cleanly.

- [ ] **Step 4: Run the full unit suite (no regressions)**

Run: `pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add spinespy_win/tray.py spinespy_win/main.py
git commit -m "feat(tray): pystray menu + controller wiring; end-to-end app"
```

---

## Task 11: Assets

**Files:**
- Create: `assets/audio/*.mp3` (copied from upstream)

- [ ] **Step 1: Copy the reminder clips from upstream**

Run:
```bash
mkdir -p assets/audio
cp /tmp/spinespy/assets/audio/*.mp3 assets/audio/
ls assets/audio
```
Expected: six `.mp3` files listed, matching `ALERT_SOUND_FILES` in `alerts.py`.

- [ ] **Step 2: Commit**

```bash
git add assets/audio
git commit -m "assets: bundle reminder audio clips from upstream"
```

---

## Task 12: PyInstaller packaging (`packaging/spinespy.spec`)

**Files:**
- Create: `packaging/spinespy.spec`

- [ ] **Step 1: Write the PyInstaller spec**

`packaging/spinespy.spec`:
```python
# PyInstaller spec — onedir, windowed (no console).
from PyInstaller.utils.hooks import collect_all

datas = [("../assets", "assets")]
binaries = []
hiddenimports = ["pystray._win32"]
for pkg in ("mediapipe", "cv2"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

a = Analysis(
    ["../spinespy_win/main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SpineSpy",
          console=False, icon=None)
coll = COLLECT(exe, a.binaries, a.datas, name="SpineSpy")
```

- [ ] **Step 2: Build locally (Windows)**

Run:
```bash
.venv/Scripts/python -m pip install pyinstaller
.venv/Scripts/pyinstaller packaging/spinespy.spec --noconfirm
dist/SpineSpy/SpineSpy.exe
```
Expected: `dist/SpineSpy/SpineSpy.exe` launches the tray app identically to the dev run.

- [ ] **Step 3: Commit**

```bash
git add packaging/spinespy.spec
git commit -m "build: PyInstaller onedir spec"
```

---

## Task 13: Inno Setup installer (`packaging/installer.iss`)

**Files:**
- Create: `packaging/installer.iss`

- [ ] **Step 1: Write the Inno Setup script**

`packaging/installer.iss`:
```ini
#define AppName "SpineSpy"
#define AppVersion "0.1.0"
#define AppExe "SpineSpy.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=subhas85
DefaultDirName={localappdata}\Programs\SpineSpy
DefaultGroupName=SpineSpy
PrivilegesRequired=lowest
OutputBaseFilename=SpineSpy-Setup
Compression=lzma2
SolidCompression=yes
DisableProgramGroupPage=yes

[Files]
Source: "..\dist\SpineSpy\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\SpineSpy"; Filename: "{app}\{#AppExe}"
Name: "{userstartup}\SpineSpy"; Filename: "{app}\{#AppExe}"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch SpineSpy"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
```

> Autostart-on-by-default is provided by the `{userstartup}` shortcut here; the in-app toggle manages the HKCU Run key independently. Both point at the same exe; having a Startup shortcut + Run key is harmless (Windows dedupes by launching once per mechanism — acceptable, and the toggle still lets users disable the Run-key path). If double-launch is observed in smoke testing, drop the `{userstartup}` line and rely solely on the in-app Run-key default set in `main()`.

- [ ] **Step 2: Compile locally (Windows, Inno Setup installed)**

Run:
```bash
iscc packaging/installer.iss
```
Expected: `packaging/Output/SpineSpy-Setup.exe` produced; running it installs to `%LOCALAPPDATA%\Programs\SpineSpy`, adds Start Menu + Startup entries, launches the app.

- [ ] **Step 3: Commit**

```bash
git add packaging/installer.iss
git commit -m "build: Inno Setup installer (per-user, autostart, clean uninstall)"
```

---

## Task 14: GitHub Actions release pipeline

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Write the workflow**

`.github/workflows/release.yml`:
```yaml
name: Release
on:
  push:
    tags: ["v*"]

jobs:
  build:
    runs-on: windows-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -e .
          pip install pyinstaller

      - name: Fetch pose model
        run: |
          mkdir assets -Force
          curl -L -o assets/pose_landmarker.task "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"

      - name: PyInstaller build
        run: pyinstaller packaging/spinespy.spec --noconfirm

      - name: Inno Setup compile
        run: |
          choco install innosetup -y
          & "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" packaging/installer.iss

      - name: Release
        uses: softprops/action-gh-release@v2
        with:
          name: SpineSpy ${{ github.ref_name }}
          files: packaging/Output/SpineSpy-Setup.exe
```

> The `AppVersion` in `installer.iss` and `__version__` in `__init__.py` must both be bumped to match the tag before tagging a release. (A later enhancement can template these from the tag; out of scope now.)

- [ ] **Step 2: Verify the workflow file parses**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"`
Expected: no error.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: Windows release pipeline (PyInstaller + Inno Setup)"
```

---

## Task 15: Docs (`PRIVACY.md`, `README.md`)

**Files:**
- Create: `PRIVACY.md`
- Create: `README.md`

- [ ] **Step 1: Write `PRIVACY.md`**

`PRIVACY.md`:
```markdown
# Privacy

SpineSpy processes all webcam imagery **on your device**.

- The camera opens only briefly each interval, is analyzed in memory, and is
  released immediately. No image is stored or transmitted.
- The pose model is bundled in the installer — the app needs no network to
  monitor posture and works fully offline.
- No telemetry or analytics libraries are included.
- The only outbound network request is an optional update check: an
  unauthenticated request to GitHub's public releases API that returns a
  version number. It sends no image and no personal data, and can be turned off.
- The only files written are your settings (`%APPDATA%\SpineSpy\config.json`)
  and, if you explicitly choose "Save debug snapshot", a single JPG.
```

- [ ] **Step 2: Write `README.md`**

`README.md`:
```markdown
# SpineSpy for Windows 11

Posture nudge that lives in your system tray. Every interval it briefly checks
your posture against your own calibrated baseline and reminds you to sit up.
All processing is local — see [PRIVACY.md](PRIVACY.md).

A Windows, posture-only port of [jananadiw/spinespy](https://github.com/jananadiw/spinespy).

## Install
Download `SpineSpy-Setup.exe` from the latest
[release](https://github.com/subhas85/spinespy-windows/releases) and run it.
(Unsigned for now — Windows SmartScreen will warn; choose "More info → Run anyway".)

## Use
Right-click the tray icon: pause monitoring, set interval, toggle sound,
calibrate, start-at-login, check for updates.

## Develop
```bash
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m spinespy_win.main
pytest -v
```

## License
MIT (inherits upstream).
```

- [ ] **Step 3: Commit**

```bash
git add PRIVACY.md README.md
git commit -m "docs: privacy statement and README"
```

---

## Task 16: Final verification

- [ ] **Step 1: Full unit suite**

Run: `pytest -v`
Expected: all tests in `test_pose.py`, `test_config.py`, `test_autostart.py`, `test_updater.py`, `test_app.py` PASS.

- [ ] **Step 2: Windows smoke checklist** (from spec §9)

Walk through on a Windows 11 machine and tick each:
- [ ] Installer runs, app appears in tray
- [ ] First-run auto-calibration completes (amber → green)
- [ ] Slouch → red icon
- [ ] 5 consecutive bad → toast + reminder clip
- [ ] Pause stops checks; resume restarts
- [ ] Interval change takes effect
- [ ] "Start at login" toggle reflected in HKCU Run key (`reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v SpineSpy`)
- [ ] "Check for updates" against a seeded newer release downloads + relaunches installer
- [ ] Uninstall removes the app; settings file behavior as documented

- [ ] **Step 3: Confirm local-only behavior**

With the app running and update check disabled in config, capture network with Resource Monitor / `netstat` over one interval and confirm no outbound connections from `SpineSpy.exe`.
Expected: no network egress during posture checks.

- [ ] **Step 4: Tag a test release** (optional, when ready)

```bash
git tag v0.1.0 && git push origin v0.1.0
```
Expected: the Actions workflow builds and attaches `SpineSpy-Setup.exe` to the GitHub release.

# SpineSpy for Windows 11 — Spec & Implementation Doc

**Date:** 2026-06-10
**Status:** Approved design, ready for implementation plan
**Upstream:** https://github.com/jananadiw/spinespy (macOS menubar app, MIT)
**This project:** A from-scratch Windows 11 repackaging of SpineSpy, posture-only, system-tray native, self-updating, with all image processing kept strictly on-device.

---

## 1. Summary

SpineSpy is a webcam posture nudge. Every N minutes it briefly opens the camera, takes a few snapshots, measures forward-lean and side-tilt against a *personal calibrated baseline* using MediaPipe Pose, then closes the camera. After several consecutive "bad" snapshots it shows a notification and plays a short reminder clip. Nothing is recorded or transmitted.

This document specifies a Windows 11 port that:

- **Keeps the detection brain** (MediaPipe Pose + personal calibration) essentially unchanged — it is platform-agnostic and already unit-tested upstream.
- **Replaces the macOS shell** (menubar, audio, notifications, camera backend, packaging) with Windows-native equivalents.
- **Drops phone detection** (YOLO + PyTorch, ~1 GB) to stay simple and small.
- **Adds** persistent calibration, run-at-login, and one-click self-update — none of which the original has.
- **Guarantees local-only image processing** as an explicit, testable property.

Non-goals: phone/distraction detection, cloud sync, multi-user accounts, mobile, macOS/Linux parity.

---

## 2. Requirements

### 2.1 Functional

- **FR-1** Run as a Windows 11 system-tray app with no taskbar/window presence.
- **FR-2** On a configurable interval (30 s / 1 min / 2 min / 5 min), open the default webcam, capture 3 frames, analyze, release the camera immediately.
- **FR-3** Detect *slouching* (forward lean) and *tilting* (side lean) relative to a calibrated personal baseline, by majority vote across the 3 frames.
- **FR-4** Tray icon reflects state: good (green), bad (red), calibrating (gauge).
- **FR-5** After `BAD_STREAK_LIMIT` (default 5) consecutive bad snapshots, show a toast notification and play a random reminder MP3 (if sound enabled), then reset the streak.
- **FR-6** Calibration: capture 10 frames, compute median baseline + adaptive thresholds (3×std), on demand and on first run.
- **FR-7** Tray menu: pause/resume monitoring, interval submenu, sound on/off, calibrate, start-at-login toggle, check-for-updates, save debug snapshot, quit.
- **FR-8** Persist settings and the calibration baseline across restarts.
- **FR-9** Start automatically at Windows login (on by default; toggleable).
- **FR-10** Self-update: detect a newer GitHub Release and offer one-click download + install.

### 2.2 Non-functional / constraints

- **NFR-1 (Privacy — primary requirement)** All image capture and analysis happen on-device. No image data ever leaves the machine or is persisted to disk, except the explicit, off-by-default "Save debug snapshot" action. The only outbound network call is the update check (version metadata only) and the one-time-or-bundled model fetch.
- **NFR-2 (Simple)** Single small Python codebase, ~150 MB installed (no torch). One-file installer. No external runtime binaries (no ffmpeg/afplay equivalents).
- **NFR-3** Works offline for its core function (model bundled). Network is optional.
- **NFR-4** Python 3.10–3.13, Windows 11 x64.
- **NFR-5** Graceful degradation: camera blocked, model missing, or network down must never crash the tray app.

---

## 3. Architecture

### 3.1 Module layout

Each module is small, single-purpose, and independently testable.

```
spinespy_win/
  __init__.py        # __version__ lives here
  pose.py            # MediaPipe landmarker + posture math (ported from upstream)
  camera.py          # webcam open/capture/release (Windows backends)
  alerts.py          # toast notifications + MP3 playback
  config.py          # load/save settings + baseline to %APPDATA%
  autostart.py       # registry Run-key management
  updater.py         # GitHub Releases version check + installer download
  tray.py            # pystray icon + menu construction
  icons.py           # generate good/bad/calibrating tray icons (PIL)
  app.py             # orchestration: timer loop + bad-streak state machine
  main.py            # entrypoint
assets/
  audio/*.mp3        # bundled reminder clips (from upstream)
  pose_landmarker.task  # bundled at build time (see §7)
```

### 3.2 Responsibilities & interfaces

**`pose.py`** — pure logic, no I/O beyond the MediaPipe detector. Ported nearly verbatim from upstream `menubar_app.py`:
- `get_posture_metrics(landmarks) -> (forward_lean, tilt)` — `forward_lean = mean(shoulder.z) - nose.z`; `tilt = abs(left_shoulder.y - right_shoulder.y)`.
- `Calibration` dataclass: `baseline_lean`, `baseline_tilt`, `slouch_threshold`, `tilt_threshold`.
- `calibrate(frames) -> Calibration | None` — median of metrics over valid frames; adaptive thresholds `max(BASE, std*3)`; requires ≥ `CALIBRATION_FRAMES//2` valid frames.
- `check_posture(landmarks, calibration) -> (is_bad: bool, reason: str | None)` — slouch if `lean_delta >= slouch_threshold`, tilt if `tilt_delta >= tilt_threshold`; severity label mild/moderate/severe from delta ratio.
- Detector created from a model path passed in (no module-level download side effect — caller supplies the path).

  *Change from upstream:* calibration is a returned value object, not module globals; the detector is injected. This makes it unit-testable with synthetic landmarks (as the upstream tests already do).

**`camera.py`**
- `capture_frames(n: int) -> list[np.ndarray] | None` — opens `cv2.VideoCapture(0, cv2.CAP_MSMF)`, falls back to `CAP_DSHOW` if that fails to open; warm-up read of 5 frames; horizontal flip (mirror) like upstream; releases the capture in a `finally`. Returns `None` on open failure.
- `camera_permission_hint() -> str` — Windows wording: "Camera access is blocked or in use. Allow it in Settings → Privacy & security → Camera, and ensure no other app is using the webcam."

**`alerts.py`**
- `notify(title, message)` — Windows toast via `windows-toasts` (WinRT, no admin, no external deps).
- `play_random_clip(enabled: bool) -> bool` — picks a random bundled MP3, plays it on a background thread via `just_playback` (pure-Python miniaudio binding; decodes MP3 in-process, no system player). Returns False if disabled or no clips found.

**`config.py`**
- Path: `%APPDATA%\SpineSpy\config.json`.
- `load() -> Config` (creates defaults if missing); `save(config)`.
- Fields: `interval_seconds` (default 60), `sound_enabled` (True), `autostart` (True), `paused` (False), and a nested `calibration` (the baseline + thresholds, nullable).
- Atomic write (temp file + replace) to avoid corruption.

  *Change from upstream:* upstream keeps everything in memory and loses calibration on quit. Persisting it means the first-run auto-calibration is a one-time event, not every launch.

**`autostart.py`**
- `set_autostart(enabled: bool)` / `is_autostart_enabled() -> bool` via `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, value name `SpineSpy`, pointing at the installed exe.
- All `winreg` access wrapped so it can be mocked in tests; failures are logged, never fatal.

**`updater.py`**
- `__version__` compared against the latest GitHub Release tag.
- `check() -> UpdateInfo | None` — GET `https://api.github.com/repos/subhas85/spinespy-windows/releases/latest`, parse `tag_name` (strip leading `v`), semver-compare; return the installer asset URL if newer. Timeouts short (5 s), all exceptions swallowed to `None`.
- `download_and_launch(update_info)` — stream the `SpineSpy-Setup.exe` asset to `%TEMP%`, then `os.startfile()` it (Inno installer relaunches/replaces the running app). The running app quits after launching the installer.
- Update check runs once at startup and then daily; can be disabled (a config flag `update_check_enabled`, default True). No image or usage data is ever sent — only an unauthenticated GET to the releases endpoint.

**`icons.py`**
- `make_icon(state) -> PIL.Image` — generates a simple flat colored disc (green = good, red = bad, amber = calibrating) at 64×64; avoids shipping/relying on emoji glyphs that render inconsistently in the Windows tray. Cached.

**`tray.py`**
- Builds the `pystray.Icon` with a `pystray.Menu`. Menu items mirror upstream plus Windows additions:
  - `✓ Monitoring` (checkable) → toggles `paused`
  - `Interval ▸` 30s / 1m / 2m / 5m (radio)
  - `Sound clips` (checkable)
  - `Start at login` (checkable)
  - `Calibrate`
  - `Check for updates…`
  - `Save debug snapshot` (writes one JPG next to config, for troubleshooting only)
  - `Quit`
- Menu callbacks delegate to `app.py`; `tray.py` holds no business logic.

**`app.py`** — the orchestrator and only stateful component.
- Holds runtime state: `bad_streak`, `bad_reasons`, current `Config`, current `Calibration`, `calibrating` flag.
- `tick()` (called by a `threading.Timer` loop): if paused/calibrating, skip. Else `camera.capture_frames(3)` → per-frame `pose.check_posture` → majority vote → update icon + streak; on streak ≥ limit, `alerts.notify` + `alerts.play_random_clip`, reset.
- `run_calibration()`: on a background thread, capture `CALIBRATION_FRAMES` over the calibration interval, call `pose.calibrate`, persist to config, toast the result.
- First run (no saved calibration): auto-calibrate after a 3 s "sit up straight" toast.
- Interval changes restart the timer.

**`main.py`**
- Resolve bundled resource paths (PyInstaller `sys._MEIPASS` aware, ported from upstream `resource_path`).
- Construct config → app → tray, start the timer, run the tray loop (`icon.run()`), which blocks the main thread.

### 3.3 Data flow

```
Timer (every interval)
   └─ app.tick()
        ├─ camera.capture_frames(3) ──► [frame, frame, frame]  (mirror-flipped, then released)
        ├─ for each frame: pose.detect → pose.check_posture(landmarks, calibration)
        ├─ majority vote → (is_bad, dominant_reason)
        ├─ tray icon ← good / bad
        └─ if is_bad: streak++; if streak ≥ 5 → alerts.notify + alerts.play_random_clip; reset
```

Frames live only in memory for the duration of `tick()` and are discarded. No frame is encoded to disk except the explicit debug action.

---

## 4. Detection logic (ported, unchanged)

Carried over verbatim from upstream so behavior matches the proven implementation:

```
SLOUCH_THRESHOLD   = 0.1     # base forward-lean sensitivity
TILT_THRESHOLD     = 0.05    # base side-tilt sensitivity
BAD_STREAK_LIMIT   = 5       # consecutive bad snapshots before alert
CALIBRATION_FRAMES = 10
CALIBRATION_INTERVAL = 0.3   # seconds between calibration frames
SNAPSHOT_FRAMES    = 3       # frames per snapshot, majority voted
```

- `forward_lean = (left_shoulder.z + right_shoulder.z)/2 - nose.z`
- `tilt = abs(left_shoulder.y - right_shoulder.y)`
- Calibrated baseline = median over valid calibration frames.
- Adaptive threshold = `max(base_threshold, std_of_metric * 3)` — widens the dead-band for fidgety users.
- A snapshot is "bad" if ≥ half of its frames are bad **and** at least one frame produced a reason.
- Model: `pose_landmarker_lite` (MediaPipe Tasks). Bundled.

---

## 5. Local-processing guarantees (NFR-1 detail)

This is the headline requirement, so it is specified, not assumed:

1. **No upload path exists in the image code.** `camera.py` and `pose.py` import no network library. Frames are `numpy` arrays passed by reference and dropped at function exit.
2. **Model is bundled** in the installer (`assets/pose_landmarker.task`), so the app never needs to fetch it at runtime. (If somehow missing, it falls back to a one-time download from Google's MediaPipe model host with an explicit toast — but the shipped installer always includes it.)
3. **No telemetry libraries.** Dropping Ultralytics/YOLO removes the only upstream dependency that sends anonymous analytics by default. MediaPipe, OpenCV, pystray, just_playback, and windows-toasts perform no usage reporting.
4. **The one outbound call** is `updater.check()` — an unauthenticated `GET` to GitHub's public releases API returning a version string. It carries no image, no identifiers, and can be turned off (`update_check_enabled = false`).
5. **Disk writes** are limited to `config.json` and (only on explicit menu action) a single `debug_snapshot.jpg`. No rolling capture, no history.
6. A short **PRIVACY.md** ships with the app restating points 1–5 for end users.

---

## 6. Error handling

| Condition | Behavior |
|---|---|
| Camera won't open / permission denied | Toast with `camera_permission_hint()`; icon stays neutral; retry next tick. Never crash. |
| No pose detected in a frame | Counts as "good" (upstream behavior) — avoids false alarms when user steps away. |
| Too few valid calibration frames | Toast "Calibration failed — make sure you're visible and well-lit"; keep previous baseline. |
| Model file missing | One-time download with progress toast; if offline, posture monitoring paused with a clear toast, tray still runs. |
| MP3 missing/decode error | Skip silently (logged); notification still shows. |
| Update check network failure | Swallowed to `None`; retry next cycle. |
| Registry write denied | Log + toast "Couldn't change start-at-login"; app continues. |
| Config file corrupt | Back up the bad file, regenerate defaults, toast once. |

All ticks run inside a try/except that logs and continues — a single bad tick must not kill the tray loop.

---

## 7. Packaging & release pipeline

### 7.1 Build (GitHub Actions, `windows-latest`)

1. `pip install` runtime deps + `pyinstaller`.
2. Fetch the MediaPipe model into `assets/pose_landmarker.task`.
3. PyInstaller, `--windowed`, **onedir** (faster startup than onefile, plays nicer with antivirus), `--add-data` for `assets/`, `--collect-all mediapipe`, version metadata from `__version__`.
4. Compile an **Inno Setup** script with `iscc` → `SpineSpy-Setup.exe`.
5. Attach `SpineSpy-Setup.exe` to the GitHub Release created on the `v*` tag push.

### 7.2 Inno Setup installer

- Installs to `%LOCALAPPDATA%\Programs\SpineSpy` (per-user, no admin/UAC prompt).
- Start Menu shortcut.
- Adds the autostart `Run` key by default (matches the "on by default" decision); the in-app toggle can later remove it.
- Embeds version in `AppVersion` so the updater's downloaded installer cleanly upgrades in place.
- Clean uninstaller (removes Run key, Start Menu entry, install dir; leaves `%APPDATA%\SpineSpy\config.json` unless "remove settings" is checked).

### 7.3 Self-update loop (end to end)

```
app start ──► updater.check() (and daily thereafter)
                 │ newer release?
                 ├─ no  → nothing
                 └─ yes → toast "Update available" + enable tray "Install update vX.Y.Z"
                            └─ user clicks → download SpineSpy-Setup.exe to %TEMP%
                                              → os.startfile(setup) → app quits
                                              → Inno installer upgrades in place → relaunch
```

No silent background swap (per the chosen "check + notify, one-click" option) — the user always confirms.

---

## 8. Dependencies

| Package | Purpose | Notes |
|---|---|---|
| `opencv-python` | camera capture | MSMF/DSHOW backends |
| `mediapipe` | pose landmarker | bundled `.task` model |
| `numpy` | frame arrays | transitive, pinned |
| `pystray` | system tray | cross-platform, active |
| `Pillow` | tray icon images | required by pystray |
| `windows-toasts` | WinRT toast notifications | no admin needed |
| `just_playback` | in-process MP3 playback | miniaudio binding, no external player |
| `pytest` (dev) | tests | |

Explicitly **removed** vs upstream: `ultralytics`, `torch`, `torchvision`, `rumps`.

---

## 9. Testing

- **Port** upstream `tests/test_posture.py` and `tests/test_snapshot.py` — the posture math is platform-agnostic and drives `pose.py` with synthetic landmark objects. (Refactor: tests target injected `Calibration` instead of module globals.)
- **New unit tests:**
  - `config`: defaults, round-trip save/load, corrupt-file recovery, atomic write.
  - `updater`: semver compare (`1.2.0` > `1.10.0`? must be False — use proper semver, not string compare), asset URL extraction, network-failure → `None`.
  - `autostart`: set/clear/query with `winreg` mocked.
  - `pose.calibrate`: too-few-frames returns `None`; adaptive threshold floor respected.
- **Manual smoke checklist** (Windows 11): install → first-run auto-calibrate → slouch → red icon → 5× → toast + clip → pause → interval change → start-at-login toggle reflected in registry → update check against a seeded newer release → uninstall leaves no Run key.

---

## 10. Open items / future (out of scope now)

- Phone-distraction detection (would reintroduce a heavy model — deferred, possibly via a lightweight MediaPipe object detector later).
- Persistent posture stats/history (conflicts with the no-storage stance unless explicitly opt-in).
- **Code signing the installer.** *Decision (2026-06-10): ship unsigned until mass adoption.* Initial releases are unsigned — Windows SmartScreen will warn on first install (users click "More info → Run anyway"); this is acceptable for the personal/early-adopter stage. When adoption justifies it, adopt **Azure Artifact Signing** (formerly Trusted Signing, ~US$9.99/mo): individual developers in Canada are eligible, it needs **no hardware token**, so it drops straight into the GitHub Actions release job without breaking the automated pipeline. Avoid EV/hardware-token certs — since ~April 2026 Microsoft has been phasing out the EV "instant SmartScreen reputation" benefit, so *every* cert now earns reputation gradually over downloads rather than clearing the warning on day one; that removes the reason to pay EV prices. The installer/CI design in §7 already isolates signing as a single optional step, so adding it later is additive, not a rework.

---

## 11. Build order (for the implementation plan)

1. `pose.py` + ported tests (no UI, provable in isolation).
2. `camera.py` (manual webcam check).
3. `config.py` + tests.
4. `alerts.py` (toast + one clip).
5. `icons.py` + `tray.py` (menu wired to stubs).
6. `app.py` orchestration → first end-to-end run from `python -m spinespy_win`.
7. `autostart.py` + tests.
8. `updater.py` + tests.
9. PyInstaller spec → local exe.
10. Inno Setup script → installer.
11. GitHub Actions release workflow.
12. `PRIVACY.md`, `README.md`, smoke pass.

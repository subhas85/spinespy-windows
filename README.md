# SpineSpy for Windows 11

Posture nudge that lives in your system tray. Every interval it briefly checks
your posture against your own calibrated baseline and reminds you to sit up.
All processing is local — see [PRIVACY.md](PRIVACY.md).

A Windows, posture-only port of [jananadiw/spinespy](https://github.com/jananadiw/spinespy).

## Install

Download `SpineSpy-Setup.exe` from the latest
[release](https://github.com/subhas85/spinespy-windows/releases) and run it.

> Unsigned for now — Windows SmartScreen will warn on first run. Click
> **More info → Run anyway**. (Code signing is planned once the project sees
> wider use; see the design doc.)

After install it starts automatically and lives in the system tray (look for the
green dot near the clock; click the **^** chevron if it's hidden).

## Use

Right-click the tray icon:

- **Monitoring** — pause/resume posture checks
- **Interval** — 30s / 1m / 2m / 5m between checks
- **Sound clips** — toggle the spoken reminder clips
- **Start at login** — toggle autostart
- **Calibrate** — recapture your good-posture baseline
- **Check for updates…** — fetch the latest release
- **Save debug snapshot** — write one JPG for troubleshooting
- **Quit**

On first launch it auto-calibrates: sit up straight when you see the
"calibrating" toast (icon turns amber, then green).

## How it works

Every interval the app opens the webcam, grabs 3 frames, runs MediaPipe Pose to
measure forward-lean and side-tilt against your calibrated baseline (majority
vote across the frames), then closes the camera. After 5 consecutive bad
snapshots it shows a toast and plays a random reminder clip.

## Develop

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m spinespy_win.main
pytest -v
```

Building the installer (Windows, with Inno Setup) is automated by
`.github/workflows/release.yml` on any `v*` tag.

## Docs

- [Design / spec](docs/2026-06-10-spinespy-windows-design.md)
- [Implementation plan](docs/superpowers/plans/2026-06-10-spinespy-windows.md)
- [Privacy](PRIVACY.md)

## License

MIT (inherits upstream).

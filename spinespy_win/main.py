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
                alerts.notify(
                    "SpineSpy",
                    f"Update {info.version} available — use the tray menu to install.",
                )

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
                    alerts.notify(
                        "SpineSpy",
                        "Calibration failed — make sure you're visible and well-lit.",
                    )
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
    controller = Controller()
    autostart.set_autostart(controller.config.autostart)
    controller.start()


if __name__ == "__main__":
    main()

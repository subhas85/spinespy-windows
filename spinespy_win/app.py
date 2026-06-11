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

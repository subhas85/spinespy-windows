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

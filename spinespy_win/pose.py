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

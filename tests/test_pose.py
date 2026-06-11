from spinespy_win import pose


def test_get_posture_metrics_computes_lean_and_tilt(landmarks_factory):
    # shoulders at z=0.4, nose at z=0.0 -> forward_lean = 0.4 - 0.0 = 0.4
    # shoulder y diff = |0.6 - 0.5| = 0.1
    lms = landmarks_factory(nose_z=0.0, l_sh_z=0.4, r_sh_z=0.4, l_sh_y=0.6, r_sh_y=0.5)
    lean, tilt = pose.get_posture_metrics(lms)
    assert lean == 0.4
    assert abs(tilt - 0.1) < 1e-9


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

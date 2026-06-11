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

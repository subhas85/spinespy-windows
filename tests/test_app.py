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

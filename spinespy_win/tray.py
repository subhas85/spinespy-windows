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

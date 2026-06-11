"""Windows toast notifications and bundled MP3 playback (in-process)."""

from __future__ import annotations

import os
import random
import threading

ALERT_SOUND_FILES = [
    "assets/audio/Come on, shoulders back.mp3",
    "assets/audio/auditioning to be a shrimp.mp3",
    "assets/audio/did gravity offend u.mp3",
    "assets/audio/slouching_bella.mp3",
    "assets/audio/writing in cursive.mp3",
    "assets/audio/you're not a croissant.mp3",
]


def pick_clip(resolve, rng=random):
    """Return a playable clip path among bundled clips that exist, else None.

    `resolve` maps a relative asset path to an absolute one (resource_path).
    """
    available = [resolve(p) for p in ALERT_SOUND_FILES if os.path.exists(resolve(p))]
    if not available:
        return None
    return rng.choice(available)


def notify(title, message):
    """Show a Windows toast. Never raises."""
    try:
        from windows_toasts import Toast, WindowsToaster

        toaster = WindowsToaster("SpineSpy")
        toast = Toast()
        toast.text_fields = [title, message]
        toaster.show_toast(toast)
    except Exception as exc:  # noqa: BLE001 — UI nicety must not crash the app
        print(f"[alerts] toast failed: {exc}")


def play_random_clip(enabled, resolve):
    """Play a random reminder clip on a background thread. Returns False if skipped."""
    if not enabled:
        return False
    clip = pick_clip(resolve)
    if clip is None:
        return False

    def _play():
        try:
            import time

            from just_playback import Playback

            pb = Playback()
            pb.load_file(clip)
            pb.play()
            while pb.active:
                time.sleep(0.1)
        except Exception as exc:  # noqa: BLE001
            print(f"[alerts] playback failed: {exc}")

    threading.Thread(target=_play, daemon=True).start()
    return True

"""Check GitHub Releases for a newer SpineSpy and fetch its installer.

The only outbound network call in the app. Sends no image or usage data — an
unauthenticated GET to the public releases endpoint. Disable via config.
"""

from __future__ import annotations

import json
import os
import tempfile
import urllib.request
from dataclasses import dataclass

from spinespy_win import __version__

RELEASES_URL = (
    "https://api.github.com/repos/subhas85/spinespy-windows/releases/latest"
)
INSTALLER_ASSET = "SpineSpy-Setup.exe"
_TIMEOUT = 5


@dataclass
class UpdateInfo:
    version: str
    installer_url: str


def _to_tuple(v):
    return tuple(int(p) for p in v.lstrip("vV").split(".") if p.isdigit())


def is_newer(candidate, current):
    return _to_tuple(candidate) > _to_tuple(current)


def parse_release(payload, current=__version__):
    tag = payload.get("tag_name", "")
    if not tag or not is_newer(tag, current):
        return None
    for asset in payload.get("assets", []):
        if asset.get("name") == INSTALLER_ASSET:
            return UpdateInfo(
                version=tag.lstrip("vV"),
                installer_url=asset["browser_download_url"],
            )
    return None


def check(current=__version__):
    """Return UpdateInfo if a newer release exists, else None. Never raises."""
    try:
        req = urllib.request.Request(
            RELEASES_URL, headers={"Accept": "application/vnd.github+json"}
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return parse_release(payload, current=current)
    except Exception as exc:  # noqa: BLE001
        print(f"[updater] check failed: {exc}")
        return None


def download_and_launch(info):
    """Download the installer to %TEMP% and launch it. Returns the path, or None."""
    try:
        dest = os.path.join(tempfile.gettempdir(), INSTALLER_ASSET)
        urllib.request.urlretrieve(info.installer_url, dest)
        os.startfile(dest)  # noqa: S606 — launching our own installer
        return dest
    except Exception as exc:  # noqa: BLE001
        print(f"[updater] download/launch failed: {exc}")
        return None

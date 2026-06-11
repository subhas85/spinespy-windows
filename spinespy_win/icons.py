"""Generate flat colored tray icons (avoids inconsistent emoji glyph rendering)."""

from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw

_COLORS = {
    "good": (46, 160, 67),          # green
    "bad": (218, 54, 51),           # red
    "calibrating": (210, 153, 34),  # amber
}
_SIZE = 64


@lru_cache(maxsize=4)
def make_icon(state):
    """Return a 64x64 RGBA PIL image for the given state."""
    color = _COLORS.get(state, _COLORS["good"])
    img = Image.new("RGBA", (_SIZE, _SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([6, 6, _SIZE - 6, _SIZE - 6], fill=color)
    return img

"""Reads the game state from screen pixels.

Pure numpy, no Windows calls, so it is fully unit-testable.

All thresholds are fractions of the scanned area. The original version used
raw pixel counts tuned at 1920x1080, which made detection drift at other
resolutions. The ratios below give exactly the same result at 1080p.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Region:
    """A rectangle given as fractions (0..1) of a monitor."""

    left: float
    top: float
    right: float
    bottom: float

    def to_rect(self, monitor: dict) -> dict:
        w, h = monitor["width"], monitor["height"]
        left = int(w * self.left)
        top = int(h * self.top)
        return {
            "left": monitor["left"] + left,
            "top": monitor["top"] + top,
            "width": max(1, int(w * self.right) - left),
            "height": max(1, int(h * self.bottom) - top),
        }


# Centre-left area where "server full" (red) and the queue text (yellow) show up.
DIALOG_REGION = Region(0.28, 0.28, 0.52, 0.45)
# Bottom-left area where the in-game ESC / Back button lives.
ESC_REGION = Region(0.05, 0.65, 0.45, 0.95)

_DIALOG_AREA_1080P = 460 * 183
RED_FULL_RATIO = 50 / _DIALOG_AREA_1080P          # ~0.06 % of the area
YELLOW_QUEUE_RATIO = 1500 / _DIALOG_AREA_1080P    # ~1.8 % of the area
ESC_BUTTON_RATIO = 300 / (768 * 324)              # ~0.12 % of the area


@dataclass(frozen=True)
class DialogReading:
    yellow: float  # share of pixels that look like queue text
    red: float     # share of pixels that look like the "server full" dialog

    @property
    def server_full(self) -> bool:
        return self.red > RED_FULL_RATIO

    @property
    def in_queue(self) -> bool:
        return self.yellow > YELLOW_QUEUE_RATIO


def _channels(bgra: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return bgra[..., 2], bgra[..., 1], bgra[..., 0]


def analyze_dialog(bgra: np.ndarray) -> DialogReading:
    """Classify a BGRA screenshot of DIALOG_REGION."""
    area = bgra.shape[0] * bgra.shape[1]
    if area == 0:
        return DialogReading(0.0, 0.0)
    r, g, b = _channels(bgra)
    warm = (r > 180) & (b < 80)  # shared part of both masks, computed once
    yellow = np.count_nonzero(warm & (g > 130))
    red = np.count_nonzero(warm & (g < 80))
    return DialogReading(float(yellow) / area, float(red) / area)


def find_esc_button(bgra: np.ndarray) -> tuple[int, int] | None:
    """Return the ESC button centre inside an ESC_REGION screenshot, if visible."""
    area = bgra.shape[0] * bgra.shape[1]
    if area == 0:
        return None
    r, g, b = _channels(bgra)
    mask = (r > 200) & (g > 160) & (g < 230) & (b < 90)
    if np.count_nonzero(mask) / area < ESC_BUTTON_RATIO:
        return None
    ys, xs = np.nonzero(mask)
    return int(xs.mean()), int(ys.mean())

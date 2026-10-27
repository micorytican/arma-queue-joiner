"""Screen capture for the monitor the game is on."""

from __future__ import annotations

import mss
import numpy as np

from .detection import DIALOG_REGION, ESC_REGION, DialogReading, analyze_dialog, find_esc_button


class ScreenVision:
    """Grabs only the two small regions the joiner needs.

    mss keeps per-thread GDI handles, so create and use this object on the
    worker thread (it is a context manager).
    """

    def __init__(self, x: int, y: int):
        self._point = (x, y)
        self._sct: mss.base.MSSBase | None = None
        self.monitor: dict = {}

    def __enter__(self) -> ScreenVision:
        self._sct = mss.mss()
        self.monitor = self._monitor_at(*self._point)
        return self

    def __exit__(self, *exc) -> None:
        if self._sct is not None:
            self._sct.close()
            self._sct = None

    def _monitor_at(self, x: int, y: int) -> dict:
        monitors = self._sct.monitors[1:]
        for mon in monitors:
            if mon["left"] <= x < mon["left"] + mon["width"] and mon["top"] <= y < mon["top"] + mon["height"]:
                return mon
        return monitors[0]

    def _grab(self, rect: dict) -> np.ndarray:
        shot = self._sct.grab(rect)
        return np.frombuffer(shot.raw, dtype=np.uint8).reshape(shot.height, shot.width, 4)

    def read_dialog(self) -> DialogReading:
        return analyze_dialog(self._grab(DIALOG_REGION.to_rect(self.monitor)))

    def find_esc(self) -> tuple[int, int] | None:
        rect = ESC_REGION.to_rect(self.monitor)
        found = find_esc_button(self._grab(rect))
        if found is None:
            return None
        return rect["left"] + found[0], rect["top"] + found[1]

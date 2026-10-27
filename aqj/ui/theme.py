"""Windows 11 look: follows the system light/dark mode and the user's accent colour.

The app is a Windows utility, so the platform is the design system. Colours
are the WinUI 3 / Fluent values used by Settings and PowerToys; the accent
comes from Windows, so every user sees their own colour.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette

TEXT_FONT = "Segoe UI Variable Text"
DISPLAY_FONT = "Segoe UI Variable Display"
ICON_FONTS = ["Segoe Fluent Icons", "Segoe MDL2 Assets"]


class Glyph:
    """Segoe Fluent Icons code points (same as Segoe MDL2 Assets on Windows 10)."""

    SETTINGS = ""
    BACK = ""
    READY = ""       # play
    SYNC = ""
    PAUSE = ""
    DONE = ""        # completed
    ERROR = ""
    TIMER = ""       # stopwatch
    KEYBOARD = ""
    GAME = ""
    MOUSE = ""
    CLOSE = ""
    VOLUME = ""
    PHONE = ""
    PIN = ""
    MINIMIZE = ""
    INFO = ""
    CHEVRON_DOWN = ""
    CHEVRON_UP = ""
    LINK = ""        # open in new window
    HISTORY = ""


@dataclass(frozen=True)
class Colors:
    dark: bool
    background: QColor
    card: QColor
    card_hover: QColor
    stroke: QColor
    divider: QColor
    text: QColor
    text_secondary: QColor
    text_tertiary: QColor
    accent: QColor
    on_accent: QColor
    success: QColor
    caution: QColor
    critical: QColor
    control_stroke: QColor


def is_dark() -> bool:
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def colors() -> Colors:
    accent = QGuiApplication.palette().color(QPalette.Accent)
    if is_dark():
        return Colors(
            dark=True,
            background=QColor("#202020"),
            card=QColor("#2b2b2b"),
            card_hover=QColor("#323232"),
            stroke=QColor("#1d1d1d"),
            divider=QColor("#3a3a3a"),
            text=QColor("#ffffff"),
            text_secondary=QColor("#c5c5c5"),
            text_tertiary=QColor("#9e9e9e"),
            accent=accent,
            on_accent=QColor("#000000"),
            success=QColor("#6ccb5f"),
            caution=QColor("#fce100"),
            critical=QColor("#ff99a4"),
            control_stroke=QColor("#9e9e9e"),
        )
    return Colors(
        dark=False,
        background=QColor("#f3f3f3"),
        card=QColor("#fbfbfb"),
        card_hover=QColor("#f6f6f6"),
        stroke=QColor("#e5e5e5"),
        divider=QColor("#eaeaea"),
        text=QColor("#1b1b1b"),
        text_secondary=QColor("#5d5d5d"),
        text_tertiary=QColor("#8a8a8a"),
        accent=accent,
        on_accent=QColor("#ffffff"),
        success=QColor("#0f7b0f"),
        caution=QColor("#9d5d00"),
        critical=QColor("#c42b1c"),
        control_stroke=QColor("#8a8a8a"),
    )


def font(size: int, weight: QFont.Weight = QFont.Normal, display: bool = False) -> QFont:
    f = QFont(DISPLAY_FONT if display else TEXT_FONT)
    f.setPixelSize(size)
    f.setWeight(weight)
    return f


def icon_font(size: int) -> QFont:
    f = QFont()
    f.setFamilies(ICON_FONTS)
    f.setPixelSize(size)
    return f


def stylesheet(c: Colors) -> str:
    """Only the few things the native style does not cover. Everything else is native."""
    accent = c.accent.name()
    accent_hover = c.accent.lighter(110 if c.dark else 112).name()
    accent_pressed = c.accent.darker(115).name()
    return f"""
    QMainWindow, #page {{ background: {c.background.name()}; }}
    QLabel {{ color: {c.text.name()}; }}
    QLabel[role="secondary"] {{ color: {c.text_secondary.name()}; }}
    QLabel[role="tertiary"] {{ color: {c.text_tertiary.name()}; }}
    QPushButton[accent="true"] {{
        background: {accent};
        color: {c.on_accent.name()};
        border: 1px solid {accent};
        border-radius: 4px;
        padding: 6px 20px;
        min-height: 20px;
        font-weight: 600;
    }}
    QPushButton[accent="true"]:hover {{ background: {accent_hover}; border-color: {accent_hover}; }}
    QPushButton[accent="true"]:pressed {{ background: {accent_pressed}; border-color: {accent_pressed}; }}
    QPushButton[accent="true"]:focus {{ border: 2px solid {c.text.name()}; }}
    QToolButton[flat="true"] {{
        background: transparent; border: none; border-radius: 4px; padding: 6px;
        color: {c.text.name()};
    }}
    QToolButton[flat="true"]:hover {{ background: {c.card_hover.name()}; }}
    QPlainTextEdit#activity {{
        background: transparent; border: none;
        color: {c.text.name()};
    }}
    """

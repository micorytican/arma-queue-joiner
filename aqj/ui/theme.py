"""Colours, fonts and the Qt style sheet.

Look: a field instrument that sits next to Arma Reforger's own UI. Olive-black
surfaces, hairline borders, warm off-white text and a single amber accent
taken from the game's queue text. No gradients, no glow, small radii.
"""

from pathlib import Path

BG = "#121412"
SURFACE = "#181B18"
RAISED = "#1F231F"
BORDER = "#2A2F2A"
BORDER_STRONG = "#3B423B"
TEXT = "#E7E5DD"
MUTED = "#A0A69C"
DIM = "#7F877C"
ACCENT = "#E2A43B"
ACCENT_HOVER = "#EDB55A"
ACCENT_PRESSED = "#C98F2E"
ON_ACCENT = "#17150F"
SUCCESS = "#8DC667"
DANGER = "#E06A5E"
STEEL = "#93ACBF"

FONT = "Segoe UI Variable Text, Segoe UI"
MONO = "Cascadia Mono, Consolas"

STATE_COLORS = {
    "idle": DIM,
    "countdown": ACCENT,
    "running": ACCENT,
    "paused": STEEL,
    "success": SUCCESS,
    "error": DANGER,
}

def stylesheet() -> str:
    """Qt style sheet; built at runtime so image paths work when frozen."""
    chevron = (Path(__file__).parent / "assets" / "chevron-down.svg").as_posix()
    return f"""
* {{
    font-family: "Segoe UI Variable Text", "Segoe UI";
    font-size: 13px;
    color: {TEXT};
    outline: none;
}}
QMainWindow, #root {{ background: {BG}; }}

QLabel#overline {{
    color: {DIM};
    font-size: 10px;
    font-weight: 600;
}}
QLabel#appTitle {{ font-size: 17px; font-weight: 600; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#hint {{ color: {DIM}; font-size: 12px; }}
QLabel#stepNo {{ color: {ACCENT}; font-family: "Cascadia Mono", Consolas; font-size: 12px; }}
QLabel#keycap {{
    font-family: "Cascadia Mono", Consolas;
    font-size: 11px;
    color: {TEXT};
    background: {RAISED};
    border: 1px solid {BORDER_STRONG};
    border-bottom-width: 2px;
    border-radius: 3px;
    padding: 0px 5px;
}}

QPushButton#nav {{
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: {MUTED};
    padding: 6px 2px 5px 2px;
    font-weight: 600;
}}
QPushButton#nav:hover {{ color: {TEXT}; }}
QPushButton#nav:checked {{ color: {TEXT}; border-bottom-color: {ACCENT}; }}

QFrame#card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}
QFrame#rule {{ background: {BORDER}; max-height: 1px; min-height: 1px; border: none; }}

QLabel#stateTitle {{ font-size: 24px; font-weight: 600; }}
QLabel#timer {{ font-family: "Cascadia Mono", Consolas; font-size: 28px; }}
QLabel#statNumber {{ font-family: "Cascadia Mono", Consolas; font-size: 13px; color: {MUTED}; }}

QPushButton {{
    background: {RAISED};
    border: 1px solid {BORDER_STRONG};
    border-radius: 4px;
    padding: 7px 14px;
    font-weight: 600;
}}
QPushButton:hover {{ border-color: {DIM}; }}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton:focus {{ border-color: {ACCENT}; }}
QPushButton#primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: {ON_ACCENT};
    font-size: 14px;
    padding: 10px 14px;
}}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton#primary:pressed {{ background: {ACCENT_PRESSED}; }}
QPushButton#primary[mode="stop"] {{
    background: {RAISED};
    border-color: {BORDER_STRONG};
    color: {TEXT};
}}
QPushButton#primary[mode="stop"]:hover {{ border-color: {DANGER}; color: {DANGER}; }}
QPushButton#link {{
    background: transparent;
    border: none;
    color: {MUTED};
    padding: 0;
    font-weight: 400;
    font-size: 12px;
}}
QPushButton#link:hover {{ color: {ACCENT}; }}

QPlainTextEdit#log {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 8px;
    font-family: "Cascadia Mono", Consolas;
    font-size: 11px;
    color: {MUTED};
    selection-background-color: {BORDER_STRONG};
}}

QComboBox, QDoubleSpinBox, QLineEdit {{
    background: {RAISED};
    border: 1px solid {BORDER_STRONG};
    border-radius: 4px;
    padding: 5px 8px;
    min-height: 18px;
    selection-background-color: {ACCENT};
    selection-color: {ON_ACCENT};
}}
QComboBox:hover, QDoubleSpinBox:hover, QLineEdit:hover {{ border-color: {DIM}; }}
QComboBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {{ border-color: {ACCENT}; }}
QLineEdit:disabled {{ color: {DIM}; border-color: {BORDER}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox::down-arrow {{ image: url("{chevron}"); width: 10px; height: 6px; margin-right: 8px; }}
QComboBox QAbstractItemView {{
    background: {RAISED};
    border: 1px solid {BORDER_STRONG};
    selection-background-color: {BORDER_STRONG};
    selection-color: {TEXT};
    padding: 2px;
}}
QDoubleSpinBox {{ font-family: "Cascadia Mono", Consolas; }}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0; border: none; }}
QDoubleSpinBox QLineEdit {{
    background: transparent; border: none; padding: 0; min-height: 0; margin: 0;
}}

QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER_STRONG}; border-radius: 2px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {DIM}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    background: none; height: 0;
}}

QToolTip {{
    background: {RAISED};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    padding: 4px 6px;
}}
QMenu {{
    background: {RAISED};
    border: 1px solid {BORDER_STRONG};
    padding: 4px;
}}
QMenu::item {{ padding: 6px 18px; border-radius: 3px; }}
QMenu::item:selected {{ background: {BORDER_STRONG}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 6px; }}
"""

"""Fluent-style building blocks: settings cards, toggle switch, expander, glyphs.

Custom-painted widgets read the current colours on every paint, so they follow
a light/dark switch in Windows without extra code.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Property, Signal
from PySide6.QtGui import QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .theme import Glyph


def label(text: str, size: int = 14, role: str = "", weight=None, display: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(theme.font(size, weight or QFont.Normal, display))
    if role:
        lbl.setProperty("role", role)
    return lbl


class GlyphIcon(QWidget):
    """One Segoe Fluent Icons glyph, coloured by a theme role."""

    def __init__(self, glyph: str, size: int = 20, role: str = "text", parent: QWidget | None = None):
        super().__init__(parent)
        self._glyph = glyph
        self._size = size
        self._role = role
        self.setFixedSize(size + 4, size + 4)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_glyph(self, glyph: str, role: str | None = None) -> None:
        self._glyph = glyph
        if role:
            self._role = role
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setFont(theme.icon_font(self._size))
        p.setPen(getattr(theme.colors(), self._role))
        p.drawText(self.rect(), Qt.AlignCenter, self._glyph)


class Card(QFrame):
    """Filled, hairline-bordered surface with a 4 px radius (WinUI control radius)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, False)

    def paintEvent(self, _event) -> None:  # noqa: N802
        c = theme.colors()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(c.stroke, 1))
        p.setBrush(c.card)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)


class SettingsCard(Card):
    """Icon, title, description on the left; a control on the right (Windows Settings pattern)."""

    def __init__(self, glyph: str, title: str, description: str = "", control: QWidget | None = None):
        super().__init__()
        self.setMinimumHeight(68)
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 10, 16, 10)
        row.setSpacing(16)
        row.addWidget(GlyphIcon(glyph, 20), 0, Qt.AlignVCenter)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addStretch(1)
        self.title = label(title, 14)
        texts.addWidget(self.title)
        self.description = label(description, 12, "secondary")
        self.description.setWordWrap(True)
        self.description.setVisible(bool(description))
        texts.addWidget(self.description)
        texts.addStretch(1)
        row.addLayout(texts, 1)
        if control is not None:
            row.addWidget(control, 0, Qt.AlignVCenter)
        self.control = control


class ToggleSwitch(QAbstractButton):
    """WinUI ToggleSwitch: 'On'/'Off' text, then a 40x20 pill."""

    W, H = 40, 20

    def __init__(self, checked: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self._pos = 1.0 if checked else 0.0
        super().setChecked(checked)
        self._hover = False
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def _get(self) -> float:
        return self._pos

    def _set(self, v: float) -> None:
        self._pos = v
        self.update()

    knob = Property(float, _get, _set)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def sizeHint(self) -> QSize:
        return QSize(84, 32)

    def enterEvent(self, e) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _event) -> None:  # noqa: N802
        c = theme.colors()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        enabled = self.isEnabled()

        p.setFont(theme.font(14))
        p.setPen(c.text if enabled else c.text_tertiary)
        text_rect = QRectF(0, 0, self.width() - self.W - 12, self.height())
        p.drawText(text_rect, Qt.AlignRight | Qt.AlignVCenter, "On" if on else "Off")

        x = self.width() - self.W
        y = (self.height() - self.H) / 2
        track = QRectF(x + 0.5, y + 0.5, self.W - 1, self.H - 1)
        if on and enabled:
            p.setPen(Qt.NoPen)
            p.setBrush(c.accent)
        else:
            p.setPen(QPen(c.control_stroke if enabled else c.divider, 1))
            p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(track, self.H / 2, self.H / 2)

        d = 14 if self._hover and enabled else 12
        travel = self.W - 8 - 12
        cx = x + 4 + 6 + travel * self._pos
        cy = y + self.H / 2
        p.setPen(Qt.NoPen)
        p.setBrush(c.on_accent if on and enabled else (c.text_secondary if enabled else c.divider))
        p.drawEllipse(QRectF(cx - d / 2, cy - d / 2, d, d))

        if self.hasFocus():
            p.setPen(QPen(c.text, 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(x - 3, y - 3, self.W + 6, self.H + 6), self.H / 2 + 3, self.H / 2 + 3)


class ExpanderCard(QWidget):
    """A settings card that opens to reveal more rows."""

    toggled = Signal(bool)

    def __init__(self, glyph: str, title: str, description: str):
        super().__init__()
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)
        self._chevron = GlyphIcon(Glyph.CHEVRON_DOWN, 12, "text_secondary")
        self.header = _ClickableCard(glyph, title, description, self._chevron)
        self.header.clicked.connect(self.toggle)
        col.addWidget(self.header)
        self.body = Card()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(56, 8, 16, 8)
        self.body_layout.setSpacing(0)
        self.body.hide()
        col.addWidget(self.body)

    def add_row(self, text: str, control: QWidget) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 6, 0, 6)
        row.addWidget(label(text, 14), 1)
        row.addWidget(control)
        self.body_layout.addLayout(row)

    def toggle(self) -> None:
        opened = not self.body.isVisible()
        self.body.setVisible(opened)
        self._chevron.set_glyph(Glyph.CHEVRON_UP if opened else Glyph.CHEVRON_DOWN)
        self.toggled.emit(opened)


class _ClickableCard(SettingsCard):
    clicked = Signal()

    def __init__(self, glyph: str, title: str, description: str, control: QWidget):
        super().__init__(glyph, title, description, control)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self._hover = False

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if e.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.clicked.emit()
        else:
            super().keyPressEvent(e)

    def enterEvent(self, e) -> None:  # noqa: N802
        self._hover = True
        self.update()

    def leaveEvent(self, e) -> None:  # noqa: N802
        self._hover = False
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        c = theme.colors()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(c.text if self.hasFocus() else c.stroke, 1))
        p.setBrush(c.card_hover if self._hover else c.card)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)

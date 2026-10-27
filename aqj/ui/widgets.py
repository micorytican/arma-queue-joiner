"""Fluent-style building blocks: settings cards, toggle switch, expander, meter, glyphs.

Custom-painted widgets read the current colours on every paint, so they follow
a light/dark switch in Windows without extra code.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QEnterEvent, QFont, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .theme import Glyph

ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
ALIGN_VCENTER = Qt.AlignmentFlag.AlignVCenter
POINTING = Qt.CursorShape.PointingHandCursor


def label(
    text: str = "",
    size: int = 14,
    role: str = "",
    weight: QFont.Weight = QFont.Weight.Normal,
    display: bool = False,
    wrap: bool = False,
) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(theme.font(size, weight, display))
    lbl.setWordWrap(wrap)
    if role:
        lbl.setProperty("role", role)
    return lbl


def icon_button(glyph: str, tip: str, slot: Callable[[], object]) -> QToolButton:
    btn = QToolButton()
    btn.setProperty("flat", True)
    btn.setText(glyph)
    btn.setFont(theme.icon_font(16))
    btn.setToolTip(tip)
    btn.setAccessibleName(tip)
    btn.setCursor(POINTING)
    btn.setFixedSize(36, 36)
    btn.clicked.connect(slot)
    return btn


class GlyphIcon(QWidget):
    """One Segoe Fluent Icons glyph, coloured by a theme role."""

    def __init__(self, glyph: str, size: int = 20, role: str = "text", parent: QWidget | None = None):
        super().__init__(parent)
        self._glyph = glyph
        self._size = size
        self._role = role
        self.setFixedSize(size + 4, size + 4)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_glyph(self, glyph: str, role: str | None = None) -> None:
        self._glyph = glyph
        if role:
            self._role = role
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setFont(theme.icon_font(self._size))
        p.setPen(getattr(theme.colors(), self._role))
        p.drawText(self.rect(), ALIGN_CENTER, self._glyph)


def _paint_card(widget: QWidget, hover: bool = False, focus: bool = False) -> None:
    c = theme.colors()
    p = QPainter(widget)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(c.text if focus else c.stroke, 1))
    p.setBrush(c.card_hover if hover else c.card)
    p.drawRoundedRect(QRectF(widget.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)


class Card(QFrame):
    """Filled, hairline-bordered surface with a 4 px radius (WinUI control radius)."""

    def paintEvent(self, event: QPaintEvent) -> None:
        _paint_card(self)


class SettingsCard(Card):
    """Icon, title, description on the left; a control on the right (Windows Settings pattern)."""

    def __init__(self, glyph: str, title: str, description: str = "", control: QWidget | None = None):
        super().__init__()
        self.setMinimumHeight(68)
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 10, 16, 10)
        row.setSpacing(16)
        self.icon = GlyphIcon(glyph, 20)
        row.addWidget(self.icon, 0, ALIGN_VCENTER)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addStretch(1)
        self.title = label(title, 14, wrap=True)
        texts.addWidget(self.title)
        self.description = label(description, 12, "secondary", wrap=True)
        self.description.setVisible(bool(description))
        texts.addWidget(self.description)
        texts.addStretch(1)
        row.addLayout(texts, 1)
        if control is not None:
            row.addWidget(control, 0, ALIGN_VCENTER)
            control.setAccessibleName(title)
            if description:
                control.setAccessibleDescription(description)
        self.control = control

    def set_description(self, text: str) -> None:
        self.description.setText(text)
        self.description.setVisible(bool(text))


class ToggleSwitch(QAbstractButton):
    """WinUI ToggleSwitch: 'On'/'Off' text, then a 40x20 pill."""

    W, H = 40, 20

    def __init__(
        self, checked: bool = False, on_text: str = "On", off_text: str = "Off", parent: QWidget | None = None
    ):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(POINTING)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._texts = (off_text, on_text)
        self._pos = 1.0 if checked else 0.0
        super().setChecked(checked)
        self._hover = False
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

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
        return QSize(96, 32)

    def enterEvent(self, event: QEnterEvent) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        c = theme.colors()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        enabled = self.isEnabled()

        p.setFont(theme.font(14))
        p.setPen(c.text if enabled else c.text_tertiary)
        text_rect = QRectF(0, 0, self.width() - self.W - 12, self.height())
        p.drawText(text_rect, Qt.AlignmentFlag.AlignRight | ALIGN_VCENTER, self._texts[int(on)])

        x = self.width() - self.W
        y = (self.height() - self.H) / 2
        track = QRectF(x + 0.5, y + 0.5, self.W - 1, self.H - 1)
        if on and enabled:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c.accent)
        else:
            p.setPen(QPen(c.control_stroke if enabled else c.divider, 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(track, self.H / 2, self.H / 2)

        d = 14 if self._hover and enabled else 12
        travel = self.W - 8 - 12
        cx = x + 4 + 6 + travel * self._pos
        cy = y + self.H / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c.on_accent if on and enabled else (c.text_secondary if enabled else c.divider))
        p.drawEllipse(QRectF(cx - d / 2, cy - d / 2, d, d))

        if self.hasFocus():
            p.setPen(QPen(c.text, 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(x - 3, y - 3, self.W + 6, self.H + 6), self.H / 2 + 3, self.H / 2 + 3)


class ClickableCard(SettingsCard):
    """A settings card that acts as a button (keyboard and mouse)."""

    clicked = Signal()

    def __init__(self, glyph: str, title: str, description: str, trailing: QWidget):
        super().__init__(glyph, title, description, trailing)
        self.setCursor(POINTING)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(title)
        self._hover = False

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)

    def enterEvent(self, event: QEnterEvent) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event: QEvent) -> None:
        self._hover = False
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        _paint_card(self, self._hover, self.hasFocus())


class ExpanderCard(QWidget):
    """A settings card that opens to reveal more rows."""

    def __init__(self, glyph: str, title: str, description: str):
        super().__init__()
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)
        self._chevron = GlyphIcon(Glyph.CHEVRON_DOWN, 12, "text_secondary")
        self.header = ClickableCard(glyph, title, description, self._chevron)
        self.header.setAccessibleDescription(description)
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
        row.addWidget(label(text, 14, wrap=True), 1)
        row.addWidget(control)
        control.setAccessibleName(text)
        self.body_layout.addLayout(row)

    def toggle(self) -> None:
        opened = not self.body.isVisible()
        self.body.setVisible(opened)
        self._chevron.set_glyph(Glyph.CHEVRON_UP if opened else Glyph.CHEVRON_DOWN)


class Meter(QWidget):
    """A thin bar for a share of pixels, with a tick at the detection threshold."""

    def __init__(self, threshold: float, scale: float):
        super().__init__()
        self._value = 0.0
        self._threshold = threshold
        self._scale = scale  # value that fills the bar
        self.setFixedHeight(6)
        self.setMinimumWidth(120)

    def set_value(self, value: float) -> None:
        self._value = value
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        c = theme.colors()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c.divider)
        p.drawRoundedRect(r, 3, 3)
        frac = max(0.0, min(1.0, self._value / self._scale))
        if frac > 0:
            p.setBrush(c.accent if self._value > self._threshold else c.text_tertiary)
            p.drawRoundedRect(QRectF(r.x(), r.y(), max(r.height(), r.width() * frac), r.height()), 3, 3)
        tick_x = r.x() + r.width() * min(1.0, self._threshold / self._scale)
        p.setPen(QPen(c.text, 1.5))
        p.drawLine(int(tick_x), 0, int(tick_x), self.height())

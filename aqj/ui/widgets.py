"""Small custom widgets used by the main window."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Property
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from . import theme


def overline(text: str) -> QLabel:
    """Small spaced caps label used for section headers."""
    label = QLabel(text.upper())
    label.setObjectName("overline")
    font = label.font()
    font.setPixelSize(10)
    font.setWeight(QFont.DemiBold)
    font.setLetterSpacing(QFont.AbsoluteSpacing, 1.6)
    label.setFont(font)
    return label


def rule() -> QFrame:
    line = QFrame()
    line.setObjectName("rule")
    return line


class KeyCap(QLabel):
    def __init__(self, key: str = ""):
        super().__init__(key)
        self.setObjectName("keycap")
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)


class SwitchRow(QAbstractButton):
    """A full-width row: title, optional hint, and a switch on the right.

    The whole row is the hit target, which is friendlier than a tiny checkbox.
    """

    TRACK_W, TRACK_H = 32, 18

    def __init__(self, title: str, hint: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(title)
        self._title = title
        self._hint = hint
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _get_knob(self) -> float:
        return self._pos

    def _set_knob(self, value: float) -> None:
        self._pos = value
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def setChecked(self, checked: bool) -> None:  # noqa: N802 (Qt naming)
        super().setChecked(checked)
        self._anim.stop()
        self._pos = 1.0 if checked else 0.0
        self.update()

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def sizeHint(self) -> QSize:
        return QSize(300, 50 if self._hint else 34)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        enabled = self.isEnabled()

        title_font = QFont(self.font())
        title_font.setPixelSize(13)
        hint_font = QFont(self.font())
        hint_font.setPixelSize(12)

        text_w = rect.width() - self.TRACK_W - 16
        p.setFont(title_font)
        p.setPen(QColor(theme.TEXT if enabled else theme.DIM))
        if self._hint:
            p.drawText(QRectF(0, 6, text_w, 18), Qt.AlignLeft | Qt.AlignVCenter, self._title)
            p.setFont(hint_font)
            p.setPen(QColor(theme.DIM))
            p.drawText(QRectF(0, 25, text_w, 18), Qt.AlignLeft | Qt.AlignVCenter, self._hint)
        else:
            p.drawText(QRectF(0, 0, text_w, rect.height()), Qt.AlignLeft | Qt.AlignVCenter, self._title)

        x = rect.width() - self.TRACK_W - 2
        y = (rect.height() - self.TRACK_H) / 2
        track = QRectF(x, y, self.TRACK_W, self.TRACK_H)
        off, on = QColor(theme.RAISED), QColor(theme.ACCENT)
        t = self._pos
        fill = QColor(
            int(off.red() + (on.red() - off.red()) * t),
            int(off.green() + (on.green() - off.green()) * t),
            int(off.blue() + (on.blue() - off.blue()) * t),
        )
        if not enabled:
            fill = QColor(theme.SURFACE)
        border = QColor(theme.ACCENT if self.hasFocus() else (theme.BORDER_STRONG if t < 0.5 else theme.ACCENT))
        p.setPen(QPen(border, 1))
        p.setBrush(fill)
        p.drawRoundedRect(track.adjusted(0.5, 0.5, -0.5, -0.5), self.TRACK_H / 2, self.TRACK_H / 2)

        knob_d = self.TRACK_H - 6
        kx = x + 3 + (self.TRACK_W - 6 - knob_d) * t
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.ON_ACCENT if t > 0.5 else theme.MUTED))
        p.drawEllipse(QRectF(kx, y + 3, knob_d, knob_d))


class StatusCard(QFrame):
    """The hero block: state, what is happening, timer and attempts."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 16, 0)
        outer.setSpacing(14)

        self._bar = QFrame()
        self._bar.setFixedWidth(3)
        outer.addWidget(self._bar)

        left = QVBoxLayout()
        left.setContentsMargins(0, 14, 0, 14)
        left.setSpacing(2)
        left.addWidget(overline("Status"))
        self.title = QLabel("Ready")
        self.title.setObjectName("stateTitle")
        left.addWidget(self.title)
        self.detail = QLabel("")
        self.detail.setObjectName("muted")
        self.detail.setWordWrap(True)
        left.addWidget(self.detail)
        outer.addLayout(left, 1)

        right = QVBoxLayout()
        right.setContentsMargins(0, 14, 0, 14)
        right.setSpacing(2)
        right.addWidget(overline("Time"), 0, Qt.AlignRight)
        self.timer = QLabel("00:00")
        self.timer.setObjectName("timer")
        self.timer.setAlignment(Qt.AlignRight)
        right.addWidget(self.timer)
        self.attempts = QLabel("0 attempts")
        self.attempts.setObjectName("statNumber")
        self.attempts.setAlignment(Qt.AlignRight)
        right.addWidget(self.attempts)
        outer.addLayout(right)

        self.set_state("idle", "Ready", "")

    def set_state(self, key: str, title: str, detail: str) -> None:
        color = theme.STATE_COLORS.get(key, theme.DIM)
        self._bar.setStyleSheet(f"background: {color}; border: none;")
        self.title.setText(title)
        self.title.setStyleSheet(f"color: {color if key in ('success', 'error') else theme.TEXT};")
        self.detail.setText(detail)
        self.setAccessibleName(f"{title}. {detail}")

    def set_attempts(self, n: int) -> None:
        self.attempts.setText(f"{n} attempt" + ("" if n == 1 else "s"))

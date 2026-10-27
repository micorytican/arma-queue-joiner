"""lime98 intro: a 1980s air-defence radar scope picks up a Su-27.

Everything is drawn with QPainter from a single function of time, so the
same code renders the startup splash live and the README GIF frame by frame.
Look: dim P7-style green phosphor on black glass, DIN lettering (Bahnschrift),
no neon. One scene, about three seconds.
"""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QFont,
    QFontMetricsF,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import QApplication, QWidget

# Palette: phosphor on glass
PANEL = QColor("#0a0c0b")
GLASS = QColor("#03110a")
PHOSPHOR = QColor("#8cff9e")
PHOSPHOR_DIM = QColor("#2f8a4b")
GRID = QColor(76, 170, 104, 70)
TEXT_DIM = QColor("#4f9d68")

DURATION = 3.2  # intro length in seconds
SWEEP_START = 0.30  # beam starts moving
SWEEP_PERIOD = 1.10  # seconds per turn
TARGET_BEARING = 45.0  # degrees, clockwise from north
TARGET_RANGE = 0.62  # share of the scope radius
PERSISTENCE = 0.85  # phosphor decay time constant, seconds

READOUT = ("CONTACT  BRG 045  RNG 38", "TYPE     SU-27", "IFF      FRIENDLY")
CALLSIGN = "LIME98"

DISPLAY_FONT = "Bahnschrift"
MONO_FONT = "Consolas"


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _ease_out(x: float) -> float:
    x = _clamp(x)
    return 1 - (1 - x) ** 3


def _with_alpha(color: QColor, alpha: float) -> QColor:
    c = QColor(color)
    c.setAlphaF(_clamp(alpha) * color.alphaF())
    return c


def beam_bearing(t: float) -> float:
    return (t - SWEEP_START) * 360.0 / SWEEP_PERIOD


def pass_time(k: int) -> float:
    """When the beam crosses the target for the k-th time (k = 0, 1, ...)."""
    return SWEEP_START + (TARGET_BEARING + 360.0 * k) * SWEEP_PERIOD / 360.0


def su27_path() -> QPainterPath:
    """Top view of a Su-27, nose up, length 1.0 centred on the origin.

    Right half traced from the nose, then mirrored: long pointed nose, the big
    leading-edge root extensions, cropped delta wings with tip rails, wide-set
    engines, tailplanes and the tail 'stinger' between the nozzles.
    """

    def quad(p0, c, p1, steps=10):
        return [
            (
                (1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * c[0] + u * u * p1[0],
                (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * c[1] + u * u * p1[1],
            )
            for u in (i / steps for i in range(1, steps + 1))
        ]

    right = [(0.000, -0.500)]
    right += quad((0.000, -0.500), (0.020, -0.450), (0.028, -0.360))  # nose
    right += [(0.034, -0.280)]  # canopy
    right += quad((0.034, -0.280), (0.048, -0.110), (0.118, -0.030), 14)  # ogival LERX
    right += [
        (0.330, 0.155),
        (0.338, 0.155),
        (0.338, 0.245),
        (0.326, 0.245),  # wing and tip rail
        (0.124, 0.215),
        (0.120, 0.300),  # trailing edge, tail boom
        (0.236, 0.392),
        (0.238, 0.448),
        (0.120, 0.442),  # tailplane
        (0.112, 0.468),
        (0.050, 0.470),
        (0.044, 0.445),  # nozzle
        (0.022, 0.445),
        (0.014, 0.560),
        (0.000, 0.570),  # tail stinger
    ]
    path = QPainterPath(QPointF(*right[0]))
    for x, y in right[1:]:
        path.lineTo(x, y)
    for x, y in reversed(right[:-1]):
        path.lineTo(-x, y)
    path.closeSubpath()
    return path


def su27_tails() -> list[tuple[QPointF, QPointF]]:
    """The twin vertical fins, seen from above as short canted lines."""
    return [(QPointF(s * 0.124, 0.235), QPointF(s * 0.136, 0.430)) for s in (1, -1)]


class RadarIntro:
    """Draws the intro at any size; call paint() with the time in seconds."""

    def __init__(self, seed: int = 98):
        rng = random.Random(seed)
        self._grain = [(rng.uniform(-1, 1), rng.uniform(-1, 1), rng.random()) for _ in range(420)]
        self._plane = su27_path()
        self._tails = su27_tails()

    # Scene ------------------------------------------------------------------

    def paint(self, p: QPainter, w: int, h: int, t: float, frame: int = 0) -> None:
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.fillRect(QRectF(0, 0, w, h), PANEL)

        r = h * 0.42
        c = QPointF(h * 0.5, h * 0.5)
        power = _ease_out(t / 0.35)
        flicker = 1.0 if t > 0.35 else (0.55 + 0.45 * ((frame % 3) != 1))

        self._bezel(p, c, r, power)
        p.save()
        clip = QPainterPath()
        clip.addEllipse(c, r, r)
        p.setClipPath(clip)
        self._glass(p, c, r)
        self._grid(p, c, r, power * flicker)
        if t >= SWEEP_START:
            self._sweep(p, c, r, t)
        self._target(p, c, r, t)
        self._grain_layer(p, c, r, frame)
        p.restore()
        self._glass_highlight(p, c, r)

        self._readout(p, w, h, t)
        self._callsign(p, w, h, t, frame)

    # Scope --------------------------------------------------------------------

    def _bezel(self, p: QPainter, c: QPointF, r: float, power: float) -> None:
        ring = QRadialGradient(c, r * 1.12)
        ring.setColorAt(0.86, QColor("#1b1f1d"))
        ring.setColorAt(0.93, QColor("#2a2f2c"))
        ring.setColorAt(1.0, QColor("#0d100e"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(ring))
        p.drawEllipse(c, r * 1.1, r * 1.1)

        # Engraved azimuth marks every 10 degrees, numbers every 30
        p.setFont(self._mono(r * 0.075))
        fm = QFontMetricsF(p.font())
        for deg in range(0, 360, 10):
            a = math.radians(deg)
            inner = r * (1.015 if deg % 30 else 1.0)
            outer = r * 1.045
            p.setPen(QPen(_with_alpha(TEXT_DIM, 0.35 + 0.65 * power), 1.0))
            p.drawLine(
                QPointF(c.x() + inner * math.sin(a), c.y() - inner * math.cos(a)),
                QPointF(c.x() + outer * math.sin(a), c.y() - outer * math.cos(a)),
            )
            if deg % 30 == 0:
                label = f"{deg // 10:02d}"
                lr = r * 1.075
                pos = QPointF(c.x() + lr * math.sin(a), c.y() - lr * math.cos(a))
                p.drawText(
                    QPointF(pos.x() - fm.horizontalAdvance(label) / 2, pos.y() + fm.ascent() / 2 - 1), label
                )

    def _glass(self, p: QPainter, c: QPointF, r: float) -> None:
        g = QRadialGradient(c, r)
        g.setColorAt(0.0, QColor("#06190e"))
        g.setColorAt(0.75, GLASS)
        g.setColorAt(1.0, QColor("#010604"))
        p.fillRect(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), QBrush(g))

    def _grid(self, p: QPainter, c: QPointF, r: float, power: float) -> None:
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(_with_alpha(GRID, power), 1.0))
        for k in (0.25, 0.5, 0.75):
            p.drawEllipse(c, r * k, r * k)
        p.drawLine(QPointF(c.x() - r, c.y()), QPointF(c.x() + r, c.y()))
        p.drawLine(QPointF(c.x(), c.y() - r), QPointF(c.x(), c.y() + r))
        p.setFont(self._mono(r * 0.06))
        p.setPen(_with_alpha(TEXT_DIM, 0.8 * power))
        for k, nm in ((0.25, "10"), (0.5, "20"), (0.75, "30")):
            p.drawText(QPointF(c.x() + 3, c.y() - r * k - 3), nm)

    def _sweep(self, p: QPainter, c: QPointF, r: float, t: float) -> None:
        bearing = beam_bearing(t)
        qt_angle = 90.0 - bearing  # Qt: counter-clockwise from 3 o'clock
        trail = QConicalGradient(c, qt_angle)
        trail.setColorAt(0.0, _with_alpha(PHOSPHOR, 0.42))
        trail.setColorAt(0.06, _with_alpha(PHOSPHOR, 0.14))
        trail.setColorAt(0.20, _with_alpha(PHOSPHOR, 0.0))
        trail.setColorAt(1.0, _with_alpha(PHOSPHOR, 0.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(trail))
        p.drawEllipse(c, r, r)

        a = math.radians(bearing)
        tip = QPointF(c.x() + r * math.sin(a), c.y() - r * math.cos(a))
        p.setPen(QPen(_with_alpha(PHOSPHOR, 0.35), 4.0))
        p.drawLine(c, tip)
        p.setPen(QPen(PHOSPHOR, 1.4))
        p.drawLine(c, tip)

    # Target -------------------------------------------------------------------

    def _target(self, p: QPainter, c: QPointF, r: float, t: float) -> None:
        t0, t1 = pass_time(0), pass_time(1)
        if t < t0:
            return
        k = int((beam_bearing(t) - TARGET_BEARING) // 360.0)
        glow = math.exp(-(t - pass_time(max(0, k))) / PERSISTENCE)

        # The contact drifts slowly toward the station
        drift = 0.025 * (t - t0)
        rng = TARGET_RANGE - drift
        a = math.radians(TARGET_BEARING)
        pos = QPointF(c.x() + r * rng * math.sin(a), c.y() - r * rng * math.cos(a))

        morph = _ease_out((t - t1) / 0.40) if t >= t1 else 0.0
        if morph < 1.0:  # first returns are a plain blip
            size = r * 0.035 * (1.0 - 0.6 * morph)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_with_alpha(PHOSPHOR, 0.25 * glow * (1 - morph)))
            p.drawEllipse(pos, size * 2.4, size * 2.4)
            p.setBrush(_with_alpha(PHOSPHOR, glow * (1 - morph)))
            p.drawEllipse(pos, size, size)
        if morph > 0.0:
            self._plane_at(p, pos, r * 0.42 * (0.6 + 0.4 * morph), max(0.6, glow) * morph)
            self._brackets(p, pos, r * 0.26, t - t1 - 0.25)

    def _plane_at(self, p: QPainter, pos: QPointF, length: float, alpha: float) -> None:
        heading = TARGET_BEARING + 180.0 + 12.0  # inbound, slightly crossing
        xf = QTransform()
        xf.translate(pos.x(), pos.y())
        xf.rotate(heading)
        xf.scale(length, length)
        body = xf.map(self._plane)
        p.setBrush(_with_alpha(PHOSPHOR, 0.16 * alpha))
        p.setPen(QPen(_with_alpha(PHOSPHOR, 0.35 * alpha), 3.2))
        p.drawPath(body)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(_with_alpha(PHOSPHOR, alpha), 1.1))
        p.drawPath(body)
        for a, b in self._tails:
            p.drawLine(xf.map(a), xf.map(b))

    def _brackets(self, p: QPainter, pos: QPointF, half: float, age: float) -> None:
        if age <= 0:
            return
        grow = _ease_out(age / 0.25)
        arm = half * 0.45 * grow
        p.setPen(QPen(_with_alpha(PHOSPHOR, 0.9 * grow), 1.2))
        for sx in (-1, 1):
            for sy in (-1, 1):
                corner = QPointF(pos.x() + sx * half, pos.y() + sy * half)
                p.drawLine(corner, QPointF(corner.x() - sx * arm, corner.y()))
                p.drawLine(corner, QPointF(corner.x(), corner.y() - sy * arm))

    # Glass texture --------------------------------------------------------------

    def _grain_layer(self, p: QPainter, c: QPointF, r: float, frame: int) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        for i, (x, y, v) in enumerate(self._grain):
            if (i + frame * 7) % 5:
                continue
            p.setBrush(_with_alpha(PHOSPHOR, 0.05 + 0.08 * v))
            p.drawRect(QRectF(c.x() + x * r, c.y() + y * r, 1.2, 1.2))

    def _glass_highlight(self, p: QPainter, c: QPointF, r: float) -> None:
        g = QRadialGradient(QPointF(c.x() - r * 0.35, c.y() - r * 0.45), r * 0.9)
        g.setColorAt(0.0, QColor(255, 255, 255, 18))
        g.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(c, r, r)

    # Text -----------------------------------------------------------------------

    def _readout(self, p: QPainter, w: int, h: int, t: float) -> None:
        start = pass_time(1) + 0.10
        if t < start:
            return
        x = h * 1.02
        p.setFont(self._mono(h * 0.052))
        fm = QFontMetricsF(p.font())
        cps = 85.0  # teletype characters per second
        typed = int((t - start) * cps)
        y = h * 0.22
        for line in READOUT:
            shown = line[: max(0, typed)]
            typed -= len(line) + 3  # short pause between lines
            if shown:
                p.setPen(PHOSPHOR_DIM if len(shown) == len(line) else PHOSPHOR)
                p.drawText(QPointF(x, y), shown)
                if len(shown) < len(line):
                    cursor_x = x + fm.horizontalAdvance(shown) + 2
                    p.fillRect(
                        QRectF(
                            cursor_x, y - fm.ascent() * 0.8, fm.averageCharWidth() * 0.8, fm.ascent() * 0.9
                        ),
                        PHOSPHOR,
                    )
            y += fm.height() * 1.15

    def _callsign(self, p: QPainter, w: int, h: int, t: float, frame: int) -> None:
        start = 2.40
        if t < start:
            return
        x = h * 1.02
        age = t - start
        on = 1.0 if age > 0.18 else (0.25, 1.0, 0.15, 0.9, 0.5, 1.0)[frame % 6]

        p.setFont(self._mono(h * 0.045))
        p.setPen(_with_alpha(TEXT_DIM, on))
        p.drawText(QPointF(x, h * 0.62), "CALLSIGN")

        font = QFont(DISPLAY_FONT)
        font.setPixelSize(int(h * 0.25))
        font.setWeight(QFont.Weight.Bold)
        font.setStretch(QFont.Stretch.Condensed)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, h * 0.012)
        p.setFont(font)
        fm = QFontMetricsF(font)
        baseline = h * 0.62 + fm.ascent() * 0.98
        text_w = fm.horizontalAdvance(CALLSIGN)
        reveal = _ease_out(age / 0.45)

        p.save()
        p.setClipRect(QRectF(x - 4, 0, (text_w + 8) * reveal, h))
        path = QPainterPath()
        path.addText(QPointF(x, baseline), font, CALLSIGN)
        p.setPen(QPen(_with_alpha(PHOSPHOR, 0.22 * on), h * 0.02))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)  # bloom
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_with_alpha(PHOSPHOR, on))
        p.drawPath(path)
        p.restore()

        rule_y = baseline + h * 0.05
        p.setPen(QPen(_with_alpha(PHOSPHOR_DIM, on), 1.2))
        p.drawLine(QPointF(x, rule_y), QPointF(x + text_w * _ease_out((age - 0.2) / 0.5), rule_y))

    @staticmethod
    def _mono(px: float) -> QFont:
        f = QFont(MONO_FONT)
        f.setPixelSize(max(8, int(px)))
        f.setStyleHint(QFont.StyleHint.Monospace)
        return f


class IntroWindow(QWidget):
    """Frameless startup splash. Click or press any key to skip."""

    finished = Signal()
    SIZE = (640, 300)

    def __init__(self) -> None:
        super().__init__(
            None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFixedSize(*self.SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("lime98")
        self.setWindowTitle("lime98 intro")
        self._scene = RadarIntro()
        self._clock = QElapsedTimer()
        self._frame = 0
        self._done = False
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def play(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(geo.center().x() - self.width() // 2, geo.center().y() - self.height() // 2)
        self.show()
        from .. import winapi

        winapi.round_corners(int(self.winId()))
        self._clock.start()
        self._timer.start()

    def _tick(self) -> None:
        self._frame += 1
        t = self._clock.elapsed() / 1000.0
        if t > DURATION + 0.6:
            self.skip()
            return
        if t > DURATION + 0.3:
            self.setWindowOpacity(max(0.0, 1.0 - (t - DURATION - 0.3) / 0.3))
        self.update()

    def skip(self) -> None:
        if self._done:
            return
        self._done = True
        self._timer.stop()
        self.close()
        self.finished.emit()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        self._scene.paint(p, self.width(), self.height(), self._clock.elapsed() / 1000.0, self._frame)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.skip()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        self.skip()

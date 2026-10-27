"""lime98 intro, "Intercept": a radar locks a contact, the contact breaks out of
the scope as a Su-27 that flies over the viewer, and the callsign slams in.

Everything is drawn with QPainter from a single function of time, so the
same code plays the startup splash live and renders the README GIF.
Look: green phosphor scope, DIN lettering (Bahnschrift), one hot accent for
the afterburners. About two seconds of action.
"""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QElapsedTimer, QLineF, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QFont,
    QFontMetricsF,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import QApplication, QWidget

PANEL = QColor("#070908")
GLASS = QColor("#03110a")
PHOSPHOR = QColor("#8cff9e")
PHOSPHOR_DIM = QColor("#2f8a4b")
GRID = QColor(76, 170, 104, 90)
TEXT_DIM = QColor("#4f9d68")
HULL = QColor("#06130b")
BURNER = QColor("#ffb347")
WHITE = QColor("#f4fff6")

# Timeline, seconds
SWEEP_START = 0.08  # beam whips round
SWEEP_PERIOD = 0.62
TARGET_BEARING = 120.0  # degrees clockwise from north, lower right of the scope
TARGET_RANGE = 0.58
BREAKOUT = 0.62  # the contact leaves the scope as a Su-27
FLYBY = 0.55  # seconds from breakout until the jet passes the camera
IMPACT = BREAKOUT + FLYBY  # flash, shake, callsign slams in
DURATION = IMPACT + 1.1  # splash length
PERSISTENCE = 0.5

CALLSIGN = "LIME98"
DISPLAY_FONT = "Bahnschrift"
MONO_FONT = "Consolas"


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _ease_out(x: float) -> float:
    x = _clamp(x)
    return 1 - (1 - x) ** 3


def _ease_in(x: float) -> float:
    return _clamp(x) ** 3


def _with_alpha(color: QColor, alpha: float) -> QColor:
    c = QColor(color)
    c.setAlphaF(_clamp(alpha) * color.alphaF())
    return c


def _lerp(a: QPointF, b: QPointF, u: float) -> QPointF:
    return QPointF(a.x() + (b.x() - a.x()) * u, a.y() + (b.y() - a.y()) * u)


def beam_bearing(t: float) -> float:
    return (t - SWEEP_START) * 360.0 / SWEEP_PERIOD


def pass_time(k: int) -> float:
    """When the beam crosses the target for the k-th time (k = 0, 1, ...)."""
    return SWEEP_START + (TARGET_BEARING + 360.0 * k) * SWEEP_PERIOD / 360.0


LOCK = pass_time(0)  # first return is enough: the scope locks at once


def su27_path() -> QPainterPath:
    """Top view of a Su-27, nose up, length about 1.0 centred on the origin.

    Right half traced from the nose, then mirrored: long pointed nose, the big
    ogival leading-edge root extensions, cropped delta wings with tip rails,
    wide-set engines on tail booms, tailplanes and the 'stinger' between the nozzles.
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
        (0.330, 0.155), (0.338, 0.155), (0.338, 0.245), (0.326, 0.245),  # wing, tip rail
        (0.124, 0.215), (0.120, 0.300),  # trailing edge, tail boom
        (0.236, 0.392), (0.238, 0.448), (0.120, 0.442),  # tailplane
        (0.112, 0.468), (0.050, 0.470), (0.044, 0.445),  # nozzle
        (0.022, 0.445), (0.014, 0.560), (0.000, 0.570),  # tail stinger
    ]  # fmt: skip
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


def su27_panel_lines() -> list[tuple[QPointF, QPointF]]:
    """A few structural lines so the jet reads when it fills the frame."""
    lines = [(QPointF(0, -0.36), QPointF(0, 0.44))]
    for s in (1, -1):
        lines += [
            (QPointF(s * 0.040, -0.06), QPointF(s * 0.070, 0.20)),  # intake
            (QPointF(s * 0.070, 0.20), QPointF(s * 0.078, 0.445)),  # nacelle
            (QPointF(s * 0.140, 0.010), QPointF(s * 0.300, 0.150)),  # leading-edge flap
            (QPointF(s * 0.180, 0.205), QPointF(s * 0.300, 0.220)),  # flaperon
        ]
    return lines


class RadarIntro:
    """Draws the intro at any size; call paint() with the time in seconds."""

    def __init__(self, seed: int = 98):
        rng = random.Random(seed)
        self._grain = [(rng.uniform(-1, 1), rng.uniform(-1, 1), rng.random()) for _ in range(360)]
        self._streaks = [(rng.uniform(-1, 1), rng.uniform(0.3, 1.0), rng.random()) for _ in range(26)]
        self._plane = su27_path()
        self._tails = su27_tails()
        self._panels = su27_panel_lines()

    # Scene ----------------------------------------------------------------------

    def paint(self, p: QPainter, w: int, h: int, t: float, frame: int = 0) -> None:
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.fillRect(QRectF(0, 0, w, h), PANEL)

        p.save()
        p.translate(self._shake(t, h))
        r = h * 0.40
        c = QPointF(h * 0.52, h * 0.5)
        dim = 1.0 - 0.55 * _ease_out((t - BREAKOUT) / 0.3)  # scope steps back once the jet is out

        self._scope(p, c, r, t, frame, dim)
        self._callsign(p, w, h, t)
        if BREAKOUT <= t < IMPACT:
            self._jet_flyby(p, w, h, c, r, t)
        p.restore()

        self._flash(p, w, h, t)

    @staticmethod
    def _shake(t: float, h: float) -> QPointF:
        age = t - IMPACT
        if age < 0 or age > 0.45:
            return QPointF(0, 0)
        amp = h * 0.035 * math.exp(-age / 0.09)
        return QPointF(amp * math.sin(age * 97.0), amp * math.cos(age * 71.0))

    # Scope -------------------------------------------------------------------------

    def _scope(self, p: QPainter, c: QPointF, r: float, t: float, frame: int, dim: float) -> None:
        open_ = _ease_out(t / 0.22)
        rr = r * (0.6 + 0.4 * open_)

        # Bezel: one bold ring with tick marks, no clutter
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(_with_alpha(PHOSPHOR_DIM, dim * open_), r * 0.035))
        p.drawEllipse(c, rr * 1.06, rr * 1.06)
        p.setPen(QPen(_with_alpha(TEXT_DIM, dim * open_), 1.2))
        for deg in range(0, 360, 15):
            a = math.radians(deg)
            inner = rr * (1.10 if deg % 45 else 1.09)
            outer = rr * (1.14 if deg % 45 else 1.18)
            p.drawLine(QPointF(c.x() + inner * math.sin(a), c.y() - inner * math.cos(a)),
                       QPointF(c.x() + outer * math.sin(a), c.y() - outer * math.cos(a)))  # fmt: skip

        p.save()
        clip = QPainterPath()
        clip.addEllipse(c, rr, rr)
        p.setClipPath(clip)
        glass = QRadialGradient(c, rr)
        glass.setColorAt(0.0, QColor("#07200f"))
        glass.setColorAt(1.0, QColor("#010604"))
        p.fillRect(QRectF(c.x() - rr, c.y() - rr, 2 * rr, 2 * rr), QBrush(glass))

        # Range rings burst outward as the scope powers on
        for i, k in enumerate((0.33, 0.66)):
            grow = _ease_out((t - 0.04 * i) / 0.25)
            p.setPen(QPen(_with_alpha(GRID, dim), 1.2))
            p.drawEllipse(c, rr * k * grow, rr * k * grow)
        p.drawLine(QPointF(c.x() - rr, c.y()), QPointF(c.x() + rr, c.y()))
        p.drawLine(QPointF(c.x(), c.y() - rr), QPointF(c.x(), c.y() + rr))

        if t >= SWEEP_START:
            self._sweep(p, c, rr, t, dim)
        self._contact(p, c, rr, t)
        self._grain_layer(p, c, rr, frame, dim)
        p.restore()

    def _sweep(self, p: QPainter, c: QPointF, r: float, t: float, dim: float) -> None:
        bearing = beam_bearing(t)
        trail = QConicalGradient(c, 90.0 - bearing)
        trail.setColorAt(0.0, _with_alpha(PHOSPHOR, 0.55 * dim))
        trail.setColorAt(0.08, _with_alpha(PHOSPHOR, 0.18 * dim))
        trail.setColorAt(0.28, _with_alpha(PHOSPHOR, 0.0))
        trail.setColorAt(1.0, _with_alpha(PHOSPHOR, 0.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(trail))
        p.drawEllipse(c, r, r)
        a = math.radians(bearing)
        tip = QPointF(c.x() + r * math.sin(a), c.y() - r * math.cos(a))
        p.setPen(QPen(_with_alpha(PHOSPHOR, 0.4 * dim), 5.0))
        p.drawLine(c, tip)
        p.setPen(QPen(_with_alpha(PHOSPHOR, dim), 1.6))
        p.drawLine(c, tip)

    def target_pos(self, c: QPointF, r: float) -> QPointF:
        a = math.radians(TARGET_BEARING)
        return QPointF(c.x() + r * TARGET_RANGE * math.sin(a), c.y() - r * TARGET_RANGE * math.cos(a))

    def _contact(self, p: QPainter, c: QPointF, r: float, t: float) -> None:
        if t < LOCK or t >= BREAKOUT + 0.06:
            return
        pos = self.target_pos(c, r)
        age = t - LOCK
        glow = 0.6 + 0.4 * math.exp(-age / PERSISTENCE)

        # Ping: one ring rushing out of the contact
        ping = _ease_out(age / 0.45)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(_with_alpha(PHOSPHOR, 0.8 * (1 - ping)), 2.0))
        p.drawEllipse(pos, r * 0.9 * ping, r * 0.9 * ping)

        # The blip swells just before it breaks out
        swell = 1.0 + 1.5 * _ease_in((t - (BREAKOUT - 0.12)) / 0.12)
        size = r * 0.04 * swell
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_with_alpha(PHOSPHOR, 0.3 * glow))
        p.drawEllipse(pos, size * 2.5, size * 2.5)
        p.setBrush(_with_alpha(WHITE if swell > 1.2 else PHOSPHOR, glow))
        p.drawEllipse(pos, size, size)

        # Lock brackets slam in from wide to tight
        snap = _ease_out(age / 0.14)
        half = r * (0.75 - 0.6 * snap)
        arm = half * 0.5
        p.setPen(QPen(_with_alpha(PHOSPHOR, snap), 2.0))
        for sx in (-1, 1):
            for sy in (-1, 1):
                k = QPointF(pos.x() + sx * half, pos.y() + sy * half)
                p.drawLine(k, QPointF(k.x() - sx * arm, k.y()))
                p.drawLine(k, QPointF(k.x(), k.y() - sy * arm))
        if age > 0.12 and int(age * 14) % 2 == 0:
            p.setFont(self._mono(r * 0.13, bold=True))
            p.setPen(PHOSPHOR)
            p.drawText(QPointF(pos.x() - half, pos.y() - half - r * 0.05), "LOCK")

    def _grain_layer(self, p: QPainter, c: QPointF, r: float, frame: int, dim: float) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        for i, (x, y, v) in enumerate(self._grain):
            if (i + frame * 7) % 5:
                continue
            p.setBrush(_with_alpha(PHOSPHOR, (0.05 + 0.08 * v) * dim))
            p.drawRect(QRectF(c.x() + x * r, c.y() + y * r, 1.2, 1.2))

    # Jet ------------------------------------------------------------------------------

    def _jet_state(self, w: int, h: int, c: QPointF, r: float, u: float) -> tuple[QPointF, float, float]:
        """Position, length and heading of the jet at flyby progress u (0..1).

        It climbs out of the scope to the middle of the frame while it grows,
        as if rushing at the camera, then whips over the top-left edge.
        """
        start = self.target_pos(c, r)
        mid = QPointF(w * 0.42, h * 0.52)
        end = QPointF(w * 0.18, -h * 0.9)
        if u < 0.78:
            pos = _lerp(start, mid, _ease_out(u / 0.78))
        else:
            pos = _lerp(mid, end, _ease_in((u - 0.78) / 0.22))
        small, big = r * 0.08, h * 2.4
        length = small * (big / small) ** (u**2.2)
        heading = -28.0 + 10.0 * u  # nose up and to the left, easing into the pass
        return pos, length, heading

    def _jet_flyby(self, p: QPainter, w: int, h: int, c: QPointF, r: float, t: float) -> None:
        if t >= IMPACT:
            return
        u = _clamp((t - BREAKOUT) / FLYBY)
        pos, length, heading = self._jet_state(w, h, c, r, u)

        if u > 0.4:  # zoom lines rushing out from the jet
            strength = _clamp((u - 0.4) / 0.35)
            for angle_seed, ln, v in self._streaks:
                ang = math.pi * angle_seed
                dx, dy = math.cos(ang), math.sin(ang)
                inner = h * (0.35 + ((v + u * 2.5) % 1.0) * 0.9)
                outer = inner + h * 0.45 * ln
                a = QPointF(pos.x() + dx * inner, pos.y() + dy * inner)
                b = QPointF(pos.x() + dx * outer, pos.y() + dy * outer)
                g = QLinearGradient(a, b)
                g.setColorAt(0.0, _with_alpha(PHOSPHOR, 0.0))
                g.setColorAt(1.0, _with_alpha(PHOSPHOR, 0.45 * strength))
                p.setPen(QPen(QBrush(g), 1.0 + 1.5 * v))
                p.drawLine(QLineF(a, b))

        for lag, alpha in ((0.05, 0.06), (0.03, 0.11), (0.012, 0.2)):  # motion smear
            gp, gl, gh = self._jet_state(w, h, c, r, max(0.0, u - lag))
            self._draw_jet(p, gp, gl, gh, alpha, burner=0.0)
        self._draw_jet(p, pos, length, heading, 1.0, burner=_clamp(u * 1.6))

    def _draw_jet(self, p: QPainter, pos: QPointF, length: float, heading: float, alpha: float,
                  burner: float) -> None:  # fmt: skip
        xf = QTransform()
        xf.translate(pos.x(), pos.y())
        xf.rotate(heading)
        xf.scale(length, length)
        line = max(1.2, length * 0.006)

        if burner > 0:  # afterburner plumes behind the nozzles
            for s in (1, -1):
                n = xf.map(QPointF(s * 0.078, 0.50))
                tail = xf.map(QPointF(s * 0.078, 0.50 + 0.38 * burner))
                plume = QLinearGradient(n, tail)
                plume.setColorAt(0.0, _with_alpha(WHITE, 0.95 * alpha))
                plume.setColorAt(0.25, _with_alpha(BURNER, 0.8 * alpha))
                plume.setColorAt(1.0, _with_alpha(BURNER, 0.0))
                p.setPen(QPen(QBrush(plume), length * 0.042, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(QLineF(n, tail))

        body = xf.map(self._plane)
        p.setPen(QPen(_with_alpha(PHOSPHOR, 0.35 * alpha), line * 3.5))
        p.setBrush(_with_alpha(HULL, 0.92 * alpha))
        p.drawPath(body)
        p.setPen(QPen(_with_alpha(PHOSPHOR, alpha), line))
        p.drawPath(body)
        p.setPen(QPen(_with_alpha(PHOSPHOR_DIM, alpha), line * 0.8))
        for a, b in self._panels:
            p.drawLine(xf.map(a), xf.map(b))
        p.setPen(QPen(_with_alpha(PHOSPHOR, alpha), line))
        for a, b in self._tails:
            p.drawLine(xf.map(a), xf.map(b))
        canopy = QPainterPath()
        canopy.addEllipse(QPointF(0, -0.30), 0.018, 0.055)
        p.setBrush(_with_alpha(PHOSPHOR, 0.55 * alpha))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(xf.map(canopy))

    # Impact ------------------------------------------------------------------------------

    @staticmethod
    def _flash(p: QPainter, w: int, h: int, t: float) -> None:
        age = t - IMPACT
        if age < -0.02 or age > 0.30:
            return
        strength = 0.9 * math.exp(-max(0.0, age) / 0.05)
        p.fillRect(QRectF(0, 0, w, h), _with_alpha(WHITE, strength))

    def _callsign(self, p: QPainter, w: int, h: int, t: float) -> None:
        age = t - IMPACT
        if age < 0:
            return
        x = h * 1.08
        font = QFont(DISPLAY_FONT)
        font.setPixelSize(int(h * 0.30))
        font.setWeight(QFont.Weight.Bold)
        font.setStretch(QFont.Stretch.Condensed)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, h * 0.012)
        fm = QFontMetricsF(font)
        text_w = fm.horizontalAdvance(CALLSIGN)
        baseline = h * 0.5 + fm.capHeight() * 0.5

        # Slam: comes in big, lands with a small overshoot
        k = _clamp(age / 0.16)
        scale = 1.0 + 0.55 * (1 - k) ** 3 - 0.04 * math.sin(math.pi * _clamp((age - 0.16) / 0.12))
        centre = QPointF(x + text_w / 2, baseline - fm.capHeight() / 2)

        # Shock streak behind the word on impact
        burst = math.exp(-age / 0.18)
        g = QLinearGradient(QPointF(x - h * 0.3, 0), QPointF(x + text_w + h * 0.3, 0))
        g.setColorAt(0.0, _with_alpha(PHOSPHOR, 0.0))
        g.setColorAt(0.5, _with_alpha(PHOSPHOR, 0.45 * burst))
        g.setColorAt(1.0, _with_alpha(PHOSPHOR, 0.0))
        p.fillRect(QRectF(x - h * 0.3, centre.y() - h * 0.012, text_w + h * 0.6, h * 0.024), QBrush(g))

        p.save()
        p.translate(centre)
        p.scale(scale, scale)
        p.translate(-centre.x(), -centre.y())
        path = QPainterPath()
        path.addText(QPointF(x, baseline), font, CALLSIGN)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(_with_alpha(PHOSPHOR, 0.25 + 0.5 * burst), h * (0.02 + 0.03 * burst)))
        p.drawPath(path)  # glow, hot on impact
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_with_alpha(WHITE, burst) if burst > 0.5 else PHOSPHOR)
        p.drawPath(path)
        p.restore()

        label = _ease_out((age - 0.15) / 0.25)
        p.setFont(self._mono(h * 0.05))
        p.setPen(_with_alpha(TEXT_DIM, label))
        p.drawText(QPointF(x + 2, baseline - fm.capHeight() - h * 0.05), "CALLSIGN")
        rule_y = baseline + h * 0.06
        p.setPen(QPen(_with_alpha(PHOSPHOR_DIM, label), 1.4))
        p.drawLine(QPointF(x, rule_y), QPointF(x + text_w * _ease_out((age - 0.2) / 0.4), rule_y))

    @staticmethod
    def _mono(px: float, bold: bool = False) -> QFont:
        f = QFont(MONO_FONT)
        f.setPixelSize(max(8, int(px)))
        f.setBold(bold)
        f.setStyleHint(QFont.StyleHint.Monospace)
        return f


class IntroWindow(QWidget):
    """Frameless startup splash. Click or press any key to skip."""

    finished = Signal()
    SIZE = (640, 300)

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint,
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
        if t > DURATION + 0.3:
            self.skip()
            return
        if t > DURATION:
            self.setWindowOpacity(max(0.0, 1.0 - (t - DURATION) / 0.3))
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

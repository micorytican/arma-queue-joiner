"""lime98 intro.

Beats (about three seconds):
1. A Su-27 style head-up radar picture: scan, contacts, designator closes, lock.
2. A beat of stillness: only the lock box blinks.
3. Hard cut: a vector Su-27 in profile tears in on afterburner and brakes to a
   stop, the lock brackets slam onto it and SU-27 FLANKER is typed under it.
4. It blasts off screen; a Cold War terminal types the callsign key by key and
   the last key lands with a flash and a shake.

Everything is drawn with QPainter from one function of time, so the same code
plays the startup splash and renders the README GIF. All green phosphor; the
only warm colour is the afterburner.
"""

from __future__ import annotations

import math
import random
from functools import cache
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QLineF, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QApplication, QWidget

from .su27 import Point, Profile, su27_profile

PANEL = QColor("#050806")
HUD = QColor("#8cff9e")
HUD_DIM = QColor("#2f8a4b")
HULL = QColor("#04110a")
BURNER = QColor("#ffb347")
WHITE = QColor("#f4fff6")

# Timeline, seconds
POWER_ON = 0.18
SCAN = (0.10, 0.55)  # the scan bar crosses the display once
LOCK = 0.70  # designator closes on the target
CUT = 0.90  # stillness ends, the jet tears in
STOP = 1.12  # the jet brakes to a halt mid-frame
LAUNCH = 1.55  # it blasts off
GONE = 1.78
TYPE_LABEL = 1.79  # "> CALLSIGN"
TYPE_NAME = 1.96  # first letter of the callsign
KEY_GAP = 0.085  # seconds per key
CALLSIGN = "LIME98"
IMPACT = TYPE_NAME + KEY_GAP * (len(CALLSIGN) - 1)  # the last key lands hard
DURATION = IMPACT + 0.8

AZIMUTH = 60  # degrees each side, as on the HUD scale
CONTACTS = (  # (azimuth deg, range 0..1 from bottom, friendly)
    (-38, 0.70, False),
    (22, 0.62, False),  # the target
    (44, 0.30, True),
)
TARGET = 1

TITLE_FONT = "Black Ops One"
MONO_FONT = "Consolas"
FONT_FILE = Path(__file__).resolve().parent / "fonts" / "BlackOpsOne-Regular.ttf"


@cache
def load_fonts() -> str:
    """Register the bundled title font once; returns the family to use."""
    font_id = QFontDatabase.addApplicationFont(str(FONT_FILE))
    families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
    return families[0] if families else "Bahnschrift"


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _ease_out(x: float) -> float:
    x = _clamp(x)
    return 1 - (1 - x) ** 4


def _ease_in(x: float) -> float:
    return _clamp(x) ** 3


def _with_alpha(color: QColor, alpha: float) -> QColor:
    c = QColor(color)
    c.setAlphaF(_clamp(alpha) * color.alphaF())
    return c


class RadarIntro:
    """Draws the intro at any size; call paint() with the time in seconds."""

    def __init__(self, seed: int = 98):
        rng = random.Random(seed)
        self._streaks = [(rng.uniform(0.05, 0.95), rng.uniform(0.3, 1.0), rng.random()) for _ in range(22)]
        self._profile: Profile = su27_profile()
        self._title_family = load_fonts()

    def paint(self, p: QPainter, w: int, h: int, t: float, frame: int = 0) -> None:
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.fillRect(QRectF(0, 0, w, h), PANEL)
        p.save()
        p.translate(self._shake(t, h))
        if t < CUT:
            self._hud(p, w, h, t, frame)
        elif t < GONE:
            self._jet_scene(p, w, h, t)
        else:
            self._terminal(p, w, h, t)
        p.restore()
        self._scanlines(p, w, h)
        self._flash(p, w, h, t)

    # 1. HUD radar picture -------------------------------------------------------------

    @staticmethod
    def scope_rect(w: float, h: float) -> QRectF:
        return QRectF(w * 0.24, h * 0.14, w * 0.52, h * 0.66)

    def contact_pos(self, w: float, h: float, index: int) -> QPointF:
        az, rng, _ = CONTACTS[index]
        r = self.scope_rect(w, h)
        return QPointF(r.center().x() + r.width() / 2 * az / AZIMUTH, r.bottom() - r.height() * rng)

    def _hud(self, p: QPainter, w: int, h: int, t: float, frame: int) -> None:
        on = _ease_out(t / POWER_ON) * (1.0 if t > POWER_ON else (0.4, 1.0, 0.6)[frame % 3])
        locked = t >= LOCK
        still = 0.35 if locked else 1.0  # everything but the lock box steps back
        r = self.scope_rect(w, h)
        target = self.contact_pos(w, h, TARGET)
        line = QPen(_with_alpha(HUD, 0.85 * on * still), 1.4)

        # Glass corners of the HUD combiner
        p.setPen(QPen(_with_alpha(HUD_DIM, on * still), 1.4))
        arm = h * 0.06
        for sx, sy, x, y in ((1, 1, w * 0.04, h * 0.05), (-1, 1, w * 0.96, h * 0.05),
                             (1, -1, w * 0.04, h * 0.95), (-1, -1, w * 0.96, h * 0.95)):  # fmt: skip
            p.drawLine(QPointF(x, y), QPointF(x + sx * arm, y))
            p.drawLine(QPointF(x, y), QPointF(x, y + sy * arm))

        # Azimuth scale along the bottom, range scale up the left side
        p.setPen(line)
        p.drawLine(QPointF(r.left(), r.bottom()), QPointF(r.right(), r.bottom()))
        p.drawLine(QPointF(r.left(), r.top()), QPointF(r.left(), r.bottom()))
        p.setFont(self._mono(h * 0.042))
        for az in range(-AZIMUTH, AZIMUTH + 1, 10):
            x = r.center().x() + r.width() / 2 * az / AZIMUTH
            tall = az % 30 == 0
            p.drawLine(QPointF(x, r.bottom()), QPointF(x, r.bottom() + (h * 0.03 if tall else h * 0.015)))
            if tall:
                p.setPen(_with_alpha(HUD_DIM, on * still))
                p.drawText(QPointF(x - h * 0.03, r.bottom() + h * 0.08), f"{abs(az)}")
                p.setPen(line)
        for k in range(1, 6):
            y = r.bottom() - r.height() * k / 5
            p.drawLine(QPointF(r.left() - h * 0.02, y), QPointF(r.left(), y))
        p.setPen(_with_alpha(HUD_DIM, on * still))
        p.drawText(QPointF(r.left() - h * 0.11, r.top() + h * 0.03), "100")

        if (t > POWER_ON and int(t * 6) % 2 == 0) or t > SCAN[1]:
            p.setFont(self._mono(h * 0.06, bold=True))
            p.setPen(_with_alpha(HUD, on * still))
            p.drawText(QPointF(w * 0.07, h * 0.2), "ИЗЛ")

        scan = _clamp((t - SCAN[0]) / (SCAN[1] - SCAN[0]))
        if 0 < scan < 1:
            x = r.left() + r.width() * scan
            g = QLinearGradient(QPointF(x - r.width() * 0.12, 0), QPointF(x, 0))
            g.setColorAt(0.0, _with_alpha(HUD, 0.0))
            g.setColorAt(1.0, _with_alpha(HUD, 0.2 * on))
            p.fillRect(QRectF(x - r.width() * 0.12, r.top(), r.width() * 0.12, r.height()), QBrush(g))
            p.setPen(QPen(_with_alpha(HUD, on), 1.6))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
        for i, (az, _rng, friendly) in enumerate(CONTACTS):
            if (az + AZIMUTH) / (2 * AZIMUTH) >= scan and t <= SCAN[1]:
                continue
            pos = self.contact_pos(w, h, i)
            p.setPen(QPen(_with_alpha(HUD, on * (1.0 if i == TARGET else still)), 2.2))
            half = h * 0.03
            p.drawLine(QPointF(pos.x() - half, pos.y()), QPointF(pos.x() + half, pos.y()))
            if friendly:
                p.drawLine(QPointF(pos.x() - half, pos.y() + 5), QPointF(pos.x() + half, pos.y() + 5))

        slide = _ease_out((t - SCAN[1]) / (LOCK - SCAN[1]))
        if slide > 0 and not locked:
            start = QPointF(r.center().x(), r.bottom() - r.height() * 0.2)
            pos = QPointF(
                start.x() + (target.x() - start.x()) * slide, start.y() + (target.y() - start.y()) * slide
            )
            gap = h * (0.16 - 0.10 * slide)
            p.setPen(QPen(_with_alpha(HUD, on), 1.8))
            for s in (-1, 1):
                x = pos.x() + s * gap
                p.drawLine(QPointF(x, pos.y() - gap * 0.7), QPointF(x, pos.y() + gap * 0.7))
        if locked:  # stillness: only the lock box blinks
            blink = int((t - LOCK) * 10) % 2 == 0
            box = h * 0.07
            p.setPen(QPen(_with_alpha(HUD, 1.0 if blink else 0.25), 2.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(target.x() - box, target.y() - box, 2 * box, 2 * box))
            p.setFont(self._mono(h * 0.09, bold=True))
            p.setPen(_with_alpha(HUD, 1.0 if blink else 0.4))
            p.drawText(QPointF(w * 0.83, h * 0.58), "А")

    # 2. The jet ----------------------------------------------------------------------

    def jet_x(self, w: float, t: float) -> float:
        """Nose position along x: tears in, brakes hard, drifts, then blasts off."""
        length = w * 0.70
        rest = w * 0.47 + length * 0.5
        if t < STOP:
            return -length * 0.15 + (rest + length * 0.15) * _ease_out((t - CUT) / (STOP - CUT))
        if t < LAUNCH:
            return rest + w * 0.02 * (t - STOP) / (LAUNCH - STOP)
        return rest + w * 0.02 + (w + length) * _ease_in((t - LAUNCH) / (GONE - LAUNCH))

    def _jet_scene(self, p: QPainter, w: int, h: int, t: float) -> None:
        length = w * 0.70
        nose_x = self.jet_x(w, t)
        speed = abs(self.jet_x(w, t + 0.01) - nose_x) / 0.01 / w  # screen widths per second
        y = h * 0.47
        tilt = 4.0 * (1 - _ease_out((t - CUT) / (STOP - CUT))) - 2.0 * _ease_in((t - LAUNCH) / 0.2)

        # Horizon line and speed streaks
        p.setPen(QPen(_with_alpha(HUD_DIM, 0.5), 1.0))
        p.drawLine(QPointF(0, h * 0.78), QPointF(w, h * 0.78))
        if speed > 0.4:
            k = _clamp((speed - 0.4) / 2.5)
            for yy, ln, v in self._streaks:
                x = ((v - t * 3.0) % 1.0) * w * 1.4 - w * 0.2
                a, b = QPointF(x, h * yy), QPointF(x + w * 0.4 * ln * k, h * yy)
                g = QLinearGradient(a, b)
                g.setColorAt(0.0, _with_alpha(HUD, 0.45 * k))
                g.setColorAt(1.0, _with_alpha(HUD, 0.0))
                p.setPen(QPen(QBrush(g), 1.0 + v))
                p.drawLine(QLineF(a, b))

        burner = 0.5 + 0.5 * _clamp(speed / 2.0)
        if speed > 1.0:
            for lag, alpha in ((0.02, 0.10), (0.01, 0.2)):
                self._draw_profile(p, self.jet_x(w, t - lag), y, length, tilt, alpha, 0.0)
        self._draw_profile(p, nose_x, y, length, tilt, 1.0, burner)

        # Lock brackets slam onto the real aircraft, its name is typed underneath
        if STOP - 0.02 <= t < LAUNCH + 0.05:
            age = t - (STOP - 0.02)
            snap = _ease_out(age / 0.12)
            cx = nose_x - length * 0.5
            half_w = length * 0.56 + w * 0.25 * (1 - snap)
            half_h = h * 0.27 + h * 0.3 * (1 - snap)
            arm = h * 0.08
            p.setPen(QPen(_with_alpha(HUD, snap), 2.2))
            for sx in (-1, 1):
                for sy in (-1, 1):
                    k = QPointF(cx + sx * half_w, y + sy * half_h)
                    p.drawLine(k, QPointF(k.x() - sx * arm, k.y()))
                    p.drawLine(k, QPointF(k.x(), k.y() - sy * arm))
            self._typed(p, QPointF(cx - half_w, y + half_h + h * 0.09), "SU-27  FLANKER", age - 0.06,
                        0.017, self._mono(h * 0.06, bold=True))  # fmt: skip

    def _draw_profile(self, p: QPainter, nose_x: float, y: float, length: float, tilt: float,
                      alpha: float, burner: float) -> None:  # fmt: skip
        pr = self._profile
        p.save()
        p.translate(nose_x, y)
        p.rotate(-tilt)

        def m(pt: Point) -> QPointF:
            return QPointF((pt[0] - 1.0) * length, -pt[1] * length)

        def poly(points: list[Point]) -> QPolygonF:
            return QPolygonF([m(q) for q in points])

        line = max(1.2, length * 0.0035)
        if burner > 0:
            nozzle = m(pr.nozzle)
            tail = QPointF(nozzle.x() - length * 0.28 * burner, nozzle.y())
            plume = QLinearGradient(nozzle, tail)
            plume.setColorAt(0.0, _with_alpha(WHITE, alpha))
            plume.setColorAt(0.25, _with_alpha(BURNER, 0.9 * alpha))
            plume.setColorAt(1.0, _with_alpha(BURNER, 0.0))
            p.setPen(QPen(QBrush(plume), length * 0.032, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QLineF(nozzle, tail))
            core = QRadialGradient(nozzle, length * 0.03)
            core.setColorAt(0.0, _with_alpha(WHITE, alpha))
            core.setColorAt(1.0, _with_alpha(BURNER, 0.0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(core))
            p.drawEllipse(nozzle, length * 0.03, length * 0.03)

        glow = QPen(_with_alpha(HUD, 0.28 * alpha), line * 3.5)
        sharp = QPen(_with_alpha(HUD, alpha), line)
        far = QPen(_with_alpha(HUD_DIM, alpha), line)
        p.setBrush(_with_alpha(HULL, 0.95 * alpha))
        for shape, pens in ((pr.fin_far, (far,)), (pr.tailplane, (glow, sharp)), (pr.ventral, (glow, sharp)),
                            (pr.body, (glow, sharp)), (pr.wing, (far,)), (pr.fin_near, (glow, sharp)),
                            (pr.canopy, (sharp,))):  # fmt: skip
            for pen in pens:
                p.setPen(pen)
                p.drawPolygon(poly(shape))
        p.setPen(QPen(_with_alpha(HUD_DIM, alpha), line * 0.8))
        for a, b in pr.lines:
            p.drawLine(m(a), m(b))
        p.setPen(sharp)
        p.drawLine(m(pr.pitot[0]), m(pr.pitot[1]))
        centre, radius = pr.irst
        p.setBrush(_with_alpha(HUD, 0.5 * alpha))
        p.drawEllipse(m(centre), radius * length, radius * length)
        p.restore()

    # 3. Terminal ----------------------------------------------------------------------

    def _terminal(self, p: QPainter, w: int, h: int, t: float) -> None:
        font = QFont(self._title_family)
        font.setPixelSize(int(h * 0.36))
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, h * 0.01)
        fm = QFontMetricsF(font)
        total = fm.horizontalAdvance(CALLSIGN)
        x0 = (w - total) / 2
        baseline = h * 0.56 + fm.capHeight() / 2

        label = self._mono(h * 0.06, bold=True)
        self._typed(p, QPointF(x0, baseline - fm.capHeight() - h * 0.07), "> CALLSIGN", t - TYPE_LABEL, 0.015,
                    label, cursor=t < TYPE_NAME)  # fmt: skip

        typed = 0 if t < TYPE_NAME else min(len(CALLSIGN), int((t - TYPE_NAME) / KEY_GAP) + 1)
        p.setFont(font)
        for i in range(typed):
            hit = TYPE_NAME + i * KEY_GAP
            age = t - hit
            last = i == len(CALLSIGN) - 1
            pop = math.exp(-age / (0.12 if last else 0.06))
            x = x0 + fm.horizontalAdvance(CALLSIGN[:i])
            ch = CALLSIGN[i]
            cw = fm.horizontalAdvance(ch)
            centre = QPointF(x + cw / 2, baseline - fm.capHeight() / 2)
            scale = 1.0 + (0.45 if last else 0.18) * pop
            p.save()
            p.translate(centre)
            p.scale(scale, scale)
            p.translate(-centre.x(), -centre.y())
            p.setPen(QPen(_with_alpha(HUD, 0.22 + 0.4 * pop), h * 0.03))
            p.drawText(QPointF(x, baseline), ch)  # glow pass
            p.setPen(_with_alpha(WHITE, pop) if pop > 0.5 else HUD)
            p.drawText(QPointF(x, baseline), ch)
            p.restore()

        # Block cursor after the last typed letter
        if t >= TYPE_NAME and int(t * 3.5) % 2 == 0:
            cx = x0 + fm.horizontalAdvance(CALLSIGN[:typed]) + h * 0.03
            p.fillRect(
                QRectF(cx, baseline - fm.capHeight(), h * 0.06, fm.capHeight()), _with_alpha(HUD, 0.85)
            )

        rule = _ease_out((t - IMPACT) / 0.35)
        if rule > 0:
            y = baseline + h * 0.07
            p.setPen(QPen(_with_alpha(HUD_DIM, 1.0), 1.6))
            p.drawLine(QPointF(w / 2 - total / 2 * rule, y), QPointF(w / 2 + total / 2 * rule, y))

    def _typed(self, p: QPainter, at: QPointF, text: str, age: float, per_char: float, font: QFont,
               cursor: bool = True) -> None:  # fmt: skip
        if age <= 0:
            return
        shown = text[: min(len(text), int(age / per_char) + 1)]
        p.setFont(font)
        p.setPen(HUD)
        p.drawText(at, shown)
        if cursor and (len(shown) < len(text) or int(age * 4) % 2 == 0):
            fm = QFontMetricsF(font)
            x = at.x() + fm.horizontalAdvance(shown) + 2
            p.fillRect(
                QRectF(x, at.y() - fm.ascent() * 0.8, fm.averageCharWidth() * 0.8, fm.ascent() * 0.9), HUD
            )

    # Shared effects -------------------------------------------------------------------

    @staticmethod
    def _shake(t: float, h: float) -> QPointF:
        amp = 0.0
        for start, size in ((CUT, 0.025), (LAUNCH + 0.1, 0.015), (IMPACT, 0.04)):
            age = t - start
            if 0 <= age < 0.4:
                amp += h * size * math.exp(-age / 0.08)
        return QPointF(amp * math.sin(t * 97.0), amp * math.cos(t * 71.0))

    @staticmethod
    def _flash(p: QPainter, w: int, h: int, t: float) -> None:
        strength = 0.0
        for start, peak in ((CUT, 0.75), (IMPACT, 0.7)):
            age = t - start
            if -0.01 <= age < 0.25:
                strength = max(strength, peak * math.exp(-max(0.0, age) / 0.045))
        if strength > 0.01:
            p.fillRect(QRectF(0, 0, w, h), _with_alpha(WHITE, strength))

    @staticmethod
    def _scanlines(p: QPainter, w: int, h: int) -> None:
        p.setPen(QPen(QColor(0, 0, 0, 55), 1.0))
        for y in range(0, h, 3):
            p.drawLine(QPointF(0, y + 0.5), QPointF(w, y + 0.5))
        vignette = QRadialGradient(QPointF(w / 2, h / 2), w * 0.62)
        vignette.setColorAt(0.6, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 150))
        p.fillRect(QRectF(0, 0, w, h), QBrush(vignette))

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

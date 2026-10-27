"""lime98 intro, "Through the Su-27's eyes".

The scene follows the Su-27's own sight: the ILS-31 head-up display shows the
N001 radar picture as a top-down view (azimuth across, range up), contacts as
short bars, double bars for friendlies, ИЗЛ while the radar transmits and the
attack cue А once a target is locked. After the lock the camera dives into
the target and a 3D vector Su-27 rushes past on afterburner. Flash, shake,
and the callsign lands in the style of a Flanker's painted side number with
the lock box slamming around it.

Everything is drawn with QPainter from a single function of time, so the
same code plays the startup splash live and renders the README GIF.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from PySide6.QtCore import QElapsedTimer, QLineF, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QApplication, QWidget

PANEL = QColor("#050806")
HUD = QColor("#8cff9e")
HUD_DIM = QColor("#2f8a4b")
HULL = QColor("#04110a")
BURNER = QColor("#ffb347")
WHITE = QColor("#f4fff6")

# Timeline, seconds
POWER_ON = 0.18
SCAN = (0.12, 0.62)  # the scan bar crosses the display once
LOCK = 0.78  # designator closes on the target, attack cue on
DIVE = 0.10  # camera dives into the target
FLYBY = 0.80  # 3D pass, from far away to the camera
IMPACT = LOCK + FLYBY  # flash, shake, callsign
DURATION = IMPACT + 1.0

AZIMUTH = 60  # degrees each side, as on the HUD scale
CONTACTS = (  # (azimuth deg, range 0..1 from bottom, friendly)
    (-38, 0.70, False),
    (22, 0.62, False),  # the target
    (44, 0.30, True),
)
TARGET = 1

CALLSIGN = "LIME98"
DISPLAY_FONT = "Bahnschrift"
MONO_FONT = "Consolas"


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _ease_out(x: float) -> float:
    x = _clamp(x)
    return 1 - (1 - x) ** 3


def _ease_in(x: float) -> float:
    return _clamp(x) ** 2


def _with_alpha(color: QColor, alpha: float) -> QColor:
    c = QColor(color)
    c.setAlphaF(_clamp(alpha) * color.alphaF())
    return c


# 3D model ------------------------------------------------------------------------------

Vec = tuple[float, float, float]


def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a: Vec, k: float) -> Vec:
    return (a[0] * k, a[1] * k, a[2] * k)


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a: Vec) -> Vec:
    n = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


def su27_planform() -> list[tuple[float, float]]:
    """Top view of a Su-27, nose toward -y, length about 1.07, centred near the origin.

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
    return right + [(-x, y) for x, y in reversed(right[1:-1])]


@dataclass(frozen=True)
class Model:
    """Model space: x to the right wing, y forward (nose), z up. Length about 1."""

    planform: list[Vec]
    fins: list[list[Vec]]
    nacelles: list[list[Vec]]
    spine: list[Vec]
    canopy: list[Vec]
    nozzles: list[Vec]


def su27_model() -> Model:
    planform = [(x, -y, 0.0) for x, y in su27_planform()]
    fins = [
        [(s * 0.124, -0.235, 0.0), (s * 0.168, -0.335, 0.175), (s * 0.176, -0.405, 0.175),
         (s * 0.136, -0.430, 0.0)]
        for s in (1, -1)
    ]  # fmt: skip
    nacelles = [
        [(s * 0.045, 0.02, -0.055), (s * 0.108, 0.02, -0.055), (s * 0.108, -0.46, -0.04),
         (s * 0.045, -0.46, -0.04)]
        for s in (1, -1)
    ]  # fmt: skip
    spine = [(0, 0.5, 0), (0, 0.38, 0.03), (0, 0.31, 0.07), (0, 0.22, 0.075), (0, 0.0, 0.055),
             (0, -0.44, 0.03)]  # fmt: skip
    canopy = [(0, 0.37, 0.035), (0.028, 0.30, 0.055), (0, 0.235, 0.078), (-0.028, 0.30, 0.055)]
    nozzles = [(s * 0.078, -0.475, -0.03) for s in (1, -1)]
    return Model(planform, fins, nacelles, spine, canopy, nozzles)


@dataclass(frozen=True)
class Pose:
    position: Vec  # camera space: x right, y up, z into the screen
    forward: Vec
    roll: float  # degrees
    up_hint: Vec = (0.0, 1.0, 0.0)  # where the top of the jet should face before roll


class Camera:
    def __init__(self, w: float, h: float):
        self.cx, self.cy = w / 2, h / 2
        self.f = h * 1.15

    def project(self, p: Vec) -> QPointF | None:
        if p[2] < 0.12:
            return None
        return QPointF(self.cx + self.f * p[0] / p[2], self.cy - self.f * p[1] / p[2])

    def unproject(self, x: float, y: float, depth: float) -> Vec:
        return ((x - self.cx) * depth / self.f, (self.cy - y) * depth / self.f, depth)


def place(model_point: Vec, pose: Pose) -> Vec:
    """Model space to camera space."""
    fwd = _norm(pose.forward)
    right = _norm(_cross(pose.up_hint, fwd))
    if right == (0.0, 0.0, 0.0):
        right = (1.0, 0.0, 0.0)
    up = _cross(fwd, right)
    r = math.radians(pose.roll)
    right, up = (
        _add(_mul(right, math.cos(r)), _mul(up, math.sin(r))),
        _add(_mul(up, math.cos(r)), _mul(right, -math.sin(r))),
    )
    x, y, z = model_point
    return _add(pose.position, _add(_mul(right, x), _add(_mul(fwd, y), _mul(up, z))))


# Scene ---------------------------------------------------------------------------------


class RadarIntro:
    """Draws the intro at any size; call paint() with the time in seconds."""

    def __init__(self, seed: int = 98):
        rng = random.Random(seed)
        self._streaks = [(rng.uniform(-1, 1), rng.uniform(0.3, 1.0), rng.random()) for _ in range(28)]
        self._model = su27_model()

    def paint(self, p: QPainter, w: int, h: int, t: float, frame: int = 0) -> None:
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.fillRect(QRectF(0, 0, w, h), PANEL)
        cam = Camera(w, h)

        p.save()
        p.translate(self._shake(t, h))
        if t < LOCK + DIVE + 0.05:
            self._hud(p, w, h, t, frame)
        if LOCK <= t < IMPACT:
            self._flyby(p, w, h, cam, t)
        if t >= IMPACT:
            self._callsign(p, w, h, t)
        p.restore()
        self._flash(p, w, h, t)

    # HUD radar picture ----------------------------------------------------------------

    @staticmethod
    def scope_rect(w: float, h: float) -> QRectF:
        return QRectF(w * 0.24, h * 0.14, w * 0.52, h * 0.66)

    def contact_pos(self, w: float, h: float, index: int) -> QPointF:
        az, rng, _ = CONTACTS[index]
        r = self.scope_rect(w, h)
        return QPointF(r.center().x() + r.width() / 2 * az / AZIMUTH, r.bottom() - r.height() * rng)

    def _hud(self, p: QPainter, w: int, h: int, t: float, frame: int) -> None:
        on = _ease_out(t / POWER_ON) * (1.0 if t > POWER_ON else (0.4, 1.0, 0.6)[frame % 3])
        target = self.contact_pos(w, h, TARGET)

        # The camera dives into the locked target
        dive = _ease_in((t - LOCK) / DIVE)
        p.save()
        if dive > 0:
            zoom = 1.0 + 5.0 * dive
            p.translate(target)
            p.scale(zoom, zoom)
            p.translate(-target.x(), -target.y())
            on *= 1.0 - dive

        r = self.scope_rect(w, h)
        p.setBrush(Qt.BrushStyle.NoBrush)
        line = QPen(_with_alpha(HUD, 0.85 * on), 1.4)

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
                p.setPen(_with_alpha(HUD_DIM, on))
                p.drawText(QPointF(x - h * 0.03, r.bottom() + h * 0.08), f"{abs(az)}")
                p.setPen(line)
        for k in range(1, 6):
            y = r.bottom() - r.height() * k / 5
            p.drawLine(QPointF(r.left() - h * 0.02, y), QPointF(r.left(), y))
        p.setPen(_with_alpha(HUD_DIM, on))
        p.drawText(QPointF(r.left() - h * 0.11, r.top() + h * 0.03), "100")

        # Radar transmitting
        if (t > POWER_ON and int(t * 6) % 2 == 0) or t > SCAN[1]:
            p.setFont(self._mono(h * 0.06, bold=True))
            p.setPen(_with_alpha(HUD, on))
            p.drawText(QPointF(w * 0.05, h * 0.16), "ИЗЛ")

        # Scan bar and the contacts it paints
        scan = _clamp((t - SCAN[0]) / (SCAN[1] - SCAN[0]))
        if 0 < scan < 1:
            x = r.left() + r.width() * scan
            g = QLinearGradient(QPointF(x - r.width() * 0.12, 0), QPointF(x, 0))
            g.setColorAt(0.0, _with_alpha(HUD, 0.0))
            g.setColorAt(1.0, _with_alpha(HUD, 0.18 * on))
            p.fillRect(QRectF(x - r.width() * 0.12, r.top(), r.width() * 0.12, r.height()), QBrush(g))
            p.setPen(QPen(_with_alpha(HUD, on), 1.6))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
        for i, (az, _rng, friendly) in enumerate(CONTACTS):
            seen = (az + AZIMUTH) / (2 * AZIMUTH) < scan or t > SCAN[1]
            if not seen:
                continue
            pos = self.contact_pos(w, h, i)
            p.setPen(QPen(_with_alpha(HUD, on), 2.2))
            half = h * 0.03
            p.drawLine(QPointF(pos.x() - half, pos.y()), QPointF(pos.x() + half, pos.y()))
            if friendly:
                p.drawLine(QPointF(pos.x() - half, pos.y() + 5), QPointF(pos.x() + half, pos.y() + 5))

        # Target designator slides over and closes, attack cue А
        slide = _ease_out((t - SCAN[1]) / (LOCK - SCAN[1]))
        if slide > 0:
            start = QPointF(r.center().x(), r.bottom() - r.height() * 0.2)
            pos = QPointF(
                start.x() + (target.x() - start.x()) * slide, start.y() + (target.y() - start.y()) * slide
            )
            gap = h * (0.16 - 0.10 * slide)
            p.setPen(QPen(_with_alpha(HUD, on), 1.8))
            for s in (-1, 1):
                x = pos.x() + s * gap
                p.drawLine(QPointF(x, pos.y() - gap * 0.7), QPointF(x, pos.y() + gap * 0.7))
            if t >= LOCK:
                box = h * 0.07
                p.drawRect(QRectF(target.x() - box, target.y() - box, 2 * box, 2 * box))
                p.setFont(self._mono(h * 0.09, bold=True))
                p.drawText(QPointF(w * 0.85, h * 0.6), "А")
        p.restore()

    # 3D pass --------------------------------------------------------------------------

    def _jet_position(self, w: float, h: float, u: float) -> Vec:
        """Camera-space position at flyby progress u.

        The screen path runs from the locked contact to mid-frame, then whips off
        the top-left edge; depth shrinks exponentially, so the jet keeps visibly
        rushing at the camera instead of popping up at the very end.
        """
        cam = Camera(w, h)
        target = self.contact_pos(w, h, TARGET)
        mid = QPointF(w * 0.44, h * 0.56)
        exit_ = QPointF(-w * 0.05, -h * 0.55)
        if u < 0.82:
            k = _ease_out(u / 0.82)
            screen = QPointF(target.x() + (mid.x() - target.x()) * k, target.y() + (mid.y() - target.y()) * k)
        else:
            k = _ease_in((u - 0.82) / 0.18)
            screen = QPointF(mid.x() + (exit_.x() - mid.x()) * k, mid.y() + (exit_.y() - mid.y()) * k)
        depth = 9.0 * (0.8 / 9.0) ** (_clamp(u) ** 1.25)
        return cam.unproject(screen.x(), screen.y(), depth)

    def jet_pose(self, w: float, h: float, u: float) -> Pose:
        """Position plus attitude.

        A jet flying straight at the camera shows only the edge of its wing, so
        the attitude is set for a three-quarter view instead: nose up and to the
        left, top turned toward the viewer, banking a little through the pass.
        """
        forward = _norm((-1.0, 0.55, -0.6))
        up_hint = _norm((0.0, 0.45, -1.0))
        return Pose(self._jet_position(w, h, u), forward, roll=18.0 - 45.0 * _ease_in(u), up_hint=up_hint)

    def _flyby(self, p: QPainter, w: int, h: int, cam: Camera, t: float) -> None:
        u = _clamp((t - LOCK) / FLYBY)
        pose = self.jet_pose(w, h, u)
        center = cam.project(pose.position)
        if center is None:
            return

        if u > 0.45:  # zoom lines out of the jet
            strength = _clamp((u - 0.45) / 0.3)
            for angle_seed, ln, v in self._streaks:
                ang = math.pi * angle_seed
                dx, dy = math.cos(ang), math.sin(ang)
                inner = h * (0.3 + ((v + u * 2.5) % 1.0) * 0.9)
                a = QPointF(center.x() + dx * inner, center.y() + dy * inner)
                b = QPointF(a.x() + dx * h * 0.45 * ln, a.y() + dy * h * 0.45 * ln)
                g = QLinearGradient(a, b)
                g.setColorAt(0.0, _with_alpha(HUD, 0.0))
                g.setColorAt(1.0, _with_alpha(HUD, 0.4 * strength))
                p.setPen(QPen(QBrush(g), 1.0 + 1.5 * v))
                p.drawLine(QLineF(a, b))

        for lag, alpha in ((0.012, 0.12),):  # a touch of motion smear
            self._draw_jet(p, cam, self.jet_pose(w, h, max(0.0, u - lag)), alpha, burner=0.0)
        self._draw_jet(p, cam, pose, 1.0, burner=_clamp(0.3 + u))

    def _draw_jet(self, p: QPainter, cam: Camera, pose: Pose, alpha: float, burner: float) -> None:
        m = self._model

        def proj(points: list[Vec]) -> QPolygonF | None:
            out = []
            for pt in points:
                q = cam.project(place(pt, pose))
                if q is None:
                    return None
                out.append(q)
            return QPolygonF(out)

        nose = cam.project(place((0, 0.5, 0), pose))
        tail = cam.project(place((0, -0.5, 0), pose))
        if nose is None or tail is None:
            return
        size = QLineF(nose, tail).length()
        line = max(1.1, size * 0.005)
        glow = QPen(_with_alpha(HUD, 0.3 * alpha), line * 3.5)
        sharp = QPen(_with_alpha(HUD, alpha), line)
        fill = _with_alpha(HULL, 0.9 * alpha)

        def shape(points: list[Vec], closed: bool = True, filled: bool = True) -> None:
            poly = proj(points)
            if poly is None:
                return
            p.setBrush(fill if filled else Qt.BrushStyle.NoBrush)
            for pen in (glow, sharp):
                p.setPen(pen)
                if closed:
                    p.drawPolygon(poly)
                else:
                    p.drawPolyline(poly)
                p.setBrush(Qt.BrushStyle.NoBrush)

        for nacelle in m.nacelles:
            shape(nacelle)
        shape(m.planform)
        for fin in m.fins:
            shape(fin)
        shape(m.spine, closed=False, filled=False)
        shape(m.canopy)

        if burner > 0:
            back = _mul(_norm(pose.forward), -1.0)
            radius = max(3.0, size * 0.04)
            for n in m.nozzles:
                start = place(n, pose)
                a = cam.project(start)
                b = cam.project(_add(start, _mul(back, 0.35 * burner)))
                if a is None or b is None:
                    continue
                plume = QLinearGradient(a, b)
                plume.setColorAt(0.0, _with_alpha(WHITE, 0.95 * alpha))
                plume.setColorAt(0.3, _with_alpha(BURNER, 0.85 * alpha))
                plume.setColorAt(1.0, _with_alpha(BURNER, 0.0))
                cap = Qt.PenCapStyle.RoundCap
                p.setPen(QPen(QBrush(plume), max(2.0, size * 0.045), Qt.PenStyle.SolidLine, cap))
                p.drawLine(QLineF(a, b))
                core = QRadialGradient(a, radius)
                core.setColorAt(0.0, _with_alpha(WHITE, alpha))
                core.setColorAt(1.0, _with_alpha(BURNER, 0.0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(core))
                p.drawEllipse(a, radius, radius)

    # Impact and callsign ------------------------------------------------------------

    @staticmethod
    def _shake(t: float, h: float) -> QPointF:
        age = t - IMPACT
        if age < 0 or age > 0.45:
            return QPointF(0, 0)
        amp = h * 0.035 * math.exp(-age / 0.09)
        return QPointF(amp * math.sin(age * 97.0), amp * math.cos(age * 71.0))

    @staticmethod
    def _flash(p: QPainter, w: int, h: int, t: float) -> None:
        age = t - IMPACT
        if age < -0.02 or age > 0.3:
            return
        p.fillRect(QRectF(0, 0, w, h), _with_alpha(WHITE, 0.9 * math.exp(-max(0.0, age) / 0.05)))

    def _callsign(self, p: QPainter, w: int, h: int, t: float) -> None:
        age = t - IMPACT
        font = QFont(DISPLAY_FONT)
        font.setPixelSize(int(h * 0.40))
        font.setWeight(QFont.Weight.Bold)
        font.setStretch(QFont.Stretch.SemiCondensed)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, h * 0.015)
        fm = QFontMetricsF(font)
        text_w = fm.horizontalAdvance(CALLSIGN)
        cap = fm.capHeight()
        x = (w - text_w) / 2
        baseline = h * 0.5 + cap / 2
        centre = QPointF(w / 2, h * 0.5)

        k = _clamp(age / 0.14)
        scale = 1.0 + 0.5 * (1 - k) ** 3 - 0.035 * math.sin(math.pi * _clamp((age - 0.14) / 0.12))
        hot = math.exp(-age / 0.16)
        round_cap, round_join = Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
        solid = Qt.PenStyle.SolidLine

        path = QPainterPath()
        path.addText(QPointF(x, baseline), font, CALLSIGN)
        p.save()
        p.translate(centre)
        p.scale(scale, scale)
        p.translate(-centre.x(), -centre.y())
        # Side-number style: outer outline, a dark gap, then the solid figure
        p.setBrush(Qt.BrushStyle.NoBrush)
        glow = _with_alpha(HUD, 0.18 + 0.4 * hot)
        p.setPen(QPen(QBrush(glow), h * 0.05, solid, round_cap, round_join))
        p.drawPath(path)
        p.setPen(QPen(QBrush(HUD), h * 0.028, solid, round_cap, round_join))
        p.drawPath(path)
        p.setPen(QPen(QBrush(PANEL), h * 0.014, solid, round_cap, round_join))
        p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_with_alpha(WHITE, hot) if hot > 0.45 else HUD)
        p.drawPath(path)
        p.restore()

        # The HUD locks onto the name
        snap = _ease_out((age - 0.08) / 0.16)
        if snap > 0:
            pad_x = text_w * 0.5 + h * (0.05 + 0.5 * (1 - snap))
            pad_y = cap * 0.5 + h * (0.06 + 0.5 * (1 - snap))
            arm = h * 0.07
            p.setPen(QPen(_with_alpha(HUD, snap), 2.0))
            for sx in (-1, 1):
                for sy in (-1, 1):
                    corner = QPointF(centre.x() + sx * pad_x, centre.y() + sy * pad_y)
                    p.drawLine(corner, QPointF(corner.x() - sx * arm, corner.y()))
                    p.drawLine(corner, QPointF(corner.x(), corner.y() - sy * arm))
            if age > 0.3 and (age > 0.6 or int(age * 12) % 2 == 0):
                p.setFont(self._mono(h * 0.07, bold=True))
                p.setPen(HUD)
                p.drawText(QPointF(centre.x() + pad_x + h * 0.03, centre.y() + h * 0.025), "А")

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

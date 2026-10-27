"""Su-27 side profile as vector shapes.

Units: length 1.0 from the tail cone (x = 0) to the nose tip (x = 1), y up,
fuselage datum at y = 0. Proportions follow the real aircraft (21.9 m long,
fins about 0.2 L above the spine): drooped nose with pitot, IRST ball in
front of the windscreen, bubble canopy, dorsal spine, intakes under the
LERX, engine nacelles, ventral fins, tailplanes reaching past the nozzles,
twin fins and the long tail 'stinger'.
"""

from __future__ import annotations

from dataclasses import dataclass

Point = tuple[float, float]


def _quad(p0: Point, c: Point, p1: Point, steps: int = 8) -> list[Point]:
    return [
        (
            (1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * c[0] + u * u * p1[0],
            (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * c[1] + u * u * p1[1],
        )
        for u in (i / steps for i in range(1, steps + 1))
    ]


@dataclass(frozen=True)
class Profile:
    body: list[Point]  # fuselage, nacelle and tail cone outline
    canopy: list[Point]
    fin_near: list[Point]
    fin_far: list[Point]
    ventral: list[Point]
    tailplane: list[Point]
    wing: list[Point]
    lines: list[tuple[Point, Point]]  # panel lines
    pitot: tuple[Point, Point]
    irst: tuple[Point, float]  # centre, radius
    nozzle: Point  # exhaust centre


def su27_profile() -> Profile:
    top = [(1.000, -0.004)]
    top += _quad((1.000, -0.004), (0.950, 0.020), (0.880, 0.033))  # drooped nose
    top += _quad((0.880, 0.033), (0.830, 0.042), (0.800, 0.046), 4)
    top += [(0.792, 0.049)]  # IRST fairing
    top += _quad((0.792, 0.049), (0.770, 0.070), (0.725, 0.079), 6)  # windscreen
    top += _quad((0.725, 0.079), (0.675, 0.083), (0.630, 0.068), 6)  # canopy top
    top += _quad((0.630, 0.068), (0.590, 0.074), (0.520, 0.071), 6)  # hump behind the canopy
    top += [(0.380, 0.062), (0.240, 0.050), (0.110, 0.038)]  # spine sloping to the tail cone
    top += [(0.060, 0.034), (0.010, 0.024), (0.000, 0.018)]  # stinger
    bottom = [(0.000, 0.010), (0.040, 0.004), (0.080, -0.002)]  # under the stinger
    bottom += [(0.086, -0.022), (0.084, -0.060)]  # nozzle exit
    bottom += [(0.150, -0.066), (0.320, -0.076), (0.560, -0.078)]  # nacelle, rising to the nozzle
    bottom += [(0.588, -0.076), (0.622, -0.038)]  # raked intake lip
    bottom += _quad((0.622, -0.038), (0.720, -0.032), (0.830, -0.024), 6)  # LERX underside
    bottom += _quad((0.830, -0.026), (0.930, -0.020), (1.000, -0.004), 6)  # nose underside
    body = top + bottom

    canopy = [(0.792, 0.049)]
    canopy += _quad((0.792, 0.049), (0.770, 0.070), (0.725, 0.079), 6)
    canopy += _quad((0.725, 0.079), (0.675, 0.083), (0.630, 0.068), 6)
    canopy += [(0.640, 0.054), (0.780, 0.050)]

    fin_near = [(0.275, 0.055), (0.150, 0.218), (0.098, 0.218), (0.078, 0.046)]
    fin_far = [(x - 0.018, y - 0.008) for x, y in fin_near]
    ventral = [(0.250, -0.072), (0.212, -0.120), (0.178, -0.120), (0.185, -0.068)]
    tailplane = [(0.215, -0.030), (0.040, -0.052), (0.020, -0.046), (0.030, -0.034), (0.200, -0.022)]
    wing = [(0.560, -0.008), (0.300, -0.020), (0.250, -0.014), (0.300, -0.006)]
    lines = [
        ((0.622, -0.038), (0.560, -0.030)),  # top of the intake
        ((0.560, -0.030), (0.300, -0.034)),  # nacelle seam
        ((0.790, 0.030), (0.560, -0.010)),  # LERX edge
        ((0.630, 0.068), (0.630, 0.052)),  # canopy rear frame
        ((0.880, 0.030), (0.880, -0.020)),  # radome joint
        ((0.470, 0.058), (0.430, 0.050)),  # airbrake hinge
    ]
    pitot = ((1.000, -0.004), (1.035, -0.006))
    irst = ((0.800, 0.050), 0.007)
    nozzle = (0.084, -0.041)
    return Profile(body, canopy, fin_near, fin_far, ventral, tailplane, wing, lines, pitot, irst, nozzle)

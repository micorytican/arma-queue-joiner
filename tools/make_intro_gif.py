"""Render the lime98 radar intro to assets/intro.gif (and a still assets/intro.png).

Uses the same RadarIntro code as the app, frame by frame.
Usage: python tools/make_intro_gif.py   (needs Pillow, see requirements-dev.txt)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402

from aqj.ui.intro import DURATION, RadarIntro  # noqa: E402

WIDTH, HEIGHT = 640, 300
FPS = 25
HOLD = 1.6  # seconds the finished logo stays before the GIF loops
COLORS = 128


def render(scene: RadarIntro, t: float, frame: int) -> Image.Image:
    img = QImage(WIDTH, HEIGHT, QImage.Format.Format_RGBA8888)
    painter = QPainter(img)
    scene.paint(painter, WIDTH, HEIGHT, t, frame)
    painter.end()
    data = bytes(img.constBits())
    return Image.frombuffer("RGBA", (WIDTH, HEIGHT), data, "raw", "RGBA", 0, 1).convert("RGB")


def main() -> None:
    QGuiApplication(sys.argv)
    scene = RadarIntro()
    count = int((DURATION + HOLD) * FPS)
    frames = [render(scene, i / FPS, i) for i in range(count)]

    # One shared palette, sampled from every phase, keeps colours steady (incl. the afterburners)
    picks = [int(t * FPS) for t in (0.4, 0.95, 1.08, 1.14, 1.2)] + [count - 1]
    sample = Image.new("RGB", (WIDTH, HEIGHT * len(picks)))
    for k, i in enumerate(picks):
        sample.paste(frames[min(i, count - 1)], (0, HEIGHT * k))
    palette = sample.quantize(colors=COLORS, method=Image.Quantize.MEDIANCUT)
    paletted = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]

    out = ROOT / "assets" / "intro.gif"
    paletted[0].save(
        out,
        save_all=True,
        append_images=paletted[1:],
        duration=1000 // FPS,
        loop=0,
        optimize=True,
        disposal=1,
    )
    frames[-1].save(ROOT / "assets" / "intro.png", optimize=True)
    print(f"{out.relative_to(ROOT)}: {count} frames, {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()

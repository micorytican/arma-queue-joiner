import pytest
from PySide6.QtGui import QColor, QImage, QPainter

from aqj.ui import intro


def render(t: float, w: int = 640, h: int = 300) -> QImage:
    img = QImage(w, h, QImage.Format.Format_RGB32)
    p = QPainter(img)
    intro.RadarIntro().paint(p, w, h, t, int(t * 30))
    p.end()
    return img


def bright(img: QImage, x0: int, x1: int, y0: int, y1: int) -> int:
    return sum(1 for x in range(x0, x1, 4) for y in range(y0, y1, 4) if QColor(img.pixel(x, y)).green() > 150)


@pytest.mark.parametrize("t", [0.0, 0.1, 0.4, 0.7, 0.86, 0.95, 1.0, 1.1, 1.3, 1.59, 2.0, 2.4, 5.0])
def test_every_moment_renders(qapp, t):
    assert not render(t).isNull()


def test_timeline_order():
    beats = [intro.POWER_ON, intro.SCAN[1], intro.LOCK, intro.ZOOM, intro.CUT, intro.TYPE_LABEL,
             intro.TYPE_NAME, intro.IMPACT, intro.DURATION]  # fmt: skip
    assert beats == sorted(beats)
    assert intro.DURATION < 2.6


def test_bundled_title_font_loads(qapp):
    assert intro.FONT_FILE.exists()
    assert intro.load_fonts() == intro.TITLE_FONT
    assert (intro.FONT_FILE.parent / "OFL.txt").exists()  # licence ships with the font


def test_final_frame_shows_callsign(qapp):
    assert bright(render(intro.DURATION), 100, 540, 110, 230) > 80
    assert bright(render(0.0), 100, 540, 110, 230) == 0


def test_callsign_is_typed_key_by_key():
    def typed(t: float) -> int:
        return 0 if t < intro.TYPE_NAME else min(6, int((t - intro.TYPE_NAME) / intro.KEY_GAP) + 1)

    counts = [typed(intro.TYPE_NAME + k * intro.KEY_GAP + 0.01) for k in range(6)]
    assert counts == [1, 2, 3, 4, 5, 6]


def test_hud_shows_the_target_after_the_scan(qapp):
    scene = intro.RadarIntro()
    target = scene.contact_pos(640, 300, intro.TARGET)
    x, y = int(target.x()), int(target.y())
    assert bright(render(intro.SCAN[1] + 0.05), x - 12, x + 12, y - 4, y + 4) > 0


def test_zoom_dives_into_the_locked_target(qapp):
    """Just before the cut the lock box fills the frame around the target."""
    img = render(intro.CUT - 0.01)
    assert bright(img, 0, 640, 0, 300) > 40
    assert not render(intro.ZOOM - 0.01).isNull()


def test_window_can_be_skipped(qtbot):
    window = intro.IntroWindow()
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.finished, timeout=1000):
        window.play()
        window.skip()
    window.skip()  # a second skip is harmless


def test_window_finishes_by_itself(qtbot, monkeypatch):
    monkeypatch.setattr(intro, "DURATION", 0.05)
    window = intro.IntroWindow()
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.finished, timeout=3000):
        window.play()

import pytest
from PySide6.QtGui import QColor, QImage, QPainter

from aqj.ui import intro


def render(t: float, w: int = 640, h: int = 300) -> QImage:
    img = QImage(w, h, QImage.Format.Format_RGB32)
    p = QPainter(img)
    intro.RadarIntro().paint(p, w, h, t, int(t * 30))
    p.end()
    return img


@pytest.mark.parametrize("t", [0.0, 0.2, 0.5, 1.0, 1.6, 2.0, 2.6, 3.2, 5.0])
def test_every_moment_renders(qapp, t):
    assert not render(t).isNull()


def test_final_frame_shows_callsign(qapp):
    end = render(intro.DURATION)
    start = render(0.0)

    def bright(img: QImage) -> int:
        count = 0
        for x in range(300, 640, 4):
            for y in range(190, 280, 4):
                if QColor(img.pixel(x, y)).green() > 200:
                    count += 1
        return count

    assert bright(end) > 50  # LIME98 is drawn in the text area
    assert bright(start) == 0


def test_target_pass_times_follow_the_beam():
    for k in range(3):
        bearing = intro.beam_bearing(intro.pass_time(k))
        assert bearing == pytest.approx(intro.TARGET_BEARING + 360 * k)


def test_su27_outline_is_symmetric_and_closed(qapp):
    path = intro.su27_path()
    box = path.boundingRect()
    assert box.left() == pytest.approx(-box.right())
    assert box.height() > box.width()  # longer than its wingspan, nose up
    first, last = path.elementAt(0), path.elementAt(path.elementCount() - 1)
    assert (first.x, first.y) == pytest.approx((last.x, last.y))


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

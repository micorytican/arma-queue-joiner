import pytest
from PySide6.QtCore import QLineF
from PySide6.QtGui import QColor, QImage, QPainter

from aqj.ui import intro


def render(t: float, w: int = 640, h: int = 300) -> QImage:
    img = QImage(w, h, QImage.Format.Format_RGB32)
    p = QPainter(img)
    intro.RadarIntro().paint(p, w, h, t, int(t * 30))
    p.end()
    return img


def bright(img: QImage, x0: int, x1: int, y0: int, y1: int) -> int:
    return sum(1 for x in range(x0, x1, 4) for y in range(y0, y1, 4) if QColor(img.pixel(x, y)).green() > 200)


@pytest.mark.parametrize("t", [0.0, 0.1, 0.4, 0.7, 0.78, 0.85, 1.1, 1.5, 1.58, 1.62, 2.0, 2.6, 5.0])
def test_every_moment_renders(qapp, t):
    assert not render(t).isNull()


def test_timeline_order():
    assert 0 < intro.POWER_ON < intro.SCAN[1] < intro.LOCK < intro.IMPACT < intro.DURATION <= 3.0


def test_final_frame_shows_callsign_in_the_middle(qapp):
    assert bright(render(intro.DURATION), 140, 500, 100, 200) > 80
    assert bright(render(0.0), 140, 500, 100, 200) == 0


def test_hud_shows_contacts_after_the_scan(qapp):
    w, h = 640, 300
    scene = intro.RadarIntro()
    target = scene.contact_pos(w, h, intro.TARGET)
    img = render(intro.SCAN[1] + 0.05)
    x, y = int(target.x()), int(target.y())
    assert bright(img, x - 12, x + 12, y - 4, y + 4) > 0


def projected_length(scene: intro.RadarIntro, u: float, w: int = 640, h: int = 300) -> float:
    cam = intro.Camera(w, h)
    pose = scene.jet_pose(w, h, u)
    nose = cam.project(intro.place((0, 0.5, 0), pose))
    tail = cam.project(intro.place((0, -0.5, 0), pose))
    assert nose is not None and tail is not None
    return QLineF(nose, tail).length()


def test_jet_starts_at_the_locked_contact_and_grows(qapp):
    w, h = 640, 300
    scene = intro.RadarIntro()
    start = intro.Camera(w, h).project(scene.jet_pose(w, h, 0.0).position)
    target = scene.contact_pos(w, h, intro.TARGET)
    assert start is not None
    assert abs(start.x() - target.x()) < 1 and abs(start.y() - target.y()) < 1
    sizes = [projected_length(scene, u) for u in (0.0, 0.3, 0.6, 0.9, 0.99)]
    assert sizes == sorted(sizes)
    assert sizes[0] < 60 < 300 < sizes[-1]


def test_jet_is_seen_in_three_quarter_view(qapp):
    """The wing must not collapse into a line: span on screen stays a good share of length."""
    w, h = 640, 300
    scene = intro.RadarIntro()
    cam = intro.Camera(w, h)
    pose = scene.jet_pose(w, h, 0.5)
    left = cam.project(intro.place((-0.338, -0.2, 0), pose))
    right = cam.project(intro.place((0.338, -0.2, 0), pose))
    assert left is not None and right is not None
    assert QLineF(left, right).length() > 0.3 * projected_length(scene, 0.5)


def test_su27_planform_is_symmetric():
    points = intro.su27_planform()
    xs = [x for x, _ in points]
    assert min(xs) == pytest.approx(-max(xs))
    ys = [y for _, y in points]
    assert max(ys) - min(ys) > max(xs) - min(xs)  # longer than its wingspan


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

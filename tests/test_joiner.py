import threading
import time
from contextlib import contextmanager

from aqj.detection import DialogReading
from aqj.hotkeys import vk_for
from aqj.joiner import Joiner, JoinerConfig, State

FULL = DialogReading(0.0, 0.01)
QUEUE = DialogReading(0.05, 0.0)
EMPTY = DialogReading(0.0, 0.0)

FAST = JoinerConfig(
    wait_after_click=0.0,
    connect_timeout=0.05,
    start_delay=0.0,
    double_click_gap=0.0,
    poll_interval=0.005,
    queue_confirm=0.05,
)


class FakeVision:
    def __init__(self, script, esc=None):
        self.script = list(script)
        self.esc = esc

    def read_dialog(self):
        return self.script.pop(0) if len(self.script) > 1 else self.script[0]

    def find_esc(self):
        return self.esc


class FakeInputs:
    def __init__(self, target=(500, 400)):
        self.clicks = []
        self.escapes = 0
        self.cursor = target

    def click(self, x, y):
        self.clicks.append((x, y))
        self.cursor = (x, y)

    def press_escape(self, hold):
        self.escapes += 1

    def cursor_pos(self):
        return self.cursor


class FakeGuard:
    def __init__(self, focused=True):
        self.focused = focused

    def is_game_focused(self):
        return self.focused


class Recorder:
    def __init__(self):
        self.states, self.logs, self.attempts = [], [], []

    def on_state(self, state, detail):
        self.states.append((state, detail))

    def on_attempt(self, n):
        self.attempts.append(n)

    def on_log(self, message):
        self.logs.append(message)


def make(vision, inputs=None, guard=None):
    rec = Recorder()

    @contextmanager
    def factory(x, y):
        yield vision

    joiner = Joiner(factory, inputs or FakeInputs(), guard or FakeGuard(), rec)
    return joiner, rec


def test_retries_until_queue_then_succeeds():
    vision = FakeVision([FULL, FULL, QUEUE])
    inputs = FakeInputs()
    joiner, rec = make(vision, inputs)
    assert joiner.run((500, 400), FAST) is State.SUCCESS
    assert inputs.escapes == 2
    assert rec.attempts == [1, 2, 3]
    assert len(inputs.clicks) == 6  # double click per attempt
    assert rec.states[-1][0] is State.SUCCESS
    assert rec.states[-1][1].params == {"n": 3}


def test_queue_that_disappears_is_closed_and_retried():
    vision = FakeVision([QUEUE, EMPTY, QUEUE])
    inputs = FakeInputs()
    joiner, rec = make(vision, inputs)
    assert joiner.run((500, 400), FAST) is State.SUCCESS
    assert inputs.escapes == 1
    assert any(m.key == "log.queue_lost" for m in rec.logs)


def test_fast_esc_clicks_button_when_found():
    vision = FakeVision([FULL, QUEUE], esc=(100, 900))
    inputs = FakeInputs()
    joiner, _ = make(vision, inputs)
    cfg = JoinerConfig(**{**FAST.__dict__, "fast_esc": True})
    assert joiner.run((500, 400), cfg) is State.SUCCESS
    assert (100, 900) in inputs.clicks
    assert inputs.escapes == 0


def test_fast_esc_falls_back_to_key():
    vision = FakeVision([FULL, QUEUE], esc=None)
    inputs = FakeInputs()
    joiner, rec = make(vision, inputs)
    cfg = JoinerConfig(**{**FAST.__dict__, "fast_esc": True})
    joiner.run((500, 400), cfg)
    assert inputs.escapes == 1
    assert any(m.key == "log.esc_not_found" for m in rec.logs)


def test_moving_the_mouse_stops():
    inputs = FakeInputs()
    inputs.cursor = (0, 0)  # user moved away before the first click
    joiner, rec = make(FakeVision([FULL]), inputs)
    assert joiner.run((500, 400), FAST) is State.IDLE
    assert inputs.clicks == []
    assert rec.states[-1][1].key == "state.stopped_mouse"


def test_waits_while_game_not_focused():
    guard = FakeGuard(focused=False)
    joiner, rec = make(FakeVision([QUEUE]), FakeInputs(), guard)
    joiner.start((500, 400), FAST)
    time.sleep(0.2)
    assert any(s is State.PAUSED for s, _ in rec.states)
    assert rec.attempts == []
    guard.focused = True
    joiner.join(3)
    assert rec.states[-1][0] is State.SUCCESS


def test_stop_is_fast():
    joiner, rec = make(FakeVision([FULL]))
    cfg = JoinerConfig(**{**FAST.__dict__, "pause_before_retry": 5.0})
    joiner.start((500, 400), cfg)
    time.sleep(0.05)
    t0 = time.monotonic()
    joiner.stop()
    joiner.join(2)
    assert time.monotonic() - t0 < 0.3
    assert rec.states[-1][0] is State.IDLE


def test_crash_is_reported_as_error():
    class Boom(FakeVision):
        def read_dialog(self):
            raise RuntimeError("capture failed")

    joiner, rec = make(Boom([EMPTY]))
    assert joiner.run((500, 400), FAST) is State.ERROR
    assert rec.states[-1][0] is State.ERROR
    assert rec.states[-1][1].params == {"error": "capture failed"}


def test_cannot_start_twice():
    joiner, _ = make(FakeVision([EMPTY]))
    cfg = JoinerConfig(**{**FAST.__dict__, "connect_timeout": 1.0})
    assert joiner.start((500, 400), cfg)
    assert not joiner.start((500, 400), cfg)
    joiner.stop()
    joiner.join(2)


def test_hotkey_codes():
    assert vk_for("F1") == 0x70
    assert vk_for("F12") == 0x7B
    for bad in ("F0", "F25", "A", "Ctrl"):
        try:
            vk_for(bad)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_thread_safety_smoke():
    """Many quick start/stop cycles must never leave a thread behind."""
    joiner, _ = make(FakeVision([FULL]))
    for _ in range(20):
        joiner.start((500, 400), FAST)
        joiner.stop()
        joiner.join(2)
    assert not joiner.running
    assert threading.active_count() < 10


def test_returning_with_the_mouse_resumes_instead_of_stopping():
    guard = FakeGuard(focused=False)
    inputs = FakeInputs()
    joiner, rec = make(FakeVision([QUEUE]), inputs, guard)
    joiner.start((500, 400), FAST)
    time.sleep(0.2)
    inputs.cursor = (5, 5)  # user clicked another window, then clicks back into the game
    guard.focused = True
    joiner.join(3)
    assert rec.states[-1][0] is State.SUCCESS


def test_blocked_input_is_explained():
    from aqj.joiner import InputBlockedError

    class Blocked(FakeInputs):
        def click(self, x, y):
            raise InputBlockedError("blocked")

    joiner, rec = make(FakeVision([EMPTY]), Blocked())
    assert joiner.run((500, 400), FAST) is State.ERROR
    assert rec.states[-1][1].key == "state.input_blocked"

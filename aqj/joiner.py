"""The join loop: click Join, read the result, close the dialog, repeat.

The loop talks to the outside world only through small interfaces (Vision,
Inputs, FocusGuard, Listener), so it can be tested without a game. It reports
progress as message keys plus parameters; the UI turns them into text in the
user's language.
"""

from __future__ import annotations

import enum
import math
import threading
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Any, Protocol

from .detection import DialogReading


class InputBlockedError(OSError):
    """Windows refused to send input (the game runs with higher rights)."""


class State(enum.Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"  # waiting for the game window to be active again
    SUCCESS = "success"
    ERROR = "error"


class Outcome(enum.Enum):
    SERVER_FULL = "full"
    QUEUE = "queue"
    NOTHING = "nothing"
    STOPPED = "stopped"


@dataclass(frozen=True)
class Message:
    """A translatable message: an i18n key and its parameters."""

    key: str
    params: dict[str, Any] = field(default_factory=dict)


def msg(key: str, **params: Any) -> Message:
    return Message(key, params)


class Vision(Protocol):
    def read_dialog(self) -> DialogReading: ...
    def find_esc(self) -> tuple[int, int] | None: ...


class Inputs(Protocol):
    def click(self, x: int, y: int) -> None: ...
    def press_escape(self, hold: float) -> None: ...
    def cursor_pos(self) -> tuple[int, int]: ...


class FocusGuard(Protocol):
    def is_game_focused(self) -> bool: ...


class Listener(Protocol):
    """Called from the worker thread. Implementations must be thread-safe."""

    def on_state(self, state: State, detail: Message) -> None: ...
    def on_attempt(self, attempt: int) -> None: ...
    def on_log(self, message: Message) -> None: ...


@dataclass(frozen=True)
class JoinerConfig:
    wait_after_click: float = 0.1
    escape_hold: float = 0.1
    pause_before_retry: float = 0.0
    connect_timeout: float = 8.0
    fast_esc: bool = False
    require_game_focus: bool = True
    stop_on_mouse_move: bool = True
    # Internal timings, overridable in tests
    start_delay: float = 0.3
    double_click_gap: float = 0.1
    poll_interval: float = 0.1
    queue_confirm: float = 3.0
    mouse_tolerance: int = 25


VisionFactory = Callable[[int, int], AbstractContextManager[Vision]]


class Joiner:
    def __init__(
        self,
        vision_factory: VisionFactory,
        inputs: Inputs,
        guard: FocusGuard,
        listener: Listener,
    ):
        self._vision_factory = vision_factory
        self._inputs = inputs
        self._guard = guard
        self._listener = listener
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.attempt = 0
        self._expected_cursor: tuple[int, int] | None = None

    # ── Control (any thread) ────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, target: tuple[int, int], config: JoinerConfig) -> bool:
        with self._lock:
            if self.running:
                return False
            self._stop.clear()
            self._thread = threading.Thread(
                target=self.run, args=(target, config), name="joiner", daemon=True
            )
            self._thread.start()
            return True

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    # ── Worker ──────────────────────────────────────────────────────────────

    def run(self, target: tuple[int, int], cfg: JoinerConfig) -> State:
        """Run the loop on the calling thread and return the final state."""
        self.attempt = 0
        try:
            with self._vision_factory(*target) as vision:
                final, detail = self._loop(vision, target, cfg)
        except InputBlockedError:
            final, detail = State.ERROR, msg("state.input_blocked")
            self._listener.on_log(msg("log.error", error="SendInput blocked"))
        except Exception as exc:  # report every crash instead of dying silently
            error = str(exc) or exc.__class__.__name__
            final, detail = State.ERROR, msg("state.error", error=error)
            self._listener.on_log(msg("log.error", error=error))
        self._listener.on_state(final, detail)
        return final

    def _loop(self, vision: Vision, target: tuple[int, int], cfg: JoinerConfig) -> tuple[State, Message]:
        stopped = msg("state.stopped")
        self._listener.on_log(msg("log.target", x=target[0], y=target[1]))
        self._listener.on_state(State.RUNNING, msg("state.starting"))
        self._expected_cursor = target
        if self._wait(cfg.start_delay):
            return State.IDLE, stopped

        while not self._stop.is_set():
            blocked = self._wait_until_ready(cfg)
            if blocked is not None:
                return State.IDLE, blocked

            self.attempt += 1
            n = self.attempt
            self._listener.on_attempt(n)
            self._listener.on_state(State.RUNNING, msg("state.clicking"))
            self._inputs.click(*target)
            if self._wait(cfg.double_click_gap):
                break
            self._inputs.click(*target)
            self._expected_cursor = target

            outcome = self._watch(vision, cfg)
            if outcome is Outcome.STOPPED:
                break

            if outcome is Outcome.SERVER_FULL:
                self._listener.on_log(msg("log.server_full", n=n))
                self._listener.on_state(State.RUNNING, msg("state.server_full"))
                self._close_dialog(vision, cfg)
            elif outcome is Outcome.QUEUE:
                self._listener.on_state(State.RUNNING, msg("state.confirming"))
                if self._confirm_queue(vision, cfg):
                    self._listener.on_log(msg("log.in_queue", n=n))
                    return State.SUCCESS, msg("state.success", n=n)
                if self._stop.is_set():
                    break
                self._listener.on_log(msg("log.queue_lost", n=n))
                self._close_dialog(vision, cfg)
            else:
                self._listener.on_log(msg("log.no_dialog", n=n))

            if self._wait(cfg.pause_before_retry):
                break

        return State.IDLE, stopped

    # ── Steps ───────────────────────────────────────────────────────────────

    def _wait(self, seconds: float) -> bool:
        """Sleep, waking instantly on stop. Returns True if stopped."""
        return self._stop.wait(max(0.0, seconds))

    def _mouse_moved(self, cfg: JoinerConfig) -> bool:
        if not cfg.stop_on_mouse_move or self._expected_cursor is None:
            return False
        x, y = self._inputs.cursor_pos()
        ex, ey = self._expected_cursor
        return math.hypot(x - ex, y - ey) > cfg.mouse_tolerance

    def _wait_until_ready(self, cfg: JoinerConfig) -> Message | None:
        """Hold while the game is not active. Returns a reason if we must stop."""
        paused = False
        while True:
            if self._stop.is_set():
                return msg("state.stopped")
            if not paused and self._mouse_moved(cfg):
                self._listener.on_log(msg("log.mouse_moved"))
                return msg("state.stopped_mouse")
            if not cfg.require_game_focus or self._guard.is_game_focused():
                if paused:
                    self._listener.on_log(msg("log.focus_back"))
                return None
            if not paused:
                paused = True
                self._listener.on_log(msg("log.waiting_focus"))
                self._listener.on_state(State.PAUSED, msg("state.waiting_focus"))
            if self._wait(0.5):
                return msg("state.stopped")

    def _watch(self, vision: Vision, cfg: JoinerConfig) -> Outcome:
        """Poll the dialog area until it shows 'server full' or the queue."""
        deadline = time.monotonic() + cfg.wait_after_click + cfg.connect_timeout
        while True:
            reading = vision.read_dialog()
            if reading.server_full:
                return Outcome.SERVER_FULL
            if reading.in_queue:
                return Outcome.QUEUE
            if time.monotonic() >= deadline:
                return Outcome.NOTHING
            if self._wait(cfg.poll_interval):
                return Outcome.STOPPED

    def _confirm_queue(self, vision: Vision, cfg: JoinerConfig) -> bool:
        """The queue text must stay visible for queue_confirm seconds."""
        deadline = time.monotonic() + cfg.queue_confirm
        while time.monotonic() < deadline:
            if self._wait(cfg.poll_interval * 5):
                return False
            if not vision.read_dialog().in_queue:
                return False
        return True

    def _close_dialog(self, vision: Vision, cfg: JoinerConfig) -> None:
        if cfg.fast_esc:
            pos = vision.find_esc()
            if pos is not None:
                self._inputs.click(*pos)
                self._expected_cursor = pos
                self._wait(0.05)
                return
            self._listener.on_log(msg("log.esc_not_found"))
        self._inputs.press_escape(cfg.escape_hold)

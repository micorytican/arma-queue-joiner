"""The join loop: click JOIN, read the result, close the dialog, repeat.

The loop talks to the outside world only through small interfaces (Vision,
Inputs, FocusGuard, Listener), so it can be tested without a game.
"""

from __future__ import annotations

import enum
import math
import threading
import time
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol
from collections.abc import Callable

from .detection import DialogReading


class State(enum.Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"      # waiting for the game window to be active again
    SUCCESS = "success"
    ERROR = "error"


class Outcome(enum.Enum):
    SERVER_FULL = "full"
    QUEUE = "queue"
    NOTHING = "nothing"
    STOPPED = "stopped"


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

    def on_state(self, state: State, detail: str) -> None: ...
    def on_attempt(self, attempt: int) -> None: ...
    def on_log(self, message: str) -> None: ...


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
        final = State.IDLE
        detail = "Stopped"
        try:
            with self._vision_factory(*target) as vision:
                final, detail = self._loop(vision, target, cfg)
        except Exception as exc:  # report every crash instead of dying silently
            final, detail = State.ERROR, str(exc) or exc.__class__.__name__
            self._listener.on_log(f"Error: {detail}")
        self._listener.on_state(final, detail)
        return final

    def _loop(self, vision: Vision, target: tuple[int, int], cfg: JoinerConfig) -> tuple[State, str]:
        self._listener.on_log(f"Join button at {target[0]}, {target[1]}")
        self._listener.on_state(State.RUNNING, "Starting")
        self._expected_cursor = target
        if self._wait(cfg.start_delay):
            return State.IDLE, "Stopped"

        while not self._stop.is_set():
            blocked = self._wait_until_ready(cfg)
            if blocked:
                return State.IDLE, blocked

            self.attempt += 1
            self._listener.on_attempt(self.attempt)
            self._listener.on_state(State.RUNNING, "Clicking Join")
            self._inputs.click(*target)
            if self._wait(cfg.double_click_gap):
                break
            self._inputs.click(*target)
            self._expected_cursor = target

            outcome = self._watch(vision, cfg)
            if outcome is Outcome.STOPPED:
                break

            if outcome is Outcome.SERVER_FULL:
                self._listener.on_log(f"#{self.attempt} Server full, closing dialog")
                self._listener.on_state(State.RUNNING, "Server full, retrying")
                self._close_dialog(vision, cfg)
            elif outcome is Outcome.QUEUE:
                self._listener.on_state(State.RUNNING, "Queue screen found, confirming")
                if self._confirm_queue(vision, cfg):
                    self._listener.on_log(f"#{self.attempt} In queue")
                    return State.SUCCESS, f"Got in after {self.attempt} attempt" + ("" if self.attempt == 1 else "s")
                if self._stop.is_set():
                    break
                self._listener.on_log(f"#{self.attempt} Queue screen disappeared, closing")
                self._close_dialog(vision, cfg)
            else:
                self._listener.on_log(f"#{self.attempt} No dialog appeared, retrying")

            if self._wait(cfg.pause_before_retry):
                break

        return State.IDLE, "Stopped"

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

    def _wait_until_ready(self, cfg: JoinerConfig) -> str | None:
        """Hold while the game is not active. Returns a reason if we must stop."""
        paused = False
        while True:
            if self._stop.is_set():
                return "Stopped"
            if self._mouse_moved(cfg):
                self._listener.on_log("You moved the mouse, stopped so you can take over")
                return "Stopped because you moved the mouse"
            if not cfg.require_game_focus or self._guard.is_game_focused():
                if paused:
                    self._listener.on_log("Arma Reforger is active again, resuming")
                return None
            if not paused:
                paused = True
                self._listener.on_log("Arma Reforger is not the active window, waiting")
                self._listener.on_state(State.PAUSED, "Waiting for the Arma Reforger window")
            if self._wait(0.5):
                return "Stopped"

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
            self._listener.on_log("ESC button not found on screen, pressing the key")
        self._inputs.press_escape(cfg.escape_hold)

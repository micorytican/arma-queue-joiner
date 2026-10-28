"""Follows Arma Reforger's own console.log to see what happens after the queue.

The game writes every join step to
Documents\\My Games\\ArmaReforger\\logs\\logs_<date>_<time>\\console.log.
Lines we rely on (taken from real logs, game 1.x):

    BACKEND (E): [RestApi] ... apiCode="JoinQueueIsFull" ...   join refused, queue full
    ... JoiningDialogs.conf, tag: SERVER_FULL ...                 "server full" dialog shown
    BACKEND (E): Join Queue no longer exist!                      dropped out of the queue
    ... JoiningDialogs.conf, tag: JOIN_FAILED ...                 join failed
    BACKEND      : Server Join Data:                              queue passed, joining
     BACKEND      : Server Name:    '<name>'                      the server being joined
    DEFAULT      : Entered online game state.                     in the game
    RPL          : Replication terminated.                        left the server

The file is only read, never changed. Everything here is pure Python and
works on any folder, so it is tested with recorded log lines.
"""

from __future__ import annotations

import ctypes
import enum
import re
from dataclasses import dataclass, field
from pathlib import Path


class GameEvent(enum.Enum):
    SERVER_FULL = "server_full"
    QUEUE_LOST = "queue_lost"
    JOIN_FAILED = "join_failed"
    JOINING = "joining"  # the queue let us in; data: server name
    IN_GAME = "in_game"
    LEFT = "left"


_PATTERNS: list[tuple[GameEvent, re.Pattern[str]]] = [
    (GameEvent.SERVER_FULL, re.compile(r"JoiningDialogs\.conf, tag: SERVER_FULL\b")),
    (GameEvent.QUEUE_LOST, re.compile(r"Join Queue no longer exist|apiCode=\"JoinQueueNotFound\"")),
    (GameEvent.JOIN_FAILED, re.compile(r"JoiningDialogs\.conf, tag: JOIN_FAILED\b")),
    (GameEvent.JOINING, re.compile(r"BACKEND\s+: Server Join Data:")),
    (GameEvent.IN_GAME, re.compile(r"Entered online game state\.")),
    (GameEvent.LEFT, re.compile(r"RPL\s+: Replication terminated\.")),
]
_SERVER_NAME = re.compile(r"BACKEND\s+: Server Name:\s+'(.*)'\s*$")


@dataclass(frozen=True)
class LogLine:
    event: GameEvent
    detail: str = ""


def parse_line(line: str) -> LogLine | None:
    for event, pattern in _PATTERNS:
        if pattern.search(line):
            return LogLine(event)
    return None


def documents_dir() -> Path:
    """The user's Documents folder, following OneDrive or other redirections."""
    try:
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD), ("d3", wintypes.WORD),
                        ("d4", ctypes.c_ubyte * 8)]  # fmt: skip

        folderid_documents = GUID(
            0xFDD39AD0, 0x238F, 0x46AF, (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7)
        )
        out = ctypes.c_wchar_p()
        shell32 = ctypes.WinDLL("shell32")
        if shell32.SHGetKnownFolderPath(ctypes.byref(folderid_documents), 0, None, ctypes.byref(out)) == 0:
            try:
                return Path(out.value or "")
            finally:
                ctypes.windll.ole32.CoTaskMemFree(out)
    except (AttributeError, OSError):
        pass
    return Path.home() / "Documents"


def default_logs_dir() -> Path:
    return documents_dir() / "My Games" / "ArmaReforger" / "logs"


def latest_console_log(logs_dir: Path) -> Path | None:
    """console.log of the newest game session, if any."""
    try:
        sessions = [d for d in logs_dir.iterdir() if d.is_dir() and d.name.startswith("logs_")]
    except OSError:
        return None
    for session in sorted(sessions, key=lambda d: d.name, reverse=True):
        log = session / "console.log"
        if log.is_file():
            return log
    return None


@dataclass
class LogFollower:
    """Reads only the lines added since the last poll, like `tail -f`.

    Starts at the current end of the newest log, so old sessions never
    trigger anything. Switches to a newer session folder when the game
    is restarted.
    """

    logs_dir: Path
    path: Path | None = None
    _offset: int = 0
    _partial: str = ""
    _pending_name: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        self.path = latest_console_log(self.logs_dir)
        self._offset = self._size(self.path)

    @staticmethod
    def _size(path: Path | None) -> int:
        try:
            return path.stat().st_size if path else 0
        except OSError:
            return 0

    def poll(self) -> list[LogLine]:
        newest = latest_console_log(self.logs_dir)
        if newest is not None and newest != self.path:
            self.path, self._offset, self._partial = newest, 0, ""
        if self.path is None:
            return []
        try:
            size = self.path.stat().st_size
            if size < self._offset:  # file was replaced
                self._offset, self._partial = 0, ""
            if size == self._offset:
                return []
            with self.path.open("rb") as f:
                f.seek(self._offset)
                chunk = f.read(size - self._offset)
            self._offset = size
        except OSError:
            return []

        text = self._partial + chunk.decode("utf-8", errors="replace")
        lines = text.split("\n")
        self._partial = lines.pop()  # an unfinished last line waits for the next poll
        events: list[LogLine] = []
        for raw in lines:
            line = raw.rstrip("\r")
            if self._pending_name:
                match = _SERVER_NAME.search(line)
                if match:
                    named = LogLine(GameEvent.JOINING, match.group(1))
                    if events and events[-1].event is GameEvent.JOINING:
                        events[-1] = named
                    else:  # "Server Join Data" came in the previous poll
                        events.append(named)
                    self._pending_name = False
                    continue
            parsed = parse_line(line)
            if parsed is None:
                continue
            events.append(parsed)
            self._pending_name = parsed.event is GameEvent.JOINING
        return events


class Stage(enum.Enum):
    QUEUED = "queued"
    JOINING = "joining"
    IN_GAME = "in_game"
    QUEUE_LOST = "queue_lost"


@dataclass
class QueueWatch:
    """Turns log events into the stages after the queue: queued, joining, in game.

    `update` returns the stage when it changes, otherwise None.
    """

    follower: LogFollower
    stage: Stage = Stage.QUEUED
    server: str = ""

    def update(self) -> Stage | None:
        changed: Stage | None = None
        for line in self.follower.poll():
            new = self._next(line)
            if new is not None and new is not self.stage:
                self.stage = changed = new
        return changed

    def _next(self, line: LogLine) -> Stage | None:
        if line.event is GameEvent.JOINING:
            self.server = line.detail or self.server
            return Stage.JOINING
        if line.event is GameEvent.IN_GAME and self.stage in (Stage.QUEUED, Stage.JOINING):
            return Stage.IN_GAME
        if line.event in (GameEvent.QUEUE_LOST, GameEvent.JOIN_FAILED) and self.stage is Stage.QUEUED:
            return Stage.QUEUE_LOST
        return None

    @property
    def finished(self) -> bool:
        return self.stage in (Stage.IN_GAME, Stage.QUEUE_LOST)

"""Game log follower. Sample lines are copied from real Arma Reforger console.log
files (server IDs, IPs and request IDs removed)."""

from pathlib import Path

import pytest

from aqj.gamelog import GameEvent, LogFollower, QueueWatch, Stage, latest_console_log, parse_line

FULL = (
    "21:11:54.318 SCRIPT       : [SCR_ConfigurableDialogUi] presetsResourceName: "
    "{471EFCF445C3E9C6}Configs/ServerBrowser/JoiningDialogs.conf, tag: SERVER_FULL, "
    "customDialogObj: SCR_ServerFullDialog<0x000002CC7F3D3B50>"
)
QUEUE_FULL_API = (
    "21:11:54.293 BACKEND   (E): [RestApi] ID:[480] TYPE:[LobbyClient/RoomsJoin] ENV:[production] "
    'Error Code:400 - Bad Request, apiCode="JoinQueueIsFull", uid="x", '
    'message="Reached join queue maxSize 25"'
)
JOIN_TAG = (
    "12:00:58.016 SCRIPT       : [SCR_ConfigurableDialogUi] presetsResourceName: "
    "{471EFCF445C3E9C6}Configs/ServerBrowser/JoiningDialogs.conf, tag: JOIN, customDialogObj: NULL"
)
JOIN_DATA = "12:09:18.617 BACKEND      : Server Join Data:"
SERVER_ID = "12:09:18.618  BACKEND      : Server ID:      'df14d9aa-0000-0000-0000-000000000000'"
SERVER_NAME = (
    "12:09:18.618  BACKEND      : Server Name:    '[EU] Conflict in Europe #6 (CIE) | Hardcore UA-RU | 1pp'"
)
IN_GAME = "12:09:31.155 DEFAULT      : Entered online game state."
LEFT = "12:19:45.156 RPL          : Replication terminated."
QUEUE_GONE = "18:57:47.816 BACKEND   (E): Join Queue no longer exist!"
JOIN_FAILED = (
    "18:57:47.834 SCRIPT       : [SCR_ConfigurableDialogUi] presetsResourceName: "
    "{471EFCF445C3E9C6}Configs/ServerBrowser/JoiningDialogs.conf, tag: JOIN_FAILED, customDialogObj: NULL"
)
NOISE = "12:09:23.448 PROFILING    : Entities load took: 731.556100 ms"


@pytest.mark.parametrize(
    "line, event",
    [
        (FULL, GameEvent.SERVER_FULL),
        (QUEUE_GONE, GameEvent.QUEUE_LOST),
        (JOIN_FAILED, GameEvent.JOIN_FAILED),
        (JOIN_DATA, GameEvent.JOINING),
        (IN_GAME, GameEvent.IN_GAME),
        (LEFT, GameEvent.LEFT),
    ],
)
def test_parse_known_lines(line, event):
    parsed = parse_line(line)
    assert parsed is not None and parsed.event is event


@pytest.mark.parametrize("line", [NOISE, JOIN_TAG, QUEUE_FULL_API, SERVER_ID, SERVER_NAME, ""])
def test_other_lines_are_ignored(line):
    assert parse_line(line) is None


def session(logs: Path, name: str, text: str = "") -> Path:
    folder = logs / name
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / "console.log"
    log.write_text(text, "utf-8")
    return log


def append(log: Path, *lines: str, newline: bool = True) -> None:
    with log.open("a", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(lines) + ("\r\n" if newline else ""))


def test_newest_session_wins(tmp_path):
    session(tmp_path, "logs_2026-10-05_18-51-42")
    newest = session(tmp_path, "logs_2026-10-17_11-47-07")
    (tmp_path / "unrelated").mkdir()
    assert latest_console_log(tmp_path) == newest
    assert latest_console_log(tmp_path / "missing") is None


def test_follower_ignores_what_was_there_before(tmp_path):
    log = session(tmp_path, "logs_2026-10-17_11-47-07", IN_GAME + "\r\n")
    follower = LogFollower(tmp_path)
    assert follower.poll() == []
    append(log, NOISE, IN_GAME)
    assert [e.event for e in follower.poll()] == [GameEvent.IN_GAME]
    assert follower.poll() == []


def test_follower_reads_the_server_name(tmp_path):
    log = session(tmp_path, "logs_2026-10-17_11-47-07")
    follower = LogFollower(tmp_path)
    append(log, JOIN_DATA, SERVER_ID, SERVER_NAME)
    (event,) = follower.poll()
    assert event.event is GameEvent.JOINING
    assert event.detail == "[EU] Conflict in Europe #6 (CIE) | Hardcore UA-RU | 1pp"


def test_server_name_in_a_later_poll(tmp_path):
    log = session(tmp_path, "logs_2026-10-17_11-47-07")
    watch = QueueWatch(LogFollower(tmp_path))
    append(log, JOIN_DATA)
    assert watch.update() is Stage.JOINING and watch.server == ""
    append(log, SERVER_ID, SERVER_NAME)
    assert watch.update() is None
    assert watch.server.startswith("[EU] Conflict in Europe")


def test_follower_waits_for_unfinished_lines(tmp_path):
    log = session(tmp_path, "logs_2026-10-17_11-47-07")
    follower = LogFollower(tmp_path)
    append(log, "12:09:31.155 DEFAULT      : Entered online", newline=False)
    assert follower.poll() == []
    append(log, " game state.")
    assert [e.event for e in follower.poll()] == [GameEvent.IN_GAME]


def test_follower_moves_to_a_new_game_session(tmp_path):
    session(tmp_path, "logs_2026-10-17_11-47-07")
    follower = LogFollower(tmp_path)
    newer = session(tmp_path, "logs_2026-10-17_12-30-00", IN_GAME + "\r\n")
    assert [e.event for e in follower.poll()] == [GameEvent.IN_GAME]
    assert follower.path == newer


def test_follower_without_logs_is_quiet(tmp_path):
    follower = LogFollower(tmp_path / "nothing")
    assert follower.path is None
    assert follower.poll() == []


def test_queue_watch_full_journey(tmp_path):
    log = session(tmp_path, "logs_2026-10-17_11-47-07")
    watch = QueueWatch(LogFollower(tmp_path))
    assert watch.update() is None and watch.stage is Stage.QUEUED
    append(log, JOIN_DATA, SERVER_ID, SERVER_NAME, NOISE)
    assert watch.update() is Stage.JOINING
    assert watch.server.startswith("[EU] Conflict in Europe")
    append(log, IN_GAME)
    assert watch.update() is Stage.IN_GAME
    assert watch.finished


def test_queue_watch_in_game_without_join_data(tmp_path):
    log = session(tmp_path, "logs_2026-10-17_11-47-07")
    watch = QueueWatch(LogFollower(tmp_path))
    append(log, JOIN_DATA, IN_GAME)
    assert watch.update() is Stage.IN_GAME  # both in one poll: the last stage wins


def test_queue_watch_dropped_from_queue(tmp_path):
    log = session(tmp_path, "logs_2026-10-05_18-51-42")
    watch = QueueWatch(LogFollower(tmp_path))
    append(log, QUEUE_GONE, JOIN_FAILED)
    assert watch.update() is Stage.QUEUE_LOST
    assert watch.finished


def test_queue_lost_after_joining_is_ignored(tmp_path):
    log = session(tmp_path, "logs_2026-10-17_11-47-07")
    watch = QueueWatch(LogFollower(tmp_path))
    append(log, JOIN_DATA)
    watch.update()
    append(log, JOIN_FAILED)
    assert watch.update() is None and watch.stage is Stage.JOINING

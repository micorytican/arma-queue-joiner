import sys
import threading

import pytest

from aqj import logs


@pytest.fixture(autouse=True)
def detach_handlers():
    yield
    for handler in list(logs.log.handlers):
        logs.log.removeHandler(handler)
        handler.close()


def test_log_file_is_created(tmp_path):
    path = logs.setup_logging(tmp_path / "logs")
    logs.log.info("hello from test")
    for handler in logs.log.handlers:
        handler.flush()
    text = path.read_text("utf-8")
    assert "Arma Queue Joiner" in text
    assert "hello from test" in text


def test_crash_handler_logs_and_notifies(tmp_path, monkeypatch):
    path = logs.setup_logging(tmp_path / "logs")
    seen = []
    old_hook, old_thread_hook = sys.excepthook, threading.excepthook
    try:
        logs.install_crash_handler(seen.append)

        def boom():
            raise RuntimeError("worker exploded")

        t = threading.Thread(target=boom)
        t.start()
        t.join()
    finally:
        sys.excepthook, threading.excepthook = old_hook, old_thread_hook
    for handler in logs.log.handlers:
        handler.flush()
    assert seen == ["RuntimeError: worker exploded"]
    assert "worker exploded" in path.read_text("utf-8")


def test_default_log_dir_follows_appdata(isolated_appdata):
    assert logs.log_dir() == isolated_appdata / "ArmaQueueJoiner" / "logs"

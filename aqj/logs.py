"""Log file and crash reporting.

Logs go to %APPDATA%\\ArmaQueueJoiner\\logs\\aqj.log (rotated at 1 MB, 3 files
kept) so users can attach them to bug reports.
"""

from __future__ import annotations

import logging
import platform
import sys
import threading
import traceback
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

from . import __version__
from .settings import default_path

log = logging.getLogger("aqj")


def log_dir() -> Path:
    return default_path().parent / "logs"


def setup_logging(directory: Path | None = None) -> Path:
    """Attach a rotating file handler to the 'aqj' logger. Returns the log file path."""
    directory = directory or log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "aqj.log"
    for handler in list(log.handlers):
        log.removeHandler(handler)
        handler.close()
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(threadName)s: %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    log.info(
        "Arma Queue Joiner %s on Windows %s, Python %s",
        __version__,
        platform.version(),
        platform.python_version(),
    )
    return path


CrashCallback = Callable[[str], None]


def install_crash_handler(on_crash: CrashCallback | None = None) -> None:
    """Log every unhandled exception (main and worker threads) and notify the UI."""

    def report(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            return
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        log.critical("Unhandled exception\n%s", text)
        if on_crash is not None:
            try:
                on_crash(f"{exc_type.__name__}: {exc}")
            except Exception:  # the crash handler itself must never raise
                log.exception("Crash callback failed")

    def thread_hook(args: threading.ExceptHookArgs) -> None:
        if args.exc_value is not None:
            report(args.exc_type, args.exc_value, args.exc_traceback)

    sys.excepthook = report
    threading.excepthook = thread_hook

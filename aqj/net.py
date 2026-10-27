"""Small HTTP helpers. Kept in one place so tests can replace `urlopen`."""

from __future__ import annotations

import http.client
import json
import logging
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from . import __version__

USER_AGENT = f"ArmaQueueJoiner/{__version__} (+https://github.com/micorytican/arma-queue-joiner)"
TIMEOUT = 8.0

urlopen = urllib.request.urlopen  # replaced in tests


class NetError(OSError):
    """A request failed. The message is safe to show to the user."""


def request(
    url: str, data: bytes | None = None, headers: dict[str, str] | None = None, method: str | None = None
) -> bytes:
    req = urllib.request.Request(url, data=data, method=method or ("POST" if data is not None else "GET"))
    req.add_header("User-Agent", USER_AGENT)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urlopen(req, timeout=TIMEOUT) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise NetError(f"server answered {exc.code}") from exc
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise NetError(f"no connection ({reason})") from exc


def get_json(url: str, headers: dict[str, str] | None = None) -> Any:
    try:
        return json.loads(request(url, headers=headers))
    except ValueError as exc:
        raise NetError("unexpected answer from the server") from exc


def in_background(job: Callable[[], Any], on_done: Callable[[Any, Exception | None], None]) -> None:
    """Run `job` on a daemon thread and call on_done(result, error) from that thread."""

    def run() -> None:
        try:
            result = job()
        except Exception as exc:  # always report back, or the UI waits forever
            if not isinstance(exc, NetError | ValueError):
                logging.getLogger("aqj").exception("Background request failed")
            on_done(None, exc)
        else:
            on_done(result, None)

    threading.Thread(target=run, name="net", daemon=True).start()

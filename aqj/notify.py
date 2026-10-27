"""Alerts: a short beep pattern and optional phone push through ntfy.sh."""

from __future__ import annotations

import threading
import urllib.error
import urllib.request

NTFY_SERVER = "https://ntfy.sh"


def play_alert() -> None:
    """Three rising beeps, played off the UI thread."""

    def _beep() -> None:
        try:
            import winsound

            for freq in (880, 1100, 1320):
                winsound.Beep(freq, 180)
        except (ImportError, RuntimeError):
            pass

    threading.Thread(target=_beep, name="beep", daemon=True).start()


def send_ntfy(topic: str, title: str, message: str, timeout: float = 8.0) -> None:
    """Publish a push message. Raises OSError on failure."""
    if not topic:
        raise ValueError("Enter a topic name first")
    request = urllib.request.Request(
        f"{NTFY_SERVER}/{topic}",
        data=message.encode("utf-8"),
        method="POST",
        headers={"Title": title, "Priority": "high", "Tags": "video_game"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status >= 300:
            raise OSError(f"ntfy answered {response.status}")


def send_ntfy_async(topic: str, title: str, message: str, on_done=None) -> None:
    """Send in the background; on_done(error_or_None) is called from that thread."""

    def _run() -> None:
        error: Exception | None = None
        try:
            send_ntfy(topic, title, message)
        except (OSError, ValueError, urllib.error.URLError) as exc:
            error = exc
        if on_done is not None:
            on_done(error)

    threading.Thread(target=_run, name="ntfy", daemon=True).start()

"""Alerts when you are in the queue: sound, phone (ntfy) and Discord."""

from __future__ import annotations

import json
import re
import threading

from . import net

NTFY_SERVER = "https://ntfy.sh"
_DISCORD_HOOK = re.compile(r"^https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+$")


def play_alert() -> None:
    """Three rising beeps, played off the UI thread."""

    def beep() -> None:
        try:
            import winsound

            for freq in (880, 1100, 1320):
                winsound.Beep(freq, 180)
        except (ImportError, RuntimeError):
            pass

    threading.Thread(target=beep, name="beep", daemon=True).start()


def send_ntfy(topic: str, title: str, message: str) -> None:
    """Publish as JSON, which keeps non-Latin titles (e.g. Ukrainian) intact."""
    if not topic:
        raise ValueError("topic is empty")
    body = {"topic": topic, "title": title, "message": message, "priority": 4, "tags": ["video_game"]}
    net.request(
        NTFY_SERVER, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}
    )


def is_discord_webhook(url: str) -> bool:
    return bool(_DISCORD_HOOK.match(url.strip()))


def send_discord(webhook: str, message: str) -> None:
    if not is_discord_webhook(webhook):
        raise ValueError("not a Discord webhook link")
    body = json.dumps({"content": message, "username": "Queue Joiner"}).encode("utf-8")
    net.request(webhook.strip(), data=body, headers={"Content-Type": "application/json"})

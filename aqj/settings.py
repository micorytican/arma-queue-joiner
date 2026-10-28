"""User settings, stored as JSON in %APPDATA%\\ArmaQueueJoiner."""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path

from . import APP_ID

HOTKEYS = [f"F{i}" for i in range(1, 13)]
LANGUAGES = ("en", "uk")

# name: (minimum, maximum) for every number the user can type in
LIMITS: dict[str, tuple[float, float]] = {
    "wait_after_click": (0.05, 10.0),
    "escape_hold": (0.05, 5.0),
    "pause_before_retry": (0.0, 5.0),
    "connect_timeout": (2.0, 30.0),
}


def default_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / APP_ID / "settings.json"


@dataclasses.dataclass
class Settings:
    start_hotkey: str = "F6"
    stop_hotkey: str = "F4"

    wait_after_click: float = 0.1
    escape_hold: float = 0.1
    pause_before_retry: float = 0.0
    connect_timeout: float = 8.0

    fast_esc: bool = False
    require_game_focus: bool = True
    stop_on_mouse_move: bool = True

    notify_queue: bool = True  # alert when the queue screen shows
    notify_game: bool = True  # alert when the game has loaded the server
    sound: bool = True
    phone_notify: bool = False
    ntfy_topic: str = ""

    discord_notify: bool = False
    discord_webhook: str = ""

    always_on_top: bool = False
    close_to_tray: bool = True
    check_updates: bool = True
    language: str = ""  # "en" or "uk"; empty until the first start picks one

    def normalized(self) -> Settings:
        """Return a copy with every value forced into a valid range."""
        s = dataclasses.replace(self)
        for name, (lo, hi) in LIMITS.items():
            setattr(s, name, round(min(hi, max(lo, float(getattr(s, name)))), 2))
        if s.start_hotkey not in HOTKEYS:
            s.start_hotkey = "F6"
        if s.stop_hotkey not in HOTKEYS:
            s.stop_hotkey = "F4"
        if s.start_hotkey == s.stop_hotkey:
            s.stop_hotkey = next(k for k in ("F4", "F7", "F8") if k != s.start_hotkey)
        s.discord_webhook = s.discord_webhook.strip()[:300]
        if s.language not in LANGUAGES:
            s.language = ""  # also turns the old "system" value into a fresh pick
        s.ntfy_topic = "".join(ch for ch in s.ntfy_topic.strip() if ch.isalnum() or ch in "-_")[:64]
        return s

    @classmethod
    def from_dict(cls, data: dict) -> Settings:
        data = dict(data)
        # Keys used by v1.x
        if "experimental" in data and "fast_esc" not in data:
            data["fast_esc"] = data["experimental"]
        if "mute" in data and "sound" not in data:
            data["sound"] = not data["mute"]

        s = cls()
        for field in dataclasses.fields(cls):
            if field.name not in data:
                continue
            current = getattr(s, field.name)
            raw = data[field.name]
            try:
                if isinstance(current, bool):
                    if isinstance(raw, bool):
                        setattr(s, field.name, raw)
                elif isinstance(current, float):
                    setattr(s, field.name, float(raw))
                else:
                    setattr(s, field.name, str(raw))
            except (TypeError, ValueError):
                pass
        return s.normalized()

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        path = path or default_path()
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            return cls()
        return cls.from_dict(data) if isinstance(data, dict) else cls()

    def save(self, path: Path | None = None) -> None:
        """Write atomically so a crash can never leave a half-written file."""
        path = path or default_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(dataclasses.asdict(self.normalized()), indent=2), "utf-8")
        os.replace(tmp, path)

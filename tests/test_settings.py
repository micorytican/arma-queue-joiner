import json

from aqj.settings import Settings


def test_missing_file_gives_defaults(tmp_path):
    assert Settings.load(tmp_path / "nope.json") == Settings()


def test_round_trip(tmp_path):
    path = tmp_path / "sub" / "settings.json"
    s = Settings(wait_after_click=2.3, fast_esc=True, sound=False, ntfy_topic="abc-123")
    s.save(path)
    assert Settings.load(path) == s
    assert not path.with_suffix(".tmp").exists()


def test_corrupt_json_gives_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("not json {{", "utf-8")
    assert Settings.load(path) == Settings()


def test_v1_keys_are_migrated(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"experimental": True, "mute": True, "wait_after_click": 0.5}), "utf-8")
    s = Settings.load(path)
    assert s.fast_esc is True
    assert s.sound is False
    assert s.wait_after_click == 0.5


def test_values_are_clamped_and_types_checked():
    s = Settings.from_dict({"wait_after_click": 999, "escape_hold": -1, "sound": "yes", "connect_timeout": "x"})
    assert s.wait_after_click == 10.0
    assert s.escape_hold == 0.05
    assert s.sound is True          # a string is not a bool, default kept
    assert s.connect_timeout == 8.0


def test_same_hotkeys_are_fixed():
    s = Settings.from_dict({"start_hotkey": "F4", "stop_hotkey": "F4"})
    assert s.start_hotkey == "F4" and s.stop_hotkey != "F4"


def test_unknown_hotkey_falls_back():
    assert Settings.from_dict({"start_hotkey": "Ctrl+X"}).start_hotkey == "F6"


def test_topic_is_sanitized():
    assert Settings.from_dict({"ntfy_topic": "  my topic/../x?  "}).ntfy_topic == "mytopicx"

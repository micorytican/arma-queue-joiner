"""Window tests with pytest-qt. The join loop, hotkeys and screen are faked."""

import numpy as np
import pytest

from aqj import i18n
from aqj.joiner import State, msg
from aqj.settings import Settings
from aqj.ui import window as win


class FakeHotkeys:
    def __init__(self, on_hotkey, on_error):
        self.bound = {}

    def start(self):
        pass

    def bind(self, bindings):
        self.bound = dict(bindings)

    def shutdown(self):
        pass


class FakeJoiner:
    def __init__(self, *args):
        self.started = None
        self.stopped = False

    @property
    def running(self):
        return False

    def start(self, pos, config):
        self.started = (pos, config)
        return True

    def stop(self):
        self.stopped = True

    def join(self, timeout=None):
        pass


class FakeVision:
    monitor = {"left": 0, "top": 0, "width": 1920, "height": 1080}

    def __init__(self, x, y):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def retarget(self, x, y):
        pass

    def grab_dialog(self):
        arr = np.zeros((40, 80, 4), dtype=np.uint8)
        arr[...] = (40, 50, 200, 255)  # all red: reads as "server full"
        return arr

    def find_esc(self):
        return None


@pytest.fixture
def window(qtbot, monkeypatch):
    monkeypatch.setattr(win, "HotkeyListener", FakeHotkeys)
    monkeypatch.setattr(win, "Joiner", FakeJoiner)
    monkeypatch.setattr(win, "ScreenVision", FakeVision)
    monkeypatch.setattr(win.winapi, "get_cursor_pos", lambda: (640, 360))
    monkeypatch.setattr(
        win.winapi, "foreground_window_info", lambda: ("Arma Reforger", "ArmaReforgerSteam.exe")
    )
    monkeypatch.setattr(win.winapi, "flash_taskbar", lambda hwnd: None)
    monkeypatch.setattr(win.notify, "play_alert", lambda: None)
    w = win.MainWindow(win.QIcon(), Settings(language="en"))
    qtbot.addWidget(w)
    w.tray = None  # no tray balloons from tests
    yield w
    w._shutdown()
    i18n.set_language("en")


def test_opens_ready(window):
    assert window.status_title.text() == "Ready to join"
    assert "F6" in window.status_detail.text()
    assert window.hotkeys.bound == {"start": "F6", "stop": "F4"}


def test_countdown_can_be_cancelled(window, qtbot):
    window.action.click()
    assert window.status_title.text() == "Starting in 3"
    window.action.click()
    assert window.status_title.text() == "Ready to join"
    assert window.joiner.started is None


def test_countdown_starts_at_mouse_position(window, qtbot):
    window.action.click()
    qtbot.waitUntil(lambda: window.joiner.started is not None, timeout=5000)
    pos, config = window.joiner.started
    assert pos == (640, 360)
    assert config.require_game_focus is True


def test_hotkey_starts_and_stops(window):
    window._on_hotkey("start")
    assert window.joiner.started[0] == (640, 360)
    window._ui_state = "running"
    window._on_hotkey("stop")
    assert window.joiner.stopped


def test_states_render(window):
    window._started_at = 0.0
    window._on_state("running", msg("state.server_full"))
    assert window.status_title.text() == "Trying to join"
    assert "Server full" in window.status_detail.text()
    window._on_state("success", msg("state.success", n=4))
    assert window.status_title.text() == "You're in the queue"
    assert "4 attempts" in window.status_detail.text()
    assert window.action.text() == "Start again"
    window._on_state(State.ERROR.value, msg("state.error", error="capture failed"))
    assert "capture failed" in window.status_detail.text()


def test_settings_are_saved(window, isolated_appdata, qtbot):
    window.sw_sound.click()
    window.spins["connect_timeout"].setValue(12.5)
    window._save_settings()
    saved = Settings.load()
    assert saved.sound is False
    assert saved.connect_timeout == 12.5


def test_same_hotkeys_are_refused(window):
    window.combo_stop.setCurrentText("F6")
    assert not window.hotkey_note.isHidden()
    assert window.hotkey_note.text() == i18n.tr("set.keys_same")
    assert window.hotkeys.bound["stop"] == "F4"


def test_language_switch_rebuilds_pages(window):
    window.combo_lang.setCurrentIndex(window.combo_lang.findData("uk"))
    assert window.status_title.text() == "Можна починати"
    assert window.action.text() == "Почати"
    assert window.settings.language == "uk"


def test_activity_is_translated_on_switch(window):
    window._log(msg("log.server_full", n=1))
    assert "Server full" in window.activity_view.toPlainText()
    window.combo_lang.setCurrentIndex(window.combo_lang.findData("uk"))
    assert "Сервер заповнений" in window.activity_view.toPlainText()


def test_diagnostics_page(window):
    window.show_page(win.DIAGNOSTICS)
    assert "Arma Reforger detected" in window.diag_values["window"].text()
    assert window.diag_values["display"].text() == "1920 × 1080"
    assert window.diag_verdict.text() == "Reads as: server full"
    assert "ntfy_topic" not in window._last_report  # secrets stay out of the report
    window.show_page(win.MAIN)
    assert not window._diag_timer.isActive()


def test_invalid_discord_link_is_explained(window):
    window.sw_discord.setChecked(True)
    window.webhook_edit.setText("https://example.com/nope")
    window._send_test("Discord")
    assert "isn't a Discord webhook" in window.discord_note.text()


def test_update_banner(window):
    from aqj.updates import Release

    assert not window.update_bar.isVisibleTo(window)
    window._on_update_found(Release("9.9.9", "https://github.com/x"))
    assert window.update_bar.isVisibleTo(window)
    assert "9.9.9" in window.update_text.text()


def test_escape_goes_back(window, qtbot):
    window.show()
    window.activateWindow()
    qtbot.waitActive(window)
    window.show_page(win.SETTINGS)
    qtbot.keyClick(window.pages.currentWidget(), win.Qt.Key.Key_Escape)
    assert window.pages.currentIndex() == win.MAIN

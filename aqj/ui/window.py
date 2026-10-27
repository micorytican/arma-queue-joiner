"""Main window: status, start/stop, activity log and settings."""

from __future__ import annotations

import secrets
import time

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, REPO_URL, __version__, notify, winapi
from ..hotkeys import HotkeyListener
from ..joiner import Joiner, JoinerConfig, State
from ..screen import ScreenVision
from ..settings import HOTKEYS, LIMITS, Settings
from .widgets import KeyCap, StatusCard, SwitchRow, overline, rule

COUNTDOWN_SECONDS = 3


class Bridge(QObject):
    """Carries events from worker/hotkey threads to the UI thread (queued signals)."""

    state = Signal(str, str)
    attempt = Signal(int)
    log = Signal(str)
    hotkey = Signal(str)
    hotkey_error = Signal(str)
    ntfy_result = Signal(str)

    # Joiner Listener interface
    def on_state(self, state: State, detail: str) -> None:
        self.state.emit(state.value, detail)

    def on_attempt(self, attempt: int) -> None:
        self.attempt.emit(attempt)

    def on_log(self, message: str) -> None:
        self.log.emit(message)


def fmt_elapsed(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class MainWindow(QMainWindow):
    def __init__(self, icon: QIcon, settings: Settings | None = None):
        super().__init__()
        self.settings = (settings or Settings.load()).normalized()
        self._icon = icon
        self._quitting = False
        self._tray_hint_shown = False
        self._started_at: float | None = None
        self._countdown_left = 0
        self._ui_state = "idle"

        self.bridge = Bridge()
        self.joiner = Joiner(ScreenVision, winapi.WinInput(), winapi.WinFocusGuard(), self.bridge)

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icon)
        self.setMinimumSize(380, 560)
        self.resize(400, 620)

        self._save_timer = QTimer(self, singleShot=True, interval=400, timeout=self._save_settings)
        self._clock = QTimer(self, interval=500, timeout=self._tick_clock)
        self._countdown = QTimer(self, interval=1000, timeout=self._tick_countdown)

        self._build()
        self._connect_bridge()
        self._setup_tray()
        self._apply_window_flags()

        self.hotkeys = HotkeyListener(self.bridge.hotkey.emit, self.bridge.hotkey_error.emit)
        self.hotkeys.start()
        self._rebind_hotkeys()
        self._set_idle("Hover JOIN in game, then start")

    # ── Layout ──────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        col = QVBoxLayout(root)
        col.setContentsMargins(20, 16, 20, 16)
        col.setSpacing(14)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(overline("Arma Reforger"))
        title = QLabel("Queue Joiner", objectName="appTitle")
        titles.addWidget(title)
        header.addLayout(titles)
        header.addStretch(1)
        self.nav_main = QPushButton("Main", objectName="nav", checkable=True, checked=True)
        self.nav_settings = QPushButton("Settings", objectName="nav", checkable=True)
        for btn, index in ((self.nav_main, 0), (self.nav_settings, 1)):
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, i=index: self._show_page(i))
            header.addWidget(btn, 0, Qt.AlignBottom)
        header.setSpacing(16)
        col.addLayout(header)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_main_page())
        self.pages.addWidget(self._build_settings_page())
        col.addWidget(self.pages, 1)

    def _build_main_page(self) -> QWidget:
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(12)

        self.status = StatusCard()
        col.addWidget(self.status)

        self.primary = QPushButton("Start", objectName="primary")
        self.primary.setCursor(Qt.PointingHandCursor)
        self.primary.setProperty("mode", "start")
        self.primary.clicked.connect(self._on_primary)
        col.addWidget(self.primary)

        hint = QHBoxLayout()
        hint.setSpacing(6)
        hint.addWidget(QLabel("In game: hover JOIN and press", objectName="hint"))
        self.key_start = KeyCap(self.settings.start_hotkey)
        hint.addWidget(self.key_start)
        hint.addWidget(QLabel("· stop", objectName="hint"))
        self.key_stop = KeyCap(self.settings.stop_hotkey)
        hint.addWidget(self.key_stop)
        hint.addStretch(1)
        col.addLayout(hint)

        col.addSpacing(4)
        col.addWidget(overline("How it works"))
        steps = QGridLayout()
        steps.setHorizontalSpacing(12)
        steps.setVerticalSpacing(6)
        lines = (
            "Open the server browser and pick a full server",
            "Hover the JOIN button, then press Start or the hotkey",
            "Leave the mouse alone. It retries until you are in the queue",
        )
        for row, text in enumerate(lines):
            steps.addWidget(QLabel(f"0{row + 1}", objectName="stepNo"), row, 0, Qt.AlignTop)
            label = QLabel(text, objectName="muted")
            label.setWordWrap(True)
            steps.addWidget(label, row, 1)
        steps.setColumnStretch(1, 1)
        col.addLayout(steps)

        col.addSpacing(4)
        log_header = QHBoxLayout()
        log_header.addWidget(overline("Activity"))
        log_header.addStretch(1)
        clear = QPushButton("Clear", objectName="link", cursor=Qt.PointingHandCursor)
        clear.clicked.connect(lambda: self.log_view.clear())
        log_header.addWidget(clear)
        col.addLayout(log_header)

        self.log_view = QPlainTextEdit(objectName="log", readOnly=True)
        self.log_view.setMaximumBlockCount(300)
        self.log_view.setPlaceholderText("Nothing yet")
        self.log_view.setMinimumHeight(90)
        col.addWidget(self.log_view, 1)
        return page

    def _build_settings_page(self) -> QWidget:
        scroll = QScrollArea(widgetResizable=True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(0, 0, 8, 8)
        col.setSpacing(6)
        s = self.settings

        # Hotkeys
        col.addWidget(overline("Hotkeys"))
        keys = QGridLayout()
        keys.setHorizontalSpacing(10)
        self.combo_start = self._hotkey_combo(s.start_hotkey)
        self.combo_stop = self._hotkey_combo(s.stop_hotkey)
        keys.addWidget(QLabel("Start"), 0, 0)
        keys.addWidget(self.combo_start, 0, 1)
        keys.addWidget(QLabel("Stop"), 0, 2)
        keys.addWidget(self.combo_stop, 0, 3)
        keys.setColumnStretch(1, 1)
        keys.setColumnStretch(3, 1)
        col.addLayout(keys)
        self.hotkey_note = QLabel("", objectName="hint")
        self.hotkey_note.setWordWrap(True)
        self.hotkey_note.hide()
        col.addWidget(self.hotkey_note)
        col.addSpacing(10)

        # Safety
        col.addWidget(overline("Safety"))
        self.sw_focus = self._switch(
            "Only click inside Arma Reforger", "Pauses while another window is active", s.require_game_focus
        )
        self.sw_mouse = self._switch(
            "Stop when I move the mouse", "Grab the mouse to take back control", s.stop_on_mouse_move
        )
        col.addWidget(self.sw_focus)
        col.addWidget(self.sw_mouse)
        col.addSpacing(10)

        # Speed
        col.addWidget(overline("Speed"))
        self.sw_fast_esc = self._switch(
            "Fast close", "Click the on-screen ESC button instead of the key", s.fast_esc
        )
        col.addWidget(self.sw_fast_esc)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        self.spins: dict[str, QDoubleSpinBox] = {}
        spin_rows = (
            ("wait_after_click", "Wait after click", 0.05),
            ("connect_timeout", "Give up on a try after", 0.5),
            ("pause_before_retry", "Pause before retry", 0.05),
            ("escape_hold", "Hold ESC key for", 0.05),
        )
        for row, (name, label, step) in enumerate(spin_rows):
            lo, hi = LIMITS[name]
            spin = QDoubleSpinBox(minimum=lo, maximum=hi, singleStep=step, decimals=2, suffix=" s")
            spin.setValue(getattr(s, name))
            spin.setFixedWidth(92)
            spin.setAlignment(Qt.AlignRight)
            spin.setAccessibleName(label)
            spin.valueChanged.connect(self._queue_save)
            self.spins[name] = spin
            grid.addWidget(QLabel(label, objectName="muted"), row, 0)
            grid.addWidget(spin, row, 1, Qt.AlignRight)
        col.addLayout(grid)
        col.addSpacing(10)

        # Alerts
        col.addWidget(overline("When you're in"))
        self.sw_sound = self._switch("Sound alert", "", s.sound)
        col.addWidget(self.sw_sound)
        self.sw_phone = self._switch(
            "Notify my phone", "Free push through the ntfy app, no account needed", s.phone_notify
        )
        self.sw_phone.toggled.connect(self._on_phone_toggled)
        col.addWidget(self.sw_phone)
        topic_row = QHBoxLayout()
        topic_row.setSpacing(8)
        self.topic_edit = QLineEdit(s.ntfy_topic, placeholderText="ntfy topic, e.g. aqj-7f3k92")
        self.topic_edit.setAccessibleName("ntfy topic")
        self.topic_edit.textChanged.connect(self._queue_save)
        topic_row.addWidget(self.topic_edit, 1)
        self.test_btn = QPushButton("Send test", cursor=Qt.PointingHandCursor)
        self.test_btn.clicked.connect(self._send_test)
        topic_row.addWidget(self.test_btn)
        col.addLayout(topic_row)
        self.topic_note = QLabel(
            "Install ntfy on your phone and subscribe to this topic. "
            "Anyone who knows the name can read it, so keep it hard to guess.",
            objectName="hint",
        )
        self.topic_note.setWordWrap(True)
        col.addWidget(self.topic_note)
        self._on_phone_toggled(s.phone_notify, save=False)
        col.addSpacing(10)

        # Window
        col.addWidget(overline("Window"))
        self.sw_top = self._switch("Keep on top of other windows", "", s.always_on_top)
        self.sw_top.toggled.connect(lambda _: self._apply_window_flags())
        self.sw_tray = self._switch("Close to tray", "Keeps running when you close the window", s.close_to_tray)
        col.addWidget(self.sw_top)
        col.addWidget(self.sw_tray)

        col.addSpacing(14)
        col.addWidget(rule())
        footer = QHBoxLayout()
        footer.addWidget(QLabel(f"v{__version__} · by lime98", objectName="hint"))
        footer.addStretch(1)
        repo = QPushButton("Source on GitHub", objectName="link", cursor=Qt.PointingHandCursor)
        repo.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        footer.addWidget(repo)
        col.addLayout(footer)
        col.addStretch(1)

        scroll.setWidget(page)
        return scroll

    def _hotkey_combo(self, value: str) -> QComboBox:
        combo = QComboBox(cursor=Qt.PointingHandCursor)
        combo.addItems(HOTKEYS)
        combo.setCurrentText(value)
        combo.currentTextChanged.connect(self._on_hotkey_changed)
        return combo

    def _switch(self, title: str, hint: str, checked: bool) -> SwitchRow:
        sw = SwitchRow(title, hint)
        sw.setChecked(checked)
        sw.toggled.connect(self._queue_save)
        return sw

    def _show_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        self.nav_main.setChecked(index == 0)
        self.nav_settings.setChecked(index == 1)

    # ── Settings ────────────────────────────────────────────────────────────

    def _collect(self) -> Settings:
        s = Settings(
            start_hotkey=self.combo_start.currentText(),
            stop_hotkey=self.combo_stop.currentText(),
            fast_esc=self.sw_fast_esc.isChecked(),
            require_game_focus=self.sw_focus.isChecked(),
            stop_on_mouse_move=self.sw_mouse.isChecked(),
            sound=self.sw_sound.isChecked(),
            phone_notify=self.sw_phone.isChecked(),
            ntfy_topic=self.topic_edit.text(),
            always_on_top=self.sw_top.isChecked(),
            close_to_tray=self.sw_tray.isChecked(),
            **{name: spin.value() for name, spin in self.spins.items()},
        )
        return s.normalized()

    def _queue_save(self, *_args) -> None:
        self._save_timer.start()

    def _save_settings(self) -> None:
        self.settings = self._collect()
        try:
            self.settings.save()
        except OSError as exc:
            self._log(f"Could not save settings: {exc}")

    def _on_hotkey_changed(self, _text: str) -> None:
        start, stop = self.combo_start.currentText(), self.combo_stop.currentText()
        if start == stop:
            self.hotkey_note.setText("Start and stop need different keys.")
            self.hotkey_note.show()
            return
        self.hotkey_note.hide()
        self.key_start.setText(start)
        self.key_stop.setText(stop)
        self._queue_save()
        self._rebind_hotkeys(start, stop)

    def _rebind_hotkeys(self, start: str | None = None, stop: str | None = None) -> None:
        self.hotkeys.bind({"start": start or self.settings.start_hotkey, "stop": stop or self.settings.stop_hotkey})

    def _on_phone_toggled(self, checked: bool, save: bool = True) -> None:
        if checked and not self.topic_edit.text().strip():
            self.topic_edit.setText(f"aqj-{secrets.token_hex(4)}")
        for w in (self.topic_edit, self.test_btn):
            w.setEnabled(checked)
        self.topic_note.setVisible(checked)
        if save:
            self._queue_save()

    def _send_test(self) -> None:
        self._save_settings()
        self.test_btn.setEnabled(False)
        self.test_btn.setText("Sending…")
        notify.send_ntfy_async(
            self.settings.ntfy_topic,
            "Queue Joiner",
            "Test notification. You will get one like this when you are in the queue.",
            lambda err: self.bridge.ntfy_result.emit("" if err is None else str(err)),
        )

    def _on_ntfy_result(self, error: str) -> None:
        self.test_btn.setEnabled(self.sw_phone.isChecked())
        self.test_btn.setText("Send test")
        self._log("Test notification sent" if not error else f"Phone notification failed: {error}")
        if self.pages.currentIndex() == 1:
            self.topic_note.setText(
                "Sent. Check your phone." if not error else f"Could not send: {error}"
            )

    def _apply_window_flags(self) -> None:
        on_top = getattr(self, "sw_top", None) is not None and self.sw_top.isChecked()
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on_top)
        if visible:
            self.show()

    # ── Start / stop ────────────────────────────────────────────────────────

    def _on_primary(self) -> None:
        if self._ui_state in ("running", "paused"):
            self.stop()
        elif self._ui_state == "countdown":
            self._countdown.stop()
            self._set_idle("Cancelled")
        else:
            self._begin_countdown()

    def _begin_countdown(self) -> None:
        self._countdown_left = COUNTDOWN_SECONDS
        self._ui_state = "countdown"
        self._set_primary("Cancel", "stop")
        self._update_countdown()
        self._countdown.start()

    def _tick_countdown(self) -> None:
        self._countdown_left -= 1
        if self._countdown_left <= 0:
            self._countdown.stop()
            self.start_at(winapi.get_cursor_pos())
        else:
            self._update_countdown()

    def _update_countdown(self) -> None:
        self.status.set_state(
            "countdown", f"Starting in {self._countdown_left}", "Move your mouse over the JOIN button in game"
        )

    def start_at(self, pos: tuple[int, int]) -> None:
        if self.joiner.running:
            return
        self._countdown.stop()
        self._save_settings()
        s = self.settings
        config = JoinerConfig(
            wait_after_click=s.wait_after_click,
            escape_hold=s.escape_hold,
            pause_before_retry=s.pause_before_retry,
            connect_timeout=s.connect_timeout,
            fast_esc=s.fast_esc,
            require_game_focus=s.require_game_focus,
            stop_on_mouse_move=s.stop_on_mouse_move,
        )
        self.log_view.clear()
        self.status.set_attempts(0)
        self._started_at = time.monotonic()
        self._clock.start()
        self._tick_clock()
        self._ui_state = "running"
        self._set_primary(f"Stop  ({s.stop_hotkey})", "stop")
        self.joiner.start(pos, config)

    def stop(self) -> None:
        if self._ui_state == "countdown":
            self._countdown.stop()
            self._set_idle("Cancelled")
        self.joiner.stop()

    def _set_primary(self, text: str, mode: str) -> None:
        self.primary.setText(text)
        self.primary.setProperty("mode", mode)
        self.primary.style().unpolish(self.primary)
        self.primary.style().polish(self.primary)

    def _set_idle(self, detail: str) -> None:
        self._ui_state = "idle"
        self._clock.stop()
        self.status.set_state("idle", "Ready", detail)
        self._set_primary("Start", "start")

    def _tick_clock(self) -> None:
        if self._started_at is not None:
            self.status.timer.setText(fmt_elapsed(time.monotonic() - self._started_at))

    # ── Worker events ───────────────────────────────────────────────────────

    def _connect_bridge(self) -> None:
        self.bridge.state.connect(self._on_state)
        self.bridge.attempt.connect(self.status.set_attempts)
        self.bridge.log.connect(self._log)
        self.bridge.hotkey.connect(self._on_hotkey)
        self.bridge.hotkey_error.connect(self._on_hotkey_error)
        self.bridge.ntfy_result.connect(self._on_ntfy_result)

    def _on_hotkey(self, action: str) -> None:
        if action == "start" and self._ui_state not in ("running", "paused"):
            self.start_at(winapi.get_cursor_pos())
        elif action == "stop":
            self.stop()

    def _on_hotkey_error(self, message: str) -> None:
        self.hotkey_note.setText(message)
        self.hotkey_note.show()
        self._log(message)

    def _on_state(self, state: str, detail: str) -> None:
        if state == "running":
            self._ui_state = "running"
            self.status.set_state("running", "Joining", detail)
        elif state == "paused":
            self._ui_state = "paused"
            self.status.set_state("paused", "Paused", detail)
        elif state == "success":
            self._clock.stop()
            self._tick_clock()
            self._ui_state = "success"
            self.status.set_state("success", "In queue", detail)
            self._set_primary("Start again", "start")
            self._announce_success(detail)
        elif state == "error":
            self._clock.stop()
            self._ui_state = "error"
            self.status.set_state("error", "Something went wrong", detail)
            self._set_primary("Start", "start")
        else:
            self._set_idle(detail)

    def _announce_success(self, detail: str) -> None:
        s = self.settings
        if s.sound:
            notify.play_alert()
        winapi.flash_taskbar(int(self.winId()))
        if self.tray is not None:
            self.tray.showMessage("You're in the queue", detail, self._icon, 6000)
        if s.phone_notify and s.ntfy_topic:
            notify.send_ntfy_async(
                s.ntfy_topic,
                "In the queue",
                f"Arma Reforger: {detail}.",
                lambda err: err and self.bridge.log.emit(f"Phone notification failed: {err}"),
            )

    def _log(self, message: str) -> None:
        self.log_view.appendPlainText(f"{time.strftime('%H:%M:%S')}  {message}")

    # ── Tray and lifecycle ──────────────────────────────────────────────────

    def _setup_tray(self) -> None:
        self.tray: QSystemTrayIcon | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(self._icon, self)
        self.tray.setToolTip(APP_NAME)
        menu = QMenu(self)
        show = QAction("Show", self, triggered=self.show_window)
        stop = QAction("Stop", self, triggered=self.stop)
        quit_ = QAction("Quit", self, triggered=self.quit)
        menu.addAction(show)
        menu.addAction(stop)
        menu.addSeparator()
        menu.addAction(quit_)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self.show_window() if reason == QSystemTrayIcon.Trigger else None
        )
        self.tray.show()

    def show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        winapi.use_dark_title_bar(int(self.winId()))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if not self._quitting and self.tray is not None and self.sw_tray.isChecked():
            event.ignore()
            self.hide()
            if not self._tray_hint_shown:
                self._tray_hint_shown = True
                self.tray.showMessage(APP_NAME, "Still running here. Right-click to quit.", self._icon, 3000)
            return
        self._shutdown()
        event.accept()
        QApplication.quit()

    def quit(self) -> None:
        self._quitting = True
        self.close()

    def _shutdown(self) -> None:
        self._save_timer.stop()
        self._save_settings()
        self.joiner.stop()
        self.joiner.join(1.0)
        self.hotkeys.shutdown()
        if self.tray is not None:
            self.tray.hide()

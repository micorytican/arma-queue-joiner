"""Main window, laid out like the Windows 11 Update and Settings pages."""

from __future__ import annotations

import html
import secrets
import time
from collections import deque

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QFont, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, REPO_URL, __version__, notify, winapi
from ..hotkeys import HotkeyListener
from ..joiner import Joiner, JoinerConfig, State
from ..screen import ScreenVision
from ..settings import HOTKEYS, LIMITS, Settings
from . import theme
from .theme import Glyph
from .widgets import Card, ExpanderCard, GlyphIcon, SettingsCard, ToggleSwitch, label

COUNTDOWN_SECONDS = 3
PAGE_MARGIN = 24


class Bridge(QObject):
    """Carries events from worker and hotkey threads to the UI thread (queued signals)."""

    state = Signal(str, str)
    attempt = Signal(int)
    log = Signal(str)
    hotkey = Signal(str)
    hotkey_error = Signal(str)
    ntfy_result = Signal(str)

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
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


class MainWindow(QMainWindow):
    def __init__(self, icon: QIcon, settings: Settings | None = None):
        super().__init__()
        self.settings = (settings or Settings.load()).normalized()
        self._icon = icon
        self._quitting = False
        self._tray_hint_shown = False
        self._started_at: float | None = None
        self._finished_at: float | None = None
        self._attempts = 0
        self._countdown_left = 0
        self._ui_state = "idle"
        self._last_detail = ""
        self._activity: deque[tuple[str, str]] = deque(maxlen=200)

        self.bridge = Bridge()
        self.joiner = Joiner(ScreenVision, winapi.WinInput(), winapi.WinFocusGuard(), self.bridge)

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icon)
        self.setMinimumSize(440, 600)
        self.resize(480, 660)

        self._save_timer = QTimer(self, singleShot=True, interval=400, timeout=self._save_settings)
        self._clock = QTimer(self, interval=500, timeout=self._refresh_stats)
        self._countdown = QTimer(self, interval=1000, timeout=self._tick_countdown)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_main_page())
        self.pages.addWidget(self._build_settings_page())
        self.setCentralWidget(self.pages)

        self._connect_bridge()
        self._setup_tray()
        self._apply_window_flags()
        self.apply_theme()
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: self.apply_theme())

        self.hotkeys = HotkeyListener(self.bridge.hotkey.emit, self.bridge.hotkey_error.emit)
        self.hotkeys.start()
        self._rebind_hotkeys()
        self._render("idle")

    # ── Main page ───────────────────────────────────────────────────────────

    def _build_main_page(self) -> QWidget:
        page = QWidget(objectName="page")
        col = QVBoxLayout(page)
        col.setContentsMargins(PAGE_MARGIN, 20, PAGE_MARGIN, PAGE_MARGIN)
        col.setSpacing(0)

        header = QHBoxLayout()
        header.addWidget(label("Queue Joiner", 28, weight=QFont.DemiBold, display=True))
        header.addStretch(1)
        settings_btn = self._icon_button(Glyph.SETTINGS, "Settings", lambda: self._show_page(1))
        header.addWidget(settings_btn)
        col.addLayout(header)
        col.addSpacing(20)

        # Status, Windows Update style: big icon, headline, details, action on the right
        status = QHBoxLayout()
        status.setSpacing(16)
        self.status_icon = GlyphIcon(Glyph.READY, 40, "accent")
        status.addWidget(self.status_icon, 0, Qt.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.status_title = label("", 20, weight=QFont.DemiBold, display=True)
        self.status_title.setWordWrap(True)
        self.status_detail = label("", 14, "secondary")
        self.status_detail.setWordWrap(True)
        self.status_stats = label("", 12, "tertiary")
        texts.addWidget(self.status_title)
        texts.addWidget(self.status_detail)
        texts.addWidget(self.status_stats)
        status.addLayout(texts, 1)
        self.action = QPushButton("Start")
        self.action.setMinimumWidth(120)
        self.action.setCursor(Qt.PointingHandCursor)
        self.action.clicked.connect(self._on_action)
        status.addWidget(self.action, 0, Qt.AlignTop)
        col.addLayout(status)
        col.addSpacing(24)

        change = QPushButton("Change")
        change.setCursor(Qt.PointingHandCursor)
        change.clicked.connect(lambda: self._show_page(1))
        self.hotkey_card = SettingsCard(Glyph.KEYBOARD, "Hotkeys", "", change)
        col.addWidget(self.hotkey_card)
        col.addSpacing(4)

        activity = Card()
        a_col = QVBoxLayout(activity)
        a_col.setContentsMargins(16, 12, 12, 12)
        a_col.setSpacing(8)
        a_head = QHBoxLayout()
        a_head.setSpacing(16)
        a_head.addWidget(GlyphIcon(Glyph.HISTORY, 20))
        a_head.addWidget(label("Activity", 14), 1)
        clear = QPushButton("Clear")
        clear.setCursor(Qt.PointingHandCursor)
        clear.clicked.connect(self._clear_activity)
        a_head.addWidget(clear)
        a_col.addLayout(a_head)
        self.activity_view = QPlainTextEdit(objectName="activity", readOnly=True)
        self.activity_view.setFrameShape(QFrame.NoFrame)
        self.activity_view.setFont(theme.font(13))
        self.activity_view.setPlaceholderText("Events from the current run show up here.")
        self.activity_view.setMinimumHeight(120)
        a_col.addWidget(self.activity_view, 1)
        col.addWidget(activity, 1)
        return page

    # ── Settings page ───────────────────────────────────────────────────────

    def _build_settings_page(self) -> QWidget:
        scroll = QScrollArea(widgetResizable=True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        page = QWidget(objectName="page")
        col = QVBoxLayout(page)
        col.setContentsMargins(PAGE_MARGIN, 20, PAGE_MARGIN, PAGE_MARGIN)
        col.setSpacing(4)
        s = self.settings

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self._icon_button(Glyph.BACK, "Back", lambda: self._show_page(0)))
        header.addWidget(label("Settings", 28, weight=QFont.DemiBold, display=True))
        header.addStretch(1)
        col.addLayout(header)

        self._group(col, "Controls")
        self.combo_start = self._hotkey_combo(s.start_hotkey)
        self.combo_stop = self._hotkey_combo(s.stop_hotkey)
        col.addWidget(SettingsCard(Glyph.KEYBOARD, "Start hotkey", "Starts at the current mouse position", self.combo_start))
        col.addWidget(SettingsCard(Glyph.KEYBOARD, "Stop hotkey", "Stops right away", self.combo_stop))
        self.hotkey_note = label("", 12, "secondary")
        self.hotkey_note.setWordWrap(True)
        self.hotkey_note.setContentsMargins(4, 4, 4, 0)
        self.hotkey_note.hide()
        col.addWidget(self.hotkey_note)

        self._group(col, "Safety")
        self.sw_focus = self._toggle(s.require_game_focus)
        self.sw_mouse = self._toggle(s.stop_on_mouse_move)
        col.addWidget(SettingsCard(Glyph.GAME, "Only click inside Arma Reforger",
                                   "Pauses while another window is in front", self.sw_focus))
        col.addWidget(SettingsCard(Glyph.MOUSE, "Stop when I move the mouse",
                                   "Grab the mouse to take back control", self.sw_mouse))

        self._group(col, "Speed")
        self.sw_fast_esc = self._toggle(s.fast_esc)
        col.addWidget(SettingsCard(Glyph.CLOSE, "Fast close",
                                   "Click the ESC button on screen instead of pressing the key", self.sw_fast_esc))
        timing = ExpanderCard(Glyph.TIMER, "Timing", "How long each step waits. The defaults suit most servers.")
        self.spins: dict[str, QDoubleSpinBox] = {}
        for name, text, step in (
            ("wait_after_click", "Wait after clicking Join", 0.05),
            ("connect_timeout", "Try again if nothing happens after", 0.5),
            ("pause_before_retry", "Pause between attempts", 0.05),
            ("escape_hold", "Hold the ESC key for", 0.05),
        ):
            lo, hi = LIMITS[name]
            spin = QDoubleSpinBox(minimum=lo, maximum=hi, singleStep=step, decimals=2, suffix=" s")
            spin.setValue(getattr(s, name))
            spin.setFixedWidth(110)
            spin.setAccessibleName(text)
            spin.valueChanged.connect(self._queue_save)
            self.spins[name] = spin
            timing.add_row(text, spin)
        col.addWidget(timing)

        self._group(col, "When you're in the queue")
        self.sw_sound = self._toggle(s.sound)
        col.addWidget(SettingsCard(Glyph.VOLUME, "Play a sound", "Three short beeps", self.sw_sound))
        self.sw_phone = self._toggle(s.phone_notify)
        self.sw_phone.toggled.connect(self._on_phone_toggled)
        col.addWidget(SettingsCard(Glyph.PHONE, "Notify my phone",
                                   "Free push through the ntfy app, no account needed", self.sw_phone))
        self.phone_box = Card()
        p_col = QVBoxLayout(self.phone_box)
        p_col.setContentsMargins(56, 12, 16, 12)
        p_col.setSpacing(8)
        p_row = QHBoxLayout()
        p_row.setSpacing(8)
        self.topic_edit = QLineEdit(s.ntfy_topic, placeholderText="Topic name")
        self.topic_edit.setAccessibleName("ntfy topic")
        self.topic_edit.textChanged.connect(self._queue_save)
        p_row.addWidget(self.topic_edit, 1)
        self.test_btn = QPushButton("Send test")
        self.test_btn.setCursor(Qt.PointingHandCursor)
        self.test_btn.clicked.connect(self._send_test)
        p_row.addWidget(self.test_btn)
        p_col.addLayout(p_row)
        self.topic_note = label(
            "Install ntfy on your phone and subscribe to this topic. "
            "Anyone who knows the name can read it, so keep it hard to guess.",
            12, "secondary",
        )
        self.topic_note.setWordWrap(True)
        p_col.addWidget(self.topic_note)
        col.addWidget(self.phone_box)
        self._on_phone_toggled(s.phone_notify, save=False)

        self._group(col, "Window")
        self.sw_top = self._toggle(s.always_on_top)
        self.sw_top.toggled.connect(lambda _: self._apply_window_flags())
        self.sw_tray = self._toggle(s.close_to_tray)
        col.addWidget(SettingsCard(Glyph.PIN, "Keep on top", "Stay above other windows", self.sw_top))
        col.addWidget(SettingsCard(Glyph.MINIMIZE, "Close to the tray",
                                   "Keeps running in the notification area when you close the window", self.sw_tray))

        self._group(col, "About")
        source = QPushButton("Source code")
        source.setCursor(Qt.PointingHandCursor)
        source.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        col.addWidget(SettingsCard(Glyph.INFO, APP_NAME, f"Version {__version__} · by lime98 · MIT licence", source))
        col.addStretch(1)

        scroll.setWidget(page)
        return scroll

    # ── Small builders ──────────────────────────────────────────────────────

    def _group(self, col: QVBoxLayout, title: str) -> None:
        col.addSpacing(24)
        head = label(title, 14, weight=QFont.DemiBold)
        head.setContentsMargins(2, 0, 0, 4)
        col.addWidget(head)

    def _icon_button(self, glyph: str, tip: str, slot) -> QToolButton:
        btn = QToolButton()
        btn.setProperty("flat", True)
        btn.setText(glyph)
        btn.setFont(theme.icon_font(16))
        btn.setToolTip(tip)
        btn.setAccessibleName(tip)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedSize(36, 36)
        btn.clicked.connect(slot)
        return btn

    def _hotkey_combo(self, value: str) -> QComboBox:
        combo = QComboBox()
        combo.addItems(HOTKEYS)
        combo.setCurrentText(value)
        combo.setFixedWidth(110)
        combo.setCursor(Qt.PointingHandCursor)
        combo.currentTextChanged.connect(self._on_hotkey_changed)
        return combo

    def _toggle(self, checked: bool) -> ToggleSwitch:
        sw = ToggleSwitch(checked)
        sw.toggled.connect(self._queue_save)
        return sw

    def _show_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)

    # ── Theme ───────────────────────────────────────────────────────────────

    def apply_theme(self) -> None:
        c = theme.colors()
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(theme.stylesheet(c))
        winapi.set_title_bar_theme(int(self.winId()), c.dark)
        self._render_activity()
        self.update()

    # ── Settings ────────────────────────────────────────────────────────────

    def _collect(self) -> Settings:
        return Settings(
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
        ).normalized()

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
        self._queue_save()
        self._rebind_hotkeys(start, stop)
        self._render(self._ui_state, self._last_detail)

    def _rebind_hotkeys(self, start: str | None = None, stop: str | None = None) -> None:
        self.hotkeys.bind({"start": start or self.settings.start_hotkey, "stop": stop or self.settings.stop_hotkey})

    def _keys(self) -> tuple[str, str]:
        return self.combo_start.currentText(), self.combo_stop.currentText()

    def _on_phone_toggled(self, checked: bool, save: bool = True) -> None:
        if checked and not self.topic_edit.text().strip():
            self.topic_edit.setText(f"aqj-{secrets.token_hex(4)}")
        self.phone_box.setVisible(checked)
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
        self.test_btn.setEnabled(True)
        self.test_btn.setText("Send test")
        if error:
            self.topic_note.setText(f"Couldn't send: {error}. Check your internet connection and the topic name.")
            self._log(f"Phone notification failed: {error}")
        else:
            self.topic_note.setText("Sent. If nothing arrives, check that the topic on your phone is the same.")
            self._log("Test notification sent")

    def _apply_window_flags(self) -> None:
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.sw_top.isChecked())
        if visible:
            self.show()

    # ── Status rendering ────────────────────────────────────────────────────

    def _render(self, kind: str, detail: str = "") -> None:
        self._ui_state = kind
        self._last_detail = detail
        start, stop = self._keys()
        glyph, role, title, text, button, accent = {
            "idle": (Glyph.READY, "accent", "Ready to join",
                     detail or f"Hover over Join in the server browser, then press {start}.", "Start", True),
            "countdown": (Glyph.TIMER, "accent", f"Starting in {self._countdown_left}",
                          "Move the mouse over the Join button in the game.", "Cancel", False),
            "running": (Glyph.SYNC, "accent", "Trying to join",
                        f"{detail}. Press {stop} or move the mouse to stop." if detail else "", "Stop", False),
            "paused": (Glyph.PAUSE, "caution", "Paused", detail, "Stop", False),
            "success": (Glyph.DONE, "success", "You're in the queue", detail, "Start again", True),
            "error": (Glyph.ERROR, "critical", "Something went wrong", detail, "Start", True),
        }[kind]
        self.status_icon.set_glyph(glyph, role)
        self.status_title.setText(title)
        self.status_detail.setText(text)
        self.action.setText(button)
        self.action.setProperty("accent", accent)
        self.action.style().unpolish(self.action)
        self.action.style().polish(self.action)
        self.hotkey_card.description.setText(f"{start} starts at the mouse position, {stop} stops")
        self.hotkey_card.description.show()
        self._refresh_stats()

    def _refresh_stats(self) -> None:
        if self._started_at is None or self._ui_state in ("idle", "countdown"):
            self.status_stats.setText("")
            self.status_stats.hide()
            return
        end = self._finished_at or time.monotonic()
        self.status_stats.setText(f"{fmt_elapsed(end - self._started_at)} · {plural(self._attempts, 'attempt')}")
        self.status_stats.show()

    # ── Start / stop ────────────────────────────────────────────────────────

    def _on_action(self) -> None:
        if self._ui_state in ("running", "paused"):
            self.stop()
        elif self._ui_state == "countdown":
            self._countdown.stop()
            self._render("idle", "Cancelled.")
        else:
            self._countdown_left = COUNTDOWN_SECONDS
            self._render("countdown")
            self._countdown.start()

    def _tick_countdown(self) -> None:
        self._countdown_left -= 1
        if self._countdown_left <= 0:
            self._countdown.stop()
            self.start_at(winapi.get_cursor_pos())
        else:
            self._render("countdown")

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
        self._clear_activity()
        self._attempts = 0
        self._started_at = time.monotonic()
        self._finished_at = None
        self._render("running", "Starting")
        self._clock.start()
        self.joiner.start(pos, config)

    def stop(self) -> None:
        if self._ui_state == "countdown":
            self._countdown.stop()
            self._render("idle", "Cancelled.")
        self.joiner.stop()

    # ── Worker events ───────────────────────────────────────────────────────

    def _connect_bridge(self) -> None:
        self.bridge.state.connect(self._on_state)
        self.bridge.attempt.connect(self._on_attempt)
        self.bridge.log.connect(self._log)
        self.bridge.hotkey.connect(self._on_hotkey)
        self.bridge.hotkey_error.connect(self._on_hotkey_error)
        self.bridge.ntfy_result.connect(self._on_ntfy_result)

    def _on_attempt(self, n: int) -> None:
        self._attempts = n
        self._refresh_stats()

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
        if state in ("success", "error", "idle"):
            self._clock.stop()
            self._finished_at = time.monotonic()
        if state == "success":
            elapsed = fmt_elapsed(self._finished_at - (self._started_at or self._finished_at))
            self._render("success", f"{detail}. Keep the game open.")
            self._announce_success(f"{detail}, in {elapsed}")
        elif state == "idle":
            self._render("idle", f"{detail}." if detail and not detail.endswith(".") else detail)
        else:
            self._render(state, detail)

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
                "You're in the queue",
                f"Arma Reforger: {detail}.",
                lambda err: err and self.bridge.log.emit(f"Phone notification failed: {err}"),
            )

    # ── Activity ────────────────────────────────────────────────────────────

    def _log(self, message: str) -> None:
        entry = (time.strftime("%H:%M:%S"), message)
        self._activity.append(entry)
        self._append_entry(*entry)

    def _append_entry(self, stamp: str, message: str) -> None:
        c = theme.colors()
        self.activity_view.appendHtml(
            f'<span style="color:{c.text_tertiary.name()}">{stamp}</span>&nbsp;&nbsp;'
            f'<span style="color:{c.text.name()}">{html.escape(message)}</span>'
        )

    def _render_activity(self) -> None:
        self.activity_view.clear()
        for entry in self._activity:
            self._append_entry(*entry)

    def _clear_activity(self) -> None:
        self._activity.clear()
        self.activity_view.clear()

    # ── Tray and lifecycle ──────────────────────────────────────────────────

    def _setup_tray(self) -> None:
        self.tray: QSystemTrayIcon | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(self._icon, self)
        self.tray.setToolTip(APP_NAME)
        menu = QMenu(self)
        menu.addAction(QAction("Open", self, triggered=self.show_window))
        menu.addAction(QAction("Stop", self, triggered=self.stop))
        menu.addSeparator()
        menu.addAction(QAction("Quit", self, triggered=self.quit))
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
        winapi.set_title_bar_theme(int(self.winId()), theme.is_dark())

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if not self._quitting and self.tray is not None and self.sw_tray.isChecked():
            event.ignore()
            self.hide()
            if not self._tray_hint_shown:
                self._tray_hint_shown = True
                self.tray.showMessage(APP_NAME, "Still running in the notification area.", self._icon, 3000)
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

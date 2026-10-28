"""Main window, laid out like the Windows 11 Update and Settings pages.

Pages: 0 main, 1 settings, 2 diagnostics. All text goes through i18n.tr, and
switching language rebuilds the pages from the current settings.
"""

from __future__ import annotations

import dataclasses
import html
import logging
import os
import platform
import secrets
import time
from collections import deque
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAccessible,
    QAccessibleEvent,
    QAction,
    QCloseEvent,
    QDesktopServices,
    QFont,
    QGuiApplication,
    QIcon,
    QImage,
    QKeyEvent,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, REPO_URL, __version__, detection, logs, net, notify, updates, winapi
from ..gamelog import LogFollower, QueueWatch, Stage, default_logs_dir, latest_console_log
from ..hotkeys import HotkeyListener
from ..i18n import LANGUAGE_NAMES, attempts, set_language, system_language, tr
from ..joiner import Joiner, JoinerConfig, Message, State, msg
from ..screen import ScreenVision
from ..settings import HOTKEYS, LIMITS, Settings
from . import theme
from .theme import Glyph
from .widgets import Card, ExpanderCard, GlyphIcon, Meter, SettingsCard, ToggleSwitch, icon_button, label

log = logging.getLogger("aqj")

COUNTDOWN_SECONDS = 3
WATCH_LIMIT = 3 * 3600  # stop following the game log after three hours
PAGE_MARGIN = 24
MAIN, SETTINGS, DIAGNOSTICS = 0, 1, 2
POINTING = Qt.CursorShape.PointingHandCursor
SEMIBOLD = QFont.Weight.DemiBold


class Bridge(QObject):
    """Carries events from worker, hotkey and network threads to the UI thread (queued signals)."""

    state = Signal(str, object)
    attempt = Signal(int)
    log = Signal(object)
    hotkey = Signal(str)
    hotkey_error = Signal(str)
    test_result = Signal(str, str)  # channel, error ("" on success)
    update_found = Signal(object)
    crash = Signal(str)

    def on_state(self, state: State, detail: Message) -> None:
        self.state.emit(state.value, detail)

    def on_attempt(self, attempt: int) -> None:
        self.attempt.emit(attempt)

    def on_log(self, message: Message) -> None:
        self.log.emit(message)


def fmt_elapsed(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def text_of(message: Message) -> str:
    return tr(message.key, **message.params)


def percent(value: float) -> str:
    return f"{value * 100:.2f} %"


class MainWindow(QMainWindow):
    def __init__(self, icon: QIcon, settings: Settings | None = None):
        super().__init__()
        self.settings = (settings or Settings.load()).normalized()
        if not self.settings.language:  # first start: pick once, then it shows as a normal choice
            self.settings.language = system_language()
        set_language(self.settings.language)
        self._icon = icon
        self._quitting = False
        self._tray_hint_shown = False
        self._started_at: float | None = None
        self._finished_at: float | None = None
        self._attempts = 0
        self._countdown_left = 0
        self._ui_state = "idle"
        self._detail: Message | None = None
        self._activity: deque[tuple[str, Message]] = deque(maxlen=200)
        self._release: updates.Release | None = None
        self._diag_vision: ScreenVision | None = None
        self._last_report = ""

        self.bridge = Bridge()
        self.joiner = Joiner(ScreenVision, winapi.WinInput(), winapi.WinFocusGuard(), self.bridge)

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icon)
        self.setMinimumSize(460, 620)
        self.resize(500, 680)

        self._save_timer = self._timer(400, self._save_settings, single=True)
        self._clock = self._timer(500, self._refresh_stats)
        self._countdown = self._timer(1000, self._tick_countdown)
        self._diag_timer = self._timer(400, self._refresh_diagnostics)
        self._watch_timer = self._timer(1000, self._poll_game_log)
        self._watch: QueueWatch | None = None
        self._watch_started = 0.0

        self.pages = QStackedWidget()
        self.setCentralWidget(self.pages)
        self._build_pages()

        self._connect_bridge()
        self._setup_tray()
        self._apply_window_flags()
        self.apply_theme()
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _scheme: self.apply_theme())

        self.hotkeys = HotkeyListener(self.bridge.hotkey.emit, self.bridge.hotkey_error.emit)
        self.hotkeys.start()
        self._rebind_hotkeys()
        self._render("idle")

    def _timer(self, interval: int, slot: Callable[[], None], single: bool = False) -> QTimer:
        timer = QTimer(self)
        timer.setInterval(interval)
        timer.setSingleShot(single)
        timer.timeout.connect(slot)
        return timer

    def check_for_updates(self) -> None:
        if self.settings.check_updates:
            net.in_background(
                updates.latest_release,
                lambda release, _err: release and self.bridge.update_found.emit(release),
            )

    # ── Pages ───────────────────────────────────────────────────────────────

    def _build_pages(self) -> None:
        while self.pages.count():
            old = self.pages.widget(0)
            if old is None:
                break
            self.pages.removeWidget(old)
            old.deleteLater()
        self.pages.addWidget(self._build_main_page())
        self.pages.addWidget(self._build_settings_page())
        self.pages.addWidget(self._build_diagnostics_page())

    def _page(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page.setObjectName("page")
        col = QVBoxLayout(page)
        col.setContentsMargins(PAGE_MARGIN, 20, PAGE_MARGIN, PAGE_MARGIN)
        return page, col

    def _scrolling(self, page: QWidget) -> QScrollArea:
        scroll = QScrollArea(widgetResizable=True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        return scroll

    def _header(self, col: QVBoxLayout, title: str, back: bool) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(8)
        if back:
            header.addWidget(icon_button(Glyph.BACK, tr("button.back"), lambda: self.show_page(MAIN)))
        header.addWidget(label(title, 28, weight=SEMIBOLD, display=True))
        header.addStretch(1)
        col.addLayout(header)
        return header

    def _group(self, col: QVBoxLayout, title: str) -> None:
        col.addSpacing(24)
        head = label(title, 14, weight=SEMIBOLD)
        head.setContentsMargins(2, 0, 0, 4)
        col.addWidget(head)

    def show_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        if index == DIAGNOSTICS:
            self._refresh_diagnostics()
            self._diag_timer.start()
        else:
            self._diag_timer.stop()
            self._close_diag_vision()

    # ── Main page ───────────────────────────────────────────────────────────

    def _build_main_page(self) -> QWidget:
        page, col = self._page()
        col.setSpacing(0)
        header = self._header(col, "Queue Joiner", back=False)
        header.addWidget(icon_button(Glyph.SETTINGS, tr("main.settings"), lambda: self.show_page(SETTINGS)))
        col.addSpacing(16)

        # Update banner (hidden until a newer release is found)
        self.update_bar = Card()
        bar = QHBoxLayout(self.update_bar)
        bar.setContentsMargins(16, 10, 8, 10)
        bar.setSpacing(12)
        bar.addWidget(GlyphIcon(Glyph.INFO, 16, "accent"))
        self.update_text = label("", 14, wrap=True)
        bar.addWidget(self.update_text, 1)
        download = push_button(tr("update.download"))
        download.clicked.connect(self._open_release)
        bar.addWidget(download)
        bar.addWidget(icon_button(Glyph.CLOSE, tr("button.close"), self.update_bar.hide))
        self.update_bar.setVisible(self._release is not None)
        if self._release is not None:
            self.update_text.setText(tr("update.available", version=self._release.version))
        col.addWidget(self.update_bar)
        col.addSpacing(12)

        # Status, Windows Update style: big icon, headline, details, action on the right
        status = QHBoxLayout()
        status.setSpacing(16)
        self.status_icon = GlyphIcon(Glyph.READY, 40, "accent")
        status.addWidget(self.status_icon, 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.status_title = label("", 20, weight=SEMIBOLD, display=True, wrap=True)
        self.status_detail = label("", 14, "secondary", wrap=True)
        self.status_stats = label("", 12, "tertiary")
        for w in (self.status_title, self.status_detail, self.status_stats):
            texts.addWidget(w)
        status.addLayout(texts, 1)
        self.action = push_button(tr("button.start"))
        self.action.setMinimumWidth(130)
        self.action.clicked.connect(self._on_action)
        status.addWidget(self.action, 0, Qt.AlignmentFlag.AlignTop)
        col.addLayout(status)
        col.addSpacing(24)

        change = push_button(tr("button.change"))
        change.clicked.connect(lambda: self.show_page(SETTINGS))
        self.hotkey_card = SettingsCard(Glyph.KEYBOARD, tr("main.hotkeys"), "", change)
        col.addWidget(self.hotkey_card)
        col.addSpacing(4)

        activity = Card()
        a_col = QVBoxLayout(activity)
        a_col.setContentsMargins(16, 12, 12, 12)
        a_col.setSpacing(8)
        a_head = QHBoxLayout()
        a_head.setSpacing(16)
        a_head.addWidget(GlyphIcon(Glyph.HISTORY, 20))
        a_head.addWidget(label(tr("main.activity"), 14), 1)
        clear = push_button(tr("button.clear"))
        clear.clicked.connect(self._clear_activity)
        a_head.addWidget(clear)
        a_col.addLayout(a_head)
        self.activity_view = QPlainTextEdit()
        self.activity_view.setObjectName("activity")
        self.activity_view.setReadOnly(True)
        self.activity_view.setFrameShape(QFrame.Shape.NoFrame)
        self.activity_view.setFont(theme.font(13))
        self.activity_view.setPlaceholderText(tr("main.activity.empty"))
        self.activity_view.setAccessibleName(tr("main.activity"))
        self.activity_view.setMinimumHeight(120)
        a_col.addWidget(self.activity_view, 1)
        col.addWidget(activity, 1)
        return page

    # ── Settings page ───────────────────────────────────────────────────────

    def _build_settings_page(self) -> QWidget:
        page, col = self._page()
        col.setSpacing(4)
        s = self.settings
        self._header(col, tr("settings.title"), back=True)

        self._group(col, tr("group.controls"))
        self.combo_start = self._hotkey_combo(s.start_hotkey)
        self.combo_stop = self._hotkey_combo(s.stop_hotkey)
        col.addWidget(
            SettingsCard(Glyph.KEYBOARD, tr("set.start_key"), tr("set.start_key.text"), self.combo_start)
        )
        col.addWidget(
            SettingsCard(Glyph.KEYBOARD, tr("set.stop_key"), tr("set.stop_key.text"), self.combo_stop)
        )
        self.hotkey_note = label("", 12, "secondary", wrap=True)
        self.hotkey_note.setContentsMargins(4, 4, 4, 0)
        self.hotkey_note.hide()
        col.addWidget(self.hotkey_note)

        self._group(col, tr("group.safety"))
        self.sw_focus = self._toggle(s.require_game_focus)
        self.sw_mouse = self._toggle(s.stop_on_mouse_move)
        col.addWidget(SettingsCard(Glyph.GAME, tr("set.focus"), tr("set.focus.text"), self.sw_focus))
        col.addWidget(SettingsCard(Glyph.MOUSE, tr("set.mouse"), tr("set.mouse.text"), self.sw_mouse))

        self._group(col, tr("group.speed"))
        self.sw_fast_esc = self._toggle(s.fast_esc)
        col.addWidget(SettingsCard(Glyph.CLOSE, tr("set.fast"), tr("set.fast.text"), self.sw_fast_esc))
        timing = ExpanderCard(Glyph.TIMER, tr("set.timing"), tr("set.timing.text"))
        self.spins: dict[str, QDoubleSpinBox] = {}
        for name, step in (
            ("wait_after_click", 0.05),
            ("connect_timeout", 0.5),
            ("pause_before_retry", 0.05),
            ("escape_hold", 0.05),
        ):
            lo, hi = LIMITS[name]
            spin = QDoubleSpinBox(
                minimum=lo, maximum=hi, singleStep=step, decimals=2, suffix=tr("unit.seconds")
            )
            spin.setValue(getattr(s, name))
            spin.setFixedWidth(110)
            spin.valueChanged.connect(self._queue_save)
            self.spins[name] = spin
            timing.add_row(tr(f"set.{name}"), spin)
        col.addWidget(timing)

        self._group(col, tr("group.alerts"))
        self.sw_notify_queue = self._toggle(s.notify_queue)
        col.addWidget(SettingsCard(Glyph.TIMER, tr("set.notify_queue"), tr("set.notify_queue.text"),
                                   self.sw_notify_queue))  # fmt: skip
        self.sw_notify_game = self._toggle(s.notify_game)
        col.addWidget(SettingsCard(Glyph.GAME, tr("set.notify_game"), tr("set.notify_game.text"),
                                   self.sw_notify_game))  # fmt: skip
        self.sw_sound = self._toggle(s.sound)
        col.addWidget(SettingsCard(Glyph.VOLUME, tr("set.sound"), tr("set.sound.text"), self.sw_sound))

        self.sw_phone = self._toggle(s.phone_notify)
        col.addWidget(SettingsCard(Glyph.PHONE, tr("set.phone"), tr("set.phone.text"), self.sw_phone))
        self.topic_edit = QLineEdit(s.ntfy_topic, placeholderText=tr("set.phone.placeholder"))
        self.topic_edit.setAccessibleName(tr("set.phone.placeholder"))
        self.topic_edit.textChanged.connect(self._queue_save)
        self.phone_box, self.phone_note, self.phone_test = self._channel_box(
            self.topic_edit, tr("set.phone.help"), lambda: self._send_test("ntfy")
        )
        col.addWidget(self.phone_box)
        self.sw_phone.toggled.connect(self._on_phone_toggled)
        self._on_phone_toggled(s.phone_notify, save=False)

        self.sw_discord = self._toggle(s.discord_notify)
        col.addWidget(SettingsCard(Glyph.CHAT, tr("set.discord"), tr("set.discord.text"), self.sw_discord))
        self.webhook_edit = QLineEdit(s.discord_webhook, placeholderText="https://discord.com/api/webhooks/…")
        self.webhook_edit.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.webhook_edit.setAccessibleName(tr("set.discord"))
        self.webhook_edit.textChanged.connect(self._queue_save)
        self.discord_box, self.discord_note, self.discord_test = self._channel_box(
            self.webhook_edit, tr("set.discord.help"), lambda: self._send_test("Discord")
        )
        col.addWidget(self.discord_box)
        self.sw_discord.toggled.connect(self._on_discord_toggled)
        self._on_discord_toggled(s.discord_notify, save=False)

        self._group(col, tr("group.app"))
        self.combo_lang = combo_box()
        for code, name in LANGUAGE_NAMES.items():
            self.combo_lang.addItem(name, code)
        self.combo_lang.setCurrentIndex(max(0, self.combo_lang.findData(s.language)))
        self.combo_lang.setMinimumWidth(150)
        self.combo_lang.currentIndexChanged.connect(self._on_language_changed)
        col.addWidget(
            SettingsCard(Glyph.LANGUAGE, tr("set.language"), tr("set.language.text"), self.combo_lang)
        )
        self.sw_top = self._toggle(s.always_on_top)
        self.sw_top.toggled.connect(lambda _on: self._apply_window_flags())
        col.addWidget(SettingsCard(Glyph.PIN, tr("set.top"), tr("set.top.text"), self.sw_top))
        self.sw_tray = self._toggle(s.close_to_tray)
        col.addWidget(SettingsCard(Glyph.MINIMIZE, tr("set.tray"), tr("set.tray.text"), self.sw_tray))
        self.sw_updates = self._toggle(s.check_updates)
        col.addWidget(SettingsCard(Glyph.UPDATE, tr("set.updates"), tr("set.updates.text"), self.sw_updates))
        open_diag = push_button(tr("button.open"))
        open_diag.clicked.connect(lambda: self.show_page(DIAGNOSTICS))
        col.addWidget(
            SettingsCard(Glyph.DIAGNOSTIC, tr("set.diagnostics"), tr("set.diagnostics.text"), open_diag)
        )

        self._group(col, tr("group.about"))
        source = push_button(tr("button.source"))
        source.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        col.addWidget(SettingsCard(Glyph.INFO, APP_NAME, tr("set.about.text", version=__version__), source))
        col.addStretch(1)
        return self._scrolling(page)

    def _channel_box(
        self, edit: QLineEdit, help_text: str, on_test: Callable[[], None]
    ) -> tuple[Card, QLabel, QPushButton]:
        box = Card()
        b_col = QVBoxLayout(box)
        b_col.setContentsMargins(56, 12, 16, 12)
        b_col.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(edit, 1)
        test = push_button(tr("button.send_test"))
        test.clicked.connect(on_test)
        row.addWidget(test)
        b_col.addLayout(row)
        note = label(help_text, 12, "secondary", wrap=True)
        b_col.addWidget(note)
        return box, note, test

    def _hotkey_combo(self, value: str) -> QComboBox:
        combo = combo_box()
        combo.addItems(HOTKEYS)
        combo.setCurrentText(value)
        combo.setFixedWidth(110)
        combo.currentTextChanged.connect(self._on_hotkey_changed)
        return combo

    def _toggle(self, checked: bool) -> ToggleSwitch:
        sw = ToggleSwitch(checked, tr("toggle.on"), tr("toggle.off"))
        sw.toggled.connect(self._queue_save)
        return sw

    # ── Diagnostics page ────────────────────────────────────────────────────

    def _build_diagnostics_page(self) -> QWidget:
        page, col = self._page()
        col.setSpacing(4)
        self._header(col, tr("diag.title"), back=True)
        col.addSpacing(8)
        col.addWidget(label(tr("diag.intro"), 14, "secondary", wrap=True))
        col.addSpacing(16)

        card = Card()
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 12, 16, 12)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)
        self.diag_values: dict[str, QLabel] = {}
        self.diag_meters: dict[str, Meter] = {}
        rows = [
            ("window", "diag.window"),
            ("gamelog", "diag.gamelog"),
            ("display", "diag.display"),
            ("red", "diag.red"),
            ("yellow", "diag.yellow"),
            ("esc", "diag.esc"),
        ]
        for r, (key, title) in enumerate(rows):
            grid.addWidget(label(tr(title), 14, "secondary"), r, 0, Qt.AlignmentFlag.AlignTop)
            cell = QVBoxLayout()
            cell.setSpacing(4)
            value = label("…", 14, wrap=True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setAccessibleName(tr(title))
            cell.addWidget(value)
            self.diag_values[key] = value
            if key in ("red", "yellow"):
                threshold = detection.RED_FULL_RATIO if key == "red" else detection.YELLOW_QUEUE_RATIO
                meter = Meter(threshold, threshold * 3)
                cell.addWidget(meter)
                self.diag_meters[key] = meter
            grid.addLayout(cell, r, 1)
        grid.setColumnStretch(1, 1)
        col.addWidget(card)
        col.addSpacing(4)

        verdict = Card()
        v_row = QHBoxLayout(verdict)
        v_row.setContentsMargins(16, 12, 16, 12)
        v_row.setSpacing(12)
        self.diag_verdict_icon = GlyphIcon(Glyph.INFO, 16, "text_secondary")
        v_row.addWidget(self.diag_verdict_icon)
        self.diag_verdict = label("", 14, wrap=True)
        v_row.addWidget(self.diag_verdict, 1)
        col.addWidget(verdict)

        col.addSpacing(16)
        col.addWidget(label(tr("diag.preview"), 14, weight=SEMIBOLD))
        col.addSpacing(4)
        self.diag_preview = QLabel()
        self.diag_preview.setObjectName("preview")
        self.diag_preview.setMinimumHeight(90)
        self.diag_preview.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.diag_preview.setAccessibleName(tr("diag.preview"))
        col.addWidget(self.diag_preview)

        col.addSpacing(16)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.copy_btn = push_button(tr("diag.copy"))
        self.copy_btn.clicked.connect(self._copy_report)
        buttons.addWidget(self.copy_btn)
        logs_btn = push_button(tr("diag.logs"))
        logs_btn.clicked.connect(open_log_folder)
        buttons.addWidget(logs_btn)
        buttons.addStretch(1)
        col.addLayout(buttons)
        col.addSpacing(6)
        col.addWidget(label(tr("diag.logs.text"), 12, "secondary", wrap=True))
        col.addStretch(1)
        return self._scrolling(page)

    def _close_diag_vision(self) -> None:
        if self._diag_vision is not None:
            self._diag_vision.__exit__(None, None, None)
            self._diag_vision = None

    def _refresh_diagnostics(self) -> None:
        title, exe = winapi.foreground_window_info()
        is_arma = winapi.is_arma_window(title, exe)
        window_text = f"{title or '—'} ({exe or '?'})\n" + tr(
            "diag.window.arma" if is_arma else "diag.window.other"
        )
        self.diag_values["window"].setText(window_text)
        game_log = latest_console_log(default_logs_dir())
        self.diag_values["gamelog"].setText(str(game_log) if game_log else tr("diag.gamelog.none"))
        report = {
            "version": __version__,
            "windows": platform.version(),
            "language": self.settings.language,
            "window": exe or "?",  # no title: it can contain private text
            "arma": is_arma,
        }
        try:
            x, y = winapi.get_cursor_pos()
            if self._diag_vision is None:
                self._diag_vision = ScreenVision(x, y).__enter__()
            self._diag_vision.retarget(x, y)
            mon = self._diag_vision.monitor
            pixels = self._diag_vision.grab_dialog()
            reading = detection.analyze_dialog(pixels)
            esc = self._diag_vision.find_esc()
        except Exception as exc:  # screen capture can fail on locked or remote sessions
            self._close_diag_vision()
            self.diag_verdict.setText(tr("diag.unavailable", error=exc))
            log.warning("Diagnostics capture failed: %s", exc)
            return

        display = f"{mon['width']} × {mon['height']}"
        self.diag_values["display"].setText(display)
        for key, value, limit in (
            ("red", reading.red, detection.RED_FULL_RATIO),
            ("yellow", reading.yellow, detection.YELLOW_QUEUE_RATIO),
        ):
            self.diag_values[key].setText(tr("diag.share", value=percent(value), limit=percent(limit)))
            self.diag_meters[key].set_value(value)
        self.diag_values["esc"].setText(
            tr("diag.esc.found", x=esc[0], y=esc[1]) if esc else tr("diag.esc.none")
        )
        if reading.server_full:
            verdict, glyph, role = "diag.verdict.full", Glyph.WARNING, "caution"
        elif reading.in_queue:
            verdict, glyph, role = "diag.verdict.queue", Glyph.DONE, "success"
        else:
            verdict, glyph, role = "diag.verdict.none", Glyph.INFO, "text_secondary"
        self.diag_verdict.setText(tr(verdict))
        self.diag_verdict_icon.set_glyph(glyph, role)

        image = QImage(
            pixels.data, pixels.shape[1], pixels.shape[0], pixels.strides[0], QImage.Format.Format_ARGB32
        ).copy()
        width = max(120, self.diag_preview.width() - 2)
        self.diag_preview.setPixmap(
            QPixmap.fromImage(image).scaledToWidth(
                min(width, image.width()), Qt.TransformationMode.SmoothTransformation
            )
        )

        report.update(
            {
                "display": display,
                "red": percent(reading.red),
                "yellow": percent(reading.yellow),
                "red_limit": percent(detection.RED_FULL_RATIO),
                "yellow_limit": percent(detection.YELLOW_QUEUE_RATIO),
                "esc_button": esc,
                "verdict": verdict.rsplit(".", 1)[-1],
            }
        )
        private = {"ntfy_topic", "discord_webhook"}
        settings = {k: v for k, v in dataclasses.asdict(self.settings).items() if k not in private}
        lines = (
            [f"{k}: {v}" for k, v in report.items()]
            + ["settings:"]
            + [f"  {k}: {v}" for k, v in settings.items()]
        )
        lines.append(f"log: {logs.log_dir() / 'aqj.log'}")
        self._last_report = "\n".join(lines)

    def _copy_report(self) -> None:
        QGuiApplication.clipboard().setText(self._last_report)
        self.copy_btn.setText(tr("diag.copied"))
        QTimer.singleShot(1500, lambda: self.copy_btn.setText(tr("diag.copy")))

    # ── Theme and language ──────────────────────────────────────────────────

    def apply_theme(self) -> None:
        c = theme.colors()
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyleSheet(theme.stylesheet(c))
        winapi.set_title_bar_theme(int(self.winId()), c.dark)
        self._render_activity()
        self.update()

    def _on_language_changed(self, _index: int) -> None:
        self._save_settings()
        set_language(self.settings.language)
        current = self.pages.currentIndex()
        self._build_pages()
        self.pages.setCurrentIndex(current)
        self._update_tray_texts()
        self._render(self._ui_state, self._detail)
        self._render_activity()

    # ── Settings ────────────────────────────────────────────────────────────

    def _collect(self) -> Settings:
        start, stop = self._keys()
        if start == stop:  # refused in the UI; keep the last valid pair
            start, stop = self.settings.start_hotkey, self.settings.stop_hotkey
        return Settings(
            start_hotkey=start,
            stop_hotkey=stop,
            fast_esc=self.sw_fast_esc.isChecked(),
            require_game_focus=self.sw_focus.isChecked(),
            stop_on_mouse_move=self.sw_mouse.isChecked(),
            sound=self.sw_sound.isChecked(),
            phone_notify=self.sw_phone.isChecked(),
            ntfy_topic=self.topic_edit.text(),
            discord_notify=self.sw_discord.isChecked(),
            discord_webhook=self.webhook_edit.text(),
            notify_queue=self.sw_notify_queue.isChecked(),
            notify_game=self.sw_notify_game.isChecked(),
            always_on_top=self.sw_top.isChecked(),
            close_to_tray=self.sw_tray.isChecked(),
            check_updates=self.sw_updates.isChecked(),
            language=str(self.combo_lang.currentData()),
            **{name: spin.value() for name, spin in self.spins.items()},
        ).normalized()

    def _queue_save(self, *_args: Any) -> None:
        self._save_timer.start()

    def _save_settings(self) -> None:
        self.settings = self._collect()
        try:
            self.settings.save()
        except OSError as exc:
            self._log(msg("log.settings_failed", error=exc))

    def _on_hotkey_changed(self, _text: str) -> None:
        start, stop = self.combo_start.currentText(), self.combo_stop.currentText()
        if start == stop:
            self.hotkey_note.setText(tr("set.keys_same"))
            self.hotkey_note.show()
            return
        self.hotkey_note.hide()
        self._queue_save()
        self._rebind_hotkeys(start, stop)
        self._render(self._ui_state, self._detail)

    def _rebind_hotkeys(self, start: str | None = None, stop: str | None = None) -> None:
        self.hotkeys.bind(
            {"start": start or self.settings.start_hotkey, "stop": stop or self.settings.stop_hotkey}
        )

    def _keys(self) -> tuple[str, str]:
        return self.combo_start.currentText(), self.combo_stop.currentText()

    def _on_phone_toggled(self, checked: bool, save: bool = True) -> None:
        if checked and not self.topic_edit.text().strip():
            self.topic_edit.setText(f"aqj-{secrets.token_hex(4)}")
        self.phone_box.setVisible(checked)
        if save:
            self._queue_save()

    def _on_discord_toggled(self, checked: bool, save: bool = True) -> None:
        self.discord_box.setVisible(checked)
        if save:
            self._queue_save()

    def _send_test(self, channel: str) -> None:
        self._save_settings()
        s = self.settings
        button, note = (
            (self.phone_test, self.phone_note)
            if channel == "ntfy"
            else (self.discord_test, self.discord_note)
        )
        if channel == "Discord" and not notify.is_discord_webhook(s.discord_webhook):
            note.setText(tr("set.discord.invalid"))
            return
        button.setEnabled(False)
        button.setText(tr("button.sending"))
        text = tr("push.test")

        def job() -> None:
            if channel == "ntfy":
                notify.send_ntfy(s.ntfy_topic, tr("push.title"), text)
            else:
                notify.send_discord(s.discord_webhook, text)

        net.in_background(
            job, lambda _r, err: self.bridge.test_result.emit(channel, "" if err is None else str(err))
        )

    def _on_test_result(self, channel: str, error: str) -> None:
        button, note = (
            (self.phone_test, self.phone_note)
            if channel == "ntfy"
            else (self.discord_test, self.discord_note)
        )
        button.setEnabled(True)
        button.setText(tr("button.send_test"))
        if error:
            note.setText(tr("test.failed", error=error))
            self._log(msg("log.notify_failed", channel=channel, error=error))
        else:
            note.setText(tr("test.ntfy.ok" if channel == "ntfy" else "test.discord.ok"))
            self._log(msg("log.test_sent", channel=channel))

    def _apply_window_flags(self) -> None:
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.sw_top.isChecked())
        if visible:
            self.show()

    # ── Status rendering ────────────────────────────────────────────────────

    def _render(self, kind: str, detail: Message | None = None) -> None:
        self._ui_state = kind
        self._detail = detail
        start, stop = self._keys()
        detail_text = text_of(detail) if detail else ""
        glyph, role, title, text, button, accent = {
            "idle": (
                Glyph.READY,
                "accent",
                tr("status.idle.title"),
                detail_text or tr("status.idle.text", start=start),
                tr("button.start"),
                True,
            ),
            "countdown": (
                Glyph.TIMER,
                "accent",
                tr("status.countdown.title", n=self._countdown_left),
                tr("status.countdown.text"),
                tr("button.cancel"),
                False,
            ),
            "running": (
                Glyph.SYNC,
                "accent",
                tr("status.running.title"),
                tr("status.running.text", detail=detail_text, stop=stop) if detail_text else "",
                tr("button.stop"),
                False,
            ),
            "paused": (
                Glyph.PAUSE,
                "caution",
                tr("status.paused.title"),
                detail_text,
                tr("button.stop"),
                False,
            ),
            "success": (
                Glyph.DONE,
                "success",
                tr("status.success.title"),
                tr("status.success.watching" if self._watch else "status.success.text", detail=detail_text),
                tr("button.start_again"),
                True,
            ),
            "joining": (
                Glyph.SYNC,
                "accent",
                tr("status.joining.title"),
                detail_text,
                tr("button.start_again"),
                True,
            ),
            "in_game": (
                Glyph.DONE,
                "success",
                tr("status.in_game.title"),
                detail_text,
                tr("button.start_again"),
                True,
            ),
            "queue_lost": (
                Glyph.WARNING,
                "caution",
                tr("status.queue_lost.title"),
                tr("status.queue_lost.text"),
                tr("button.start_again"),
                True,
            ),
            "error": (
                Glyph.ERROR,
                "critical",
                tr("status.error.title"),
                tr("status.error.text", detail=detail_text),
                tr("button.start"),
                True,
            ),
        }[kind]
        self.status_icon.set_glyph(glyph, role)
        self.status_title.setText(title)
        self.status_detail.setText(text)
        self.status_title.setAccessibleName(f"{title}. {text}")
        if QAccessible.isActive():  # let screen readers announce the new status
            event = QAccessibleEvent(self.status_title, QAccessible.Event.NameChanged)
            QAccessible.updateAccessibility(event)
        self.action.setText(button)
        self.action.setProperty("accent", accent)
        self.action.style().unpolish(self.action)
        self.action.style().polish(self.action)
        self.hotkey_card.set_description(tr("main.hotkeys.text", start=start, stop=stop))
        self._refresh_stats()

    def _refresh_stats(self) -> None:
        if self._started_at is None or self._ui_state in ("idle", "countdown"):
            self.status_stats.hide()
            return
        end = self._finished_at or time.monotonic()
        self.status_stats.setText(f"{fmt_elapsed(end - self._started_at)} · {attempts(self._attempts)}")
        self.status_stats.show()

    # ── Start / stop ────────────────────────────────────────────────────────

    def _on_action(self) -> None:
        if self._ui_state in ("running", "paused"):
            self.stop()
        elif self._ui_state == "countdown":
            self._countdown.stop()
            self._render("idle")
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
        self._stop_watch()
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
        log.info("Start at %s with %s", pos, config)
        self._clear_activity()
        self._attempts = 0
        self._started_at = time.monotonic()
        self._finished_at = None
        self._render("running", msg("state.starting"))
        self._clock.start()
        self.joiner.start(pos, config)

    def stop(self) -> None:
        self._stop_watch()
        if self._ui_state == "countdown":
            self._countdown.stop()
            self._render("idle")
        self.joiner.stop()

    # ── Worker events ───────────────────────────────────────────────────────

    def _connect_bridge(self) -> None:
        self.bridge.state.connect(self._on_state)
        self.bridge.attempt.connect(self._on_attempt)
        self.bridge.log.connect(self._log)
        self.bridge.hotkey.connect(self._on_hotkey)
        self.bridge.hotkey_error.connect(self._on_hotkey_error)
        self.bridge.test_result.connect(self._on_test_result)
        self.bridge.update_found.connect(self._on_update_found)
        self.bridge.crash.connect(self.show_crash)

    def _on_attempt(self, n: int) -> None:
        self._attempts = n
        self._refresh_stats()

    def _on_hotkey(self, action: str) -> None:
        if action == "start" and self._ui_state not in ("running", "paused"):
            self.start_at(winapi.get_cursor_pos())
        elif action == "stop":
            self.stop()

    def _on_hotkey_error(self, key: str) -> None:
        self.hotkey_note.setText(tr("set.key_taken", key=key))
        self.hotkey_note.show()
        log.warning("Hotkey %s is taken by another program", key)

    def _on_state(self, state: str, detail: Message) -> None:
        log.info("State %s: %s", state, detail.key)
        if state in ("success", "error", "idle"):
            self._clock.stop()
            self._finished_at = time.monotonic()
        if state == "success":
            self._start_watch()
        self._render(state, detail)
        if state == "success" and self.settings.notify_queue:
            elapsed = fmt_elapsed((self._finished_at or 0) - (self._started_at or self._finished_at or 0))
            n = int(detail.params.get("n", self._attempts))
            self._announce(tr("push.title"), tr("push.text", n=n, time=elapsed))

    # ── After the queue: follow the game's own log ──────────────────────────

    def _start_watch(self) -> None:
        self._stop_watch()
        if not self.settings.notify_game:
            return
        follower = LogFollower(default_logs_dir())
        if follower.path is None:
            self._log(msg("log.watch_missing"))
            return
        self._watch = QueueWatch(follower)
        self._watch_started = time.monotonic()
        self._watch_timer.start()
        self._log(msg("log.watch_start", path=follower.path.parent.name))

    def _stop_watch(self) -> None:
        self._watch_timer.stop()
        self._watch = None

    def _poll_game_log(self) -> None:
        watch = self._watch
        if watch is None:
            return
        if time.monotonic() - self._watch_started > WATCH_LIMIT:
            self._log(msg("log.watch_timeout"))
            self._stop_watch()
            return
        stage = watch.update()
        server = watch.server or tr("unknown_server")
        if stage is Stage.JOINING:
            self._log(msg("log.joining", server=server))
            self._render("joining", msg("status.joining.text", server=server))
        elif stage is Stage.IN_GAME:
            self._log(msg("log.in_game", server=server))
            self._render("in_game", msg("status.in_game.text", server=server))
            self._announce(tr("push.in_game.title"), tr("push.in_game.text", server=server))
        elif stage is Stage.QUEUE_LOST:
            self._log(msg("log.dropped"))
            self._render("queue_lost")
            self._announce(tr("push.queue_lost.title"), tr("push.queue_lost.text"))
        if watch.finished:
            self._stop_watch()

    def _announce(self, title: str, text: str) -> None:
        """Sound, taskbar flash, Windows notification, phone and Discord, as configured."""
        s = self.settings
        if s.sound:
            notify.play_alert()
        winapi.flash_taskbar(int(self.winId()))
        if self.tray is not None:
            self.tray.showMessage(title, text, self._icon, 6000)

        def report(channel: str) -> Callable[[Any, Exception | None], None]:
            return lambda _r, err: (
                err and self.bridge.log.emit(msg("log.notify_failed", channel=channel, error=err))
            )

        if s.phone_notify and s.ntfy_topic:
            net.in_background(lambda: notify.send_ntfy(s.ntfy_topic, title, text), report("ntfy"))
        if s.discord_notify and notify.is_discord_webhook(s.discord_webhook):
            net.in_background(lambda: notify.send_discord(s.discord_webhook, text), report("Discord"))

    def _on_update_found(self, release: updates.Release) -> None:
        self._release = release
        log.info("Update available: %s", release.version)
        self.update_text.setText(tr("update.available", version=release.version))
        self.update_bar.show()

    def _open_release(self) -> None:
        if self._release is not None:
            QDesktopServices.openUrl(QUrl(self._release.url))

    def show_crash(self, error: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(APP_NAME)
        box.setText(tr("crash.title"))
        box.setInformativeText(tr("crash.text", error=error))
        open_logs = box.addButton(tr("diag.logs"), QMessageBox.ButtonRole.ActionRole)
        box.addButton(tr("button.close"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is open_logs:
            open_log_folder()

    # ── Activity ────────────────────────────────────────────────────────────

    def _log(self, message: Message) -> None:
        entry = (time.strftime("%H:%M:%S"), message)
        self._activity.append(entry)
        log.info("%s %s", message.key, message.params)  # the log file stays language-neutral
        self._append_entry(*entry)

    def _append_entry(self, stamp: str, message: Message) -> None:
        c = theme.colors()
        self.activity_view.appendHtml(
            f'<span style="color:{c.text_tertiary.name()}">{stamp}</span>&nbsp;&nbsp;'
            f'<span style="color:{c.text.name()}">{html.escape(text_of(message))}</span>'
        )

    def _render_activity(self) -> None:
        if not hasattr(self, "activity_view"):
            return
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
        self._tray_actions = {
            "tray.open": QAction(self),
            "tray.stop": QAction(self),
            "tray.quit": QAction(self),
        }
        self._tray_actions["tray.open"].triggered.connect(self.show_window)
        self._tray_actions["tray.stop"].triggered.connect(self.stop)
        self._tray_actions["tray.quit"].triggered.connect(self.quit)
        menu.addAction(self._tray_actions["tray.open"])
        menu.addAction(self._tray_actions["tray.stop"])
        menu.addSeparator()
        menu.addAction(self._tray_actions["tray.quit"])
        self.tray.setContextMenu(menu)
        self._update_tray_texts()
        self.tray.activated.connect(
            lambda reason: self.show_window() if reason == QSystemTrayIcon.ActivationReason.Trigger else None
        )
        self.tray.show()

    def _update_tray_texts(self) -> None:
        for key, action in getattr(self, "_tray_actions", {}).items():
            action.setText(tr(key))

    def show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Esc goes back from Settings and Diagnostics, like in Windows Settings."""
        if event.key() == Qt.Key.Key_Escape and self.pages.currentIndex() != MAIN:
            self.show_page(MAIN)
            return
        super().keyPressEvent(event)

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        winapi.set_title_bar_theme(int(self.winId()), theme.is_dark())

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._quitting and self.tray is not None and self.sw_tray.isChecked():
            event.ignore()
            self.hide()
            self.show_page(MAIN)
            if not self._tray_hint_shown:
                self._tray_hint_shown = True
                self.tray.showMessage(APP_NAME, tr("tray.still_running"), self._icon, 3000)
            return
        self._shutdown()
        event.accept()
        QApplication.quit()

    def quit(self) -> None:
        self._quitting = True
        self.close()

    def _shutdown(self) -> None:
        self._stop_watch()
        self._save_timer.stop()
        self._diag_timer.stop()
        self._close_diag_vision()
        self._save_settings()
        self.joiner.stop()
        self.joiner.join(1.0)
        self.hotkeys.shutdown()
        if self.tray is not None:
            self.tray.hide()
        log.info("Closed")


def push_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(POINTING)
    return btn


def combo_box() -> QComboBox:
    combo = QComboBox()
    combo.setCursor(POINTING)
    return combo


def open_log_folder() -> None:
    folder = logs.log_dir()
    folder.mkdir(parents=True, exist_ok=True)
    os.startfile(folder)

"""
Arma Reforger Queue Joiner | by lime98 aka micorytican
"""

import ctypes
import ctypes.wintypes
import dataclasses
import json
import os
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import keyboard
import mss
import numpy as np
import pystray
import winsound
from PIL import Image as PILImage

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32

_SETTINGS_PATH = Path(os.environ.get("APPDATA", Path.home())) / "ArmaQueueJoiner" / "settings.json"


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def move_and_click(x: int, y: int) -> None:
    user32.SetCursorPos(x, y)
    time.sleep(0.015)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.015)
    user32.mouse_event(0x0004, 0, 0, 0, 0)


def press_escape(duration: float) -> None:
    user32.keybd_event(0x1B, 0x01, 0x0008, 0)
    time.sleep(duration)
    user32.keybd_event(0x1B, 0x01, 0x000A, 0)


def get_cursor_pos() -> tuple[int, int]:
    pt = _POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def fmt_elapsed(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"


@dataclasses.dataclass
class Settings:
    wait_after_click: float = 0.1
    escape_hold: float = 0.1
    pause_before_retry: float = 0.0
    experimental: bool = False
    start_hotkey: str = "F6"
    stop_hotkey: str = "F4"
    mute: bool = False

    @classmethod
    def load(cls) -> "Settings":
        s = cls()
        try:
            if _SETTINGS_PATH.exists():
                data = json.loads(_SETTINGS_PATH.read_text("utf-8"))
                for field in dataclasses.fields(s):
                    if field.name in data:
                        try:
                            raw = data[field.name]
                            # json.loads returns native Python bools for JSON booleans,
                            # so bool(raw) works correctly for the experimental field.
                            setattr(s, field.name, type(getattr(s, field.name))(raw))
                        except (ValueError, TypeError):
                            pass
        except Exception:
            pass
        return s

    def save(self) -> None:
        try:
            _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            _SETTINGS_PATH.write_text(
                json.dumps(dataclasses.asdict(self), indent=2), "utf-8"
            )
        except Exception:
            pass


class QueueJoiner:
    def __init__(self, on_log, on_state_change):
        self.on_log = on_log
        self.on_state_change = on_state_change
        self.running = False
        self.experimental = False
        self.mouse_x = 0
        self.mouse_y = 0
        self.game_monitor = None
        self.attempt = 0
        self.wait_after_click = 0.1
        self.escape_hold = 0.1
        self.pause_before_retry = 0.0
        self.mute = False
        self._sct = None

    def _find_game_monitor(self, mx: int, my: int):
        for mon in self._sct.monitors[1:]:
            if mon["left"] <= mx < mon["left"] + mon["width"] and mon["top"] <= my < mon["top"] + mon["height"]:
                return mon
        return self._sct.monitors[1]

    def _grab_region(self, left_pct: float, top_pct: float, right_pct: float, bottom_pct: float) -> np.ndarray:
        mon = self.game_monitor
        w, h = mon["width"], mon["height"]
        region = {
            "top":    mon["top"]  + int(h * top_pct),
            "left":   mon["left"] + int(w * left_pct),
            "width":  int(w * (right_pct - left_pct)),
            "height": int(h * (bottom_pct - top_pct)),
        }
        shot = self._sct.grab(region)
        return np.frombuffer(shot.bgra, dtype=np.uint8).reshape(shot.height, shot.width, 4)

    def read_colors(self) -> tuple[int, int]:
        arr = self._grab_region(0.28, 0.28, 0.52, 0.45)
        r, g, b = arr[:, :, 2], arr[:, :, 1], arr[:, :, 0]
        yellow = int(((r > 180) & (g > 130) & (b < 80)).sum())
        red    = int(((r > 180) & (g < 80)  & (b < 80)).sum())
        return yellow, red

    def find_esc_position(self) -> tuple[int, int] | None:
        arr = self._grab_region(0.05, 0.65, 0.45, 0.95)
        r, g, b = arr[:, :, 2], arr[:, :, 1], arr[:, :, 0]
        mask = (r > 200) & (g > 160) & (b < 90) & (g < 230)

        if np.sum(mask) < 300:
            return None

        ys, xs = np.where(mask)
        rel_x = int(xs.mean())
        rel_y = int(ys.mean())

        mon = self.game_monitor
        esc_x = mon["left"] + int(mon["width"] * 0.05) + rel_x
        esc_y = mon["top"]  + int(mon["height"] * 0.65) + rel_y

        self.on_log(f"ESC button AUTO-detected at ({esc_x}, {esc_y})")
        return esc_x, esc_y

    def click_escape(self) -> None:
        if self.experimental:
            pos = self.find_esc_position()
            if pos:
                x, y = pos
                move_and_click(x, y)
                time.sleep(0.05)
                return
            self.on_log("ESC auto-detection failed → fallback to keypress")

        press_escape(self.escape_hold)

    def _poll_sleep(self, duration: float) -> bool:
        """Sleep in 100ms increments; returns False if stopped early."""
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            if not self.running:
                return False
            time.sleep(0.1)
        return True

    def _wait_for_server_full(self, timeout: float) -> bool:
        """Poll every 100ms for server-full dialog; return True if detected within timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.running:
                return False
            _, red = self.read_colors()
            if red > 50:
                return True
            time.sleep(0.1)
        return False

    def start(self, mouse_x: int, mouse_y: int) -> None:
        """Entry point for worker thread — wraps _run with a crash watchdog."""
        try:
            self._run(mouse_x, mouse_y)
        except Exception as exc:
            self.on_log(f"ERROR: {exc}")
            self.running = False
            self.on_state_change("idle")
        finally:
            self._sct = None

    def _run(self, mouse_x: int, mouse_y: int) -> None:
        self.running = True
        self.attempt = 0
        self.mouse_x = mouse_x
        self.mouse_y = mouse_y

        with mss.mss() as self._sct:
            self.game_monitor = self._find_game_monitor(mouse_x, mouse_y)

            self.on_log(f"Target server button: ({self.mouse_x}, {self.mouse_y})")
            self.on_log(f"Experimental mouse-ESC mode: {'ENABLED' if self.experimental else 'DISABLED'}")
            self.on_state_change("running")

            if not self._poll_sleep(0.3):
                return

            while self.running:
                self.attempt += 1
                self.on_log(f"[{self.attempt}] Clicking server button...")
                move_and_click(self.mouse_x, self.mouse_y)
                time.sleep(0.1)
                move_and_click(self.mouse_x, self.mouse_y)

                # Adaptive wait: exit as soon as server-full dialog appears
                if self._wait_for_server_full(self.wait_after_click):
                    self.on_log(f"[{self.attempt}] Server full → clicking ESC")
                    self.click_escape()
                    self._poll_sleep(self.pause_before_retry)
                    continue

                if not self.running:
                    break

                self.on_log(f"[{self.attempt}] Waiting 8s for connect/queue screen...")
                still_there = True
                for i in range(8):
                    if not self._poll_sleep(1.0):
                        break
                    _, red = self.read_colors()
                    if red > 50:
                        self.on_log(f"[{self.attempt}] Server full after {i+1}s → ESC")
                        still_there = False
                        self.click_escape()
                        self._poll_sleep(self.pause_before_retry)
                        break

                if not self.running or not still_there:
                    continue

                # === QUEUE CHECK ===
                yellow, _ = self.read_colors()
                if yellow > 1500:
                    confirmed = True
                    for _ in range(3):
                        if not self._poll_sleep(1.0):
                            confirmed = False
                            break
                        yellow, _ = self.read_colors()
                        if yellow <= 1500:
                            confirmed = False
                            break
                    if confirmed:
                        self.on_log(f"[{self.attempt}] CONFIRMED — IN QUEUE!")
                        self.on_state_change("success")
                        self.running = False
                        self._play_alert()
                        return
                    else:
                        self.on_log(f"[{self.attempt}] Queue lost → ESC")
                        self.click_escape()
                        self._poll_sleep(self.pause_before_retry)
                else:
                    self.on_log(f"[{self.attempt}] Connect screen passed → retrying")
                    self._poll_sleep(self.pause_before_retry)

        self.on_log("Stopped.")
        self.on_state_change("idle")

    def stop(self) -> None:
        self.running = False

    def _play_alert(self) -> None:
        if self.mute:
            return
        try:
            for _ in range(3):
                winsound.Beep(1000, 300)
                time.sleep(0.1)
        except Exception:
            pass


class App(tk.Tk):
    WINDOW_WIDTH  = 440
    WINDOW_HEIGHT = 515
    HOTKEY_OPTIONS = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"]

    def __init__(self):
        super().__init__()
        self.settings = Settings.load()

        self.title("AQJ")
        self.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")
        self.resizable(False, False)
        self.configure(bg="#1e1e1e")

        self._icon_path = self._resolve_icon()
        if self._icon_path:
            self.iconbitmap(self._icon_path)

        self.joiner = QueueJoiner(on_log=self._append_log, on_state_change=self._update_state)
        self.worker_thread: threading.Thread | None = None
        self.registered_hooks: list = []
        self._tray: pystray.Icon | None = None
        self._timer_id: str | None = None
        self._start_time: float | None = None

        self._build_ui()
        self._register_hotkeys()
        self._setup_tray()
        self.protocol("WM_DELETE_WINDOW", self._minimize_to_tray)

    def _resolve_icon(self) -> str | None:
        if getattr(sys, "frozen", False):
            path = os.path.join(sys._MEIPASS, "icon.ico")
        else:
            path = os.path.join(os.path.dirname(__file__), "icon.ico")
        return path if os.path.exists(path) else None

    # ── Tray ──────────────────────────────────────────────────────────────────

    def _setup_tray(self) -> None:
        if not self._icon_path:
            return
        try:
            img = PILImage.open(self._icon_path)
            menu = pystray.Menu(
                pystray.MenuItem("Show", lambda icon, item: self.after(0, self._show_window), default=True),
                pystray.MenuItem("Stop", lambda icon, item: self.after(0, self._on_stop)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit", lambda icon, item: self.after(0, self._quit)),
            )
            self._tray = pystray.Icon("ArmaQueueJoiner", img, "Arma Queue Joiner", menu)
            self._tray.run_detached()
        except Exception:
            self._tray = None

    def _minimize_to_tray(self) -> None:
        if self._tray:
            self.withdraw()
        else:
            self._quit()

    def _show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def _quit(self) -> None:
        self.joiner.stop()
        if self._tray:
            try:
                self._tray.stop()
            except Exception:
                pass
        keyboard.unhook_all()
        self.destroy()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame",       background="#1e1e1e")
        style.configure("TLabel",       background="#1e1e1e", foreground="#cccccc", font=("Segoe UI", 10))
        style.configure("Header.TLabel",background="#1e1e1e", foreground="#ffffff", font=("Segoe UI", 14, "bold"))
        style.configure("Status.TLabel",background="#1e1e1e", foreground="#888888", font=("Segoe UI", 10))
        style.configure("SubHeader.TLabel", background="#1e1e1e", foreground="#666666", font=("Segoe UI", 9))

        ttk.Label(self, text="Arma Reforger Queue Joiner", style="Header.TLabel").pack(pady=(15, 2))
        ttk.Label(self, text="by lime98 aka micorytican", style="SubHeader.TLabel").pack(pady=(0, 8))

        ttk.Label(
            self,
            text="1. Open server browser\n"
                 "2. Hover mouse over JOIN button\n"
                 "3. Press START hotkey\n"
                 "4. Experimental = auto mouse-click ESC",
            style="TLabel",
            justify="left",
        ).pack(padx=20, pady=(0, 10))

        # Hotkeys
        hf = ttk.Frame(self)
        hf.pack(pady=(0, 8))
        ttk.Label(hf, text="Start:").grid(row=0, column=0, padx=(0, 5), pady=2)
        self.start_hotkey_var = tk.StringVar(value=self.settings.start_hotkey)
        sc = ttk.Combobox(hf, textvariable=self.start_hotkey_var, values=self.HOTKEY_OPTIONS, state="readonly", width=6)
        sc.grid(row=0, column=1, padx=(0, 25), pady=2)
        sc.bind("<<ComboboxSelected>>", lambda e: self._register_hotkeys())

        ttk.Label(hf, text="Stop:").grid(row=0, column=2, padx=(0, 5), pady=2)
        self.stop_hotkey_var = tk.StringVar(value=self.settings.stop_hotkey)
        sc2 = ttk.Combobox(hf, textvariable=self.stop_hotkey_var, values=self.HOTKEY_OPTIONS, state="readonly", width=6)
        sc2.grid(row=0, column=3, pady=2)
        sc2.bind("<<ComboboxSelected>>", lambda e: self._register_hotkeys())

        # Settings
        sf = ttk.Frame(self)
        sf.pack(pady=(0, 6))

        ttk.Label(sf, text="Wait after click (sec):").grid(row=0, column=0, sticky="w", pady=3)
        self.wait_var = tk.StringVar(value=str(self.settings.wait_after_click))
        ttk.Spinbox(sf, from_=0.1, to=10.0, increment=0.1, textvariable=self.wait_var, width=8).grid(row=0, column=1, padx=(10, 0), pady=3)
        self.wait_var.trace_add("write", lambda *_: self.after(0, self._save_settings))

        ttk.Label(sf, text="ESC hold (fallback, sec):").grid(row=1, column=0, sticky="w", pady=3)
        self.esc_var = tk.StringVar(value=str(self.settings.escape_hold))
        ttk.Spinbox(sf, from_=0.1, to=5.0, increment=0.1, textvariable=self.esc_var, width=8).grid(row=1, column=1, padx=(10, 0), pady=3)
        self.esc_var.trace_add("write", lambda *_: self.after(0, self._save_settings))

        ttk.Label(sf, text="Pause after ESC (sec):").grid(row=2, column=0, sticky="w", pady=3)
        self.pause_var = tk.StringVar(value=str(self.settings.pause_before_retry))
        ttk.Spinbox(sf, from_=0.0, to=2.0, increment=0.05, textvariable=self.pause_var, width=8).grid(row=2, column=1, padx=(10, 0), pady=3)
        self.pause_var.trace_add("write", lambda *_: self.after(0, self._save_settings))

        self.experimental_var = tk.BooleanVar(value=self.settings.experimental)
        ttk.Checkbutton(
            sf, text="Experimental Mode: FAST ESC",
            variable=self.experimental_var, command=self._save_settings,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=4)

        self.mute_var = tk.BooleanVar(value=self.settings.mute)
        ttk.Checkbutton(
            sf, text="Mute alert sound",
            variable=self.mute_var, command=self._save_settings,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=4)

        # Status
        self.status_label = ttk.Label(self, text="Status: Idle", style="Status.TLabel")
        self.status_label.pack(pady=(5, 3))

        # Log
        lf = tk.Frame(self, bg="#1e1e1e")
        lf.pack(padx=20, pady=(0, 15), fill="both", expand=True)
        self.log_text = tk.Text(lf, bg="#111111", fg="#aaaaaa", font=("Consolas", 9), relief="flat",
                                state="disabled", wrap="word")
        sb = ttk.Scrollbar(lf, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

    def _save_settings(self) -> None:
        try:
            self.settings.wait_after_click = float(self.wait_var.get())
            self.settings.escape_hold = float(self.esc_var.get())
            self.settings.pause_before_retry = float(self.pause_var.get())
            self.settings.experimental = bool(self.experimental_var.get())
            self.settings.mute = bool(self.mute_var.get())
            self.settings.start_hotkey = self.start_hotkey_var.get()
            self.settings.stop_hotkey = self.stop_hotkey_var.get()
            self.settings.save()
        except ValueError:
            pass

    # ── Hotkeys ───────────────────────────────────────────────────────────────

    def _register_hotkeys(self) -> None:
        for h in self.registered_hooks:
            try:
                keyboard.unhook(h)
            except Exception:
                pass
        self.registered_hooks.clear()

        sk = self.start_hotkey_var.get()
        ek = self.stop_hotkey_var.get()
        if sk == ek:
            self._append_log("ERROR: Start and Stop hotkeys must be different!")
            return

        # Callbacks fire on keyboard's background thread → marshal to main thread via after()
        self.registered_hooks = [
            keyboard.on_press_key(sk, lambda e: self.after(0, self._on_start), suppress=False),
            keyboard.on_press_key(ek, lambda e: self.after(0, self._on_stop),  suppress=False),
        ]
        self._save_settings()

    def _on_start(self) -> None:
        if self.joiner.running:
            return

        mx, my = get_cursor_pos()
        try:
            self.joiner.wait_after_click = float(self.wait_var.get())
            self.joiner.escape_hold = float(self.esc_var.get())
            self.joiner.pause_before_retry = float(self.pause_var.get())
            self.joiner.experimental = self.experimental_var.get()
            self.joiner.mute = self.mute_var.get()
        except ValueError:
            self._append_log("ERROR: Invalid numeric settings.")
            return

        self._clear_log()
        self.worker_thread = threading.Thread(target=self.joiner.start, args=(mx, my), daemon=True)
        self.worker_thread.start()

    def _on_stop(self) -> None:
        self.joiner.stop()

    # ── Log ───────────────────────────────────────────────────────────────────

    def _append_log(self, msg: str) -> None:
        def u():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", f"{msg}\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.after(0, u)

    def _clear_log(self) -> None:
        def u():
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")
        self.after(0, u)

    # ── State / timer ─────────────────────────────────────────────────────────

    def _update_state(self, state: str) -> None:
        def u():
            if state == "running":
                self._start_time = time.monotonic()
                self.status_label.configure(text="Status: Running... 00:00", foreground="#e8a832")
                self._tick_timer()
            elif state == "success":
                self._cancel_timer()
                self.status_label.configure(text="Status: IN QUEUE! ✓", foreground="#2dcc5e")
                if self._tray:
                    try:
                        self._tray.notify("You're in the queue!", "Arma Queue Joiner")
                    except Exception:
                        pass
            else:
                self._cancel_timer()
                self.status_label.configure(text="Status: Idle", foreground="#888888")
        self.after(0, u)

    def _tick_timer(self) -> None:
        if self._start_time is None or not self.joiner.running:
            return
        elapsed = int(time.monotonic() - self._start_time)
        self.status_label.configure(text=f"Status: Running... {fmt_elapsed(elapsed)}")
        self._timer_id = self.after(1000, self._tick_timer)

    def _cancel_timer(self) -> None:
        if self._timer_id is not None:
            self.after_cancel(self._timer_id)
            self._timer_id = None
        self._start_time = None


if __name__ == "__main__":
    app = App()
    app.mainloop()

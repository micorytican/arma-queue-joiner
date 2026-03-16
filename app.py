"""
Arma Reforger Queue Joiner | by lime98
"""

import ctypes
import ctypes.wintypes
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

import keyboard
import mss
import numpy as np
import winsound
from PIL import Image

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32


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


def find_game_monitor(mx: int, my: int):
    with mss.mss() as sct:
        for mon in sct.monitors[1:]:
            if mon["left"] <= mx < mon["left"] + mon["width"] and mon["top"] <= my < mon["top"] + mon["height"]:
                return mon
        return sct.monitors[1]


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
        self.wait_after_click = 0.5
        self.escape_hold = 1.5
        self.pause_before_retry = 0.3

    def read_colors(self):
        with mss.mss() as sct:
            shot = sct.grab(self.game_monitor)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        w, h = img.size
        region = img.crop((int(w * 0.28), int(h * 0.28), int(w * 0.52), int(h * 0.45)))
        arr = np.array(region)
        yellow = int(((arr[:, :, 0] > 180) & (arr[:, :, 1] > 130) & (arr[:, :, 2] < 80)).sum())
        red = int(((arr[:, :, 0] > 180) & (arr[:, :, 1] < 80) & (arr[:, :, 2] < 80)).sum())
        return yellow, red

    def is_server_full(self) -> bool:
        _, red = self.read_colors()
        return red > 50

    def is_queue_text_visible(self) -> bool:
        yellow, _ = self.read_colors()
        return yellow > 1500

    def find_esc_position(self) -> tuple[int, int] | None:
        with mss.mss() as sct:
            shot = sct.grab(self.game_monitor)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            arr = np.array(img)

        h, w = arr.shape[:2]
        roi = arr[int(h * 0.65):int(h * 0.95), int(w * 0.05):int(w * 0.45)]

        mask = (
            (roi[:, :, 0] > 200) &
            (roi[:, :, 1] > 160) &
            (roi[:, :, 2] < 90) &
            (roi[:, :, 1] < 230)
        )

        if np.sum(mask) < 300:  # button is ~500-800px when visible
            return None

        ys, xs = np.where(mask)
        rel_x = int(xs.mean())
        rel_y = int(ys.mean())

        esc_x = self.game_monitor["left"] + int(w * 0.05) + rel_x
        esc_y = self.game_monitor["top"] + int(h * 0.65) + rel_y

        self.on_log(f"ESC button AUTO-detected at ({esc_x}, {esc_y})")
        return esc_x, esc_y

    def click_escape(self) -> None:
        if self.experimental:
            pos = self.find_esc_position()
            if pos:
                x, y = pos
                move_and_click(x, y)
                time.sleep(0.08)
                return
            self.on_log("ESC auto-detection failed → fallback to keypress")

        press_escape(self.escape_hold)

    def start(self, mouse_x: int, mouse_y: int) -> None:
        self.running = True
        self.attempt = 0
        self.mouse_x = mouse_x
        self.mouse_y = mouse_y
        self.game_monitor = find_game_monitor(mouse_x, mouse_y)

        self.on_log(f"Target server button: ({self.mouse_x}, {self.mouse_y})")
        self.on_log(f"Experimental mouse-ESC mode: {'ENABLED' if self.experimental else 'DISABLED'}")
        self.on_state_change("running")

        time.sleep(0.3)

        while self.running:
            self.attempt += 1
            self.on_log(f"[{self.attempt}] Clicking server button...")
            move_and_click(self.mouse_x, self.mouse_y)
            time.sleep(0.2)
            move_and_click(self.mouse_x, self.mouse_y)
            time.sleep(self.wait_after_click)

            if not self.running:
                break

            # === SERVER FULL ===
            if self.is_server_full():
                self.on_log(f"[{self.attempt}] Server full → clicking ESC")
                self.click_escape()
                time.sleep(self.pause_before_retry)
                continue

            self.on_log(f"[{self.attempt}] Waiting 8s for connect/queue screen...")
            still_there = True
            for i in range(8):
                if not self.running:
                    break
                time.sleep(1.0)
                if self.is_server_full():
                    self.on_log(f"[{self.attempt}] Server full after {i+1}s → ESC")
                    still_there = False
                    self.click_escape()
                    time.sleep(self.pause_before_retry)
                    break

            if not self.running or not still_there:
                continue

            # === QUEUE CHECK ===
            if self.is_queue_text_visible():
                confirmed = True
                for i in range(3):
                    time.sleep(1.0)
                    if not self.is_queue_text_visible():
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
                    time.sleep(self.pause_before_retry)
            else:
                self.on_log(f"[{self.attempt}] Connect screen passed → retrying")
                time.sleep(self.pause_before_retry)

        self.on_log("Stopped.")
        self.on_state_change("idle")

    def stop(self):
        self.running = False

    def _play_alert(self):
        try:
            for _ in range(3):
                winsound.Beep(1000, 300)
                time.sleep(0.1)
        except Exception:
            pass


class App(tk.Tk):
    WINDOW_WIDTH = 440
    WINDOW_HEIGHT = 480
    HOTKEY_OPTIONS = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"]

    def __init__(self):
        super().__init__()
        self.title("Arma Reforger Queue Joiner | by lime98")
        self.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")
        self.resizable(False, False)
        self.configure(bg="#1e1e1e")

        if getattr(sys, 'frozen', False):
            icon_path = os.path.join(sys._MEIPASS, "icon.ico")
        else:
            icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        self.joiner = QueueJoiner(on_log=self._append_log, on_state_change=self._update_state)
        self.worker_thread = None
        self.registered_hooks = []

        self._build_ui()
        self._register_hotkeys()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#1e1e1e")
        style.configure("TLabel", background="#1e1e1e", foreground="#cccccc", font=("Segoe UI", 10))
        style.configure("Header.TLabel", background="#1e1e1e", foreground="#ffffff", font=("Segoe UI", 14, "bold"))
        style.configure("Status.TLabel", background="#1e1e1e", foreground="#888888", font=("Segoe UI", 10))

        ttk.Label(self, text="Arma Reforger Queue Joiner | by lime98", style="Header.TLabel").pack(pady=(15, 8))

        ttk.Label(
            self,
            text="1. Open server browser\n"
                 "2. Hover mouse over JOIN button\n"
                 "3. Press START hotkey\n"
                 "4. Experimental = auto mouse-click ESC (no key needed)",
            style="TLabel",
            justify="left",
        ).pack(padx=20, pady=(0, 10))

        hf = ttk.Frame(self)
        hf.pack(pady=(0, 8))
        ttk.Label(hf, text="Start:").grid(row=0, column=0, padx=(0, 5), pady=2)
        self.start_hotkey_var = tk.StringVar(value="F6")
        sc = ttk.Combobox(hf, textvariable=self.start_hotkey_var, values=self.HOTKEY_OPTIONS, state="readonly", width=6)
        sc.grid(row=0, column=1, padx=(0, 25), pady=2)
        sc.bind("<<ComboboxSelected>>", lambda e: self._register_hotkeys())

        ttk.Label(hf, text="Stop:").grid(row=0, column=2, padx=(0, 5), pady=2)
        self.stop_hotkey_var = tk.StringVar(value="F4")
        sc2 = ttk.Combobox(hf, textvariable=self.stop_hotkey_var, values=self.HOTKEY_OPTIONS, state="readonly", width=6)
        sc2.grid(row=0, column=3, pady=2)
        sc2.bind("<<ComboboxSelected>>", lambda e: self._register_hotkeys())

        sf = ttk.Frame(self)
        sf.pack(pady=(0, 10))

        ttk.Label(sf, text="Wait after click (sec):").grid(row=0, column=0, sticky="w", pady=3)
        self.wait_var = tk.StringVar(value="0.5")
        self.wait_spin = ttk.Spinbox(sf, from_=0.5, to=10.0, increment=0.1, textvariable=self.wait_var, width=8)
        self.wait_spin.grid(row=0, column=1, padx=(10, 0), pady=3)

        ttk.Label(sf, text="ESC hold (fallback, sec):").grid(row=1, column=0, sticky="w", pady=3)
        self.esc_var = tk.StringVar(value="1.5")
        self.esc_spin = ttk.Spinbox(sf, from_=0.1, to=5.0, increment=0.1, textvariable=self.esc_var, width=8)
        self.esc_spin.grid(row=1, column=1, padx=(10, 0), pady=3)

        self.experimental_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            sf,
            text="Experimental Mode: FAST ESC",
            variable=self.experimental_var
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=8)

        self.status_label = ttk.Label(self, text="Status: Idle", style="Status.TLabel")
        self.status_label.pack(pady=(5, 3))

        lf = tk.Frame(self, bg="#1e1e1e")
        lf.pack(padx=20, pady=(0, 15), fill="both", expand=True)
        self.log_text = tk.Text(lf, bg="#111111", fg="#aaaaaa", font=("Consolas", 9), relief="flat", state="disabled", wrap="word")
        sb = ttk.Scrollbar(lf, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

    def _register_hotkeys(self):
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

        self.registered_hooks = [
            keyboard.on_press_key(sk, lambda e: self._on_start(), suppress=False),
            keyboard.on_press_key(ek, lambda e: self._on_stop(), suppress=False),
        ]

    def _on_start(self):
        if self.joiner.running:
            return

        mx, my = get_cursor_pos()
        try:
            self.joiner.wait_after_click = float(self.wait_var.get())
            self.joiner.escape_hold = float(self.esc_var.get())
            self.joiner.experimental = self.experimental_var.get()
        except ValueError:
            self._append_log("ERROR: Invalid numeric settings.")
            return

        self._clear_log()
        self.worker_thread = threading.Thread(target=self.joiner.start, args=(mx, my), daemon=True)
        self.worker_thread.start()

    def _on_stop(self):
        self.joiner.stop()

    def _on_close(self):
        self.joiner.stop()
        keyboard.unhook_all()
        self.destroy()

    def _append_log(self, msg: str):
        def u():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", f"{msg}\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.after(0, u)

    def _clear_log(self):
        def u():
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")
        self.after(0, u)

    def _update_state(self, state: str):
        def u():
            if state == "running":
                self.status_label.configure(text="Status: Running...", foreground="#e8a832")
            elif state == "success":
                self.status_label.configure(text="Status: IN QUEUE! ✓", foreground="#2dcc5e")
            else:
                self.status_label.configure(text="Status: Idle", foreground="#888888")
        self.after(0, u)


if __name__ == "__main__":
    app = App()
    app.mainloop()

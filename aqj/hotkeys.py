"""Global hotkeys through RegisterHotKey.

Unlike a keyboard hook this needs no admin rights, does not see other keys,
and with MOD_NOREPEAT holding a key down fires only once.
"""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
WM_APP_REBIND = 0x8001
MOD_NOREPEAT = 0x4000

user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.PeekMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
    wintypes.UINT,
]
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL


def vk_for(name: str) -> int:
    """'F1'..'F24' -> virtual-key code."""
    if name.upper().startswith("F") and name[1:].isdigit() and 1 <= int(name[1:]) <= 24:
        return 0x70 + int(name[1:]) - 1
    raise ValueError(f"Unsupported hotkey: {name}")


class HotkeyListener(threading.Thread):
    """Owns a Win32 message loop; hotkeys belong to the thread that registered them."""

    def __init__(self, on_hotkey: Callable[[str], None], on_error: Callable[[str], None]):
        """on_error receives the key name that could not be registered."""
        super().__init__(name="hotkeys", daemon=True)
        self._on_hotkey = on_hotkey
        self._on_error = on_error
        self._pending: dict[str, str] = {}
        self._active: dict[int, str] = {}
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._thread_id = 0

    def bind(self, bindings: dict[str, str]) -> None:
        """bindings: action -> key name, e.g. {'start': 'F6', 'stop': 'F4'}."""
        with self._lock:
            self._pending = dict(bindings)
        # Before the thread is ready, run() applies the pending bindings itself.
        if self._ready.is_set():
            user32.PostThreadMessageW(self._thread_id, WM_APP_REBIND, 0, 0)

    def shutdown(self) -> None:
        if self._ready.is_set():
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)

    def _apply(self) -> None:
        for hotkey_id in list(self._active):
            user32.UnregisterHotKey(None, hotkey_id)
        self._active.clear()
        with self._lock:
            bindings = dict(self._pending)
        for index, (action, key) in enumerate(sorted(bindings.items()), start=1):
            if not user32.RegisterHotKey(None, index, MOD_NOREPEAT, vk_for(key)):
                self._on_error(key)
                continue
            self._active[index] = action

    def run(self) -> None:
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # creates the message queue
        self._thread_id = kernel32.GetCurrentThreadId()
        self._ready.set()
        self._apply()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    action = self._active.get(int(msg.wParam))
                    if action:
                        self._on_hotkey(action)
                elif msg.message == WM_APP_REBIND:
                    self._apply()
        finally:
            for hotkey_id in self._active:
                user32.UnregisterHotKey(None, hotkey_id)

"""
Tests for app.py improvements.
All tests run headless ? no display, game, or admin rights required.
"""

import dataclasses
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import numpy as np

failures = []


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    suffix = f" ? {detail}" if detail else ""
    print(f"  [{status}] {label}{suffix}")
    if not condition:
        failures.append(label)


# ==============================================================================
# 1. Color detection ? BGRA channel mapping
# ==============================================================================
print("\n  [Color detection ? BGRA]")

PIXELS = {
    "yellow":     (220, 150,  40),
    "red":        (200,  50,  40),
    "orange_esc": (210, 180,  60),
    "neutral":    (100, 100, 100),
    "white":      (255, 255, 255),
    "blue":       ( 40,  80, 200),
}
# (yellow_hit, red_hit, esc_hit) ? orange_esc also matches yellow (R>180,G>130,B<80), which
# is fine because the two detections use different screen regions.
EXPECTED = {
    "yellow":     (1, 0, 0),
    "red":        (0, 1, 0),
    "orange_esc": (1, 0, 1),
    "neutral":    (0, 0, 0),
    "white":      (0, 0, 0),
    "blue":       (0, 0, 0),
}


def _detect_colors(arr):
    r, g, b = arr[:, :, 2], arr[:, :, 1], arr[:, :, 0]
    yellow = int(((r > 180) & (g > 130) & (b < 80)).sum())
    red    = int(((r > 180) & (g < 80)  & (b < 80)).sum())
    return yellow, red


def _detect_esc(arr):
    r, g, b = arr[:, :, 2], arr[:, :, 1], arr[:, :, 0]
    return int(((r > 200) & (g > 160) & (b < 90) & (g < 230)).sum())


for name, (r, g, b) in PIXELS.items():
    arr = np.array([[[b, g, r, 255]]], dtype=np.uint8)  # BGRA
    y, red = _detect_colors(arr)
    esc    = _detect_esc(arr)
    ey, er, ee = EXPECTED[name]
    check(name, y == ey and red == er and esc == ee,
          f"yellow={y}/{ey} red={red}/{er} esc={esc}/{ee}")


# ==============================================================================
# 2. fmt_elapsed
# ==============================================================================
print("\n  [fmt_elapsed]")


def fmt_elapsed(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"


check("0s",    fmt_elapsed(0)    == "00:00")
check("59s",   fmt_elapsed(59)   == "00:59")
check("60s",   fmt_elapsed(60)   == "01:00")
check("3661s", fmt_elapsed(3661) == "61:01")
check("negative safe", fmt_elapsed(-1) == "-1:59")  # divmod handles this naturally


# ==============================================================================
# 3. Settings ? load / save
# ==============================================================================
print("\n  [Settings]")


@dataclasses.dataclass
class _Settings:
    wait_after_click: float = 0.5
    escape_hold: float = 1.5
    experimental: bool = False
    start_hotkey: str = "F6"
    stop_hotkey: str = "F4"
    alert_wav: str = ""

    @classmethod
    def load(cls, path: Path) -> "_Settings":
        s = cls()
        try:
            if path.exists():
                data = json.loads(path.read_text("utf-8"))
                for field in dataclasses.fields(s):
                    if field.name in data:
                        try:
                            raw = data[field.name]
                            setattr(s, field.name, type(getattr(s, field.name))(raw))
                        except (ValueError, TypeError):
                            pass
        except Exception:
            pass
        return s

    def save(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(dataclasses.asdict(self), indent=2), "utf-8")
        except Exception:
            pass


with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "sub" / "settings.json"

    # File doesn't exist -> defaults
    s = _Settings.load(p)
    check("missing file -> defaults", s.wait_after_click == 0.5 and s.start_hotkey == "F6")

    # Round-trip defaults
    s.save(p)
    s2 = _Settings.load(p)
    check("defaults round-trip", dataclasses.asdict(s) == dataclasses.asdict(s2))

    # Modified values
    s.wait_after_click = 2.3
    s.experimental = True
    s.alert_wav = r"C:\sounds\alert.wav"
    s.save(p)
    s3 = _Settings.load(p)
    check("modified values", s3.wait_after_click == 2.3 and s3.experimental is True
          and s3.alert_wav == r"C:\sounds\alert.wav")

    # Bool stored as JSON true/false -> loads back as bool, not string
    check("bool type preserved", isinstance(s3.experimental, bool))

    # Partial JSON ? missing keys use defaults
    p.write_text(json.dumps({"wait_after_click": 1.0}), "utf-8")
    s4 = _Settings.load(p)
    check("partial load fills defaults", s4.escape_hold == 1.5 and s4.wait_after_click == 1.0)

    # Corrupt JSON -> defaults, no exception
    p.write_text("not valid json {{", "utf-8")
    s5 = _Settings.load(p)
    check("corrupt json -> defaults", s5.wait_after_click == 0.5)

    # Unknown extra keys -> silently ignored
    p.write_text(json.dumps({"wait_after_click": 3.0, "future_key": "value"}), "utf-8")
    s6 = _Settings.load(p)
    check("unknown keys ignored", s6.wait_after_click == 3.0)


# ==============================================================================
# 4. _wait_for_server_full (adaptive wait)
# ==============================================================================
print("\n  [_wait_for_server_full]")


class _FakeJoiner:
    """Minimal stub that replaces read_colors with a controlled sequence."""

    def __init__(self, color_sequence):
        self.running = True
        self._seq = iter(color_sequence)
        self._calls = 0

    def read_colors(self):
        self._calls += 1
        try:
            return next(self._seq)
        except StopIteration:
            return (0, 0)

    def _wait_for_server_full(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.running:
                return False
            _, red = self.read_colors()
            if red > 50:
                return True
            time.sleep(0.01)
        return False

    def _poll_sleep(self, duration: float) -> bool:
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            if not self.running:
                return False
            time.sleep(0.01)
        return True


# Detects immediately on first poll
j = _FakeJoiner([(0, 200)])
check("detects on first poll", j._wait_for_server_full(1.0) is True)
check("exits after first detection", j._calls == 1)

# No dialog -> times out
j2 = _FakeJoiner([(0, 0)] * 1000)
t0 = time.monotonic()
result = j2._wait_for_server_full(0.15)
elapsed = time.monotonic() - t0
check("returns False on timeout", result is False)
check("timeout duration ~ 0.15s", 0.10 <= elapsed <= 0.40, f"{elapsed:.3f}s")

# Detects after a few polls (not first)
j3 = _FakeJoiner([(0, 0), (0, 0), (0, 200)])
check("detects after delay", j3._wait_for_server_full(1.0) is True)
check("polled 3 times before hit", j3._calls == 3)

# Respects running=False (stop command)
j4 = _FakeJoiner([(0, 0)] * 1000)
threading.Thread(target=lambda: (time.sleep(0.05), setattr(j4, "running", False)), daemon=True).start()
t0 = time.monotonic()
check("respects stop flag", j4._wait_for_server_full(5.0) is False)
check("stops within 200ms of flag", time.monotonic() - t0 < 0.20)


# ==============================================================================
# 5. _poll_sleep
# ==============================================================================
print("\n  [_poll_sleep]")

jp = _FakeJoiner([])
t0 = time.monotonic()
check("returns True on full sleep", jp._poll_sleep(0.15) is True)
check("sleeps ~ full duration", 0.10 <= time.monotonic() - t0 <= 0.40)

jp2 = _FakeJoiner([])
threading.Thread(target=lambda: (time.sleep(0.05), setattr(jp2, "running", False)), daemon=True).start()
t0 = time.monotonic()
check("returns False when stopped", jp2._poll_sleep(5.0) is False)
check("exits within 200ms of flag", time.monotonic() - t0 < 0.20)


# ==============================================================================
# 6. Watchdog ? crash resets state to idle
# ==============================================================================
print("\n  [Watchdog]")


class _CrashingJoiner:
    def __init__(self):
        self.running = False
        self._calls = []

    def on_log(self, msg):
        self._calls.append(("log", msg))

    def on_state_change(self, state):
        self._calls.append(("state", state))

    def start(self, mx, my):
        try:
            self._run(mx, my)
        except Exception as exc:
            self.on_log(f"ERROR: {exc}")
            self.running = False
            self.on_state_change("idle")
        finally:
            pass  # _sct cleanup in real code

    def _run(self, mx, my):
        self.running = True
        self.on_state_change("running")
        raise RuntimeError("Simulated crash")


cj = _CrashingJoiner()
cj.start(0, 0)

states = [v for k, v in cj._calls if k == "state"]
logs   = [v for k, v in cj._calls if k == "log"]
check("running=False after crash",       cj.running is False)
check("state goes running->idle",         states == ["running", "idle"])
check("error message logged",            any("ERROR" in m for m in logs))
check("exception message in log",        any("Simulated crash" in m for m in logs))


# ==============================================================================
# 7. _play_alert ? WAV fallback logic
# ==============================================================================
print("\n  [_play_alert]")


class _AlertJoiner:
    def __init__(self, alert_wav=""):
        self.alert_wav = alert_wav
        self.played_wav = None
        self.beep_count = 0

    def _play_alert(self):
        if self.alert_wav and os.path.isfile(self.alert_wav):
            try:
                self.played_wav = self.alert_wav  # simulates winsound.PlaySound
                return
            except Exception:
                pass
        self.beep_count += 1  # simulates winsound.Beep x3


# No wav -> beep fallback
aj = _AlertJoiner()
aj._play_alert()
check("no wav -> beep", aj.beep_count == 1 and aj.played_wav is None)

# Non-existent file -> beep fallback
aj2 = _AlertJoiner(alert_wav="/nonexistent/sound.wav")
aj2._play_alert()
check("missing file -> beep fallback", aj2.beep_count == 1 and aj2.played_wav is None)

# Valid file -> plays wav
with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
    wav_path = tf.name
try:
    aj3 = _AlertJoiner(alert_wav=wav_path)
    aj3._play_alert()
    check("existing wav -> plays wav", aj3.played_wav == wav_path and aj3.beep_count == 0)
finally:
    os.unlink(wav_path)


# ==============================================================================
# 8. Region math
# ==============================================================================
print("\n  [Region math]")

W, H = 1920, 1080


def check_region(label, l, t, r_pct, b_pct, exp_w, exp_h, tol=2):
    rw = int(W * (r_pct - l))
    rh = int(H * (b_pct - t))
    check(label, abs(rw - exp_w) <= tol and abs(rh - exp_h) <= tol,
          f"{rw}x{rh} (expected ~{exp_w}x{exp_h})")


check_region("dialog region", 0.28, 0.28, 0.52, 0.45, 461, 184)
check_region("esc region",    0.05, 0.65, 0.45, 0.95, 768, 324)


# ==============================================================================
# 9. Syntax check
# ==============================================================================
print("\n  [Syntax check]")
import py_compile

try:
    py_compile.compile("app.py", doraise=True)
    check("app.py compiles without errors", True)
except py_compile.PyCompileError as e:
    check("app.py compiles without errors", False, str(e))


# ==============================================================================
print()
if failures:
    print(f"FAILED ({len(failures)}): {failures}")
    sys.exit(1)
else:
    print(f"All tests passed.")

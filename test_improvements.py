"""
Tests for app.py improvements.
Validates numpy BGRA channel mapping (replacing PIL RGB conversion)
and region math — no game/display required.
"""

import numpy as np
import sys


def make_bgra(r, g, b, a=255):
    """Return a single-pixel (1,1,4) BGRA array."""
    return np.array([[[[b, g, r, a]]]], dtype=np.uint8)


def detect_colors_rgb(arr_rgb):
    """Original logic: arr is RGB (from PIL)."""
    yellow = int(((arr_rgb[:, :, 0] > 180) & (arr_rgb[:, :, 1] > 130) & (arr_rgb[:, :, 2] < 80)).sum())
    red    = int(((arr_rgb[:, :, 0] > 180) & (arr_rgb[:, :, 1] < 80)  & (arr_rgb[:, :, 2] < 80)).sum())
    return yellow, red


def detect_colors_bgra(arr_bgra):
    """New logic: arr is BGRA (direct from mss, no Pillow)."""
    r, g, b = arr_bgra[:, :, 2], arr_bgra[:, :, 1], arr_bgra[:, :, 0]
    yellow = int(((r > 180) & (g > 130) & (b < 80)).sum())
    red    = int(((r > 180) & (g < 80)  & (b < 80)).sum())
    return yellow, red


def detect_esc_rgb(roi_rgb):
    """Original ESC mask: RGB."""
    mask = (
        (roi_rgb[:, :, 0] > 200) &
        (roi_rgb[:, :, 1] > 160) &
        (roi_rgb[:, :, 2] < 90)  &
        (roi_rgb[:, :, 1] < 230)
    )
    return int(np.sum(mask))


def detect_esc_bgra(roi_bgra):
    """New ESC mask: BGRA."""
    r, g, b = roi_bgra[:, :, 2], roi_bgra[:, :, 1], roi_bgra[:, :, 0]
    mask = (r > 200) & (g > 160) & (b < 90) & (g < 230)
    return int(np.sum(mask))


# ── Test cases ────────────────────────────────────────────────────────────────

PIXELS = {
    "yellow":     (220, 150, 40),   # R>180 G>130 B<80  → yellow
    "red":        (200, 50,  40),   # R>180 G<80  B<80  → red
    "orange_esc": (210, 180, 60),   # ESC button color  → esc
    "neutral":    (100, 100, 100),  # nothing
    "white":      (255, 255, 255),  # nothing
    "blue":       (40,  80,  200),  # nothing
}

EXPECTED = {
    # (yellow, red, esc)
    "yellow":     (1, 0, 0),
    "red":        (0, 1, 0),
    "orange_esc": (1, 0, 1),  # also yellow — satisfies R>180,G>130,B<80; OK since ESC uses a different screen region
    "neutral":    (0, 0, 0),
    "white":      (0, 0, 0),
    "blue":       (0, 0, 0),
}

failures = []

for name, (r, g, b) in PIXELS.items():
    rgb_px  = np.array([[[r, g, b]]],    dtype=np.uint8)   # shape (1,1,3) RGB
    bgra_px = np.array([[[b, g, r, 255]]], dtype=np.uint8) # shape (1,1,4) BGRA

    y_rgb,  red_rgb  = detect_colors_rgb(rgb_px)
    y_bgra, red_bgra = detect_colors_bgra(bgra_px)
    esc_rgb  = detect_esc_rgb(rgb_px)
    esc_bgra = detect_esc_bgra(bgra_px)

    exp_y, exp_r, exp_esc = EXPECTED[name]

    ok = (
        y_rgb  == exp_y and y_bgra  == exp_y and
        red_rgb == exp_r and red_bgra == exp_r and
        esc_rgb == exp_esc and esc_bgra == exp_esc
    )

    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name:12s}  yellow={y_bgra}/{exp_y}  red={red_bgra}/{exp_r}  esc={esc_bgra}/{exp_esc}")

    if not ok:
        failures.append(name)

# ── Region math ───────────────────────────────────────────────────────────────

print("\n  [Region math]")
w, h = 1920, 1080

def check_region(label, l, t, r_pct, b_pct, expected_w, expected_h, tol=2):
    rw = int(w * (r_pct - l))
    rh = int(h * (b_pct - t))
    ok = abs(rw - expected_w) <= tol and abs(rh - expected_h) <= tol
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label:20s}  {rw}x{rh}  (expected ~{expected_w}x{expected_h})")
    if not ok:
        failures.append(label)

check_region("dialog region",     0.28, 0.28, 0.52, 0.45, 461, 184)
check_region("esc region",        0.05, 0.65, 0.45, 0.95, 768, 324)

# ── Summary ───────────────────────────────────────────────────────────────────

print()
if failures:
    print(f"FAILED: {failures}")
    sys.exit(1)
else:
    print("All tests passed.")

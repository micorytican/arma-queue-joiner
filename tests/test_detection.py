import numpy as np
import pytest

from aqj.detection import (
    DIALOG_REGION,
    Region,
    analyze_dialog,
    find_esc_button,
)


def bgra(h: int, w: int, rgb=(100, 100, 100)) -> np.ndarray:
    r, g, b = rgb
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[...] = (b, g, r, 255)
    return arr


@pytest.mark.parametrize(
    "rgb, yellow, red",
    [
        ((220, 150, 40), True, False),
        ((200, 50, 40), False, True),
        ((100, 100, 100), False, False),
        ((255, 255, 255), False, False),
        ((40, 80, 200), False, False),
    ],
)
def test_pixel_classes(rgb, yellow, red):
    reading = analyze_dialog(bgra(10, 10, rgb))
    assert (reading.yellow == 1.0) is yellow
    assert (reading.red == 1.0) is red


@pytest.mark.parametrize("w, h", [(1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)])
def test_thresholds_do_not_depend_on_resolution(w, h):
    rect = DIALOG_REGION.to_rect({"left": 0, "top": 0, "width": w, "height": h})
    arr = bgra(rect["height"], rect["width"])
    area = arr.shape[0] * arr.shape[1]

    # 1 % red pixels: clearly a "server full" dialog at every size
    flat = arr.reshape(-1, 4)
    flat[: area // 100] = (40, 50, 200, 255)
    assert analyze_dialog(arr).server_full

    # 3 % yellow: queue text at every size; 0.5 % yellow is noise
    arr2 = bgra(rect["height"], rect["width"])
    flat2 = arr2.reshape(-1, 4)
    flat2[: area * 3 // 100] = (40, 150, 220, 255)
    assert analyze_dialog(arr2).in_queue
    arr3 = bgra(rect["height"], rect["width"])
    arr3.reshape(-1, 4)[: area // 200] = (40, 150, 220, 255)
    assert not analyze_dialog(arr3).in_queue


def test_1080p_matches_original_pixel_counts():
    rect = DIALOG_REGION.to_rect({"left": 0, "top": 0, "width": 1920, "height": 1080})
    arr = bgra(rect["height"], rect["width"])
    arr.reshape(-1, 4)[:49] = (40, 50, 200, 255)
    assert not analyze_dialog(arr).server_full
    arr.reshape(-1, 4)[:60] = (40, 50, 200, 255)
    assert analyze_dialog(arr).server_full


def test_empty_capture_is_safe():
    assert not analyze_dialog(np.zeros((0, 0, 4), dtype=np.uint8)).server_full
    assert find_esc_button(np.zeros((0, 0, 4), dtype=np.uint8)) is None


def test_find_esc_button_centre():
    arr = bgra(300, 700)
    arr[100:140, 200:300] = (60, 190, 230, 255)  # orange-ish button, BGRA
    assert find_esc_button(arr) == (249, 119)


def test_find_esc_button_missing():
    assert find_esc_button(bgra(300, 700)) is None


def test_region_to_rect_with_monitor_offset():
    rect = Region(0.5, 0.5, 1.0, 1.0).to_rect({"left": -1920, "top": 100, "width": 1920, "height": 1080})
    assert rect == {"left": -960, "top": 640, "width": 960, "height": 540}

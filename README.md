# Arma Reforger Queue Joiner

A small tool that keeps clicking the Join button on a full server until you get in — then stops and plays a sound to let you know.

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

## Download

Grab the latest `.exe` from the Releases page.

## How to use

1. Launch the tool
2. In-game, open the server browser and find the server you want to join
3. Hover your mouse over the **Join** button (don't click yet)
4. Press your **Start** hotkey (default: **F6**)
5. The tool saves that position and starts clicking for you
6. If the server is full → it presses ESC and tries again automatically
7. Once you get into the queue → it stops and plays a beep alert
8. Press your **Stop** hotkey (default: **F4**) anytime to cancel

## Settings

| Setting | Default | Description |
|---|---|---|
| Start hotkey | F6 | Hotkey to start (position saved at that moment) |
| Stop hotkey | F4 | Hotkey to stop at any time |
| Wait after click | 0.5s | How long to wait after clicking Join |
| ESC hold | 1.5s | How long to hold ESC when closing the full-server dialog |

### Experimental Mode: FAST ESC

When enabled, instead of pressing the ESC key, the tool detects the ESC button on screen by color and clicks it with the mouse. This can be faster in some cases. If detection fails, it falls back to the normal ESC keypress.

## Run from source

```bash
git clone https://github.com/micorytican/arma-queue-joiner.git
cd arma-queue-joiner
pip install -r requirements.txt
python app.py
```

## Notes

- Works only on Windows
- The tool detects "server full" by reading screen colors in the dialog area — works at any resolution
- Queue detection looks for the yellow queue text on screen
- Run as administrator if hotkeys don't register (some games capture input at a lower level)

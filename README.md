# Arma Reforger Queue Joiner

Keeps pressing **Join** on a full Arma Reforger server until you get into the queue, then tells you: a sound, a Windows notification and, if you want, a push to your phone.

![Python](https://img.shields.io/badge/Python-3.13-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-lightgrey)

<p>
  <img src="assets/screenshot-main.png" width="320" alt="Main screen while joining">
  <img src="assets/screenshot-settings.png" width="320" alt="Settings">
</p>

## Download

Grab `ArmaQueueJoiner.exe` from the [Releases](https://github.com/micorytican/arma-queue-joiner/releases) page. No install needed.

## How to use

1. Open the server browser in Arma Reforger and pick a full server.
2. Hover your mouse over the **Join** button.
3. Press **F6** (or click **Start** in the app and move the mouse to Join within 3 seconds).
4. Leave the mouse alone. The app clicks Join, closes the "server full" dialog and tries again.
5. When you are in the queue it stops and alerts you.

Press **F4** at any time to stop. Moving the mouse also stops it, so you can always take back control.

## What's new in 2.0

- **New interface** in the style of Windows 11. It follows your light or dark mode and your Windows accent colour. Status, time and attempts up front, settings on their own page.
- **Safer.** Clicks only while Arma Reforger is the active window, and stops as soon as you move the mouse.
- **Phone notifications** through the free [ntfy](https://ntfy.sh) app, no account needed.
- **Works the same at any resolution.** Detection thresholds now scale with the screen, not fixed pixel counts.
- **Faster reaction.** The queue screen is detected as soon as it appears instead of after a fixed 8 second wait.
- **No admin rights needed for hotkeys,** and holding a key no longer triggers it twice.
- **Start button with countdown** for people who prefer not to use hotkeys.
- Only one copy can run at a time; opening it again brings the window back.
- Your 1.x settings are carried over.

## Settings

| Setting | Default | What it does |
|---|---|---|
| Start / Stop hotkey | F6 / F4 | Start saves the mouse position at that moment |
| Only click inside Arma Reforger | On | Pauses while another window is active |
| Stop when I move the mouse | On | Lets you take over instantly |
| Fast close | Off | Clicks the on-screen ESC button instead of pressing the key; falls back to the key if the button is not found |
| Wait after click | 0.10 s | Extra time to wait for a dialog after clicking Join |
| Give up on a try after | 8.00 s | If neither "server full" nor the queue appears, click Join again |
| Pause before retry | 0.00 s | Breather between attempts |
| Hold ESC key for | 0.10 s | How long the ESC key is held |
| Sound alert | On | Three short beeps when you are in |
| Notify my phone | Off | Push through ntfy; see below |
| Keep on top / Close to tray | Off / On | Window behaviour |

Settings are stored in `%APPDATA%\ArmaQueueJoiner\settings.json`.

### Phone notifications

1. Install **ntfy** on your phone (Android or iOS).
2. In the app turn on **Notify my phone**. A random topic name is filled in for you.
3. In ntfy subscribe to the same topic and press **Send test**.

Anyone who knows the topic name can read its messages, so keep it hard to guess.

## How it works

The app looks at two small areas of the screen:

- the centre-left dialog area: red means "server full", yellow text means you are in the queue (it must stay for 3 seconds to count);
- the bottom-left area, only for Fast close, to find the ESC button.

It never reads game memory or network traffic. It only sees the screen and moves the mouse, like you would.

## Troubleshooting

- **Nothing happens / input is blocked:** if Arma Reforger runs as administrator, run the app as administrator too. Windows does not let a normal app send input to an elevated one.
- **A hotkey does not work:** another program already uses it. Pick a different key in Settings.
- **It keeps saying "waiting for the Arma Reforger window":** the game window is not in front. Click into the game, or turn off *Only click inside Arma Reforger*.

## Run from source

```bash
git clone https://github.com/micorytican/arma-queue-joiner.git
cd arma-queue-joiner
py -3.13 -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python app.py
```

Run the tests with `.venv\Scripts\python -m pytest`. Build the `.exe` with `build.bat` (it creates the venv, runs the tests and calls PyInstaller).

### Project layout

```
aqj/
  joiner.py     the join loop (pure logic, tested with fakes)
  detection.py  pixel analysis
  screen.py     screen capture (mss)
  winapi.py     mouse, keyboard and window calls
  hotkeys.py    global hotkeys via RegisterHotKey
  notify.py     sound and ntfy push
  settings.py   load, validate and save settings
  ui/           PySide6 window, widgets and theme
tests/          pytest suite
```

## License

MIT, by lime98 aka micorytican.

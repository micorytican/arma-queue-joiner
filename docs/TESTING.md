# Testing

## Automated tests

Run everything with `.venv\Scripts\python -m pytest`. CI runs the same suite on
`windows-latest` with `CI=1` and `QT_QPA_PLATFORM=offscreen`.

| Layer | Files | What it covers |
|---|---|---|
| Logic | `test_joiner.py`, `test_detection.py`, `test_settings.py` | Join loop with fake screen, input and focus (retry, queue confirm, fast close, mouse takeover, pause, stop latency, crash reporting); pixel thresholds at 720p to 4K; settings validation, migration from 1.x, atomic save |
| Text | `test_i18n.py` | Every string exists in English and Ukrainian with the same placeholders; Ukrainian plural forms; no exclamation marks |
| Network | `test_network.py` | ntfy JSON payload, Discord webhook validation and payload, update version comparison and release filtering. `net.urlopen` is replaced, so no request leaves the machine |
| Logging | `test_logs.py` | Log file creation, crash handler on worker threads |
| UI | `test_ui.py` (pytest-qt) | Window states, countdown and cancel, hotkey start and stop, settings saved, language switch, diagnostics page, update banner, Esc to go back. Joiner, hotkeys and screen are faked |

Tests marked `desktop` need a real desktop session and are skipped in CI.
Each test gets its own `%APPDATA%`, so your real settings are never touched.

## Manual check in the game

Do this before every release, on at least one resolution other than 1920x1080 if you can.

**Setup**
- [ ] Fresh start shows *Ready to join* and the hotkey card shows the right keys.
- [ ] Settings › Diagnostics with the game in front says *Arma Reforger detected* and the right display size.

**Joining**
- [ ] Hover Join on a full server, press F6: attempts count up, the log shows *Server full, closing the dialog*.
- [ ] Diagnostics on the "server full" dialog reads *server full*; on the queue screen it reads *queue screen*.
- [ ] With Fast close on, the dialog closes by clicking the on-screen ESC button.
- [ ] Getting into the queue stops the app, beeps, flashes the taskbar and shows *You're in the queue*.

**Safety**
- [ ] Alt+Tab away while it runs: status changes to *Paused*, no clicks happen outside the game; it resumes when you return.
- [ ] Moving the mouse stops it with *Stopped because you moved the mouse*.
- [ ] F4 stops it within a second.

**Alerts**
- [ ] ntfy *Send test* arrives on the phone; a real queue entry sends a push.
- [ ] Discord *Send test* posts in the channel; a wrong link shows the explanation.

**App**
- [ ] Switching language in Settings changes all text at once.
- [ ] Light and dark Windows themes both look right; the title bar follows.
- [ ] Closing the window keeps it in the tray; Quit from the tray menu exits.
- [ ] Starting a second copy brings the first window to the front.
- [ ] The installer installs without admin rights, adds a Start menu entry and uninstalls cleanly.

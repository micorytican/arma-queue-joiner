# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [2.1.1] - 2026-10-28

### Fixed

- Small empty windows no longer flash up for a moment when the app starts.

### Changed

- The language setting shows only English and Ukrainian. On first start the app picks Ukrainian on a Ukrainian Windows and English on any other, instead of a "Same as Windows" option that looked like it would follow German or other languages.

## [2.1.0] - 2026-10-28

### Added

- A second alert when the queue lets you in and you are in the game, with the server name. The app reads Arma Reforger's own log to know this.
- An alert when the server drops you from the queue.
- Settings to choose which alerts you get: when you get into the queue, when you are in the game, or both.
- *Game log* row on the Diagnostics page.

### Changed

- Phone notifications are sent as urgent, so they pop up even while you use other apps, and no longer start with an emoji.

## [2.0.0] - 2026-10-28

A full rewrite. Settings from 1.x are carried over.

### Added

- New interface in the style of Windows 11 that follows your light or dark mode and accent colour.
- English and Ukrainian, chosen from your Windows language or in Settings.
- Only clicks while Arma Reforger is the active window, and pauses otherwise.
- Stops as soon as you move the mouse.
- Phone notifications through ntfy and Discord messages through a webhook, each with a test button.
- Diagnostics page that shows what the app sees on screen, with a copyable report.
- Log files in `%APPDATA%\ArmaQueueJoiner\logs` and a message when something crashes.
- Update check against GitHub Releases at startup (can be turned off).
- Start button with a 3 second countdown, for playing without hotkeys.
- Installer for the current user, in addition to the portable exe.
- Only one copy runs at a time; starting it again shows the open window.

### Changed

- Detection works the same at every resolution; thresholds scale with the screen.
- The queue screen is recognised as soon as it appears instead of after a fixed 8 second wait.
- Hotkeys no longer need administrator rights, and holding a key triggers it only once.
- Settings are checked and written safely, so a bad value or a crash cannot corrupt them.

### Fixed

- Rare crashes caused by updating the window from the background thread.

## [1.3.0] - 2026-03-18

- System tray, saved settings, crash watchdog, elapsed timer.
- Adaptive wait: reacts as soon as the "server full" dialog appears.
- Faster screen capture (only the needed regions, no Pillow).
- Faster retries by default; "Pause after ESC" setting; mute toggle for the alert.

## [1.2.0] - 2026-03-16

- Fixed the minimum wait time and the build.
- Code clean-up, new README with a demo GIF.

## [1.1.0] - 2026-02-24

- Experimental fast ESC mode, speed improvements.

## [1.0.0] - 2026-02-09

- First release: clicks Join until you are in the queue, F6 / F4 hotkeys.

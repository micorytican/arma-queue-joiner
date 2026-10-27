# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [2.0.0] - unreleased

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
- lime98 intro at startup: head-up radar scan and lock, a dive into the target, then a Cold War terminal types the callsign; click to skip or turn it off.
- Installer for the current user, in addition to the portable exe.
- Only one copy runs at a time; starting it again shows the open window.

### Changed

- Detection works the same at every resolution; thresholds scale with the screen.
- The queue screen is recognised as soon as it appears instead of after a fixed 8 second wait.
- Hotkeys no longer need administrator rights, and holding a key triggers it only once.
- Settings are checked and written safely, so a bad value or a crash cannot corrupt them.

### Fixed

- Rare crashes caused by updating the window from the background thread.

## [1.1.0]

- Experimental fast ESC mode, speed improvements.

## [1.0.0]

- First release: clicks Join until you are in the queue, F6 / F4 hotkeys.

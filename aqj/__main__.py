"""Entry point: python -m aqj"""

from __future__ import annotations

import contextlib
import ctypes
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QStyleFactory

from . import APP_ID, APP_NAME


def resource(name: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return str(base / name)


def _already_running() -> bool:
    """If another copy is open, ask it to show itself and return True."""
    socket = QLocalSocket()
    socket.connectToServer(APP_ID)
    if socket.waitForConnected(300):
        socket.write(b"show")
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        return True
    return False


def main() -> int:
    # Own taskbar group and icon instead of python.exe's
    with contextlib.suppress(AttributeError, OSError):
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"lime98.{APP_ID}")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    if _already_running():
        return 0

    from . import logs, winapi
    from .ui import theme
    from .ui.window import MainWindow

    with contextlib.suppress(OSError):  # a read-only profile must not stop the app
        logs.setup_logging()
    logs.install_crash_handler()

    if "windows11" in QStyleFactory.keys():  # noqa: SIM118 (keys() is a static Qt call)
        app.setStyle("windows11")
    app.setFont(theme.font(14))

    icon = QIcon(resource("icon.ico"))
    window = MainWindow(icon)
    logs.install_crash_handler(window.bridge.crash.emit)
    window.check_for_updates()

    server = QLocalServer(app)
    QLocalServer.removeServer(APP_ID)
    if server.listen(APP_ID):

        def _on_connection() -> None:
            conn = server.nextPendingConnection()
            if conn is not None:
                conn.readyRead.connect(window.show_window)

        server.newConnection.connect(_on_connection)

    if window.settings.show_intro and winapi.animations_enabled():
        from .ui.intro import IntroWindow

        intro = IntroWindow()
        intro.finished.connect(window.show)
        intro.play()
    else:
        window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

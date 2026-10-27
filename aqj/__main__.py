"""Entry point: python -m aqj"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PySide6.QtGui import QFont, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

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
    try:  # own taskbar group and icon instead of python.exe's
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"lime98.{APP_ID}")
    except (AttributeError, OSError):
        pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    if _already_running():
        return 0

    from .ui import theme
    from .ui.window import MainWindow

    font = QFont("Segoe UI Variable Text")
    font.setPixelSize(13)
    font.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(font)
    app.setStyleSheet(theme.stylesheet())

    icon = QIcon(resource("icon.ico"))
    window = MainWindow(icon)

    server = QLocalServer(app)
    QLocalServer.removeServer(APP_ID)
    if server.listen(APP_ID):
        def _on_connection() -> None:
            conn = server.nextPendingConnection()
            if conn is not None:
                conn.readyRead.connect(window.show_window)

        server.newConnection.connect(_on_connection)

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

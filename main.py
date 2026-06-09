from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from version import APP_NAME, APP_VERSION


def resource_path(relative: str) -> str:
    """Works both in dev and when frozen by PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        return str(Path(sys._MEIPASS) / relative)
    return str(Path(__file__).parent / relative)


def main() -> int:
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "sansarsam.app"
        )

    app = QApplication(sys.argv)

    icon = QIcon(resource_path("assets/icon.ico"))
    app.setWindowIcon(icon)

    QCoreApplication.setOrganizationName(APP_NAME)
    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setApplicationVersion(APP_VERSION)

    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

"""Application entry point for the Python Launchpad clone."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from models.app_model import ApplicationCatalog
from ui.launchpad import LaunchpadWindow


def _load_stylesheet() -> str:
    """Load the application QSS file if it is available."""
    style_path = Path(__file__).resolve().parent / "styles" / "style.qss"
    if not style_path.exists():
        return ""
    return style_path.read_text(encoding="utf-8")


def main() -> int:
    """Start the Qt application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Launchpad")
    app.setOrganizationName("PythonLaunchpad")
    app.setStyleSheet(_load_stylesheet())

    catalog = ApplicationCatalog()
    window = LaunchpadWindow(catalog=catalog)
    window.resize(500, 250)
    window.show_centered()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

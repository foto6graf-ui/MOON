"""Search input used by the Launchpad window."""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLineEdit


class SearchBox(QLineEdit):
    """Glass search field with keyboard navigation signals."""

    navigate = Signal(int, int)
    accept_current = Signal()
    cancelled = Signal()

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SearchBox")
        self.setPlaceholderText("Поиск приложений...")
        self.setClearButtonEnabled(True)
        self.setMinimumHeight(44)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.clear()
            self.cancelled.emit()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept_current.emit()
            return
        if key == Qt.Key.Key_Left:
            self.navigate.emit(-1, 0)
            return
        if key == Qt.Key.Key_Right:
            self.navigate.emit(1, 0)
            return
        if key == Qt.Key.Key_Up:
            self.navigate.emit(0, -1)
            return
        if key == Qt.Key.Key_Down:
            self.navigate.emit(0, 1)
            return
        super().keyPressEvent(event)

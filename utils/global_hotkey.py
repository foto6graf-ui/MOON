"""Small Windows-only modifier hotkey watcher."""

from __future__ import annotations

import ctypes
import platform

from PySide6.QtCore import QObject, QTimer, Signal


class ModifierHotkeyWatcher(QObject):
    """Emit once when Win and Alt are pressed together."""

    activated = Signal()

    VK_MENU = 0x12
    VK_LWIN = 0x5B
    VK_RWIN = 0x5C

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._enabled = platform.system().lower() == "windows"
        self._pressed = False
        self._timer = QTimer(self)
        self._timer.setInterval(35)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        if self._enabled and not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self._pressed = False

    def _is_down(self, virtual_key: int) -> bool:
        return bool(ctypes.windll.user32.GetAsyncKeyState(virtual_key) & 0x8000)

    def _poll(self) -> None:
        alt_down = self._is_down(self.VK_MENU)
        win_down = self._is_down(self.VK_LWIN) or self._is_down(self.VK_RWIN)
        pressed = alt_down and win_down
        if pressed and not self._pressed:
            self.activated.emit()
        self._pressed = pressed

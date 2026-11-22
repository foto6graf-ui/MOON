"""Small Windows-only modifier hotkey watcher."""

from __future__ import annotations

import ctypes
import platform
import threading
import time

from PySide6.QtCore import QObject, Signal


class ModifierHotkeyWatcher(QObject):
    """Emit once when Win and Alt are pressed together."""

    activated = Signal()

    VK_MENU = 0x12
    VK_LMENU = 0xA4
    VK_RMENU = 0xA5
    VK_LWIN = 0x5B
    VK_RWIN = 0x5C

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._enabled = platform.system().lower() == "windows"
        self._pressed = False
        self._last_activated = 0.0
        self._get_key_state = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        if self._enabled:
            self._get_key_state = ctypes.WinDLL("user32", use_last_error=True).GetAsyncKeyState
            self._get_key_state.argtypes = [ctypes.c_int]
            self._get_key_state.restype = ctypes.c_short

    def start(self) -> None:
        if not self._enabled or (self._thread and self._thread.is_alive()):
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._watch_keys,
            name="MOON-global-hotkey",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=0.25)
        self._thread = None
        self._pressed = False

    def _is_down(self, virtual_key: int) -> bool:
        return bool(self._get_key_state(virtual_key) & 0x8000)

    def _watch_keys(self) -> None:
        while not self._stop_event.wait(0.008):
            self._poll()

    def _poll(self) -> None:
        alt_down = any(
            self._is_down(key)
            for key in (self.VK_MENU, self.VK_LMENU, self.VK_RMENU)
        )
        win_down = self._is_down(self.VK_LWIN) or self._is_down(self.VK_RWIN)
        pressed = alt_down and win_down
        now = time.monotonic()
        if pressed and not self._pressed and now - self._last_activated >= 0.15:
            self.activated.emit()
            self._last_activated = now
        self._pressed = pressed

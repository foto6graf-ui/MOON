"""Native translucent backdrop helpers."""

from __future__ import annotations

import ctypes
import platform


def apply_native_backdrop(window_id: int) -> None:
    """Best-effort native tweaks for transparent widget windows."""
    if platform.system().lower() != "windows":
        return
    try:
        _enable_windows_backdrop(int(window_id))
    except (AttributeError, OSError):
        return


def _enable_windows_backdrop(hwnd: int) -> None:
    dwmapi = ctypes.windll.dwmapi

    border_color = ctypes.c_uint(0xFFFFFFFE)
    dwmapi.DwmSetWindowAttribute(
        hwnd,
        34,
        ctypes.byref(border_color),
        ctypes.sizeof(border_color),
    )

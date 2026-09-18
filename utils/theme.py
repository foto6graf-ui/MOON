"""Theme state and palette helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QObject, Signal


class ThemeMode(str, Enum):
    """Theme choices supported by the UI."""

    AUTO = "Auto"
    DARK = "Dark"
    LIGHT = "Light"


@dataclass(frozen=True, slots=True)
class ThemePalette:
    """Colors used by custom-painted widgets."""

    background_start: str
    background_mid: str
    background_end: str
    panel: str
    text: str
    muted_text: str
    border: str
    accent: str = "#4DA3FF"


DARK_PALETTE = ThemePalette(
    background_start="#1A2240",
    background_mid="#263B8C",
    background_end="#324DBB",
    panel="rgba(40, 40, 60, 180)",
    text="#F5F5F5",
    muted_text="#D6D6D6",
    border="rgba(255, 255, 255, 70)",
)

LIGHT_PALETTE = ThemePalette(
    background_start="#DDE8FF",
    background_mid="#AFC9FF",
    background_end="#F5F5F5",
    panel="rgba(245, 248, 255, 196)",
    text="#1A2240",
    muted_text="#263B8C",
    border="rgba(26, 34, 64, 50)",
)


class ThemeController(QObject):
    """Small observable controller for theme transitions."""

    theme_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._mode = ThemeMode.DARK
        self._dark = True

    @property
    def mode(self) -> ThemeMode:
        return self._mode

    @property
    def palette(self) -> ThemePalette:
        return DARK_PALETTE if self._dark else LIGHT_PALETTE

    def set_mode(self, mode: ThemeMode) -> None:
        self._mode = ThemeMode.DARK
        self._dark = True
        self.theme_changed.emit()

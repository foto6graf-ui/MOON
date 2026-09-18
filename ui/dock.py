"""Pinned and favorite applications dock."""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QWidget

from models.app_model import ApplicationItem
from ui.app_card import AppCard
from utils.icon_cache import IconCache


class Dock(QWidget):
    """Compact glass strip for pinned and favorite applications."""

    card_launched = Signal(str)
    pin_requested = Signal(str)
    favorite_requested = Signal(str)

    def __init__(self, icon_cache: IconCache, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_cache = icon_cache
        self.setObjectName("Dock")
        self.setFixedHeight(104)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(16, 10, 16, 10)
        self._layout.setSpacing(12)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_apps(self, apps: list[ApplicationItem]) -> None:
        """Refresh dock cards."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for app in apps[:12]:
            card = AppCard(app, self._icon_cache, self)
            card.setFixedSize(76, 82)
            card.launched.connect(self.card_launched)
            card.pin_requested.connect(self.pin_requested)
            card.favorite_requested.connect(self.favorite_requested)
            self._layout.addWidget(card)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(255, 255, 255, 55))
        painter.setBrush(QColor(255, 255, 255, 28))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 24, 24)

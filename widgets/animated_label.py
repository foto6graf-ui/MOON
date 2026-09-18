"""Animated text label widgets."""

from __future__ import annotations

from PySide6.QtCore import Property, QPropertyAnimation
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QLabel


class AnimatedLabel(QLabel):
    """QLabel with an animatable text color property."""

    def __init__(self, text: str = "", parent: object | None = None) -> None:
        super().__init__(text, parent)
        self._color = QColor("#F5F5F5")

    def color(self) -> QColor:
        return QColor(self._color)

    def setColor(self, color: QColor) -> None:
        self._color = QColor(color)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.WindowText, self._color)
        self.setPalette(palette)

    textColor = Property(QColor, color, setColor)

    def animate_color(self, color: QColor, duration: int = 180) -> None:
        """Transition the label text to a new color."""
        animation = QPropertyAnimation(self, b"textColor", self)
        animation.setStartValue(self._color)
        animation.setEndValue(color)
        animation.setDuration(duration)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

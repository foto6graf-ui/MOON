"""Animated capsule and circular buttons."""

from __future__ import annotations

from PySide6.QtCore import Property, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QPushButton


class HoverButton(QPushButton):
    """A button with animated glass hover and selected states."""

    selected_changed = Signal(bool)

    def __init__(self, text: str = "", parent: object | None = None, *, circular: bool = False) -> None:
        super().__init__(text, parent)
        self._background = QColor(255, 255, 255, 35)
        self._hover = QColor(255, 255, 255, 60)
        self._selected = QColor("#4DA3FF")
        self._current = QColor(self._background)
        self._is_selected = False
        self._circular = circular
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setMinimumHeight(38 if not circular else 42)
        if circular:
            self.setFixedSize(42, 42)
        self.toggled.connect(self._set_selected)

    def backgroundColor(self) -> QColor:
        return QColor(self._current)

    def setBackgroundColor(self, color: QColor) -> None:
        self._current = QColor(color)
        self.update()

    backgroundColor = Property(QColor, backgroundColor, setBackgroundColor)

    def enterEvent(self, event: object) -> None:
        self._animate_color(self._selected if self._is_selected else self._hover)
        super().enterEvent(event)

    def leaveEvent(self, event: object) -> None:
        self._animate_color(self._selected if self._is_selected else self._background)
        super().leaveEvent(event)

    def _set_selected(self, checked: bool) -> None:
        self._is_selected = checked
        self.selected_changed.emit(checked)
        self._animate_color(self._selected if checked else self._background)

    def _animate_color(self, color: QColor) -> None:
        animation = QPropertyAnimation(self, b"backgroundColor", self)
        animation.setStartValue(self._current)
        animation.setEndValue(color)
        animation.setDuration(220)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = self.height() // 2 if self._circular else 18
        # Фон кнопки не рисуем
        painter.setPen(QColor("#F5F5F5"))
        painter.setFont(self.font())
        if self._circular and self.text() == "...":
            painter.setBrush(QColor("#F5F5F5"))
            center_y = self.height() // 2
            center_x = self.width() // 2
            for offset in (-8, 0, 8):
                painter.drawEllipse(center_x + offset - 2, center_y - 2, 4, 4)
            return
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())

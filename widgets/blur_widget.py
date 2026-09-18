"""Transparent background widgets for MOON."""

from __future__ import annotations

from PySide6.QtCore import Property, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QGraphicsBlurEffect,
    QGraphicsDropShadowEffect,
    QWidget,
)


class GradientBackground(QWidget):
    """
    Полностью прозрачный фон.

    Оставлен в проекте для совместимости с Launchpad.
    Ничего непрозрачного не рисует.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:

        super().__init__(parent)

        self._overlay_opacity = 0.0

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )

        self.setAutoFillBackground(False)

    def overlayOpacity(self) -> float:

        return self._overlay_opacity

    def setOverlayOpacity(
        self,
        value: float,
    ) -> None:

        self._overlay_opacity = max(
            0.0,
            min(
                1.0,
                float(value),
            ),
        )

        self.update()

    overlayOpacity = Property(
        float,
        overlayOpacity,
        setOverlayOpacity,
    )

    def paintEvent(
        self,
        event,
    ) -> None:

        # Ничего не рисуем.
        # Фон должен оставаться прозрачным.
        pass


class BlurWidget(QWidget):
    """
    Старый совместимый стеклянный виджет.

    Оставлен, чтобы другие части проекта
    не сломались при импорте.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:

        super().__init__(parent)

        self._radius = 28

        self._panel_color = QColor(
            255,
            255,
            255,
            20,
        )

        self._panel_opacity = 1.0

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        self.setAutoFillBackground(False)

    def set_light_theme(
        self,
        enabled: bool,
    ) -> None:

        if enabled:

            self._panel_color = QColor(
                255,
                255,
                255,
                28,
            )

        else:

            self._panel_color = QColor(
                255,
                255,
                255,
                14,
            )

        self.update()

    def set_panel_alpha(
        self,
        alpha: int,
    ) -> None:

        alpha = max(
            0,
            min(
                255,
                int(alpha),
            ),
        )

        self._panel_color.setAlpha(alpha)

        self.update()

    def panelOpacity(self) -> float:

        return self._panel_opacity

    def setPanelOpacity(
        self,
        value: float,
    ) -> None:

        self._panel_opacity = max(
            0.0,
            min(
                1.0,
                float(value),
            ),
        )

        self.update()

    panelOpacity = Property(
        float,
        panelOpacity,
        setPanelOpacity,
    )

    def create_blur_effect(
        self,
        radius: float = 12.0,
    ) -> QGraphicsBlurEffect:

        effect = QGraphicsBlurEffect(self)

        effect.setBlurRadius(radius)

        return effect

    def paintEvent(
        self,
        event,
    ) -> None:

        painter = QPainter(self)

        color = QColor(self._panel_color)

        color.setAlpha(
            int(
                color.alpha()
                * self._panel_opacity
            )
        )

        painter.fillRect(
            self.rect(),
            color,
        )

        painter.end()
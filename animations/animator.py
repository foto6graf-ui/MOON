"""Reusable Qt Animation Framework helpers."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QPauseAnimation,
    QSequentialAnimationGroup,
    QPoint,
    QRect,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


class Animator:
    """Factory for common animation patterns used by the interface."""

    @staticmethod
    def property_animation(
        target: object,
        property_name: bytes,
        start: object,
        end: object,
        duration: int = 250,
        easing: QEasingCurve.Type = QEasingCurve.Type.OutCubic,
    ) -> QPropertyAnimation:
        """Create a configured property animation."""
        animation = QPropertyAnimation(target, property_name)
        animation.setStartValue(start)
        animation.setEndValue(end)
        animation.setDuration(duration)
        animation.setEasingCurve(easing)
        return animation

    @staticmethod
    def fade(widget: QWidget, start: float, end: float, duration: int = 240) -> QPropertyAnimation:
        """Animate widget opacity."""
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        return Animator.property_animation(effect, b"opacity", start, end, duration)

    @staticmethod
    def slide(widget: QWidget, offset: QPoint, duration: int = 260) -> QPropertyAnimation:
        """Animate a widget from an offset position into place."""
        end = widget.pos()
        start = end + offset
        widget.move(start)
        return Animator.property_animation(widget, b"pos", start, end, duration)

    @staticmethod
    def geometry_scale(
        widget: QWidget,
        scale: float,
        duration: int = 360,
        easing: QEasingCurve.Type = QEasingCurve.Type.OutBack,
    ) -> QPropertyAnimation:
        """Animate widget geometry from a scaled center rectangle."""
        end = widget.geometry()
        center = end.center()
        start_width = max(1, int(end.width() * scale))
        start_height = max(1, int(end.height() * scale))
        start = QRect(0, 0, start_width, start_height)
        start.moveCenter(center)
        return Animator.property_animation(widget, b"geometry", start, end, duration, easing)

    @staticmethod
    def entrance_sequence(panel: QWidget, cards: list[QWidget]) -> QSequentialAnimationGroup:
        """Build the Launchpad startup sequence."""
        sequence = QSequentialAnimationGroup(panel)
        panel_group = QParallelAnimationGroup(sequence)
        panel_group.addAnimation(
            Animator.property_animation(
                panel,
                b"panelOpacity",
                0.0,
                1.0,
                210,
                QEasingCurve.Type.OutCubic,
            )
        )
        sequence.addAnimation(panel_group)

        cards_group = QParallelAnimationGroup(sequence)
        for index, card in enumerate(cards[:24]):
            card_sequence = QSequentialAnimationGroup(cards_group)
            card_sequence.addAnimation(QPauseAnimation(index * 7, card_sequence))
            card_sequence.addAnimation(
                Animator.property_animation(
                    card,
                    b"contentOpacity",
                    0.0,
                    1.0,
                    140,
                    QEasingCurve.Type.OutCubic,
                )
            )
            cards_group.addAnimation(card_sequence)
        sequence.addAnimation(cards_group)
        return sequence

    @staticmethod
    def cards_sequence(parent: QWidget, cards: list[QWidget]) -> QSequentialAnimationGroup:
        """Build a staggered card-only entrance animation."""
        sequence = QParallelAnimationGroup(parent)
        for index, card in enumerate(cards[:24]):
            card_sequence = QSequentialAnimationGroup(sequence)
            card_sequence.addAnimation(QPauseAnimation(index * 7, card_sequence))
            card_sequence.addAnimation(
                Animator.property_animation(
                    card,
                    b"contentOpacity",
                    0.0,
                    1.0,
                    140,
                    QEasingCurve.Type.OutCubic,
                )
            )
            sequence.addAnimation(card_sequence)
        return sequence

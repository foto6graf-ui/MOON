"""Animated glass popover menu used by the three-dot button."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import Property, QEasingCurve, QEvent, QPoint, QRect, Qt, QParallelAnimationGroup, QPropertyAnimation, Signal
from PySide6.QtGui import QAction, QColor, QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget


@dataclass(slots=True)
class MenuNode:
    """Single popover row backed by QAction."""

    icon: str
    text: str
    action: QAction | None = None
    children: list["MenuNode"] = field(default_factory=list)
    checkable: bool = False
    checked: bool = False


class MenuRow(QWidget):
    """One animated row in the glass menu."""

    activated = QAction

    def __init__(self, node: MenuNode, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        self.node = node
        self._hover = 0.0
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 10, 0)
        layout.setSpacing(10 if node.icon else 0)
        self.icon_label = QLabel(node.icon, self)
        self.icon_label.setFixedWidth(22 if node.icon else 0)
        self.icon_label.setVisible(bool(node.icon))
        self.text_label = QLabel(node.text, self)
        self.state_label = QLabel("" if node.checkable and node.checked else "", self)
        self.state_label.setFixedWidth(16)
        self.arrow_label = QLabel(">" if node.children else "", self)
        for label in (
                self.icon_label,
                self.text_label,
                self.state_label,
                self.arrow_label,
        ):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            label.setStyleSheet("background: transparent;")
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label, 1)
        layout.addWidget(self.state_label)
        layout.addWidget(self.arrow_label)

    def hoverAmount(self) -> float:
        return self._hover

    def setHoverAmount(self, value: float) -> None:
        self._hover = 0.0
        self.update()

    hoverAmount = Property(float, hoverAmount, setHoverAmount)

    def set_selected(self, selected: bool) -> None:
        self._hover = 0.0
        self.update()

    def enterEvent(self, event: object) -> None:
        self.parent().set_current_row(self)  # type: ignore[union-attr]
        super().enterEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.parent().activate_row(self)  # type: ignore[union-attr]
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setOpacity(0.0)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)

        painter.end()


class GlassPopoverMenu(QWidget):
    """Animated glass menu with submenus and keyboard navigation."""

    closed = Signal()

    def __init__(self, nodes: list[MenuNode], parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._nodes = nodes
        self._opacity = 1.0
        self._rows: list[MenuRow] = []
        self._current_index = 0
        self._submenu: GlassPopoverMenu | None = None
        self._submenu_row: MenuRow | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 145))
        self.setGraphicsEffect(shadow)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 10, 10, 10)
        self._layout.setSpacing(2)
        for node in nodes:
            row = MenuRow(node, self)
            self._rows.append(row)
            self._layout.addWidget(row)
        self.setFixedWidth(292)
        self.setFixedHeight(20 + len(nodes) * 40)
        self._preferred_size = self.size()

    def menuOpacity(self) -> float:
        return self._opacity

    def setMenuOpacity(self, value: float) -> None:
        self._opacity = max(0.0, min(1.0, value))
        self.update()

    menuOpacity = Property(float, menuOpacity, setMenuOpacity)

    def popup_at(self, position: QPoint) -> None:
        screen = QGuiApplication.screenAt(position)
        if screen is None and self.parentWidget() is not None:
            parent_handle = self.parentWidget().windowHandle()
            screen = parent_handle.screen() if parent_handle else None
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.setFixedSize(self._preferred_size.boundedTo(available.size()))
            x = max(available.left(), min(position.x(), available.right() - self.width() + 1))
            y = max(available.top(), min(position.y(), available.bottom() - self.height() + 1))
            position = QPoint(x, y)
        self.move(position)
        self.show()
        self.setFocus()
        QApplication.instance().installEventFilter(self)
        self._select_index(0)
        end = self.geometry()
        start = QRect(
            end.x() + 4,
            end.y() - 4,
            end.width(),
            end.height()
        )
        group = QParallelAnimationGroup(self)
        geo = QPropertyAnimation(self, b"geometry", group)
        geo.setStartValue(start)
        geo.setEndValue(end)
        geo.setDuration(120)
        geo.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade = QPropertyAnimation(self, b"menuOpacity", group)
        fade.setStartValue(0.75)
        fade.setEndValue(1.0)
        fade.setDuration(100)
        group.addAnimation(geo)
        group.addAnimation(fade)
        group.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def closeEvent(self, event: object) -> None:
        application = QApplication.instance()
        if application is not None:
            application.removeEventFilter(self)
        if self._submenu:
            self._submenu.close()
            self._submenu = None
            self._submenu_row = None
        self.closed.emit()
        super().closeEvent(event)

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress and hasattr(event, "globalPosition"):
            point = event.globalPosition().toPoint()
            submenu_open = self._submenu is not None and self._submenu.geometry().contains(point)
            if not self.geometry().contains(point) and not submenu_open:
                self.close()
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close()
            return
        if key == Qt.Key.Key_Down:
            self._select_index(self._current_index + 1)
            return
        if key == Qt.Key.Key_Up:
            self._select_index(self._current_index - 1)
            return
        if key == Qt.Key.Key_Right:
            self._open_submenu(self._rows[self._current_index])
            return
        if key == Qt.Key.Key_Left:
            self.close()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.activate_row(self._rows[self._current_index])
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self.rect().contains(event.position().toPoint()):
            self.close()
            return
        super().mousePressEvent(event)

    def set_current_row(self, row: MenuRow) -> None:
        self._select_index(self._rows.index(row))
        self._open_submenu(row)

    def activate_row(self, row: MenuRow) -> None:
        if row.node.children:
            self._open_submenu(row)
            return
        if row.node.action:
            row.node.action.trigger()
        self.close()

    def _select_index(self, index: int) -> None:
        if not self._rows:
            return
        self._current_index = index % len(self._rows)
        for row_index, row in enumerate(self._rows):
            row.set_selected(row_index == self._current_index)

    def _open_submenu(self, row: MenuRow) -> None:
        if not row.node.children:
            if self._submenu:
                self._submenu.close()
                self._submenu = None
                self._submenu_row = None
            return
        if self._submenu and self._submenu_row is row and self._submenu.isVisible():
            return
        if self._submenu:
            self._submenu.close()
        self._submenu = GlassPopoverMenu(row.node.children, self)
        self._submenu_row = row
        point = row.mapToGlobal(QPoint(row.width() - 2, -8))
        self._submenu.popup_at(point)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(1.0)

        rect = self.rect().adjusted(1, 1, -1, -1)

        path = QPainterPath()
        path.addRoundedRect(rect, 20, 20)

        painter.fillPath(
            path,
            QColor(30, 34, 48, 230)
        )

        painter.setPen(
            QColor(255, 255, 255, 80)
        )

        painter.drawPath(path)

        painter.end()

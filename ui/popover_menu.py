"""Animated glass popover menu used by the three-dot button."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import Property, QEasingCurve, QEvent, QPoint, QPointF, QRect, Qt, QParallelAnimationGroup, QPropertyAnimation, Signal
from PySide6.QtGui import QAction, QColor, QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget



@dataclass(slots=True)
class MenuNode:
    """Single popover row backed by QAction."""

    icon: str
    text: str
    action: QAction | None = None
    children: list["MenuNode"] = field(default_factory=list)
    checkable: bool = False
    checked: bool = False
    detail: str = ""


class MenuIcon(QWidget):
    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.name = name
        self.setFixedSize(22, 22)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(225, 230, 246, 235), 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self.name == "search":
            painter.drawEllipse(3.5, 3.5, 11.5, 11.5)
            painter.drawLine(13.5, 13.5, 19.5, 19.5)
        elif self.name == "settings":
            points = []
            tooth_radii = (7.0, 7.0, 9.2, 9.2)
            for tooth in range(8):
                for corner, radius in enumerate(tooth_radii):
                    angle = (tooth + corner / 4) * math.tau / 8 - math.pi / 2
                    points.append(QPointF(11 + math.cos(angle) * radius, 11 + math.sin(angle) * radius))
            painter.drawPolygon(QPolygonF(points))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(11, 11), 3.2, 3.2)
        elif self.name == "about":
            painter.drawEllipse(QPointF(11, 11), 8.5, 8.5)
            painter.drawLine(11, 10, 11, 15.5)
            painter.drawPoint(11, 7)
        elif self.name == "exit":
            painter.drawLine(3.5, 3, 11, 3)
            painter.drawLine(3.5, 3, 3.5, 19)
            painter.drawLine(3.5, 19, 11, 19)
            painter.drawLine(10, 11, 20, 11)
            painter.drawLine(16, 7, 20, 11)
            painter.drawLine(16, 15, 20, 11)
        elif self.name == "star":
            points = [
                QPointF(
                    11 + math.cos(i * math.tau / 10 - math.pi / 2) * (8.5 if i % 2 == 0 else 3.6),
                    11 + math.sin(i * math.tau / 10 - math.pi / 2) * (8.5 if i % 2 == 0 else 3.6),
                )
                for i in range(10)
            ]
            painter.drawPolygon(QPolygonF(points))
        elif self.name == "clock":
            painter.drawEllipse(QPointF(11, 11), 8.5, 8.5)
            painter.drawLine(11, 6, 11, 11)
            painter.drawLine(11, 11, 15, 13.5)
        elif self.name == "sort_name":
            font = painter.font()
            font.setPixelSize(9)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(1, 10, "A")
            painter.drawText(1, 21, "Z")
            painter.drawLine(17, 4, 17, 20)
            painter.drawLine(14, 17, 17, 20)
            painter.drawLine(20, 17, 17, 20)
        elif self.name == "pin":
            painter.drawLine(7, 4, 15, 4)
            painter.drawLine(9, 4, 9, 9)
            painter.drawLine(13, 4, 13, 9)
            painter.drawLine(8, 9, 14, 9)
            painter.drawLine(11, 9, 11, 15)
            painter.drawLine(11, 15, 7, 20)
        else:
            painter.setFont(self.font())
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.name)
        painter.end()


class MenuRow(QWidget):
    """One animated row in the glass menu."""

    activated = QAction

    def __init__(self, node: MenuNode, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        self.node = node
        self._hover = 0.0
        self._selected = False
        self.setFixedHeight(54 if node.detail else 46)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 2, 12, 2)
        layout.setSpacing(11 if node.icon else 2)
        self.icon_label = MenuIcon(node.icon, self)
        self.icon_label.setFixedWidth(24 if node.icon else 0)
        self.icon_label.setVisible(bool(node.icon))
        self.text_label = QLabel(node.text, self)
        self.text_label.setObjectName("MenuRowTitle")
        self.state_label = QLabel("✓" if node.checkable and node.checked else "", self)
        self.state_label.setObjectName("MenuRowState")
        self.state_label.setFixedWidth(22)
        self.arrow_label = QLabel("›" if node.children else "", self)
        self.arrow_label.setObjectName("MenuRowArrow")
        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)
        text_column.addWidget(self.text_label)
        if node.detail:
            self.detail_label = QLabel(node.detail, self)
            self.detail_label.setObjectName("MenuRowDetail")
            self.detail_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            text_column.addWidget(self.detail_label)
        else:
            self.detail_label = None
        for label in (
                self.icon_label,
                self.text_label,
                self.state_label,
                self.arrow_label,
        ):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            label.setStyleSheet("background: transparent;")
        layout.addWidget(self.icon_label)
        layout.addLayout(text_column, 1)
        layout.addWidget(self.state_label)
        layout.addWidget(self.arrow_label)

    def hoverAmount(self) -> float:
        return self._hover

    def setHoverAmount(self, value: float) -> None:
        self._hover = max(0.0, min(1.0, float(value)))
        self.update()

    hoverAmount = Property(float, hoverAmount, setHoverAmount)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
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
        if self._selected or self._hover:
            rect = self.rect().adjusted(1, 1, -1, -1)
            path = QPainterPath()
            path.addRoundedRect(rect, 13, 13)
            alpha = 76 if self._selected else int(40 * self._hover)
            painter.fillPath(path, QColor(119, 105, 222, alpha))
            painter.setPen(QColor(190, 183, 255, 58 if self._selected else 22))
            painter.drawPath(path)
            if self._selected:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(177, 161, 255, 225))
                painter.drawRoundedRect(QRect(2, 14, 3, self.height() - 28), 1.5, 1.5)
        painter.end()


class GlassPopoverMenu(QWidget):
    """Animated glass menu with submenus and keyboard navigation."""

    closed = Signal()

    def __init__(
        self,
        nodes: list[MenuNode],
        parent: QWidget | None = None,
        *,
        title: str = "MOON",
        subtitle: str = "Быстрые действия",
    ) -> None:
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._nodes = nodes
        self._opacity = 1.0
        self._rows: list[MenuRow] = []
        self._current_index = 0
        self._submenu: GlassPopoverMenu | None = None
        self._submenu_row: MenuRow | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("""
            QLabel#MenuHeading {
                color: #f4f2ff; font-size: 10px; font-weight: 700; letter-spacing: 1.8px;
            }
            QLabel#MenuSubtitle { color: #929ab5; font-size: 11px; }
            QFrame#MenuDivider { background: rgba(208, 211, 239, 30); border: none; }
            QLabel#MenuRowTitle { color: #f0f2fb; font-size: 12px; font-weight: 600; }
            QLabel#MenuRowDetail { color: #969fb8; font-size: 10px; }
            QLabel#MenuRowState { color: #c3b8ff; font-size: 15px; font-weight: 700; }
            QLabel#MenuRowArrow { color: #9ba4bd; font-size: 22px; }
            QLabel#MenuFooter { color: #747f9c; font-size: 9px; letter-spacing: 1.2px; }
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 10)
        self._layout.setSpacing(4)
        heading = QWidget(self)
        heading_layout = QVBoxLayout(heading)
        heading_layout.setContentsMargins(8, 2, 8, 7)
        heading_layout.setSpacing(3)
        self.title_label = QLabel(title, heading)
        self.title_label.setObjectName("MenuHeading")
        self.subtitle_label = QLabel(subtitle, heading)
        self.subtitle_label.setObjectName("MenuSubtitle")
        heading_layout.addWidget(self.title_label)
        heading_layout.addWidget(self.subtitle_label)
        self._layout.addWidget(heading)
        divider = QFrame(self)
        divider.setObjectName("MenuDivider")
        divider.setFixedHeight(1)
        self._layout.addWidget(divider)
        for node in nodes:
            row = MenuRow(node, self)
            self._rows.append(row)
            self._layout.addWidget(row)
        footer = QLabel("ESC  ·  ЗАКРЫТЬ", self)
        footer.setObjectName("MenuFooter")
        footer.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        footer.setContentsMargins(8, 5, 8, 1)
        self._layout.addWidget(footer)
        self.setFixedWidth(304)
        self._layout.activate()
        self.setFixedHeight(self._layout.sizeHint().height())
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
                root = self
                while root.parentWidget() is not None:
                    root = root.parentWidget()
                if root is not self and root.isVisible() and not root.frameGeometry().contains(point):
                    root.hide()
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
        painter.setOpacity(self._opacity)

        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)
        painter.fillPath(path, QColor(25, 29, 43, 255))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(73, 81, 105, 210), 1))
        painter.drawPath(path)

        painter.end()

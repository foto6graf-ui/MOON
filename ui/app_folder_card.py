"""Clearly identifiable, draggable folder tile in the application grid."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QMouseEvent
from PySide6.QtWidgets import QWidget

from models.app_model import AppFolder, ApplicationItem
from utils.icon_cache import IconCache


class AppFolderCard(QWidget):
    """A bordered folder preview, clickable to open and accepting app drops."""

    open_requested = Signal(str)
    app_dropped = Signal(str, str)

    def __init__(
        self,
        folder: AppFolder,
        applications: list[ApplicationItem],
        icon_cache: IconCache,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.folder = folder
        self.applications = applications
        self._icon_cache = icon_cache
        self._hovered = False
        self._press_position: QPoint | None = None
        self._drop_received = False
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._update_tooltip()

    def update_content(self, folder: AppFolder, applications: list[ApplicationItem]) -> None:
        self.folder = folder
        self.applications = applications
        self._update_tooltip()
        self.update()

    def _update_tooltip(self) -> None:
        self.setToolTip(f"\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u00ab{self.folder.name}\u00bb \u00b7 \u043f\u0435\u0440\u0435\u0442\u0430\u0449\u0438\u0442\u0435 \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0435, \u0447\u0442\u043e\u0431\u044b \u0434\u043e\u0431\u0430\u0432\u0438\u0442\u044c")

    def enterEvent(self, event: object) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: object) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_position = event.position().toPoint()
            self._drop_received = False
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._press_position is not None
            and self.rect().contains(event.position().toPoint())
            and not self._drop_received
        ):
            self.open_requested.emit(self.folder.folder_id)
        self._press_position = None
        self._drop_received = False
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event: object) -> None:
        if event.mimeData().hasFormat("application/x-launchpad-app"):
            event.acceptProposedAction()
            self._hovered = True
            self.update()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: object) -> None:
        self._hovered = False
        self.update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: object) -> None:
        source_id = bytes(event.mimeData().data("application/x-launchpad-app")).decode("utf-8")
        if source_id:
            self._drop_received = True
            self.app_dropped.emit(source_id, self.folder.folder_id)
            event.acceptProposedAction()
        self._hovered = False
        self.update()

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = min(66, self.width() - 8)
        icon_box = QRect((self.width() - side) // 2, 3, side, side)
        painter.setBrush(QColor(255, 255, 255, 38 if self._hovered else 22))
        painter.setPen(QColor(220, 225, 255, 125 if self._hovered else 72))
        painter.drawRoundedRect(icon_box, 17, 17)

        for index, app in enumerate(self.applications[:4]):
            column, row = index % 2, index // 2
            thumb_size = max(19, (side - 19) // 2)
            x = icon_box.x() + 6 + column * (thumb_size + 3)
            y = icon_box.y() + 6 + row * (thumb_size + 3)
            thumb_rect = QRect(x, y, thumb_size, thumb_size)
            painter.setBrush(QColor(255, 255, 255, 46))
            painter.setPen(QColor(255, 255, 255, 48))
            painter.drawRoundedRect(thumb_rect, 6, 6)
            pixmap = self._icon_cache.pixmap_for(app.name, app.path, app.icon_path)
            if not pixmap.isNull():
                painter.drawPixmap(thumb_rect.adjusted(2, 2, -2, -2), pixmap, pixmap.rect())

        font = QFont("Segoe UI", 10)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        label_rect = QRect(0, icon_box.bottom() + 5, self.width(), 20)
        label = painter.fontMetrics().elidedText(
            self.folder.name,
            Qt.TextElideMode.ElideRight,
            self.width() - 6,
        )
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)

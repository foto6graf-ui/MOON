"""Custom-painted application card."""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QMimeData,
    QPoint,
    QRect,
    QRectF,
    QSize,
    Qt,
    QPropertyAnimation,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QDrag,
    QFont,
    QMouseEvent,
    QPainter,
)
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from models.app_model import ApplicationItem
from utils.app_scanner import launch_application, reveal_in_file_manager, run_as_administrator
from utils.icon_cache import IconCache


class AppCard(QWidget):
    """Animated Launchpad-style application tile."""

    launched = Signal(str)
    pin_requested = Signal(str)
    favorite_requested = Signal(str)
    folder_requested = Signal(str)
    drop_requested = Signal(str, str)

    CARD_SIZE = QSize(76, 92)
    ICON_SIZE = 48

    def __init__(
        self,
        app: ApplicationItem,
        icon_cache: IconCache,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.app = app
        self._icon_cache = icon_cache
        self._visual_scale = 1.0
        self._lift = 0.0
        self._glow = 0.0
        self._content_opacity = 1.0
        self._pressed = False
        self._drag_start: QPoint | None = None
        self._font_size = 11
        self._show_label = True
        self._single_click_launch = False
        self.setFixedSize(self.CARD_SIZE)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent; border: none;")
        self.setAcceptDrops(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(app.name)

    def sizeHint(self) -> QSize:
        return QSize(self.CARD_SIZE)

    def configure(
        self,
        icon_size: int,
        font_size: int,
        show_label: bool,
        single_click_launch: bool,
    ) -> None:
        """Apply visual and launch settings to this card."""
        self.ICON_SIZE = icon_size
        self._font_size = font_size
        self._show_label = show_label
        self._single_click_launch = single_click_launch
        side = max(76, icon_size + 20)
        self.setFixedSize(QSize(side, side + (18 if show_label else 4)))
        self.updateGeometry()
        self.update()

    def visualScale(self) -> float:
        return self._visual_scale

    def setVisualScale(self, value: float) -> None:
        self._visual_scale = value
        self.update()

    visualScale = Property(float, visualScale, setVisualScale)

    def lift(self) -> float:
        return self._lift

    def setLift(self, value: float) -> None:
        self._lift = value
        self.update()

    liftAmount = Property(float, lift, setLift)

    def glow(self) -> float:
        return self._glow

    def setGlow(self, value: float) -> None:
        self._glow = value
        self.update()

    glowAmount = Property(float, glow, setGlow)

    def contentOpacity(self) -> float:
        return self._content_opacity

    def setContentOpacity(self, value: float) -> None:
        self._content_opacity = max(0.0, min(1.0, value))
        self.update()

    contentOpacity = Property(float, contentOpacity, setContentOpacity)

    def enterEvent(self, event: object) -> None:
        self._animate_state(1.04, 0.0, 1.0)
        super().enterEvent(event)

    def leaveEvent(self, event: object) -> None:
        if not self._pressed:
            self._animate_state(1.0, 0.0, 0.0)
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._drag_start = event.position().toPoint()
            self._animate_state(0.97, 0.0, 0.6, 130)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self._drag_start is None:
            super().mouseMoveEvent(event)
            return
        distance = (event.position().toPoint() - self._drag_start).manhattanLength()
        if distance < QApplication.startDragDistance():
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self.app.item_id)
        mime.setData("application/x-launchpad-app", self.app.item_id.encode("utf-8"))
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(event.position().toPoint())
        drag.exec(Qt.DropAction.MoveAction)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._pressed = False
        if self._single_click_launch and event.button() == Qt.MouseButton.LeftButton:
            self.open_application()
        self._animate_state(1.04 if self.underMouse() else 1.0, 0.0, 1.0 if self.underMouse() else 0.0)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_application()
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: object) -> None:
        if hasattr(event, "key") and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.open_application()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event: object) -> None:
        menu = QMenu(self)
        open_action = QAction("Открыть", menu)
        admin_action = QAction("Запустить от администратора", menu)
        properties_action = QAction("Показать в папке", menu)
        pin_action = QAction("Открепить" if self.app.is_pinned else "Закрепить", menu)


        open_action.triggered.connect(self.open_application)
        admin_action.triggered.connect(lambda: run_as_administrator(self.app.launch_target))
        properties_action.triggered.connect(lambda: reveal_in_file_manager(self.app.path))
        pin_action.triggered.connect(lambda: self.pin_requested.emit(self.app.item_id))


        for action in (
            open_action,
            admin_action,
            properties_action,
            pin_action,

        ):
            menu.addAction(action)
        menu.exec(event.globalPos())

    def dragEnterEvent(self, event: object) -> None:
        if event.mimeData().hasFormat("application/x-launchpad-app"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: object) -> None:
        source_id = bytes(event.mimeData().data("application/x-launchpad-app")).decode("utf-8")
        if source_id and source_id != self.app.item_id:
            self.drop_requested.emit(source_id, self.app.item_id)
            event.acceptProposedAction()

    def open_application(self) -> None:
        """Launch the application represented by this card."""
        launch_application(self.app.launch_target, self.app.arguments)
        self.launched.emit(self.app.item_id)

    def _animate_state(
        self,
        scale: float,
        lift: float,
        glow: float,
        duration: int = 250,
    ) -> None:
        for prop, end in (
            (b"visualScale", scale),
            (b"liftAmount", lift),
            (b"glowAmount", glow),
        ):
            animation = QPropertyAnimation(self, prop, self)
            animation.setStartValue(self.property(prop.decode()))
            animation.setEndValue(end)
            animation.setDuration(duration)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self._content_opacity)
        center = QPoint(self.width() // 2, self.height() // 2)
        painter.translate(center)
        painter.scale(self._visual_scale, self._visual_scale)
        painter.translate(-center.x(), -center.y() - self._lift)

        icon_rect = QRect(
            (self.width() - self.ICON_SIZE) // 2,
            4,
            self.ICON_SIZE,
            self.ICON_SIZE,
        )
        painter.setBrush(QColor(255, 255, 255, 18))
        painter.setPen(QColor(255, 255, 255, 24))
        painter.drawRoundedRect(icon_rect.adjusted(2, 2, -2, -2), 16, 16)
        painter.setPen(Qt.PenStyle.NoPen)
        pixmap = self._icon_cache.pixmap_for(self.app.name, self.app.path, self.app.icon_path)
        pixmap_x = icon_rect.x() + (icon_rect.width() - pixmap.width()) // 2
        pixmap_y = icon_rect.y() + (icon_rect.height() - pixmap.height()) // 2
        painter.drawPixmap(pixmap_x, pixmap_y, pixmap)

        if self.app.is_pinned or self.app.is_favorite:
            painter.setBrush(QColor("#4DA3FF") if self.app.is_pinned else QColor("#F5F5F5"))
            painter.drawEllipse(icon_rect.right() - 10, icon_rect.top() - 4, 12, 12)

        if not self._show_label:
            return

        text_rect = QRect(0, icon_rect.bottom() + 2, self.width(), 22)
        font = QFont("Segoe UI", 10)
        font.setPixelSize(self._font_size)
        painter.setFont(font)
        painter.setPen(QColor("#F5F5F5"))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self._elided_text(painter))

    def _elided_text(self, painter: QPainter) -> str:
        metrics = painter.fontMetrics()
        return metrics.elidedText(self.app.name, Qt.TextElideMode.ElideRight, self.width() - 10)

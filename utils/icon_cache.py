"""Icon loading and caching for application cards."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PySide6.QtCore import QFileInfo, QRect, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QFileIconProvider, QStyle

LOGGER = logging.getLogger(__name__)


class IconCache:
    """Load platform icons once and reuse pixmaps across cards."""

    def __init__(self, size: int = 72) -> None:
        self.size = size
        self._provider = QFileIconProvider()
        self._cache: dict[tuple[str, str | None, str | None, int], QPixmap] = {}
        self._loaded_count = 0
        self._cache_hit_count = 0
        self._error_count = 0

    def clear(self) -> None:
        """Clear cached icon pixmaps."""
        self.log_statistics()
        self._cache.clear()
        self._loaded_count = 0
        self._cache_hit_count = 0
        self._error_count = 0

    def log_statistics(self) -> None:
        """Log cache statistics without clearing loaded pixmaps."""
        LOGGER.info(
            "Icon cache statistics: loaded=%d, cache_hits=%d, errors=%d",
            self._loaded_count,
            self._cache_hit_count,
            self._error_count,
        )

    def pixmap_for(self, name: str, path: str | None, icon_path: str | None) -> QPixmap:
        key = (name, path, icon_path, self.size)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache_hit_count += 1
            return cached

        pixmap = self.load_and_normalize_icon(path, icon_path)
        if pixmap.isNull():
            self._error_count += 1
            pixmap = self._standard_application_icon(name)

        self._loaded_count += 1
        if len(self._cache) >= 4096:
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = pixmap
        return pixmap

    def load_and_normalize_icon(
        self,
        path: str | None,
        icon_path: str | None,
    ) -> QPixmap:
        """Extract a large icon, trim empty borders and centre it on a square canvas."""
        icon = self._icon_from_source(path, icon_path)
        if icon.isNull():
            return QPixmap()

        # Avoid asking the shell for oversized icon rasters when cards render
        # at 48–72 px. This reduces first-paint latency for large catalogs.
        requested_side = max(128, self.size * 2)
        source = icon.pixmap(QSize(requested_side, requested_side))
        if source.isNull():
            return QPixmap()

        image = source.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        content_rect = self._opaque_bounds(image)
        if not content_rect.isNull():
            image = image.copy(content_rect)

        inset = max(6, min(10, self.size // 8))
        content_side = max(1, self.size - inset * 2)
        image = image.scaled(
            content_side,
            content_side,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        canvas = QImage(self.size, self.size, QImage.Format.Format_RGBA8888)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.drawImage(
            (self.size - image.width()) // 2,
            (self.size - image.height()) // 2,
            image,
        )
        painter.end()
        return QPixmap.fromImage(canvas)

    def _icon_from_source(self, path: str | None, icon_path: str | None) -> QIcon:
        """Load the icon from the actual application path first."""
        seen: set[str] = set()
        for source in (path, icon_path):
            if not source:
                continue
            normalized_source = source.casefold()
            if normalized_source in seen:
                continue
            seen.add(normalized_source)

            source_path = Path(source)

            if source_path.exists():
                image_icon = self._icon_from_image(source_path)
                if not image_icon.isNull():
                    return image_icon

                icon = self._provider.icon(QFileInfo(str(source_path)))
                if not icon.isNull():
                    return icon

            themed = QIcon.fromTheme(source)
            if not themed.isNull():
                return themed

        return QIcon()

    @staticmethod
    def _opaque_bounds(image: QImage) -> QRect:
        """Return bounds of visible pixels without cropping opaque artwork."""
        width = image.width()
        height = image.height()
        pixels = np.frombuffer(
            image.constBits(),
            dtype=np.uint8,
            count=image.bytesPerLine() * height,
        ).reshape(height, image.bytesPerLine())
        alpha = pixels[:, 3:width * 4:4]
        rows = np.flatnonzero(np.any(alpha > 8, axis=1))
        columns = np.flatnonzero(np.any(alpha > 8, axis=0))
        if rows.size == 0 or columns.size == 0:
            return QRect()
        left = int(columns[0])
        top = int(rows[0])
        return QRect(
            left,
            top,
            int(columns[-1]) - left + 1,
            int(rows[-1]) - top + 1,
        )

    def _standard_application_icon(self, name: str) -> QPixmap:
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        pixmap = icon.pixmap(QSize(max(128, self.size * 2), max(128, self.size * 2)))
        if pixmap.isNull():
            return self._monogram_icon(name)
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        image = image.scaled(
            self.size - 16,
            self.size - 16,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        canvas = QImage(self.size, self.size, QImage.Format.Format_RGBA8888)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.drawImage((self.size - image.width()) // 2, (self.size - image.height()) // 2, image)
        painter.end()
        return QPixmap.fromImage(canvas)

    def _icon_from_image(self, path: Path) -> QIcon:
        if path.suffix.casefold() not in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".ico"}:
            return QIcon()
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return QIcon()
        return QIcon(pixmap)

    def _monogram_icon(self, name: str) -> QPixmap:
        pixmap = QPixmap(self.size, self.size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#4DA3FF"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.size, self.size, 18, 18)
        painter.setPen(QColor("#F5F5F5"))
        font = painter.font()
        font.setPixelSize(30)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, name[:1].upper() or "A")
        painter.end()
        return pixmap

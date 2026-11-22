"""Main Launchpad window and adaptive application grid."""

from __future__ import annotations
import os
import re
from PySide6.QtWidgets import QApplication
import logging
from pathlib import Path

from utils.startup import set_startup_enabled

from PySide6.QtCore import (
    QEasingCurve,
    QElapsedTimer,
    QEvent,
    QObject,
    QPoint,
    QProcess,
    QPropertyAnimation,
    QRect,
    QSize,
    QThread,
    QTimer,
    Qt,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QDesktopServices,
    QGuiApplication,
    QKeySequence,
    QPainter,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QInputDialog,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from animations.animator import Animator
from models.app_model import AppCategory, AppFolder, ApplicationCatalog, ApplicationItem, SortMode
from ui.app_folder_card import AppFolderCard
from ui.app_card import AppCard
from ui.popover_menu import GlassPopoverMenu, MenuNode
from ui.search import SearchBox
from ui.settings_dialog import InterfaceSettingsDialog
from utils.app_scanner import (
    infer_category,
    is_allowed_windows_app,
    resolve_windows_shortcut,
    reveal_in_file_manager,
    windows_uninstall_registered,
)
from utils.backdrop import apply_native_backdrop
from utils.global_hotkey import ModifierHotkeyWatcher
from utils.icon_cache import IconCache
from utils.settings_store import InterfaceSettings, SettingsStore
from utils.theme import ThemeController, ThemeMode
from widgets.blur_widget import GradientBackground
from widgets.liquid_glass import LiquidGlassWidget
from widgets.hover_button import HoverButton

LOGGER = logging.getLogger(__name__)


class ScannerWorker(QObject):
    """Background application scanner."""

    finished = Signal(list)
    failed = Signal()

    def __init__(self, show_system_apps: bool) -> None:
        super().__init__()
        self._show_system_apps = show_system_apps

    @Slot()
    def run(self) -> None:
        """Scan applications and emit the result."""
        from utils.app_scanner import scan_installed_applications

        try:
            apps = scan_installed_applications(show_system_apps=self._show_system_apps)
        except Exception:
            LOGGER.exception("Application scan failed")
            self.failed.emit()
            return
        self.finished.emit(apps)


class AppGrid(QWidget):
    """Adaptive lazy-rendered grid for application cards."""

    app_activated = Signal(str)
    pin_requested = Signal(str)
    favorite_requested = Signal(str)
    folder_drop_requested = Signal(str, str)
    remove_requested = Signal(str)
    folder_open_requested = Signal(str)

    def __init__(self, icon_cache: IconCache, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AppGrid")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent; border:none;")
        self._icon_cache = icon_cache
        self._entries: list[tuple[str, AppFolder | ApplicationItem]] = []
        self._all_apps: list[ApplicationItem] = []
        self._cards: list[AppCard] = []
        self._tiles: list[QWidget] = []
        self._card_cache: dict[str, AppCard] = {}
        self._folder_card_cache: dict[str, AppFolderCard] = {}
        self._columns = 1
        self._next_index = 0
        self._batch_size = 12
        self._icon_size = 48
        self._font_size = 16
        self._show_labels = True
        self._single_click_launch = False
        self._forced_columns = 0
        self._spacing = 2
        self._cell_width = 30
        self._cell_height = 30
        self._timer = QTimer(self)
        self._timer.setInterval(8)
        self._timer.timeout.connect(self._append_batch)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 4, 2, 30)
        self._layout.setHorizontalSpacing(self._spacing)
        self._layout.setVerticalSpacing(self._spacing)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)

    @property
    def cards(self) -> list[AppCard]:
        """Return currently materialized cards."""
        return list(self._cards)

    @property
    def columns(self) -> int:
        """Return the current column count."""
        return self._columns

    def set_apps(
        self,
        apps: list[ApplicationItem],
        folders: list[AppFolder] | None = None,
        *,
        show_folders: bool = True,
    ) -> None:
        """Show folder tiles and loose application cards in the main grid."""
        self._timer.stop()
        self._all_apps = list(apps)
        folder_map = {folder.folder_id: folder for folder in (folders or ())} if show_folders else {}
        visible_ids = {app.item_id for app in apps}
        anchored_ids = {
            folder.folder_id
            for folder in folder_map.values()
            if folder.anchor_app_id in visible_ids
        }
        placed_folders: set[str] = set()
        self._entries = []
        for app in apps:
            folder = folder_map.get(app.folder_id or "")
            if folder is None:
                self._entries.append(("app", app))
                continue
            if folder.folder_id in placed_folders:
                continue
            if folder.folder_id in anchored_ids and app.item_id != folder.anchor_app_id:
                continue
            self._entries.append(("folder", folder))
            placed_folders.add(folder.folder_id)
        self._clear()
        self._update_cell_size()
        self._columns = self._calculate_columns()
        self._next_index = 0
        self._append_batch()

    def configure(
        self,
        *,
        icon_size: int,
        spacing: int,
        forced_columns: int,
        font_size: int,
        show_labels: bool,
        single_click_launch: bool,
    ) -> None:
        """Apply grid and card settings."""
        self._icon_size = icon_size
        self._font_size = font_size
        self._show_labels = show_labels
        self._single_click_launch = single_click_launch
        self._forced_columns = forced_columns
        self._spacing = spacing
        self._layout.setHorizontalSpacing(self._spacing)
        self._layout.setVerticalSpacing(self._spacing)
        self._update_cell_size()
        for card in self._card_cache.values():
            card.configure(icon_size, font_size, show_labels, single_click_launch)
            self._apply_card_cell_size(card)
        for card in self._folder_card_cache.values():
            self._apply_card_cell_size(card)
        self._columns = self._calculate_columns()
        self._relayout()

    def focus_card(self, index: int) -> None:
        """Focus a visible card by index."""
        if not self._cards:
            return
        index = max(0, min(index, len(self._cards) - 1))
        self._cards[index].setFocus()

    def focused_index(self) -> int:
        """Return the focused card index, or zero."""
        focused = self.focusWidget()
        if focused in self._cards:
            return self._cards.index(focused)
        return 0

    def activate_focused(self) -> None:
        """Open the focused card."""
        if self._cards:
            self._cards[self.focused_index()].open_application()

    def resizeEvent(self, event: object) -> None:
        new_columns = self._calculate_columns()
        if new_columns != self._columns:
            self._columns = new_columns
            self._relayout()
        else:
            self._update_grid_height()
        super().resizeEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)

    def _calculate_columns(self) -> int:
        viewport = self.parentWidget()

        available = (
            viewport.width()
            if viewport is not None
            else self.width()
        )

        available = max(1, available - 8)

        columns = max(
            1,
            (available + self._spacing)
            // (self._cell_width + self._spacing)
        )

        if self._forced_columns > 0:
            columns = min(columns, self._forced_columns)

        # Максимум 8 колонок.
        # Если ширины экрана не хватает — автоматически меньше.
        columns = min(columns, 8)

        return columns

    def _append_batch(self) -> None:
        elapsed = QElapsedTimer()
        elapsed.start()
        processed = 0
        while self._next_index < len(self._entries) and processed < self._batch_size:
            index = self._next_index
            kind, entry = self._entries[index]
            if isinstance(entry, AppFolder):
                self._add_folder_card(entry)
            else:
                self._add_card(entry, index)
            self._next_index += 1
            processed += 1
            # Yield to input, paint and backdrop events on busy machines.
            if elapsed.elapsed() >= 6:
                break
        self._update_grid_height()
        if self._next_index < len(self._entries):
            self._timer.start()
        else:
            self._timer.stop()

    def _add_card(self, app: ApplicationItem, index: int) -> None:
        card = self._card_cache.get(app.item_id)
        if card is None:
            card = AppCard(app, self._icon_cache, self)
            card.launched.connect(self.app_activated)
            card.pin_requested.connect(self.pin_requested)
            card.favorite_requested.connect(self.favorite_requested)
            card.drop_requested.connect(self.folder_drop_requested)
            card.remove_requested.connect(self.remove_requested)
            self._card_cache[app.item_id] = card
        else:
            card.app = app
            card.show()
        card.configure(
            self._icon_size,
            self._font_size,
            self._show_labels,
            self._single_click_launch,
        )
        self._apply_card_cell_size(card)
        row, column = divmod(len(self._tiles), self._columns)
        self._layout.addWidget(card, row, column, Qt.AlignmentFlag.AlignCenter)
        self._cards.append(card)
        self._tiles.append(card)

    def _add_folder_card(self, folder: AppFolder) -> None:
        members = [app for app in self.catalog_applications if app.folder_id == folder.folder_id]
        card = self._folder_card_cache.get(folder.folder_id)
        if card is None:
            card = AppFolderCard(folder, members, self._icon_cache, self)
            card.open_requested.connect(self.folder_open_requested)
            card.app_dropped.connect(self.folder_drop_requested)
            self._folder_card_cache[folder.folder_id] = card
        else:
            card.update_content(folder, members)
            card.show()
        self._apply_card_cell_size(card)
        row, column = divmod(len(self._tiles), self._columns)
        self._layout.addWidget(card, row, column, Qt.AlignmentFlag.AlignCenter)
        self._tiles.append(card)

    @property
    def catalog_applications(self) -> list[ApplicationItem]:
        """Applications currently represented by this grid's catalog snapshot."""
        return self._all_apps

    def _relayout(self) -> None:
        for tile in self._tiles:
            self._layout.removeWidget(tile)
        for index, tile in enumerate(self._tiles):
            row, column = divmod(index, self._columns)
            self._layout.addWidget(tile, row, column, Qt.AlignmentFlag.AlignCenter)
        self._update_grid_height()

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
        self._cards.clear()
        self._tiles.clear()
        self._update_grid_height()

    def _update_cell_size(self) -> None:
        label_height = max(20, self._font_size + 6) if self._show_labels else 6

        # ↔️ компактность по горизонтали
        self._cell_width = max(70, self._icon_size + 20)

        # ↕️ компактность по вертикали
        self._cell_height = max(
            76,
            self._icon_size + label_height + 10,
        )

    def _apply_card_cell_size(self, card: QWidget) -> None:
        height = max(self._cell_height, 96) if isinstance(card, AppFolderCard) else self._cell_height
        card.setFixedSize(QSize(self._cell_width, height))

    def _update_grid_height(self) -> None:
        margins = self._layout.contentsMargins()
        height = margins.top() + margins.bottom()
        if self._tiles:
            columns = max(1, self._columns)
            row_heights = [
                max(tile.height() for tile in self._tiles[start : start + columns])
                for start in range(0, len(self._tiles), columns)
            ]
            height += sum(row_heights) + max(0, len(row_heights) - 1) * self._spacing
        if self.minimumHeight() != height:
            self.setMinimumHeight(height)
            self.updateGeometry()


class SearchResultsList(QListWidget):
    """Application-only search results shown while the user types."""

    app_activated = Signal(str)

    def __init__(self, icon_cache: IconCache, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_cache = icon_cache
        self.setObjectName("SearchResultsList")
        self.setAlternatingRowColors(False)
        self.setMouseTracking(True)
        self.setIconSize(QSize(38, 38))
        self.setSpacing(8)
        self.itemActivated.connect(self._emit_activated)
        self.itemDoubleClicked.connect(self._emit_activated)

    def set_results(self, apps: list[ApplicationItem]) -> None:
        """Refresh rows with application names and icons only."""
        self.clear()
        for app in apps[:500]:
            item = QListWidgetItem()
            item.setText(app.name)
            item.setData(Qt.ItemDataRole.UserRole, app.item_id)
            item.setSizeHint(QSize(100, 54))
            item.setIcon(
                self._icon_cache.pixmap_for(
                    app.name,
                    app.path,
                    app.icon_path,
                )
            )
            self.addItem(item)
        if not apps:
            item = QListWidgetItem("Приложения не найдены")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.addItem(item)
        if self.count():
            self.setCurrentRow(0)

    def activate_current(self) -> None:
        """Activate the selected result."""
        item = self.currentItem()
        if item is not None:
            self._emit_activated(item)

    def navigate(self, dx: int, dy: int) -> None:
        """Navigate rows with keyboard arrows."""
        if not self.count():
            return
        delta = dy if dy else dx
        next_row = max(0, min(self.count() - 1, self.currentRow() + delta))
        self.setCurrentRow(next_row)

    def _emit_activated(self, item: QListWidgetItem) -> None:
        app_id = item.data(Qt.ItemDataRole.UserRole)
        if app_id:
            self.app_activated.emit(str(app_id))


class LaunchpadWindow(QMainWindow):
    """Top-level glass Launchpad application."""

    logout_requested = Signal()

    def __init__(self, catalog: ApplicationCatalog, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.icon_cache = IconCache()
        self.theme = ThemeController()
        self.settings_store = SettingsStore()
        self.settings = self.settings_store.load()
        self._category: AppCategory | None = None
        self._custom_section: str | None = None
        self._uninstall_processes: dict[str, QProcess] = {}
        self._scanner_thread: QThread | None = None
        self._scanner_worker: ScannerWorker | None = None
        self._active_animations: list[object] = []
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(45)
        self._refresh_timer.timeout.connect(self._refresh_grid)
        self._focus_check_timer = QTimer(self)
        self._focus_check_timer.setSingleShot(True)
        self._focus_check_timer.setInterval(120)
        self._focus_check_timer.timeout.connect(self._hide_if_focus_left)
        self._focus_check_attempts = 0
        self._intro_played = False
        self._popover: GlassPopoverMenu | None = None
        self._sort_popover: GlassPopoverMenu | None = None
        self._settings_dialog: InterfaceSettingsDialog | None = None
        self._about_dialog: QMessageBox | None = None
        self._folder_dialog: QDialog | None = None
        self._promoted_app_id: str | None = None
        self._global_hotkey = ModifierHotkeyWatcher(self)
        self._global_hotkey.activated.connect(self.toggle_visibility)
        application = QApplication.instance()
        application.installEventFilter(self)
        application.applicationStateChanged.connect(self._application_state_changed)

        self.setWindowTitle("Приложения")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMinimumSize(620, 440)
        self._preferred_minimum_size = QSize(620, 440)
        self._preferred_menu_size = QSize(860, 600)
        self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

        root = QWidget(self)
        root.setObjectName("Root")
        self.setCentralWidget(root)
        root.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        root.setAutoFillBackground(False)

        root.setStyleSheet(
            "QWidget#Root { background: transparent; }"
        )
        self.background = GradientBackground(root)
        self.background.lower()

        self.panel = LiquidGlassWidget(
            root,
            radius=28,
            opacity=18,
            border_opacity=100,
        )
        self.panel.setObjectName("LaunchpadPanel")
        self._build_panel()
        self._build_shortcuts()
        self._connect_model()
        self._apply_loaded_settings()
        self._global_hotkey.start()

        QTimer.singleShot(0, self._start_scanner)
        QTimer.singleShot(80, self._play_intro)

    def resizeEvent(self, event: object) -> None:
        self._update_panel_geometry()
        super().resizeEvent(event)

    def showEvent(self, event: object) -> None:

        super().showEvent(event)

        self._update_panel_geometry()





    def closeEvent(self, event: object) -> None:
        self._global_hotkey.stop()
        self.icon_cache.log_statistics()
        try:
            scanner_running = (
                self._scanner_thread is not None
                and self._scanner_thread.isRunning()
            )
        except RuntimeError:
            scanner_running = False
            self._scanner_thread = None
            self._scanner_worker = None

        if scanner_running and self._scanner_thread is not None:
            self._scanner_thread.quit()
            self._scanner_thread.wait(1500)
        super().closeEvent(event)

    def _update_panel_geometry(self) -> None:
        """Update background and panel geometry for the current window size."""
        self.background.setGeometry(self.centralWidget().rect())
        margin_x = max(18, int(self.width() * 0.045))
        margin_y = max(18, int(self.height() * 0.045))
        self.panel.setGeometry(
            QRect(
                margin_x,
                margin_y,
                self.width() - margin_x * 2,
                self.height() - margin_y * 2,
            )
        )

    def _build_panel(self) -> None:
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(24, 20, 24, 20)
        panel_layout.setSpacing(12)

        header = QHBoxLayout()
        icon = QLabel(self.panel)
        star_path = Path(__file__).resolve().parent.parent / "assets" / "launchpad_star.png"
        star = QPixmap(str(star_path))
        if not star.isNull():
            icon.setPixmap(
                star.scaled(
                    36,
                    36,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            icon.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton).pixmap(32, 32))
        title = QLabel("Приложения", self.panel)
        title.setObjectName("TitleLabel")
        self.menu_button = HoverButton("", self.panel, circular=True, glass=True, icon_name="more")
        self.menu_button.setCheckable(False)
        self.menu_button.setToolTip("Меню")
        self.menu_button.setAccessibleName("Меню MOON")
        self.menu_button.clicked.connect(self._show_theme_menu)
        header.addWidget(icon)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.menu_button)
        panel_layout.addLayout(header)

        self.search = SearchBox(self.panel)
        self.search.textChanged.connect(self._schedule_refresh)
        self.search.navigate.connect(self._navigate_grid)
        self.search.accept_current.connect(self.grid_activate_current)
        panel_layout.addWidget(self.search)

        self._build_sections_row(panel_layout)

        # ===== Область приложений =====
        scroll = QScrollArea(self.panel)
        scroll.setObjectName("AppScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        scroll.viewport().setObjectName("AppScrollViewport")
        scroll.viewport().setAutoFillBackground(False)
        scroll.viewport().setStyleSheet(
            "background: transparent; border:none;"
        )

        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }

            QScrollBar:vertical {
                width: 10px;
                margin: 4px 2px;
                border-radius: 5px;
                background: rgba(255, 255, 255, 10);
            }

            QScrollBar::handle:vertical {
                min-height: 36px;
                border: 1px solid rgba(255, 255, 255, 32);
                border-radius: 4px;
                background: rgba(190, 184, 255, 115);
            }

            QScrollBar::handle:vertical:hover { background: rgba(205, 200, 255, 180); }
            QScrollBar::handle:vertical:pressed { background: rgba(224, 220, 255, 220); }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QScrollArea > QWidget > QWidget {
                background: transparent;
                border: none;
            }

            QWidget {
                background: transparent;
                border: none;
            }
        """)

        self.grid = AppGrid(self.icon_cache, scroll)
        self.grid.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.grid.setAutoFillBackground(False)
        self.grid.setStyleSheet("background: transparent; border:none;")

        self.grid.app_activated.connect(self.catalog.mark_opened)
        self.grid.pin_requested.connect(self._toggle_pin_for_app)
        self.grid.favorite_requested.connect(self._toggle_favorite_for_app)
        self.grid.remove_requested.connect(self._remove_app_from_moon)
        self.grid.folder_drop_requested.connect(self._create_folder_from_drop)
        self.grid.folder_open_requested.connect(self._open_folder)

        scroll.setWidget(self.grid)

        panel_layout.addWidget(scroll, 1)
        self.grid_scroll = scroll

        self.search_results = SearchResultsList(self.icon_cache, self.panel)
        self.search_results.app_activated.connect(self._open_by_id)
        self.search_results.hide()
        panel_layout.addWidget(self.search_results, stretch=1)

    def _build_sections_row(self, panel_layout: QVBoxLayout) -> None:
        section_row = QHBoxLayout()
        section_row.setSpacing(10)
        self.category_group = QButtonGroup(self)
        self.category_group.setExclusive(True)

        all_button = HoverButton("Все", self.panel)
        all_button.setChecked(True)
        self.category_group.addButton(all_button, -1)
        section_row.addWidget(all_button)

        for index, category in enumerate(AppCategory):

            if category in (
                    AppCategory.PRODUCTIVITY,
                    AppCategory.CREATIVITY,
                    AppCategory.ENTERTAINMENT,
            ):
                continue

            button = HoverButton(category.value, self.panel)
            self.category_group.addButton(button, index)
            section_row.addWidget(button)

        for index, section in enumerate(self.settings.custom_sections):
            self._add_section_button(section_row, section, 1000 + index)

        section_row.addItem(QSpacerItem(10, 10, QSizePolicy.Policy.Expanding))

        self.sort_button = HoverButton("", self.panel, circular=True, glass=True, icon_name="sort")
        self.sort_button.setAccessibleName("Сортировка приложений")
        self.sort_button.setToolTip("Сортировка")
        self.sort_button.setCheckable(False)
        self.sort_button.clicked.connect(self._show_sort_menu)
        section_row.addWidget(self.sort_button)

        self.category_group.idClicked.connect(self._set_category)
        panel_layout.addLayout(section_row)
        self.section_row = section_row


    def _add_section_button(self, section_row: QHBoxLayout, section: str, button_id: int) -> None:
        button = HoverButton(section, self.panel)
        self.category_group.addButton(button, button_id)
        section_row.addWidget(button)

    def _build_shortcuts(self) -> None:
        QShortcut(QKeySequence.StandardKey.Find, self, activated=self.search.setFocus)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self._escape)
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, activated=self.grid_activate_current)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self, activated=self.grid_activate_current)

    def _connect_model(self) -> None:
        self.catalog.applications_changed.connect(self._refresh_grid)
        self.theme.theme_changed.connect(self._apply_theme)

    def _start_scanner(self) -> None:
        if self._scanner_thread is not None:
            try:
                if self._scanner_thread.isRunning():
                    return
            except RuntimeError:
                self._scanner_thread = None
        self._scanner_thread = QThread(self)
        self._scanner_worker = ScannerWorker(self.settings.show_system_apps)
        self._scanner_worker.moveToThread(self._scanner_thread)
        self._scanner_thread.started.connect(self._scanner_worker.run)
        self._scanner_worker.finished.connect(self._scanner_finished)
        self._scanner_worker.failed.connect(self._scanner_failed)
        self._scanner_worker.finished.connect(self._scanner_thread.quit)
        self._scanner_worker.failed.connect(self._scanner_thread.quit)
        self._scanner_worker.finished.connect(self._scanner_worker.deleteLater)
        self._scanner_worker.failed.connect(self._scanner_worker.deleteLater)
        self._scanner_thread.finished.connect(self._clear_scanner_refs)
        self._scanner_thread.finished.connect(self._scanner_thread.deleteLater)
        self._scanner_thread.start()

    @Slot()
    def _clear_scanner_refs(self) -> None:
        """Drop Python references after Qt has finished the scanner thread."""
        self._scanner_thread = None
        self._scanner_worker = None

    @Slot()
    def _scanner_failed(self) -> None:
        """Keep the current catalog intact if a background refresh fails."""
        LOGGER.warning("Keeping existing application catalog after scan failure")

    @Slot(list)
    def _scanner_finished(self, apps: list[ApplicationItem]) -> None:
        """Apply scanned applications together with user-added shortcuts."""
        known_apps = [*apps, *self._custom_app_items()]
        hidden_paths = {self._storage_key(path) for path in self.settings.hidden_app_paths}
        known_apps = [app for app in known_apps if self._storage_key(app.path) not in hidden_paths]
        self.catalog.set_applications(
            known_apps,
            show_system_apps=self.settings.show_system_apps,
        )
        by_path = {self._storage_key(app.path): app.item_id for app in self.catalog.applications}
        for saved_folder in self.settings.app_folders:
            member_ids = [
                by_path[self._storage_key(path)]
                for path in saved_folder.get("apps", [])
                if isinstance(path, str) and self._storage_key(path) in by_path
            ]
            if len(member_ids) >= 2:
                anchor_path = saved_folder.get("anchor")
                anchor_id = by_path.get(self._storage_key(anchor_path)) if isinstance(anchor_path, str) else None
                self.catalog.create_folder(
                    str(saved_folder["name"]),
                    member_ids,
                    anchor_app_id=anchor_id,
                )
        LOGGER.info("Application catalog updated: displayed=%d", len(self.catalog.applications))

    def _play_intro(self) -> None:
        self.panel.setPanelOpacity(0.0)
        QTimer.singleShot(
            30,
            self._start_intro_animation,
        )
        self._intro_played = True

    def _start_intro_animation(self) -> None:
        animation = Animator.entrance_sequence(self.panel, self.grid.cards[:48])
        self.panel.pause_backdrop()
        animation.finished.connect(
            lambda: QTimer.singleShot(150, self._resume_backdrop_if_menus_closed)
        )
        self._run_animation(animation)

    @Slot()
    def _schedule_refresh(self) -> None:
        self._refresh_timer.start()

    @Slot()
    def _refresh_grid(self) -> None:
        query = self.search.text().strip()
        apps = self.catalog.filtered(
            query,
            None if query else self._category,
            favorites_only=self.settings.favorites_only and not query,
        )
        if self._custom_section and not query:
            section = self._custom_section.casefold()
            apps = [
                app
                for app in apps
                if section in app.name.casefold()
                or section in app.path.casefold()
                or section in app.category.value.casefold()
            ]
        if self.settings.folders_only and not query:
            apps = [app for app in apps if app.folder_id is not None]
        if self._promoted_app_id:
            promoted_id = self._promoted_app_id
            promoted = [app for app in apps if app.item_id == promoted_id]
            if promoted:
                apps = [*promoted, *(app for app in apps if app.item_id != promoted_id)]
        if query:
            self.grid_scroll.hide()
            self.search_results.show()
            self.search_results.set_results(apps)
            return

        self.search_results.hide()
        self.grid_scroll.show()
        visible_folder_ids = {app.folder_id for app in apps if app.folder_id}
        visible_folders = [
            folder for folder in self.catalog.folders
            if folder.folder_id in visible_folder_ids
        ]
        self.grid.set_apps(
            apps,
            visible_folders,
            show_folders=not self.settings.folders_only,
        )
        LOGGER.info("Application grid updated: apps=%d, columns=%d", len(apps), self.grid.columns)
        if self._promoted_app_id and apps and apps[0].item_id == self._promoted_app_id:
            QTimer.singleShot(0, self._focus_promoted_app)

    def _run_animation(self, animation: object) -> None:
        if hasattr(animation, "finished"):
            self._active_animations.append(animation)
            animation.finished.connect(lambda: self._active_animations.remove(animation))
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    @Slot(int)
    def _set_category(self, index: int) -> None:
        self._category = None
        self._custom_section = None
        if 0 <= index < len(AppCategory):
            self._category = list(AppCategory)[index]
        elif index >= 1000:
            custom_index = index - 1000
            if custom_index < len(self.settings.custom_sections):
                self._custom_section = self.settings.custom_sections[custom_index]
        self._schedule_refresh()

    def _navigate_grid(self, dx: int, dy: int) -> None:
        if self.search.text().strip():
            self.search_results.navigate(dx, dy)
            return
        index = self.grid.focused_index()
        next_index = index + dx + dy * max(1, self.grid.columns)
        self.grid.focus_card(next_index)

    def grid_activate_current(self) -> None:
        """Activate the current focused card."""
        if self.search.text().strip():
            self.search_results.activate_current()
            return
        self.grid.activate_focused()

    def _open_by_id(self, app_id: str) -> None:
        app = self.catalog.find(app_id)
        if app is None:
            return
        from utils.app_scanner import launch_application

        launch_application(app.launch_target, app.arguments)
        self.catalog.mark_opened(app_id)

    @Slot()
    def toggle_visibility(self) -> None:
        """Show or hide the Launchpad from the global Win+Alt hotkey."""
        if self.isVisible():
            self.hide()
            return

        self.show_centered()

    @Slot(Qt.ApplicationState)
    def _application_state_changed(self, state: Qt.ApplicationState) -> None:
        if state != Qt.ApplicationState.ApplicationInactive or not self.isVisible():
            return
        self._schedule_focus_check()

    def _schedule_focus_check(self) -> None:
        """Check focus after Qt has finished transferring it between owned windows."""
        if not self._focus_check_timer.isActive():
            self._focus_check_attempts = 0
        self._focus_check_timer.start()

    def _hide_if_focus_left(self) -> None:
        if not self.isVisible():
            return
        if self._about_dialog is not None and self._about_dialog.isVisible():
            return
        if self._settings_dialog is not None and self._settings_dialog.isVisible():
            return
        modal = QApplication.activeModalWidget()
        if modal is not None and self.isAncestorOf(modal):
            return
        active_window = QApplication.activeWindow()
        if active_window is None:
            # Qt can briefly report no active window while a dialog closes or
            # focus moves between native windows. Confirm the loss is stable.
            self._focus_check_attempts += 1
            if self._focus_check_attempts < 4:
                self._focus_check_timer.start()
                return
        owned_windows = (
            self,
            self._popover,
            self._sort_popover,
            self._settings_dialog,
            self._about_dialog,
            self._folder_dialog,
        )
        focus_is_owned = active_window is not None and any(
            window is not None
            and (active_window is window or window.isAncestorOf(active_window))
            for window in owned_windows
        )
        if focus_is_owned:
            self._focus_check_attempts = 0
            return
        if self._folder_dialog is not None and self._folder_dialog.isVisible():
            self._folder_dialog.close()
        self.hide()

    def show_centered(self) -> None:
        """Show the menu centred in the work area of the current screen."""
        self._focus_check_timer.stop()
        self._focus_check_attempts = 0
        self._center_on_current_screen()
        self.show()
        self.raise_()
        self.activateWindow()
        self._update_panel_geometry()
        apply_native_backdrop(int(self.winId()))

    def _center_on_current_screen(self) -> None:
        """Position the menu on the cursor's screen, with safe fallbacks."""
        screen = QGuiApplication.screenAt(QCursor.pos())
        if screen is None:
            active_window = QApplication.activeWindow()
            active_handle = active_window.windowHandle() if active_window else None
            screen = active_handle.screen() if active_handle else None
        if screen is None:
            focus_window = QGuiApplication.focusWindow()
            screen = focus_window.screen() if focus_window else None
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        maximum_size = QSize(
            max(1, int(available.width() * 0.72)),
            max(1, int(available.height() * 0.72)),
        )
        minimum_size = self._preferred_minimum_size.boundedTo(maximum_size)
        window_size = self._preferred_menu_size.boundedTo(maximum_size)
        window_size = window_size.expandedTo(minimum_size).boundedTo(maximum_size)

        self.setMaximumSize(maximum_size)
        self.setMinimumSize(minimum_size)
        self.resize(window_size)

        x = available.x() + (available.width() - window_size.width()) // 2
        y = available.y() + (available.height() - window_size.height()) // 2
        x = max(available.left(), min(x, available.right() - window_size.width() + 1))
        y = max(available.top(), min(y, available.bottom() - window_size.height() + 1))
        self.move(x, y)
        LOGGER.info(
            "Launchpad placement: screen=%s, available=%s,%s %sx%s, size=%sx%s, position=%s,%s",
            screen.name(),
            available.x(),
            available.y(),
            available.width(),
            available.height(),
            window_size.width(),
            window_size.height(),
            x,
            y,
        )

    def _escape(self) -> None:
        if self.search.text():
            self.search.clear()
            return
        self.search.clearFocus()

    def _show_theme_menu(self) -> None:
        if self._popover and self._popover.isVisible():
            self._popover.close()
            return
        if self._sort_popover and self._sort_popover.isVisible():
            self._sort_popover.close()
        # The popup is a separate native window. Keep the screen capture frozen
        # while it is visible so it cannot be sampled back into the glass panel.
        self.panel.pause_backdrop()
        self._popover = GlassPopoverMenu(
            self._menu_nodes(), self,
            title="MOON",
            subtitle="Быстрые действия",
        )
        self._popover.closed.connect(self._theme_menu_closed)
        point = self.menu_button.mapToGlobal(
            QPoint(self.menu_button.width() - self._popover.width(), self.menu_button.height() + 8)
        )
        self._popover.popup_at(point)
        LOGGER.info("Settings menu opened")

    def _show_sort_menu(self) -> None:
        if self._sort_popover and self._sort_popover.isVisible():
            self._sort_popover.close()
            return
        if self._popover and self._popover.isVisible():
            self._popover.close()
        # Qt.Popup is a separate top-level window and is included in desktop
        # captures unless the glass backdrop is paused first.
        self.panel.pause_backdrop()
        self._sort_popover = GlassPopoverMenu(
            self._sort_menu_nodes(), self,
            title="СОРТИРОВКА",
            subtitle="Порядок отображения приложений",
        )
        self._sort_popover.closed.connect(self._sort_menu_closed)
        point = self.sort_button.mapToGlobal(
            QPoint(self.sort_button.width() - self._sort_popover.width(), self.sort_button.height() + 8)
        )
        self._sort_popover.popup_at(point)
        LOGGER.info("Sort menu opened")

    def _theme_menu_closed(self) -> None:
        self._popover = None
        QTimer.singleShot(120, self._resume_backdrop_if_menus_closed)
        LOGGER.info("Settings menu closed")

    def _sort_menu_closed(self) -> None:
        self._sort_popover = None
        QTimer.singleShot(120, self._resume_backdrop_if_menus_closed)
        LOGGER.info("Sort menu closed")

    def _resume_backdrop_if_menus_closed(self) -> None:
        theme_open = self._popover is not None and self._popover.isVisible()
        sort_open = self._sort_popover is not None and self._sort_popover.isVisible()
        settings_open = self._settings_dialog is not None and self._settings_dialog.isVisible()
        about_open = self._about_dialog is not None and self._about_dialog.isVisible()
        folder_open = self._folder_dialog is not None and self._folder_dialog.isVisible()
        if not theme_open and not sort_open and not settings_open and not about_open and not folder_open:
            self.panel.resume_backdrop()

    def _action(self, text: str, callback: object) -> QAction:
        action = QAction(text, self)
        action.triggered.connect(callback)
        return action

    def _menu_nodes(self) -> list[MenuNode]:
        return [
            MenuNode(
                "search",
                "Показывать поиск",
                self._action("search", self._toggle_search),
                checkable=True,
                checked=self.settings.show_search,
                detail="Показать или скрыть строку поиска",
            ),
            MenuNode(
                "settings",
                "Настройки",
                self._action("settings", self._open_settings),
                detail="Внешний вид и поведение MOON",
            ),
            MenuNode(
                "about",
                "О MOON",
                self._action("about", self._about),
                detail="Информация о приложении",
            ),
            MenuNode(
                "exit",
                "Выйти из MOON",
                self._action("exit", self.close),
                detail="Закрыть окно MOON",
            ),
        ]

    def _sort_menu_nodes(self) -> list[MenuNode]:
        return [
            MenuNode(
                "sort_name",
                "Название · А–Я",
                self._action("sort_name", lambda: self._set_sort(SortMode.NAME)),
                checkable=True,
                checked=self.settings.sort_mode == SortMode.NAME.value,
                detail="По алфавиту",
            ),
            MenuNode(
                "clock",
                "Часто используемые",
                self._action("sort_used", lambda: self._set_sort(SortMode.MOST_USED)),
                checkable=True,
                checked=self.settings.sort_mode == SortMode.MOST_USED.value,
                detail="Сначала запускаемые чаще",
            ),
            MenuNode(
                "pin",
                "Закреплённые сверху",
                self._action("pin_first", self._toggle_pin_favorites_first),
                checkable=True,
                checked=self.settings.pin_favorites_first,
                detail="Избранное в начале списка",
            ),
        ]

    def _add_custom_section(self) -> None:
        name, accepted = QInputDialog.getText(self, "Новый раздел", "Название раздела:")
        section = name.strip()
        if not accepted or not section:
            return
        if any(existing.casefold() == section.casefold() for existing in self.settings.custom_sections):
            return

        self.settings.custom_sections.append(section)
        button_id = 1000 + len(self.settings.custom_sections) - 1
        button = HoverButton(section, self.panel)
        self.category_group.addButton(button, button_id)
        insert_at = self.section_row.indexOf(self._add_section_button_ref)
        self.section_row.insertWidget(insert_at, button)
        self._save_settings()

    def _sort_changed(self, index: int) -> None:
        return

    def _custom_app_items(self) -> list[ApplicationItem]:
        items: list[ApplicationItem] = []
        for entry in self.settings.custom_apps:
            path = entry.get("path", "")
            if not path:
                continue
            app_path = Path(path)
            name = entry.get("name") or app_path.stem
            executable = entry.get("executable") or path
            if app_path.suffix.casefold() == ".lnk":
                executable = resolve_windows_shortcut(app_path)
            if not is_allowed_windows_app(name, executable, require_exe=True):
                continue
            items.append(
                ApplicationItem(
                    name=name,
                    path=path,
                    executable=executable,
                    icon_path=entry.get("icon_path") or executable,
                    category=infer_category(name, executable),
                    visible_by_default=True,
                )
            )
        return items

    def _add_custom_app(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Добавить ярлык",
            "",
            "Приложения и ярлыки (*.exe *.lnk);;Все файлы (*.*)",
        )
        if not file_path:
            return

        path = str(Path(file_path))
        app_path = Path(path)
        name = app_path.stem
        executable = resolve_windows_shortcut(app_path) if app_path.suffix.casefold() == ".lnk" else path
        if not is_allowed_windows_app(name, executable, require_exe=True):
            QMessageBox.warning(
                self,
                "Ярлык не добавлен",
                "Можно добавлять только ярлыки и приложения, которые запускают .exe и не являются служебными файлами.",
            )
            return
        entry = {
            "name": name,
            "path": path,
            "executable": executable,
            "icon_path": executable,
        }
        if not any(app.get("path", "").casefold() == path.casefold() for app in self.settings.custom_apps):
            self.settings.custom_apps.append(entry)
            hidden_key = self._storage_key(path)
            self.settings.hidden_app_paths = [
                item for item in self.settings.hidden_app_paths
                if self._storage_key(item) != hidden_key
            ]
            self._save_settings()
        self.catalog.add_application(
            ApplicationItem(
                name=name,
                path=path,
                executable=executable,
                icon_path=executable,
                category=infer_category(name, executable),
                visible_by_default=True,
            )
        )

    def _save_settings(self) -> None:
        app_paths = {app.item_id: self._storage_key(app.path) for app in self.catalog.applications}
        self.settings.app_folders = [
            {
                "name": folder.name,
                "apps": [app_paths[app_id] for app_id in folder.app_ids if app_id in app_paths],
                "anchor": app_paths.get(folder.anchor_app_id),
            }
            for folder in self.catalog.folders
            if sum(app_id in app_paths for app_id in folder.app_ids) >= 2
        ]
        try:
            self.settings_store.save(self.settings)
        except OSError as error:
            LOGGER.exception("Could not save settings")
            QMessageBox.warning(
                self,
                "Не удалось сохранить настройки",
                f"Параметры применены до закрытия MOON, но не записались в файл настроек: {error}",
            )

    def _apply_loaded_settings(self) -> None:
        try:
            sort_mode = SortMode(self.settings.sort_mode)
        except ValueError:
            sort_mode = SortMode.NAME
        self.settings.sort_mode = sort_mode.value
        self.catalog.set_pin_favorites_first(self.settings.pin_favorites_first)
        self.catalog.set_sort_mode(sort_mode)
        self.search.setVisible(self.settings.show_search)
        self.panel.set_panel_alpha(self.settings.panel_opacity)
        self.panel.set_matte_effect(self.settings.matte_effect)
        self.panel.set_glass_thickness(self.settings.glass_thickness)
        self.panel.set_glass_color(self.settings.glass_color)
        try:
            theme_mode = ThemeMode(self.settings.theme)
        except ValueError:
            theme_mode = ThemeMode.DARK
        self._set_theme(theme_mode, save=False)
        if self.settings.background_mode in {"blur", "gradient"}:
            self._apply_background(self.settings.background_mode)
        self._apply_grid_settings()

    def _apply_grid_settings(self) -> None:
        self.grid.configure(
            icon_size=self._icon_pixels(self.settings.icon_size),
            spacing=self.settings.card_spacing,
            forced_columns=self.settings.forced_columns,
            font_size=self.settings.font_size,
            show_labels=self.settings.show_labels,
            single_click_launch=self.settings.single_click_launch,
        )
        self._schedule_refresh()

    def _icon_pixels(self, size: str) -> int:
        return {
            "small": 64,
            "medium": 72,
            "large": 88,
            "extra_large": 96,
        }.get(size, 72)

    def _set_icon_size(self, size: str) -> None:
        self.settings.icon_size = size
        self.icon_cache.size = self._icon_pixels(size)
        self.icon_cache.clear()
        self._apply_grid_settings()
        self._save_settings()

    def _set_sort(self, mode: SortMode) -> None:
        self.settings.sort_mode = mode.value
        self.catalog.set_sort_mode(mode)
        self._save_settings()

    def _set_grid_density(self, density: str) -> None:
        self.settings.card_spacing = {
            "compact": 10,
            "normal": 18,
            "spacious": 24,
        }.get(density, 18)
        self._apply_grid_settings()
        self._save_settings()

    def _toggle_system_apps(self) -> None:
        self.settings.show_system_apps = not self.settings.show_system_apps
        self._save_settings()
        self._start_scanner()

    def _open_settings_location(self) -> None:
        reveal_in_file_manager(str(self.settings_store.path))

    def _set_theme(self, mode: ThemeMode, *, save: bool = True) -> None:
        self.settings.theme = mode.value
        self.theme.set_mode(mode)
        self._apply_theme()
        if save:
            self._save_settings()

    def _set_background(self, mode: str) -> None:
        if mode not in {"gradient", "blur"}:
            return
        self.settings.background_mode = mode
        self._apply_background(mode)
        self._save_settings()

    def _apply_background(self, mode: str) -> None:
        if mode == "gradient":
            self.background.setOverlayOpacity(0.08)
        elif mode == "blur":
            self.background.setOverlayOpacity(0.0)

    def _cycle_panel_opacity(self) -> None:
        values = [8, 16, 24, 32, 40]
        current = self.settings.panel_opacity
        self.settings.panel_opacity = values[(values.index(current) + 1) % len(values)] if current in values else 20
        self.panel.set_panel_alpha(self.settings.panel_opacity)
        self._save_settings()

    def _toggle_favorites(self) -> None:
        self.settings.favorites_only = not self.settings.favorites_only
        self._schedule_refresh()
        self._save_settings()

    def _toggle_folders(self) -> None:
        self.settings.folders_only = not self.settings.folders_only
        self._schedule_refresh()
        self._save_settings()

    def _toggle_search(self) -> None:
        self.settings.show_search = not self.settings.show_search
        self.search.setVisible(self.settings.show_search)
        self._save_settings()

    def _toggle_pin_favorites_first(self) -> None:
        self.settings.pin_favorites_first = not self.settings.pin_favorites_first
        self.catalog.set_pin_favorites_first(self.settings.pin_favorites_first)
        self._save_settings()

    def _toggle_pin_for_app(self, app_id: str) -> None:
        self._promoted_app_id = app_id
        self.catalog.toggle_pin(app_id)

    def _toggle_favorite_for_app(self, app_id: str) -> None:
        self._promoted_app_id = app_id
        self.catalog.toggle_favorite(app_id)

    def _focus_promoted_app(self) -> None:
        self.grid_scroll.verticalScrollBar().setValue(0)
        self.grid.focus_card(0)

    def _clear_cache(self) -> None:
        self.icon_cache.clear()
        self.grid._card_cache.clear()
        self._refresh_grid()

    def _reset_layout(self) -> None:
        self.settings.icon_size = "medium"
        self.settings.forced_columns = 0
        self.settings.card_spacing = 18
        self.settings.font_size = 13
        self.settings.show_labels = True
        self.settings.single_click_launch = False
        self._apply_grid_settings()
        self._save_settings()

    def _open_settings(self) -> None:
        QTimer.singleShot(0, self._show_settings_dialog)

    def _show_settings_dialog(self) -> None:
        if self._settings_dialog is not None and self._settings_dialog.isVisible():
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        dialog = InterfaceSettingsDialog(self.settings, self)
        self._settings_dialog = dialog
        dialog.settings_previewed.connect(self._preview_settings)
        dialog.settings_applied.connect(self._settings_applied)
        dialog.finished.connect(self._settings_dialog_finished)
        dialog.finished.connect(dialog.deleteLater)
        dialog.ensurePolished()
        dialog.adjustSize()
        center = self.frameGeometry().center()
        screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            x = max(
                available.left(),
                min(center.x() - dialog.width() // 2, available.right() - dialog.width() + 1),
            )
            y = max(
                available.top(),
                min(center.y() - dialog.height() // 2, available.bottom() - dialog.height() + 1),
            )
            dialog.move(x, y)
        self.panel.pause_backdrop()
        apply_native_backdrop(int(dialog.winId()))
        dialog.open()

    def _settings_dialog_finished(self, _result: int) -> None:
        # Ignore a pending focus-loss check caused by activating the dialog.
        self._focus_check_timer.stop()
        dialog = self._settings_dialog
        self._settings_dialog = None
        if dialog is not None:
            dialog.stop_pending_preview()
        if dialog is not None and not dialog.settings_were_applied:
            self._preview_settings(self.settings)
        # Let the native settings window leave the desktop compositor before
        # refreshing the glass snapshot, avoiding a reflected ghost frame.
        QTimer.singleShot(180, self._resume_backdrop_if_menus_closed)

    def _preview_settings(self, settings: InterfaceSettings) -> None:
        self.panel.set_panel_alpha(settings.panel_opacity)
        self.panel.set_matte_effect(settings.matte_effect)
        self.panel.set_glass_thickness(settings.glass_thickness)
        self.panel.set_glass_color(settings.glass_color)

    def _settings_applied(self, settings: InterfaceSettings) -> None:
        self.settings = settings
        self._preview_settings(self.settings)

        try:
            set_startup_enabled(self.settings.startup_with_windows)
        except OSError as error:
            self.settings.startup_with_windows = False
            QMessageBox.warning(
                self,
                "Автозагрузка MOON",
                f"Не удалось изменить автозагрузку Windows: {error}",
            )

        self._apply_grid_settings()
        self._save_settings()

    def _about(self) -> None:
        if self._about_dialog is not None and self._about_dialog.isVisible():
            self._about_dialog.raise_()
            self._about_dialog.activateWindow()
            return
        dialog = QMessageBox(self)
        dialog.setWindowTitle("О программе")
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.setModal(True)
        dialog.setText(
            "MOON Launchpad\n\n"
            "Ваше пространство для приложений.\n\n"
            "MOON — современный лаунчер для Windows, созданный для "
            "быстрого и удобного доступа ко всем вашим приложениям. "
            "Минималистичный интерфейс, быстрый поиск, категории, "
            "сортировка и гибкая настройка внешнего вида позволяют "
            "создать комфортное рабочее пространство именно под себя.\n\n"
            "Возможности:\n"
            "• Быстрый поиск и запуск приложений\n"
            "• Категории и сортировка\n"
            "• Glassmorphism-интерфейс\n"
            "• Настройка прозрачности и эффектов\n"
            "• Плавные анимации\n"
            "• Персонализация интерфейса\n\n"
            "MOON 1.0\n"
            "Python • PySide6 • Qt6"
        )
        self._about_dialog = dialog
        dialog.finished.connect(self._about_dialog_finished)
        dialog.finished.connect(dialog.deleteLater)
        self.panel.pause_backdrop()
        dialog.open()

    def _about_dialog_finished(self, _result: int) -> None:
        self._focus_check_timer.stop()
        self._about_dialog = None
        # Let the native dialog disappear from the desktop compositor before
        # the glass captures a fresh frame, otherwise its pixels can linger as
        # a doubled image behind the panel.
        QTimer.singleShot(180, self._resume_backdrop_if_menus_closed)

    def _apply_theme(self) -> None:
        light = self.theme.mode == ThemeMode.LIGHT
        self.panel.set_light_theme(light)
        self.setProperty("theme", "light" if light else "dark")
        self.style().unpolish(self)
        self.style().polish(self)

    @staticmethod
    def _storage_key(path: str) -> str:
        return str(Path(path).expanduser()).casefold().replace("/", "\\").rstrip("\\")

    def _create_folder_from_drop(self, source_id: str, target_id: str) -> None:
        source = self.catalog.find(source_id)
        if source is None:
            return
        target = self.catalog.find(target_id)
        if target is not None:
            if source.folder_id and source.folder_id == target.folder_id:
                return
            self.catalog.create_folder(
                f"Папка {target.name}",
                [source_id, target_id],
                anchor_app_id=target_id,
            )
            self._save_settings()
            return
        folder = next((item for item in self.catalog.folders if item.folder_id == target_id), None)
        if folder is not None and source.folder_id != folder.folder_id:
            self.catalog.move_to_folder(source_id, folder.folder_id)
            self._save_settings()

    def _open_folder(self, folder_id: str) -> None:
        folder = next((item for item in self.catalog.folders if item.folder_id == folder_id), None)
        if folder is None:
            return
        members = [
            app for app_id in folder.app_ids
            if (app := self.catalog.find(app_id)) is not None
        ]
        dialog = QDialog(self)
        dialog.setObjectName("AppFolderDialog")
        dialog.setWindowTitle(folder.name)
        dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        dialog.setMinimumSize(440, 340)
        # Keep the folder non-modal so a click on another tile continues to
        # that tile after this folder closes.
        dialog.setModal(False)
        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(12, 12, 12, 12)
        surface = LiquidGlassWidget(
            dialog,
            radius=24,
            opacity=self.settings.panel_opacity,
            border_opacity=95,
        )
        surface.setObjectName("AppFolderSurface")
        surface.set_glass_thickness(self.settings.glass_thickness)
        surface.set_matte_effect(self.settings.matte_effect)
        surface.set_glass_color(self.settings.glass_color)
        surface.set_panel_alpha(self.settings.panel_opacity)
        surface.set_light_theme(self.theme.mode == ThemeMode.LIGHT)
        outer.addWidget(surface)
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(22, 18, 22, 22)
        header = QHBoxLayout()
        folder_text_color = "#1d2638" if self.theme.mode == ThemeMode.LIGHT else "#f5f7ff"
        title = QLineEdit(folder.name, surface)
        title.setObjectName("FolderTitleEditor")
        title.setPlaceholderText("Название папки")
        title.setClearButtonEnabled(False)
        title.setMaxLength(48)
        title.setStyleSheet(
            f"QLineEdit {{ color: {folder_text_color}; font-size: 18px; font-weight: 700; "
            "background: transparent; border: 1px solid transparent; padding: 3px; }"
            "QLineEdit:focus { border-color: rgba(120,145,195,180); "
            "border-radius: 6px; background: rgba(255,255,255,18); }"
        )
        title.editingFinished.connect(
            lambda editor=title, current_folder=folder: self._rename_folder(
                current_folder, editor.text(), editor
            )
        )
        header.addWidget(title)
        header.addStretch(1)
        layout.addLayout(header)
        layout.addWidget(QLabel("Измените название сверху. Дважды щёлкните приложение, чтобы открыть его.", surface))
        scroll = QScrollArea(surface)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        contents = QWidget(scroll)
        contents_layout = QGridLayout(contents)
        contents_layout.setContentsMargins(4, 12, 4, 4)
        contents_layout.setHorizontalSpacing(14)
        contents_layout.setVerticalSpacing(10)
        loading = QLabel("Открываем папку…", contents)
        loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        contents_layout.addWidget(loading, 0, 0, 1, 3)
        scroll.setWidget(contents)
        layout.addWidget(scroll, 1)
        dialog.setStyleSheet("""
            QDialog#AppFolderDialog { background: transparent; }
            QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
            QLabel { color: #d9dcef; background: transparent; border: none; }
        """)
        self._folder_dialog = dialog
        dialog.finished.connect(
            lambda _result, current_folder=folder, editor=title: self._rename_folder(
                current_folder, editor.text(), editor
            )
        )
        dialog.finished.connect(self._folder_dialog_finished)
        self.panel.pause_backdrop()
        dialog.adjustSize()
        dialog.resize(max(440, dialog.width()), max(340, dialog.height()))
        dialog.move(self.frameGeometry().center() - dialog.rect().center())
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        QTimer.singleShot(
            20,
            lambda current_dialog=dialog, grid=contents_layout, apps=members, indicator=loading:
                self._populate_folder_dialog(current_dialog, grid, apps, indicator),
        )

    def _populate_folder_dialog(
        self,
        dialog: QDialog,
        layout: QGridLayout,
        members: list[ApplicationItem],
        loading: QLabel,
    ) -> None:
        """Build app cards after the folder window is visible."""
        if not dialog.isVisible():
            return
        layout.removeWidget(loading)
        loading.deleteLater()
        self._populate_folder_dialog_batch(dialog, layout, members, 0)

    def _populate_folder_dialog_batch(
        self,
        dialog: QDialog,
        layout: QGridLayout,
        members: list[ApplicationItem],
        start_index: int,
    ) -> None:
        """Add a few app cards per event-loop turn to keep opening responsive."""
        if not dialog.isVisible():
            return
        end_index = min(start_index + 6, len(members))
        for index in range(start_index, end_index):
            app = members[index]
            card = AppCard(app, self.icon_cache, layout.parentWidget())
            card.configure(
                self._icon_pixels(self.settings.icon_size),
                self.settings.font_size,
                self.settings.show_labels,
                self.settings.single_click_launch,
            )
            card.launched.connect(self.catalog.mark_opened)
            card.launched.connect(dialog.accept)
            card.pin_requested.connect(self._toggle_pin_for_app)
            card.favorite_requested.connect(self._toggle_favorite_for_app)
            card.remove_requested.connect(self._remove_app_from_moon)
            layout.addWidget(card, index // 3, index % 3, Qt.AlignmentFlag.AlignCenter)
        if end_index < len(members):
            QTimer.singleShot(
                10,
                lambda: self._populate_folder_dialog_batch(
                    dialog, layout, members, end_index
                ),
            )

    def _rename_folder(self, folder: AppFolder, requested_name: str, editor: QLineEdit) -> None:
        """Rename a folder and persist it without losing the previous name on blank input."""
        name = requested_name.strip()
        if not name:
            editor.setText(folder.name)
            return
        if name == folder.name:
            return
        folder.name = name
        if self._folder_dialog is not None:
            self._folder_dialog.setWindowTitle(name)
        self._save_settings()
        self._schedule_refresh()

    def _folder_dialog_finished(self, _result: int) -> None:
        self._folder_dialog = None
        QTimer.singleShot(120, self._resume_backdrop_if_menus_closed)

    def _remove_app_from_moon(self, app_id: str) -> None:
        app = self.catalog.find(app_id)
        if app is None:
            return
        if not app.uninstall_command:
            answer = QMessageBox.question(
                self,
                "Деинсталлятор не найден",
                f'Для «{app.name}» Windows не зарегистрировала команду удаления. '
                "Откройте список установленных приложений Windows и удалите программу там.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl("ms-settings:appsfeatures"))
            return
        answer = QMessageBox.question(
            self,
            "Удалить программу из Windows?",
            f'Будет запущен деинсталлятор «{app.name}». '
            "Приложение и его компоненты могут быть удалены из Windows.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if app_id in self._uninstall_processes:
            return
        command = os.path.expandvars(app.uninstall_command)
        if "msiexec" in command[:100].casefold():
            command = re.sub(r"(?i)(^|\s)/i(?=\s*\{)", r"\1/x", command)
        process = QProcess(self)
        self._uninstall_processes[app_id] = process
        process.finished.connect(
            lambda exit_code, _status, target_id=app_id:
                self._uninstall_finished(target_id, exit_code)
        )
        process.errorOccurred.connect(
            lambda _error, target_id=app_id: self._uninstall_failed(target_id)
        )
        process.startCommand(command)

    def _uninstall_finished(self, app_id: str, exit_code: int) -> None:
        process = self._uninstall_processes.pop(app_id, None)
        if process is None:
            return
        process.deleteLater()
        if exit_code != 0:
            self._uninstall_failed_message(app_id)
            return
        app = self.catalog.find(app_id)
        if app is not None and windows_uninstall_registered(app.name):
            QMessageBox.warning(
                self,
                "Удаление не подтверждено",
                f'Windows всё ещё показывает «{app.name}» среди установленных программ. '
                "Приложение оставлено в MOON.",
            )
            return
        self._forget_uninstalled_app(app_id)

    def _uninstall_failed(self, app_id: str) -> None:
        process = self._uninstall_processes.pop(app_id, None)
        if process is not None:
            process.deleteLater()
        self._uninstall_failed_message(app_id)

    def _uninstall_failed_message(self, app_id: str) -> None:
        app = self.catalog.find(app_id)
        if app is not None:
            QMessageBox.warning(
                self,
                "Не удалось удалить приложение",
                f'Деинсталлятор «{app.name}» завершился с ошибкой. '
                "Приложение оставлено в MOON.",
            )

    def _forget_uninstalled_app(self, app_id: str) -> None:
        app = self.catalog.find(app_id)
        if app is None:
            return
        key = self._storage_key(app.path)
        if key not in {self._storage_key(path) for path in self.settings.hidden_app_paths}:
            self.settings.hidden_app_paths.append(key)
        self.settings.custom_apps = [
            entry for entry in self.settings.custom_apps
            if self._storage_key(str(entry.get("path", ""))) != key
        ]
        self.catalog.remove_application(app_id)
        self._save_settings()

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        if not self.isVisible():
            return super().eventFilter(watched, event)

        if event.type() == QEvent.Type.MouseButtonPress:
            if hasattr(event, "globalPosition"):
                point = event.globalPosition().toPoint()

                folder_dialog = self._folder_dialog
                if (
                    folder_dialog is not None
                    and folder_dialog.isVisible()
                    and not folder_dialog.frameGeometry().contains(point)
                ):
                    folder_dialog.close()

                settings_dialog = self._settings_dialog
                if (
                    settings_dialog is not None
                    and settings_dialog.isVisible()
                    and settings_dialog.frameGeometry().contains(point)
                ):
                    return super().eventFilter(watched, event)

                about_dialog = self._about_dialog
                if (
                    about_dialog is not None
                    and about_dialog.isVisible()
                    and about_dialog.frameGeometry().contains(point)
                ):
                    return super().eventFilter(watched, event)

                modal = QApplication.activeModalWidget()
                if modal is not None and (modal is self or self.isAncestorOf(modal)):
                    return super().eventFilter(watched, event)

                if not self.frameGeometry().contains(point):
                    if self._popover is not None and self._popover.isVisible():
                        if self._popover.frameGeometry().contains(point):
                            return super().eventFilter(watched, event)

                    if self._sort_popover is not None and self._sort_popover.isVisible():
                        if self._sort_popover.frameGeometry().contains(point):
                            return super().eventFilter(watched, event)

                    self.hide()

        return super().eventFilter(watched, event)

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.WindowActivate:
            self._focus_check_timer.stop()
            self._focus_check_attempts = 0
            if self.theme.mode == ThemeMode.AUTO:
                self._apply_theme()

        elif event.type() == QEvent.Type.WindowDeactivate:
            self._schedule_focus_check()

        return super().event(event)

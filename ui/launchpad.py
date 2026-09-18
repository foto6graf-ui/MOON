"""Main Launchpad window and adaptive application grid."""

from __future__ import annotations
from PySide6.QtWidgets import QApplication
import logging
from pathlib import Path

from utils.startup import set_startup_enabled

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    QThread,
    QTimer,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QGuiApplication,
    QKeySequence,
    QPainter,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
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
from models.app_model import AppCategory, ApplicationCatalog, ApplicationItem, SortMode
from ui.app_card import AppCard
from ui.popover_menu import GlassPopoverMenu, MenuNode
from ui.search import SearchBox
from ui.settings_dialog import InterfaceSettingsDialog
from utils.app_scanner import (
    infer_category,
    is_allowed_windows_app,
    resolve_windows_shortcut,
    reveal_in_file_manager,
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
            apps = []
        self.finished.emit(apps)


class AppGrid(QWidget):
    """Adaptive lazy-rendered grid for application cards."""

    app_activated = Signal(str)
    pin_requested = Signal(str)
    favorite_requested = Signal(str)
    folder_requested = Signal(str)
    folder_drop_requested = Signal(str, str)

    def __init__(self, icon_cache: IconCache, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AppGrid")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent; border:none;")
        self._icon_cache = icon_cache
        self._apps: list[ApplicationItem] = []
        self._cards: list[AppCard] = []
        self._card_cache: dict[str, AppCard] = {}
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
        self._timer.setInterval(16)
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

    def set_apps(self, apps: list[ApplicationItem]) -> None:
        """Replace grid contents and lazy-create cards."""
        self._timer.stop()
        self._apps = apps
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
        self._forced_columns = 8
        self._spacing = 6
        self._layout.setHorizontalSpacing(self._spacing)
        self._layout.setVerticalSpacing(self._spacing)
        self._update_cell_size()
        for card in self._card_cache.values():
            card.configure(icon_size, font_size, show_labels, single_click_launch)
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

        # Максимум 8 колонок.
        # Если ширины экрана не хватает — автоматически меньше.
        columns = min(columns, 8)

        return columns

    def _append_batch(self) -> None:
        end = min(len(self._apps), self._next_index + self._batch_size)
        for index in range(self._next_index, end):
            self._add_card(self._apps[index], index)
        self._next_index = end
        self._update_grid_height()
        if self._next_index < len(self._apps):
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
            card.folder_requested.connect(self.folder_requested)
            card.drop_requested.connect(self.folder_drop_requested)
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
        row, column = divmod(index, self._columns)
        self._layout.addWidget(card, row, column, Qt.AlignmentFlag.AlignCenter)
        self._cards.append(card)

    def _relayout(self) -> None:
        for card in self._cards:
            self._layout.removeWidget(card)
        for index, card in enumerate(self._cards):
            row, column = divmod(index, self._columns)
            self._layout.addWidget(card, row, column, Qt.AlignmentFlag.AlignCenter)
        self._update_grid_height()

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
        self._cards.clear()
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

    def _apply_card_cell_size(self, card: AppCard) -> None:
        card.setFixedSize(QSize(self._cell_width, self._cell_height))

    def _update_grid_height(self) -> None:
        rows = 0
        if self._cards:
            rows = (len(self._cards) + max(1, self._columns) - 1) // max(1, self._columns)
        margins = self._layout.contentsMargins()
        height = margins.top() + margins.bottom()
        if rows:
            height += rows * self._cell_height + (rows - 1) * self._spacing
        if self.minimumHeight() != height:
            self.setMinimumHeight(height)
            self.updateGeometry()


class SearchResultsList(QListWidget):
    """Compact search results shown while the user types."""

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

    def set_apps(self, apps: list[ApplicationItem]) -> None:
        """Refresh list rows from applications."""
        self.clear()
        for app in apps[:500]:
            item = QListWidgetItem()
            item.setText(f"{app.name}\n{app.path}")
            item.setToolTip(app.path)
            item.setData(Qt.ItemDataRole.UserRole, app.item_id)
            item.setSizeHint(QSize(100, 62))
            item.setIcon(
                self._icon_cache.pixmap_for(
                    app.name,
                    app.path,
                    app.icon_path,
                )
            )
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

    def __init__(self, catalog: ApplicationCatalog, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.icon_cache = IconCache()
        self.theme = ThemeController()
        self.settings_store = SettingsStore()
        self.settings = self.settings_store.load()
        self._category: AppCategory | None = None
        self._custom_section: str | None = None
        self._scanner_thread: QThread | None = None
        self._scanner_worker: ScannerWorker | None = None
        self._active_animations: list[object] = []
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(45)
        self._refresh_timer.timeout.connect(self._refresh_grid)
        self._intro_played = False
        self._popover: GlassPopoverMenu | None = None
        self._sort_popover: GlassPopoverMenu | None = None
        self._promoted_app_id: str | None = None
        self._global_hotkey = ModifierHotkeyWatcher(self)
        self._global_hotkey.activated.connect(self.toggle_visibility)
        QApplication.instance().installEventFilter(self)

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
        self.menu_button = HoverButton("...", self.panel, circular=True)
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
                width: 6px;
                background: transparent;
            }

            QScrollBar::handle:vertical {
                min-height: 28px;
                border-radius: 3px;
                background: rgba(255, 255, 255, 78);
            }

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

        self.sort_button = HoverButton("⇅", self.panel, circular=True)
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
        self._scanner_worker.finished.connect(self._scanner_thread.quit)
        self._scanner_worker.finished.connect(self._scanner_worker.deleteLater)
        self._scanner_thread.finished.connect(self._clear_scanner_refs)
        self._scanner_thread.finished.connect(self._scanner_thread.deleteLater)
        self._scanner_thread.start()

    @Slot()
    def _clear_scanner_refs(self) -> None:
        """Drop Python references after Qt has finished the scanner thread."""
        self._scanner_thread = None
        self._scanner_worker = None

    @Slot(list)
    def _scanner_finished(self, apps: list[ApplicationItem]) -> None:
        """Apply scanned applications together with user-added shortcuts."""
        self.catalog.set_applications(
            [*apps, *self._custom_app_items()],
            show_system_apps=self.settings.show_system_apps,
        )
        LOGGER.info("Application catalog updated: displayed=%d", len(self.catalog.applications))

    def _play_intro(self) -> None:
        bg_animation = QPropertyAnimation(self.background, b"overlayOpacity", self)
        bg_animation.setStartValue(0.0)
        bg_animation.setEndValue(0.0)
        bg_animation.setDuration(120)
        bg_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        bg_animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self.panel.setPanelOpacity(0.0)
        QTimer.singleShot(
            30,
            lambda: self._run_animation(Animator.entrance_sequence(self.panel, self.grid.cards[:48])),
        )
        self._intro_played = True

    @Slot()
    def _schedule_refresh(self) -> None:
        self._refresh_timer.start()

    @Slot()
    def _refresh_grid(self) -> None:
        query = self.search.text().strip()
        apps = self.catalog.filtered(
            query,
            self._category,
            favorites_only=self.settings.favorites_only,
        )
        if self._custom_section:
            section = self._custom_section.casefold()
            apps = [
                app
                for app in apps
                if section in app.name.casefold()
                or section in app.path.casefold()
                or section in app.category.value.casefold()
            ]
        if self.settings.folders_only:
            apps = [app for app in apps if app.folder_id is not None]
        if self._promoted_app_id:
            promoted_id = self._promoted_app_id
            promoted = [app for app in apps if app.item_id == promoted_id]
            if promoted:
                apps = [*promoted, *(app for app in apps if app.item_id != promoted_id)]
        if query:
            self.grid_scroll.hide()
            self.search_results.show()
            self.search_results.set_apps(apps)
            return

        self.search_results.hide()
        self.grid_scroll.show()
        self.grid.set_apps(apps)
        LOGGER.info("Application grid updated: apps=%d, columns=%d", len(apps), self.grid.columns)
        if self._promoted_app_id and apps and apps[0].item_id == self._promoted_app_id:
            QTimer.singleShot(0, self._focus_promoted_app)
        if not self._intro_played and len(apps) <= 160:
            QTimer.singleShot(0, self._animate_visible_cards)

    def _animate_visible_cards(self) -> None:
        for card in self.grid.cards[:80]:
            card.setContentOpacity(0.0)
        if self.grid.cards:
            sequence = Animator.cards_sequence(self.grid, self.grid.cards)
            self._run_animation(sequence)

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

    def show_centered(self) -> None:
        """Show the menu centred in the work area of the current screen."""
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
            self.panel.pause_backdrop()
        self._popover = GlassPopoverMenu(self._menu_nodes(), self)
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
            self.panel.pause_backdrop()
        self._sort_popover = GlassPopoverMenu(self._sort_menu_nodes(), self)
        self._sort_popover.closed.connect(self._sort_menu_closed)
        point = self.sort_button.mapToGlobal(
            QPoint(self.sort_button.width() - self._sort_popover.width(), self.sort_button.height() + 8)
        )
        self._sort_popover.popup_at(point)
        LOGGER.info("Sort menu opened")

    def _theme_menu_closed(self) -> None:
        self.panel.resume_backdrop()
        self._popover = None
        LOGGER.info("Settings menu closed")

    def _sort_menu_closed(self) -> None:
        self._sort_popover = None
        LOGGER.info("Sort menu closed")

    def _action(self, text: str, callback: object) -> QAction:
        action = QAction(text, self)
        action.triggered.connect(callback)
        return action

    def _menu_nodes(self) -> list[MenuNode]:
        return [
            MenuNode(
                "⌕",
                "Показывать поиск",
                self._action("search", self._toggle_search),
                checkable=True,
                checked=self.settings.show_search,
            ),
            MenuNode(
                "⚙",
                "Настройки",
                self._action("settings", self._open_settings),
            ),
            MenuNode(
                "ⓘ",
                "О программе",
                self._action("about", self._about),
            ),
            MenuNode(
                "×",
                "Выход",
                self._action("exit", self.close),
            ),
        ]

    def _sort_menu_nodes(self) -> list[MenuNode]:
        return [
            MenuNode("A", "По имени", self._action("sort_name", lambda: self._set_sort(SortMode.NAME)), checkable=True, checked=self.settings.sort_mode == SortMode.NAME.value),
            MenuNode("★", "Часто используемые", self._action("sort_used", lambda: self._set_sort(SortMode.MOST_USED)), checkable=True, checked=self.settings.sort_mode == SortMode.MOST_USED.value),
            MenuNode("⌂", "Закреплённые сверху", self._action("pin_first", self._toggle_pin_favorites_first), checkable=True, checked=self.settings.pin_favorites_first),
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
        self.settings_store.save(self.settings)

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
        self.panel.set_glass_color(self.settings.glass_color)
        self._set_theme(ThemeMode.DARK, save=False)
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
        self.settings.theme = ThemeMode.DARK.value
        self.theme.set_mode(ThemeMode.DARK)
        if save:
            self._save_settings()

    def _set_background(self, mode: str) -> None:
        self.settings.background_mode = mode
        if mode == "gradient":
            self.background.setOverlayOpacity(0.08)
        elif mode == "blur":
            self.background.setOverlayOpacity(0.0)
        self._save_settings()

    def _cycle_panel_opacity(self) -> None:
        values = [65, 85, 105, 125, 145]
        current = self.settings.panel_opacity
        self.settings.panel_opacity = values[(values.index(current) + 1) % len(values)] if current in values else 105
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
        dialog = InterfaceSettingsDialog(self.settings, self)
        dialog.settings_applied.connect(self._settings_applied)
        dialog.exec()

    def _settings_applied(self, settings: InterfaceSettings) -> None:
        self.settings = settings

        self.panel.set_panel_alpha(self.settings.panel_opacity)
        self.panel.set_matte_effect(self.settings.matte_effect)
        self.panel.set_glass_color(self.settings.glass_color)

        set_startup_enabled(self.settings.startup_with_windows)

        self._apply_grid_settings()
        self._save_settings()
        self._start_scanner()

    def _about(self) -> None:
        QMessageBox.information(
            self,
            "О программе",
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
            "Python • PySide6 • Qt6",
        )

    def _apply_theme(self) -> None:
        light = self.theme.mode == ThemeMode.LIGHT
        self.panel.set_light_theme(light)
        self.setProperty("theme", "light" if light else "dark")
        self.style().unpolish(self)
        self.style().polish(self)

    def _create_folder_from_single(self, app_id: str) -> None:
        app = self.catalog.find(app_id)
        if app is None:
            return
        folder = self.catalog.create_folder(f"Папка {app.name}", [app_id])
        QMessageBox.information(self, "Папка создана", f'Создана папка "{folder.name}".')

    def _create_folder_from_drop(self, source_id: str, target_id: str) -> None:
        source = self.catalog.find(source_id)
        target = self.catalog.find(target_id)
        if source is None or target is None:
            return
        folder = self.catalog.create_folder("Новая папка", [source_id, target_id])
        QMessageBox.information(
            self,
            "Папка создана",
            f'Создана папка "{folder.name}" для {source.name} и {target.name}.',
        )

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        if not self.isVisible():
            return super().eventFilter(watched, event)

        if event.type() == QEvent.Type.MouseButtonPress:
            if hasattr(event, "globalPosition"):
                point = event.globalPosition().toPoint()

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
            if self.theme.mode == ThemeMode.AUTO:
                self._apply_theme()

        elif event.type() == QEvent.Type.WindowDeactivate:
            self.hide()

        return super().event(event)
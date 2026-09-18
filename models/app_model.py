"""Domain models and catalog logic for installed applications."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable
from time import time
from uuid import uuid4

from PySide6.QtCore import QObject, Signal

from utils.app_scanner import (
    deduplicate_application_items,
    normalize_application_name,
    normalized_launch_identity,
    scan_installed_applications,
)


class AppCategory(str, Enum):
    """Supported Launchpad categories."""

    PRODUCTIVITY = "Работа и финансы"
    CREATIVITY = "Творчество"
    ENTERTAINMENT = "Развлечения"
    GAMES = "Игры"
    UTILITIES = "Утилиты"
    SOCIAL = "Соцсети"
    OTHER = "Другое"


class SortMode(str, Enum):
    """Supported application ordering modes."""

    NAME = "name"
    RECENTLY_INSTALLED = "recently_installed"
    RECENTLY_OPENED = "recently_opened"
    MOST_USED = "most_used"
    CATEGORY = "category"


@dataclass(slots=True)
class ApplicationItem:
    """An installed application that can be displayed and launched."""

    name: str
    path: str
    icon_path: str | None = None
    category: AppCategory = AppCategory.OTHER
    executable: str | None = None
    arguments: tuple[str, ...] = field(default_factory=tuple)
    is_favorite: bool = False
    is_pinned: bool = False
    visible_by_default: bool = True
    installed_at: float = 0.0
    last_opened_at: float = 0.0
    open_count: int = 0
    folder_id: str | None = None
    app_user_model_id: str | None = None
    source_type: str = "user"
    item_id: str = field(default_factory=lambda: uuid4().hex)

    @property
    def launch_target(self) -> str:
        """Return the most suitable target for opening this application."""
        return self.executable or self.path

    @property
    def path_obj(self) -> Path:
        """Return the application path as a Path object."""
        return Path(self.path)


@dataclass(slots=True)
class AppFolder:
    """A user-created application folder."""

    name: str
    app_ids: list[str] = field(default_factory=list)
    folder_id: str = field(default_factory=lambda: uuid4().hex)


class ApplicationCatalog(QObject):
    """MVC model/controller boundary for applications, folders and filters."""

    applications_changed = Signal()
    favorites_changed = Signal()
    folders_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._applications: list[ApplicationItem] = []
        self._folders: dict[str, AppFolder] = {}
        self._sort_mode = SortMode.NAME
        self._pin_favorites_first = True

    @property
    def applications(self) -> list[ApplicationItem]:
        """Return all known applications."""
        return list(self._applications)

    @property
    def folders(self) -> list[AppFolder]:
        """Return all user-created folders."""
        return list(self._folders.values())

    def load(self) -> None:
        """Scan the current platform for installed applications."""
        self._applications = scan_installed_applications()
        self.applications_changed.emit()

    def set_applications(
        self,
        applications: Iterable[ApplicationItem],
        *,
        show_system_apps: bool = True,
    ) -> None:
        """Replace applications with an explicit collection."""
        existing = {
            self._identity_for(app): app
            for app in self._applications
            if self._identity_for(app) is not None
        }
        self._applications = []
        for app in deduplicate_application_items(
            applications,
            show_system_apps=show_system_apps,
        ):
            previous = existing.get(self._identity_for(app))
            if previous is not None:
                app.item_id = previous.item_id
                app.is_favorite = previous.is_favorite
                app.is_pinned = previous.is_pinned
                app.last_opened_at = previous.last_opened_at
                app.open_count = previous.open_count
            self._applications.append(app)
        self.applications_changed.emit()

    def add_application(self, app: ApplicationItem) -> None:
        """Add one user-selected application if it is not already present."""
        key = self._identity_for(app)
        if key is None or any(self._identity_for(existing) == key for existing in self._applications):
            return
        self._applications.append(app)
        self.applications_changed.emit()

    def set_sort_mode(self, mode: SortMode) -> None:
        """Set ordering mode for filtered applications."""
        self._sort_mode = mode
        self.applications_changed.emit()

    def set_pin_favorites_first(self, enabled: bool) -> None:
        """Enable or disable favorite pinning in sort order."""
        self._pin_favorites_first = enabled
        self.applications_changed.emit()

    def mark_opened(self, app_id: str) -> None:
        """Update launch metrics without rebuilding the visible grid."""
        app = self.find(app_id)
        if app is None:
            return
        app.last_opened_at = time()
        app.open_count += 1

    def toggle_favorite(self, app_id: str) -> None:
        """Toggle favorite state for an application."""
        app = self.find(app_id)
        if app is None:
            return
        app.is_favorite = not app.is_favorite
        self.favorites_changed.emit()
        self.applications_changed.emit()

    def toggle_pin(self, app_id: str) -> None:
        """Toggle pinned state for an application."""
        app = self.find(app_id)
        if app is None:
            return
        app.is_pinned = not app.is_pinned
        self.applications_changed.emit()

    def create_folder(self, name: str, app_ids: Iterable[str]) -> AppFolder:
        """Create a folder and assign the provided applications to it."""
        folder = AppFolder(name=name, app_ids=list(dict.fromkeys(app_ids)))
        self._folders[folder.folder_id] = folder
        for app_id in folder.app_ids:
            app = self.find(app_id)
            if app is not None:
                app.folder_id = folder.folder_id
        self.folders_changed.emit()
        self.applications_changed.emit()
        return folder

    def move_to_folder(self, app_id: str, folder_id: str | None) -> None:
        """Move an application into or out of a folder."""
        app = self.find(app_id)
        if app is None:
            return
        app.folder_id = folder_id
        for folder in self._folders.values():
            if app_id in folder.app_ids and folder.folder_id != folder_id:
                folder.app_ids.remove(app_id)
        if folder_id and folder_id in self._folders:
            folder = self._folders[folder_id]
            if app_id not in folder.app_ids:
                folder.app_ids.append(app_id)
        self.folders_changed.emit()
        self.applications_changed.emit()

    def find(self, app_id: str) -> ApplicationItem | None:
        """Find an application by its stable id."""
        return next((app for app in self._applications if app.item_id == app_id), None)

    def filtered(
        self,
        query: str = "",
        category: AppCategory | None = None,
        favorites_only: bool = False,
    ) -> list[ApplicationItem]:
        """Return applications matching the current UI filter."""
        normalized = query.casefold().strip()
        items = self._applications
        if not normalized and category is None:
            items = [app for app in items if app.visible_by_default]
        if category is not None:
            items = [app for app in items if app.category == category]
        if favorites_only:
            items = [app for app in items if app.is_favorite]
        if normalized:
            items = [
                app
                for app in items
                if normalized in app.name.casefold()
                or normalized in app.path.casefold()
                or normalized in app.category.value.casefold()
            ]
        return self._sort(items)

    def _sort(self, items: list[ApplicationItem]) -> list[ApplicationItem]:
        def prefix(app: ApplicationItem) -> tuple[int, int]:
            if self._pin_favorites_first and (app.is_pinned or app.is_favorite):
                return (0, 0 if app.is_pinned else 1)
            if app.open_count:
                return (1, -app.open_count)
            if app.visible_by_default:
                return (2, 0)
            return (3, 0)

        def stable_key(app: ApplicationItem) -> tuple[str, str]:
            return (
                normalize_application_name(app.name),
                self._identity_for(app) or app.path.casefold(),
            )

        if self._sort_mode == SortMode.MOST_USED:
            return sorted(items, key=lambda app: (*prefix(app), -app.open_count, *stable_key(app)))
        return sorted(items, key=lambda app: (*prefix(app), *stable_key(app)))

    @staticmethod
    def _identity_for(app: ApplicationItem) -> str | None:
        return normalized_launch_identity(app.launch_target, app.app_user_model_id)

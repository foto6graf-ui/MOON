"""Persistent JSON settings for the Launchpad widget."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class InterfaceSettings:
    """User-customizable interface settings."""

    animation_speed: int = 220
    blur_enabled: bool = True
    shadows_enabled: bool = False
    panel_opacity: int = 20
    forced_columns: int = 0
    card_spacing: int = 30
    icon_size: str = "medium"
    font_size: int = 16
    show_labels: bool = True
    matte_effect: float = 0.2
    glass_thickness: float = 0.5
    glass_color: str = "default"
    startup_with_windows: bool = False
    single_click_launch: bool = False
    theme: str = "Dark"
    background_mode: str = "blur"
    sort_mode: str = "name"
    favorites_only: bool = False
    folders_only: bool = False
    show_search: bool = True
    pin_favorites_first: bool = True
    show_system_apps: bool = False
    custom_apps: list[dict[str, str]] = field(default_factory=list)
    custom_sections: list[str] = field(default_factory=list)
    hidden_app_paths: list[str] = field(default_factory=list)
    app_folders: list[dict[str, Any]] = field(default_factory=list)


class SettingsStore:
    """Load and save settings from a local JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        if path is not None:
            self.path = path
        elif getattr(sys, "frozen", False):
            app_data = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
            self.path = app_data / "MOON" / "settings.json"
        else:
            self.path = Path(__file__).resolve().parent.parent / "settings.json"

    def load(self) -> InterfaceSettings:
        """Read settings from disk, returning defaults on invalid files."""
        if not self.path.exists():
            return InterfaceSettings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return InterfaceSettings()
        if not isinstance(data, dict):
            return InterfaceSettings()
        defaults = asdict(InterfaceSettings())
        for key, default in defaults.items():
            value = data.get(key)
            if isinstance(default, bool):
                if isinstance(value, bool):
                    defaults[key] = value
            elif isinstance(default, int):
                if isinstance(value, int) and not isinstance(value, bool):
                    defaults[key] = value
            elif isinstance(default, float):
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    defaults[key] = float(value)
            elif isinstance(default, str):
                if isinstance(value, str):
                    defaults[key] = value
            elif isinstance(default, list) and isinstance(value, list):
                if key == "custom_apps":
                    defaults[key] = [item for item in value if isinstance(item, dict)]
                elif key == "custom_sections":
                    defaults[key] = [item for item in value if isinstance(item, str)]
                elif key == "hidden_app_paths":
                    defaults[key] = [item for item in value if isinstance(item, str)]
                elif key == "app_folders":
                    defaults[key] = [
                        item for item in value
                        if isinstance(item, dict)
                        and isinstance(item.get("name"), str)
                        and isinstance(item.get("apps"), list)
                    ]
        return InterfaceSettings(**defaults)

    def save(self, settings: InterfaceSettings) -> None:
        """Persist settings to disk."""
        payload: dict[str, Any] = asdict(settings)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_name(f"{self.path.name}.tmp")
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary_path, self.path)

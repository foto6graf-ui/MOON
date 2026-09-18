"""Cross-platform installed application discovery."""

from __future__ import annotations

import configparser
import logging
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

try:
    import win32com.client
except ImportError:
    win32com = None

if TYPE_CHECKING:
    from models.app_model import AppCategory, ApplicationItem


PRODUCTIVITY_WORDS = {
    "office",
    "word",
    "excel",
    "powerpoint",
    "numbers",
    "pages",
    "calendar",
    "finance",
    "bank",
    "notion",
    "todo",
}
CREATIVITY_WORDS = {
    "photo",
    "paint",
    "design",
    "figma",
    "sketch",
    "adobe",
    "music",
    "video",
    "studio",
    "editor",
}
ENTERTAINMENT_WORDS = {
    "steam",
    "spotify",
    "music",
    "tv",
    "movie",
    "media",
    "player",
    "netflix",
}
GAME_WORDS = {
    "battle",
    "epic games",
    "game",
    "games",
    "gog",
    "minecraft",
    "origin",
    "riot",
    "rockstar games launcher",
    "steam game",
    "ubisoft",
    "ubisoft connect",
    "xbox",
}
UTILITY_WORDS = {
    "terminal",
    "settings",
    "system",
    "utility",
    "tools",
    "control",
    "powershell",
    "cmd",
    "console",
}
SOCIAL_WORDS = {
    "mail",
    "chat",
    "slack",
    "telegram",
    "discord",
    "teams",
    "zoom",
    "skype",
    "social",
}

APP_BLACKLIST_WORDS = {
    "uninstall",
    "uninst",
    "setup",
    "update",
    "config",
    "reset",
    "manual",
    "help",
    "readme",
    "docs",
    "errorreporter",
    "gameoverlayui",
    "minidump",
    "redistributables",
    "runtime",
    "streaming_client",
    "support",
    "xboxpcappadminserver",
    "xboxpcappce",
}

SYSTEM_APP_KEYWORDS = {
    "administrative tools",
    "admin tools",
    "component services",
    "computer management",
    "control panel",
    "device manager",
    "event viewer",
    "local security policy",
    "odbc data sources",
    "performance monitor",
    "registry editor",
    "services",
    "system configuration",
    "task scheduler",
    "windows tools",
    "windows update",
}
SYSTEM_PATH_PARTS = (
    "\\windows\\system32\\",
    "\\windows\\syswow64\\",
    "\\windows\\servicing\\",
    "\\windows\\winsxs\\",
)
SYSTEM_APP_USER_MODEL_IDS = {
    "microsoft.windows.controlpanel",
    "microsoft.windows.settings",
    "microsoft.windowsadministrativetools",
}
TECHNICAL_NAME_PREFIX = re.compile(
    r"^(?:app|application|launcher|program|shortcut)\s*[-_:]*\s*",
    re.IGNORECASE,
)
LOGGER = logging.getLogger(__name__)


def scan_installed_applications(*, show_system_apps: bool = False) -> list["ApplicationItem"]:
    """Scan applications on the current operating system."""
    system = platform.system().lower()
    if system == "windows":
        apps = _scan_windows()
    elif system == "darwin":
        apps = _scan_macos()
    else:
        apps = _scan_linux()

    unique, duplicate_count, hidden_system_count = _deduplicate_applications(
        apps,
        show_system_apps=show_system_apps,
    )
    LOGGER.info(
        "Application scan completed: found=%d, duplicates_removed=%d, system_hidden=%d, displayed=%d",
        len(apps),
        duplicate_count,
        hidden_system_count,
        len(unique),
    )
    if not unique:
        return _fallback_apps()
    return sorted(unique, key=_stable_application_sort_key)


def normalize_application_name(value: str) -> str:
    """Return a predictable display/sort name without technical prefixes."""
    normalized = " ".join(value.split())
    return TECHNICAL_NAME_PREFIX.sub("", normalized).casefold()


def normalized_launch_identity(target: str, app_user_model_id: str | None = None) -> str | None:
    """Return a stable identity for a valid launch target or application id."""
    value = target.strip()
    if value.startswith(("steam://", "com.epicgames.launcher://")):
        return f"uri:{value.casefold()}"
    if value:
        try:
            path = Path(value)
            if path.suffix.casefold() == ".lnk":
                value = _resolve_shortcut(path)
                path = Path(value)
            if path.exists() and (
                path.suffix.casefold() == ".exe" or platform.system().lower() != "windows"
            ):
                resolved = path.resolve(strict=False)
                return f"path:{os.path.normcase(os.path.normpath(str(resolved)))}"
        except (OSError, ValueError):
            pass
    if app_user_model_id:
        return f"aumid:{app_user_model_id.strip().casefold()}"
    return None


def _deduplicate_applications(
    apps: Iterable["ApplicationItem"],
    *,
    show_system_apps: bool,
) -> tuple[list["ApplicationItem"], int, int]:
    """Discard invalid/system entries and keep the best item per app identity."""
    selected: dict[str, ApplicationItem] = {}
    duplicate_count = 0
    hidden_system_count = 0
    for app in apps:
        target = app.launch_target
        if Path(target).suffix.casefold() == ".lnk":
            target = _resolve_shortcut(Path(target))
            app.executable = target
        identity = normalized_launch_identity(target, app.app_user_model_id)
        if identity is None:
            continue
        if not show_system_apps and _is_system_application(app):
            hidden_system_count += 1
            continue
        previous = selected.get(identity)
        if previous is not None:
            duplicate_count += 1
            if (
                _application_quality(app) < _application_quality(previous)
                or (
                    _application_quality(app) == _application_quality(previous)
                    and _stable_application_sort_key(app)
                    >= _stable_application_sort_key(previous)
                )
            ):
                continue
        selected[identity] = app
    return list(selected.values()), duplicate_count, hidden_system_count


def deduplicate_application_items(
    apps: Iterable["ApplicationItem"],
    *,
    show_system_apps: bool = True,
) -> list["ApplicationItem"]:
    """Return one launchable item per stable identity for catalog updates."""
    items, _, _ = _deduplicate_applications(apps, show_system_apps=show_system_apps)
    return items


def _application_quality(app: "ApplicationItem") -> tuple[int, int, int, int]:
    target = app.launch_target
    target_exists = int(target.startswith(("steam://", "com.epicgames.launcher://")) or Path(target).exists())
    icon_exists = int(bool(app.icon_path) and Path(app.icon_path).exists())
    cleaned_name = normalize_application_name(app.name)
    normal_name = int(bool(cleaned_name) and cleaned_name == " ".join(app.name.split()).casefold())
    source_score = {"shortcut": 3, "registry": 2, "program_files": 1}.get(app.source_type, 0)
    return (target_exists, icon_exists, normal_name, source_score)


def _stable_application_sort_key(app: "ApplicationItem") -> tuple[str, str, str]:
    return (
        normalize_application_name(app.name),
        normalized_launch_identity(app.launch_target, app.app_user_model_id) or "",
        app.path.casefold(),
    )


def _is_system_application(app: "ApplicationItem") -> bool:
    """Classify system entries using extensible path, text, type and AUMID rules."""
    target = app.launch_target.casefold().replace("/", "\\")
    text = f"{app.name} {target} {app.source_type}".casefold()
    aumid = (app.app_user_model_id or "").casefold()
    return (
        app.source_type == "system"
        or aumid in SYSTEM_APP_USER_MODEL_IDS
        or any(part in target for part in SYSTEM_PATH_PARTS)
        or any(keyword in text for keyword in SYSTEM_APP_KEYWORDS)
        or any(keyword in text for keyword in APP_BLACKLIST_WORDS)
    )


def infer_category(name: str, hint: str = "") -> "AppCategory":
    """Infer a visual category from a name and optional metadata hint."""
    from models.app_model import AppCategory

    text = f"{name} {hint}".casefold()
    if any(word in text for word in PRODUCTIVITY_WORDS):
        return AppCategory.PRODUCTIVITY
    if any(word in text for word in CREATIVITY_WORDS):
        return AppCategory.CREATIVITY
    if any(word in text for word in SOCIAL_WORDS):
        return AppCategory.SOCIAL
    if any(word in text for word in GAME_WORDS):
        return AppCategory.GAMES
    if any(word in text for word in ENTERTAINMENT_WORDS):
        return AppCategory.ENTERTAINMENT
    if any(word in text for word in UTILITY_WORDS):
        return AppCategory.UTILITIES
    return AppCategory.OTHER

def _resolve_shortcut(path: Path) -> str:
    try:
        if win32com is None:
            return ""
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(path))
        return str(shortcut.TargetPath or "")
    except Exception:
        return ""


def resolve_windows_shortcut(path: Path) -> str:
    """Read the target path from a Windows .lnk shortcut."""
    return _resolve_shortcut(path)


def _resolve_shortcut_arguments(path: Path) -> str:
    try:
        if win32com is None:
            return ""
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(path))
        return str(shortcut.Arguments or "")
    except Exception:
        return ""


def _read_windows_url(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.casefold().startswith("url="):
                return line.split("=", 1)[1].strip()
    except OSError:
        return ""
    return ""


def _is_game_launcher_target(name: str, target: str, arguments: str = "") -> bool:
    text = f"{name} {target} {arguments}".casefold()
    return any(word in text for word in GAME_WORDS) or "steam://rungameid/" in text or "-applaunch" in text


def _looks_like_desktop_game_shortcut(shortcut: Path, target: str) -> bool:
    target_path = Path(target)
    if target_path.suffix.casefold() != ".exe":
        return False
    normalized = str(target_path).casefold()
    if "steamapps\\common" in normalized or "steamapps/common" in normalized:
        return True
    system_roots = (
        os.environ.get("ProgramFiles", "").casefold(),
        os.environ.get("ProgramFiles(x86)", "").casefold(),
        os.environ.get("LOCALAPPDATA", "").casefold(),
        os.environ.get("WINDIR", "").casefold(),
    )
    if any(root and normalized.startswith(root) for root in system_roots):
        return False
    non_game_words = (
        "chrome",
        "code",
        "cursor",
        "edge",
        "jetbrains",
        "pycharm",
        "torrent",
        "utility",
        "voice assistant",
    )
    text = f"{shortcut.stem} {normalized}".casefold()
    return not any(word in text for word in non_game_words)


def is_allowed_windows_app(name: str, target: str, *, require_exe: bool = True) -> bool:
    """Return True when a Windows shortcut/executable points to a real app."""
    target_path = Path(target)
    if target.startswith(("steam://", "com.epicgames.launcher://")):
        return True
    return not require_exe or (
        target_path.suffix.casefold() == ".exe" and target_path.exists()
    )


def launch_application(path: str, arguments: Iterable[str] = ()) -> None:
    """Open an application using the native platform command."""
    system = platform.system().lower()
    args = list(arguments)
    if system == "windows":
        if args and Path(path).suffix.casefold() == ".exe":
            subprocess.Popen([path, *args])
        else:
            os.startfile(path)  # type: ignore[attr-defined]
    elif system == "darwin":
        subprocess.Popen(["open", path, *args])
    else:
        target = path
        if target.endswith(".desktop"):
            command = _desktop_exec_command(Path(target))
            if command:
                subprocess.Popen(command)
                return
        subprocess.Popen(["xdg-open", target, *args])


def run_as_administrator(path: str) -> bool:
    """Try to run an application with elevated privileges."""
    system = platform.system().lower()
    if system == "windows":
        import ctypes

        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            path,
            None,
            None,
            1,
        )
        return result > 32
    if system == "darwin":
        subprocess.Popen(["osascript", "-e", f'do shell script "open {path}" with administrator privileges'])
        return True
    subprocess.Popen(["pkexec", "xdg-open", path])
    return True


def reveal_in_file_manager(path: str) -> None:
    """Reveal an application path in the platform file manager."""
    system = platform.system().lower()
    if system == "windows":
        subprocess.Popen(["explorer", "/select,", path])
    elif system == "darwin":
        subprocess.Popen(["open", "-R", path])
    else:
        subprocess.Popen(["xdg-open", str(Path(path).parent)])


def _scan_windows() -> list["ApplicationItem"]:
    from models.app_model import AppCategory, ApplicationItem

    apps: list[ApplicationItem] = []

    roots = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("USERPROFILE", "")) / "Desktop",
        Path(os.environ.get("PUBLIC", "")) / "Desktop",
    ]

    program_roots = [
        Path(os.environ.get("ProgramFiles", "")),
        Path(os.environ.get("ProgramFiles(x86)", "")),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs",
    ]

    for root in roots:
        if not root.exists():
            continue

        for shortcut in root.rglob("*.lnk"):
            target = _resolve_shortcut(shortcut)
            arguments = _resolve_shortcut_arguments(shortcut)
            is_game = _is_game_launcher_target(shortcut.stem, target, arguments) or _looks_like_desktop_game_shortcut(shortcut, target)
            if not is_game and not is_allowed_windows_app(shortcut.stem, target):
                continue

            category = AppCategory.GAMES if is_game else infer_category(shortcut.stem, f"{target} {arguments}")
            apps.append(
                ApplicationItem(
                    name=shortcut.stem,
                    path=str(shortcut),
                    executable=target,
                    icon_path=target,
                    arguments=tuple(arguments.split()) if arguments else (),
                    category=category,
                    visible_by_default=True,
                    installed_at=_mtime(shortcut),
                    source_type="shortcut",
                )
            )

        for shortcut in root.rglob("*.url"):
            url = _read_windows_url(shortcut)
            if not url or not _is_game_launch_uri(url):
                continue
            apps.append(
                ApplicationItem(
                    name=shortcut.stem,
                    path=url,
                    executable=url,
                    icon_path=None,
                    category=AppCategory.GAMES,
                    visible_by_default=True,
                    installed_at=_mtime(shortcut),
                    source_type="game_uri",
                )
            )

    for root in program_roots:
        if not root.exists():
            continue
        for executable in root.glob("*/*.exe"):
            if not is_allowed_windows_app(executable.stem, str(executable), require_exe=True):
                continue
            apps.append(
                ApplicationItem(
                    name=_clean_name(executable.stem),
                    path=str(executable),
                    icon_path=str(executable),
                    executable=str(executable),
                    category=infer_category(executable.stem, str(executable.parent)),
                    visible_by_default=True,
                    installed_at=_mtime(executable),
                    source_type="program_files",
                )
            )

    apps.extend(_scan_windows_registry())
    apps.extend(_scan_steam_games())
    return apps


def _scan_steam_games() -> list["ApplicationItem"]:
    from models.app_model import ApplicationItem

    apps: list[ApplicationItem] = []
    for library in _steam_libraries():
        steamapps = library / "steamapps"
        if not steamapps.exists():
            continue
        for manifest in steamapps.glob("appmanifest_*.acf"):
            data = _read_steam_manifest(manifest)
            app_id = data.get("appid") or manifest.stem.removeprefix("appmanifest_")
            name = data.get("name")
            if not app_id or not name or _is_blacklisted_name(name):
                continue
            launch_uri = f"steam://rungameid/{app_id}"
            apps.append(
                ApplicationItem(
                    name=name,
                    path=launch_uri,
                    executable=launch_uri,
                    icon_path=_steam_icon_path(app_id, data),
                    category=infer_category(name, "steam game"),
                    visible_by_default=True,
                    installed_at=_mtime(manifest),
                    source_type="steam",
                )
            )
    return apps


def _steam_icon_path(app_id: str, manifest: dict[str, str]) -> str | None:
    steam_root = _steam_install_path()
    if steam_root is not None:
        icon_hash = manifest.get("clienticon") or manifest.get("icon")
        if icon_hash:
            icon_file = steam_root / "steam" / "games" / f"{icon_hash}.ico"
            if icon_file.exists():
                return str(icon_file)

        library_cache = steam_root / "appcache" / "librarycache" / app_id
        for name in ("library_600x900.jpg", "header.jpg", "logo.png"):
            candidate = library_cache / name
            if candidate.exists():
                return str(candidate)

        if library_cache.exists():
            for candidate in library_cache.glob("*.jpg"):
                return str(candidate)
            for candidate in library_cache.glob("*.png"):
                return str(candidate)
    return None


def _steam_libraries() -> list[Path]:
    roots: list[Path] = []
    steam_root = _steam_install_path()
    if steam_root is not None:
        roots.append(steam_root)
        library_file = steam_root / "steamapps" / "libraryfolders.vdf"
        try:
            text = library_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        for match in re.finditer(r'"path"\s+"([^"]+)"', text):
            roots.append(Path(match.group(1).replace("\\\\", "\\")))
    return list(dict.fromkeys(root for root in roots if root.exists()))


def _is_game_launch_uri(value: str) -> bool:
    normalized = value.casefold()
    return normalized.startswith("steam://rungameid/") or normalized.startswith("com.epicgames.launcher://")


def _steam_install_path() -> Path | None:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            value, _ = winreg.QueryValueEx(key, "SteamPath")
            path = Path(str(value))
            return path if path.exists() else None
    except OSError:
        default = Path(os.environ.get("ProgramFiles(x86)", "")) / "Steam"
        return default if default.exists() else None


def _read_steam_manifest(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return result
    for key, value in re.findall(r'"([^"]+)"\s+"([^"]*)"', text):
        result[key.casefold()] = value
    return result


def _scan_windows_registry() -> list["ApplicationItem"]:
    from models.app_model import ApplicationItem

    try:
        import winreg
    except ImportError:
        return []

    apps: list[ApplicationItem] = []
    locations = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    ]
    for hive, location in locations:
        try:
            with winreg.OpenKey(hive, location) as key:
                for index in range(winreg.QueryInfoKey(key)[0]):
                    subkey_name = winreg.EnumKey(key, index)
                    with winreg.OpenKey(key, subkey_name) as subkey:
                        value, _ = winreg.QueryValueEx(subkey, "")
                        path = str(value).strip('"')
                        app_path = Path(path)
                        if app_path.exists() and is_allowed_windows_app(app_path.stem, path, require_exe=True):
                            apps.append(
                                ApplicationItem(
                                    name=_clean_name(app_path.stem),
                                    path=path,
                                    icon_path=path,
                                    executable=path,
                                    category=infer_category(path),
                                    visible_by_default=True,
                                    installed_at=_mtime(Path(path)),
                                    source_type="registry",
                                )
                            )
        except OSError:
            continue
    return apps


def _scan_linux() -> list["ApplicationItem"]:
    from models.app_model import ApplicationItem

    apps: list[ApplicationItem] = []
    roots = [
        Path("/usr/share/applications"),
        Path("/usr/local/share/applications"),
        Path.home() / ".local" / "share" / "applications",
    ]
    for root in roots:
        if not root.exists():
            continue
        for desktop_file in root.glob("*.desktop"):
            entry = _read_desktop_entry(desktop_file)
            if not entry or entry.get("NoDisplay", "").casefold() == "true":
                continue
            name = entry.get("Name", desktop_file.stem)
            categories = entry.get("Categories", "")
            icon = entry.get("Icon")
            apps.append(
                ApplicationItem(
                    name=name,
                    path=str(desktop_file),
                    icon_path=icon,
                    executable=entry.get("Exec"),
                    category=infer_category(name, categories),
                    installed_at=_mtime(desktop_file),
                )
            )
    return apps


def _scan_macos() -> list["ApplicationItem"]:
    from models.app_model import ApplicationItem

    apps: list[ApplicationItem] = []
    roots = [Path("/Applications"), Path.home() / "Applications"]
    for root in roots:
        if not root.exists():
            continue
        for app_bundle in root.glob("*.app"):
            name = app_bundle.stem
            apps.append(
                ApplicationItem(
                    name=name,
                    path=str(app_bundle),
                    icon_path=str(app_bundle),
                    category=infer_category(name),
                    installed_at=_mtime(app_bundle),
                )
            )
    return apps


def _read_desktop_entry(path: Path) -> dict[str, str]:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    try:
        parser.read(path, encoding="utf-8")
    except (configparser.Error, UnicodeDecodeError):
        return {}
    if not parser.has_section("Desktop Entry"):
        return {}
    return dict(parser.items("Desktop Entry"))


def _desktop_exec_command(path: Path) -> list[str]:
    entry = _read_desktop_entry(path)
    command = entry.get("Exec", "")
    if not command:
        return []
    cleaned = [
        part
        for part in command.split()
        if not part.startswith("%")
    ]
    return cleaned


def _looks_like_uninstaller(path: Path) -> bool:
    name = path.name.casefold()
    return any(token in name for token in APP_BLACKLIST_WORDS)


def _is_blacklisted_name(name: str) -> bool:
    normalized = name.casefold()
    return any(token in normalized for token in APP_BLACKLIST_WORDS)


def _clean_name(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").strip().title()


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _fallback_apps() -> list["ApplicationItem"]:
    from models.app_model import ApplicationItem

    return [
        ApplicationItem("Terminal", "cmd.exe", category=infer_category("Terminal")),
        ApplicationItem("Settings", "ms-settings:", category=infer_category("Settings")),
        ApplicationItem("File Explorer", "explorer.exe", category=infer_category("File Explorer")),
    ]

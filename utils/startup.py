from __future__ import annotations

import os
import sys
from pathlib import Path


STARTUP_NAME = "MOON.lnk"


def _startup_folder() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup"


def _shortcut_path() -> Path:
    return _startup_folder() / STARTUP_NAME


def set_startup_enabled(enabled: bool) -> None:
    shortcut = _shortcut_path()

    if not enabled:
        if shortcut.exists():
            shortcut.unlink()
        return

    startup_folder = _startup_folder()
    startup_folder.mkdir(parents=True, exist_ok=True)

    target = Path(sys.executable).resolve()

    if target.suffix.lower() == ".exe":
        if getattr(sys, "frozen", False):
            arguments = ""
            working_directory = str(Path(sys.executable).parent)
        else:
            script = Path(sys.argv[0]).resolve()
            arguments = f'"{script}"'
            working_directory = str(script.parent)
    else:
        return

    try:
        import win32com.client
    except ImportError:
        return

    shell = win32com.client.Dispatch("WScript.Shell")
    link = shell.CreateShortcut(str(shortcut))
    link.TargetPath = str(target)
    link.Arguments = arguments
    link.WorkingDirectory = working_directory
    link.IconLocation = str(target)
    link.Save()
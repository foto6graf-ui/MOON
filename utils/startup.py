from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

if platform.system() == "Windows":
    import winreg


STARTUP_VALUE_NAME = "MOON"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _startup_command() -> str:
    executable = Path(sys.executable).resolve()
    if getattr(sys, "frozen", False):
        return f'"{executable}"'

    script = Path(sys.argv[0]).resolve()
    pythonw = executable.with_name("pythonw.exe")
    launcher = pythonw if pythonw.exists() else executable
    return f'"{launcher}" "{script}"'


def set_startup_enabled(enabled: bool) -> None:
    """Enable MOON at user logon without requiring administrator rights."""
    if platform.system() == "Darwin":
        import plistlib

        agent = Path.home() / "Library" / "LaunchAgents" / "com.moon.launchpad.plist"
        if enabled:
            executable = Path(sys.executable).resolve()
            command = [str(executable)] if getattr(sys, "frozen", False) else [str(executable), str(Path(sys.argv[0]).resolve())]
            agent.parent.mkdir(parents=True, exist_ok=True)
            agent.write_bytes(plistlib.dumps({
                "Label": "com.moon.launchpad",
                "ProgramArguments": command,
                "RunAtLoad": True,
                "KeepAlive": False,
            }))
        else:
            agent.unlink(missing_ok=True)
        return

    if platform.system() != "Windows":
        return
    access = winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, access) as key:
        if enabled:
            winreg.SetValueEx(key, STARTUP_VALUE_NAME, 0, winreg.REG_SZ, _startup_command())
        else:
            try:
                winreg.DeleteValue(key, STARTUP_VALUE_NAME)
            except FileNotFoundError:
                pass


def is_startup_enabled() -> bool:
    if platform.system() == "Darwin":
        return (Path.home() / "Library" / "LaunchAgents" / "com.moon.launchpad.plist").is_file()
    if platform.system() != "Windows":
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, STARTUP_VALUE_NAME)
    except FileNotFoundError:
        return False
    return os.path.normcase(value) == os.path.normcase(_startup_command())

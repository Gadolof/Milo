"""Raccourcis Windows : démarrage automatique à l'ouverture de session et menu Démarrer."""

import os
import sys
from pathlib import Path

import comtypes.client

from .config import BASE_DIR

_PROGRAMS = Path(os.environ.get("APPDATA", Path.home())) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
STARTUP_SHORTCUT = _PROGRAMS / "Startup" / "Milo.lnk"
MENU_SHORTCUT = _PROGRAMS / "Milo.lnk"


def default_shortcuts() -> list[Path]:
    return [STARTUP_SHORTCUT, MENU_SHORTCUT]


def _pythonw() -> Path:
    """pythonw : Milo tourne sans fenêtre de console à fermer par erreur."""
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return pythonw if pythonw.is_file() else Path(sys.executable)


def create_shortcuts(paths: list[Path] | None = None) -> list[Path]:
    shell = comtypes.client.CreateObject("WScript.Shell", dynamic=True)
    created = []
    for path in paths or default_shortcuts():
        path.parent.mkdir(parents=True, exist_ok=True)
        shortcut = shell.CreateShortcut(str(path))
        shortcut.TargetPath = str(_pythonw())
        shortcut.Arguments = "-m milo"
        shortcut.WorkingDirectory = str(BASE_DIR)
        shortcut.Description = "Milo, assistant vocal (Ctrl+Alt+M pour parler)"
        shortcut.Save()
        created.append(path)
    return created


def remove_shortcuts(paths: list[Path] | None = None) -> list[Path]:
    removed = []
    for path in paths or default_shortcuts():
        if path.is_file():
            path.unlink()
            removed.append(path)
    return removed

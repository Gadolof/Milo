"""Ouverture des pages de Paramètres Windows et lancement d'applications."""

import json
import logging
import os
import subprocess
from dataclasses import dataclass

from ..text import best_match, normalize

log = logging.getLogger(__name__)

SETTINGS_HOME = "ms-settings:"
SETTINGS_CUTOFF = 80
ALIAS_CUTOFF = 85
APP_CUTOFF = 85

# Entrées du menu Démarrer à ne jamais lancer par erreur.
_EXCLUDED = ("uninstall", "desinstall", "desinstaller")


def open_target(target: str) -> None:
    """ShellExecute : gère .exe du PATH, chemins, URL, ms-settings: et shell:."""
    os.startfile(target)


@dataclass
class Match:
    label: str   # nom prononcé dans la réponse
    target: str


class SettingsPages:
    def __init__(self, pages: dict[str, str]):
        # nom normalisé -> Match(nom tel qu'écrit, URI)
        self.pages = {normalize(k): Match(k, v) for k, v in pages.items()}

    def phrases(self) -> list[str]:
        return [m.label for m in self.pages.values()]

    def find(self, query: str) -> Match | None:
        """None si `query` est vide (page d'accueil) ou introuvable."""
        if not query:
            return None
        key = best_match(normalize(query), self.pages, SETTINGS_CUTOFF)
        return self.pages[key] if key else None


def load_start_apps() -> dict[str, str]:
    """Applications du menu Démarrer {nom: AppID}, classiques et Microsoft Store."""
    script = (
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
        "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, timeout=30, check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).stdout.decode("utf-8", errors="replace")
        rows = json.loads(out) if out.strip() else []
    except (OSError, subprocess.SubprocessError, ValueError):
        log.exception("Impossible de lister les applications du menu Démarrer")
        return {}
    if isinstance(rows, dict):
        rows = [rows]
    return {
        row["Name"]: row["AppID"]
        for row in rows
        if row.get("Name") and row.get("AppID")
        and not any(word in normalize(row["Name"]) for word in _EXCLUDED)
    }


class AppIndex:
    def __init__(self, aliases: dict[str, str], start_apps: dict[str, str]):
        # nom normalisé -> Match(nom affiché, cible)
        self.aliases = {normalize(k): Match(k, v) for k, v in aliases.items()}
        self.apps = {normalize(name): Match(name, f"shell:AppsFolder\\{app_id}")
                     for name, app_id in start_apps.items()}

    def phrases(self) -> list[str]:
        return [m.label for m in (*self.aliases.values(), *self.apps.values())]

    def find(self, query: str) -> Match | None:
        query = normalize(query)
        if not query:
            return None
        key = best_match(query, self.aliases, ALIAS_CUTOFF)
        if key:
            return self.aliases[key]
        key = best_match(query, self.apps, APP_CUTOFF)
        return self.apps[key] if key else None

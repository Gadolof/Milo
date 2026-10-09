"""Modes enregistrés (« travail », « soir », « jeux »…) : un jeu de réglages à rappeler à la voix.

Chaque mode est stocké dans modes.json, modifiable à la main :
    {
      "soir": {"volume": 25, "muet": false, "luminosite": 30, "theme": "sombre",
               "applications": ["Spotify"]}
    }
Toutes les clés sont facultatives : un mode n'applique que ce qu'il contient.
"""

import json
import logging
from pathlib import Path

from .config import read_text
from .text import best_match, normalize

log = logging.getLogger(__name__)

CUTOFF = 80
# Pour enregistrer, presque exact : « soirée » ne doit pas écraser « soir ».
SAVE_CUTOFF = 90


class ModeStore:
    def __init__(self, path: Path):
        self.path = path
        self.modes: dict[str, dict] = {}
        if path.is_file():
            try:
                self.modes = json.loads(read_text(path))
            except ValueError:
                # On met le fichier de côté plutôt que de l'écraser au prochain enregistrement.
                backup = path.with_name(path.stem + ".illisible.json")
                path.replace(backup)
                log.exception("modes.json illisible, copié dans %s", backup)

    def _write(self) -> None:
        self.path.write_text(json.dumps(self.modes, ensure_ascii=False, indent=2), encoding="utf-8")

    def names(self) -> list[str]:
        return list(self.modes)

    def find(self, name: str, cutoff: float = CUTOFF) -> str | None:
        """Nom exact du mode le plus proche (« jeu » -> « jeux »), ou None."""
        by_key = {normalize(n): n for n in self.modes}
        key = best_match(normalize(name), by_key, cutoff)
        return by_key[key] if key else None

    def get(self, name: str) -> dict:
        return self.modes[name]

    def save(self, name: str, settings: dict) -> tuple[str, bool]:
        """Enregistre les réglages (en gardant les applis du mode). Renvoie (nom, créé ?)."""
        existing = self.find(name, SAVE_CUTOFF)
        created = existing is None
        if created:
            existing = name
            self.modes[name] = {"applications": []}
        self.modes[existing].update(settings)
        self._write()
        return existing, created

    def delete(self, name: str) -> None:
        del self.modes[name]
        self._write()

    def add_app(self, name: str, app: str) -> bool:
        apps = self.modes[name].setdefault("applications", [])
        if any(normalize(a) == normalize(app) for a in apps):
            return False
        apps.append(app)
        self._write()
        return True

    def remove_app(self, name: str, app: str) -> str | None:
        apps = self.modes[name].get("applications", [])
        by_key = {normalize(a): a for a in apps}
        key = best_match(normalize(app), by_key, CUTOFF)
        if not key:
            return None
        apps.remove(by_key[key])
        self._write()
        return by_key[key]


def describe(mode: dict) -> str:
    """« volume 25 pour cent, luminosité 30 pour cent, thème sombre, et ouverture de Spotify »."""
    parts = []
    if mode.get("muet"):
        parts.append("son coupé")
    elif "volume" in mode:
        parts.append(f"volume {mode['volume']} pour cent")
    if mode.get("luminosite") is not None:
        parts.append(f"luminosité {mode['luminosite']} pour cent")
    if mode.get("theme"):
        parts.append(f"thème {mode['theme']}")
    apps = mode.get("applications") or []
    if apps:
        parts.append("ouverture de " + _join(apps))
    return _join(parts) if parts else "aucun réglage"


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " et " + items[-1]

"""Chargement de config.toml (à côté du programme) et de milo/data/commandes.toml."""

import re
import sys
import tomllib
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = PACKAGE_DIR.parent

DEFAULTS = {
    "raccourci": "ctrl+alt+m",
    "modele": "models/vosk-model-small-fr-0.22",
    "micro": "",
    "pas": 10,
    "grammaire": True,
    "volume_minimum": 20,
    "modes": "modes.json",
    "recherche": "https://www.google.com/search?q={}",
    "voix": {"langue": "40C", "vitesse": 0, "volume": 100},
    "ecoute": {"delai_max": 8.0, "delai_silence": 4.0, "pause_fin": 0.7},
}


def _merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = _merge(base[key], value)
        else:
            merged[key] = value
    return merged


def read_text(path: Path) -> str:
    # utf-8-sig : le Bloc-notes ajoute parfois une marque BOM que tomllib et json refusent.
    return path.read_text(encoding="utf-8-sig")


def load_config(path: Path | None = None) -> dict:
    """Réglages fusionnés avec les valeurs par défaut.

    Un config.toml invalide ne doit pas empêcher Milo de démarrer : on prend les
    valeurs par défaut et `config["avertissement"]` explique le problème à voix haute.
    """
    path = path or BASE_DIR / "config.toml"
    override, warning = {}, None
    if path.is_file():
        try:
            override = tomllib.loads(read_text(path))
        except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
            line = getattr(exc, "lineno", None)
            where = f" à la ligne {line}" if line else ""
            warning = f"Le fichier config point toml contient une erreur{where}. J'utilise les réglages par défaut."
    config = _merge(DEFAULTS, override)
    config["avertissement"] = warning
    for key in ("modele", "modes"):
        path = Path(config[key])
        config[key] = path if path.is_absolute() else BASE_DIR / path
    return config


def save_voice_rate(rate: int, path: Path | None = None) -> None:
    """Retient la vitesse de la voix dans config.toml (sans toucher au reste du fichier)."""
    path = path or BASE_DIR / "config.toml"
    if not path.is_file():
        return
    text = read_text(path)
    updated, count = re.subn(r"(?m)^(vitesse\s*=\s*)-?\d+", rf"\g<1>{rate}", text, count=1)
    if count:
        path.write_text(updated, encoding="utf-8")


def load_commands() -> dict:
    data = tomllib.loads(read_text(PACKAGE_DIR / "data" / "commandes.toml"))
    return {"parametres": data.get("parametres", {}), "applications": data.get("applications", {})}

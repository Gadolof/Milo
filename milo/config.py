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


def load_config(path: Path | None = None) -> dict:
    path = path or BASE_DIR / "config.toml"
    config = DEFAULTS
    if path.is_file():
        with path.open("rb") as f:
            config = _merge(DEFAULTS, tomllib.load(f))
    for key in ("modele", "modes"):
        path = Path(config[key])
        config[key] = path if path.is_absolute() else BASE_DIR / path
    return config


def save_voice_rate(rate: int, path: Path | None = None) -> None:
    """Retient la vitesse de la voix dans config.toml (sans toucher au reste du fichier)."""
    path = path or BASE_DIR / "config.toml"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(r"(?m)^(vitesse\s*=\s*)-?\d+", rf"\g<1>{rate}", text, count=1)
    if count:
        path.write_text(updated, encoding="utf-8")


def load_commands() -> dict:
    with (PACKAGE_DIR / "data" / "commandes.toml").open("rb") as f:
        data = tomllib.load(f)
    return {"parametres": data.get("parametres", {}), "applications": data.get("applications", {})}

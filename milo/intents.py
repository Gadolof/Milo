"""Transforme une phrase reconnue en intention (nom + paramètres).

Module volontairement pur (pas d'appel système) pour être testé sans micro.
"""

import re
from dataclasses import dataclass, field

from .text import find_number, is_number_phrase, normalize, original_words

WAKE_WORD = "milo"


@dataclass
class Intent:
    name: str
    params: dict = field(default_factory=dict)


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text) is not None


_QUIT = r"^(?:milo )?(?:(?:au )?revoir|(?:quitte|quitter|arrete|arreter|ferme|fermer|eteins) milo)(?: milo)?$"
# Le décodeur libre entend souvent « Millau » pour « Milo ».
_WAKE_ALIASES = r"\b(?:millau|mylo|milot)\b"
_HELP = r"\b(?:aide|aider|commandes|que sais tu faire|qu est ce que tu sais faire|que peux tu faire)\b"
_SAY_AGAIN = r"^(?:repete|repetes|repeter|redis|redit|pardon|quoi|comment|qu as tu dit|tu peux repeter|peux tu repeter)$"
_SLOWER = r"\bparle\b.*\b(?:moins vite|plus lentement|lentement|doucement)\b|^(?:moins vite|plus lentement)$"
_FASTER = r"\bparle\b.*\b(?:plus vite|plus rapidement|vite)\b|^(?:plus vite|plus rapidement)$"
_PING = r"^(?:(?:tu es|es tu|est|t es) (?:la|pret)|tu m entends|tu m ecoutes|test|coucou|bonjour|salut)$"

_UNMUTE = r"\b(?:remets?|remettre|retablis|retablir|reactive|reactiver)\b.*\bson\b|\b(?:enleve|retire|desactive|quitte)\b.*\bsourdine\b"
_MUTE = r"\b(?:coupe|couper|sourdine|silence|mute)\b"

_SETTINGS = r"\b(?:parametres?|reglages?|configuration)\b"
_BRIGHTNESS = r"\b(?:luminosite|lumiere|eclairage)\b|\bplus (?:clair|sombre)\b|\b(?:eclaircis|assombris)\b"
_VOLUME = r"\b(?:volume|son)\b|\b(?:plus|moins) fort\b"
_THEME = r"\b(?:theme|modes?)\s+(?P<theme>sombre|clair)\b"

_UP = r"\b(?:monte|monter|augmente|augmenter|hausse|plus fort|plus clair|eclaircis)\b"
_DOWN = r"\b(?:baisse|baisser|diminue|diminuer|reduis|reduire|moins fort|plus sombre|assombris)\b"
_MAX = r"\b(?:maximum|max|a fond)\b"
_MIN = r"\b(?:minimum|min)\b"
_MORE = r"^(?:(?:un peu|encore) )?plus$"
_LESS = r"^(?:(?:un peu|encore) )?moins$"
_AGAIN = r"^(?:encore|recommence|pareil|continue)$"

_TIME = r"\b(?:quelle heure|l heure)\b"
_DATE = r"\b(?:quel jour|quelle date|la date|on est le combien)\b"
_BATTERY = r"\b(?:batterie|autonomie)\b"

# « modes? » partout : la grammaire confond souvent « mode » et « modes ».
_MODE_LIST = r"\b(?:liste|lister|quels sont|quelles sont|enumere|donne)\b.*\bmodes\b|\bmes modes?$"
_MODE_ADD = r"\b(?:ajoute|ajouter|rajoute)\s+(?P<app>.+?)\s+(?:au|aux|dans le|dans|a)\s+modes?\s+(?P<name>.+)$"
_MODE_REMOVE = (r"\b(?:retire|retirer|enleve|enlever|supprime|supprimer)\s+(?P<app>.+?)\s+"
                r"(?:du|de|des|dans le|dans)\s+modes?\s+(?P<name>.+)$")
_MODE_SAVE = (r"\b(?:enregistre|enregistrer|sauvegarde|sauvegarder|memorise|memoriser|cree|creer)\b"
              r".*?\bmodes?\s+(?P<name>.+)$")
_MODE_DELETE = r"\b(?:supprime|supprimer|efface|effacer|oublie|oublier)\b.*?\bmodes?\s+(?P<name>.+)$"
_MODE_DESCRIBE = (r"\b(?:decris|decrit|decrire|detaille|contient|qu y a t il|qu est ce qu il y a|c est quoi|que fait)\b"
                  r".*?\bmodes?\s+(?P<name>.+)$")
_MODE_ACTIVATE = r"\bmodes?\s+(?P<name>.+)$"

_SEARCH = r"\b(?:recherche|recherches|rechercher|cherche|chercher)\b\s*(?P<query>.*)$"
_CLOSE = r"^(?:ferme|fermer|fermez|quitte|quitter|tue)\s+(?P<rest>.+)$"
_LAUNCH = r"^(?:ouvre|ouvrir|ouvrez|lance|lancer|lancez|demarre|demarrer|execute|executer)\s+(?P<rest>.+)$"

_LEADING_FILLER = {"moi", "le", "la", "les", "l", "un", "une", "de", "du", "des", "d", "pour", "a", "au", "aux",
                   "mon", "ma", "mes", "ce", "cette", "application", "applications", "appli", "logiciel",
                   "programme"}
_SEARCH_FILLER = _LEADING_FILLER | {"sur", "internet", "web", "google", "une", "fais"}
_TRAILING_FILLER = r"\s+(?:s il te plait|s il vous plait|stp|svp|maintenant|merci)$"
_WINDOW = {"fenetre", "fenetre active"}


def _strip_filler(text: str, filler=_LEADING_FILLER) -> str:
    text = re.sub(_TRAILING_FILLER, "", text)
    words = text.split()
    while words and words[0] in filler:
        words.pop(0)
    return " ".join(words)


def _level_intent(prefix: str, text: str, step: int) -> Intent:
    """Intentions communes au volume et à la luminosité."""
    number = find_number(text)
    up, down = _has(_UP, text), _has(_DOWN, text)

    if _has(_MAX, text):
        return Intent(f"{prefix}_set", {"level": 100})
    if _has(_MIN, text):
        return Intent(f"{prefix}_set", {"level": 0})
    if up or down:
        if _has(r"\bcrans?\b", text):
            delta = (number or 1) * step
        else:
            delta = number if number is not None else step
        return Intent(f"{prefix}_change", {"delta": delta if up else -delta})
    if number is not None:
        return Intent(f"{prefix}_set", {"level": max(0, min(100, number))})
    return Intent(f"{prefix}_get")


def _mode_intent(raw: str, text: str) -> Intent | None:
    if _has(_MODE_LIST, text):
        return Intent("mode_list")
    for name, pattern in (("mode_add_app", _MODE_ADD), ("mode_remove_app", _MODE_REMOVE)):
        match = re.search(pattern, text)
        if match:
            mode = _strip_filler(match.group("name"))
            app = _strip_filler(match.group("app"))
            if mode and app:
                return Intent(name, {"name": original_words(raw, mode), "app": original_words(raw, app)})
    for name, pattern in (("mode_save", _MODE_SAVE), ("mode_delete", _MODE_DELETE),
                          ("mode_describe", _MODE_DESCRIBE)):
        match = re.search(pattern, text)
        if match and (mode := _strip_filler(match.group("name"))):
            return Intent(name, {"name": original_words(raw, mode)})
    match = re.search(_THEME, text)
    if match:
        return Intent("theme", {"theme": match.group("theme")})
    match = re.search(_MODE_ACTIVATE, text)
    if match and (mode := _strip_filler(match.group("name"))):
        return Intent("mode_activate", {"name": original_words(raw, mode)})
    return None


def parse(raw: str, step: int = 10) -> Intent:
    text = re.sub(_WAKE_ALIASES, WAKE_WORD, normalize(raw))
    if not text:
        return Intent("empty")

    if _has(_QUIT, text):
        return Intent("quit")

    # « Milo, volume à 40 » : on ignore le mot d'éveil en tête.
    if text.startswith(WAKE_WORD + " "):
        text = text[len(WAKE_WORD) + 1:]
    elif text == WAKE_WORD:
        return Intent("ping")

    if _has(_HELP, text):
        return Intent("help", {"topic": "modes"} if _has(r"\bmodes?\b", text) else {})
    if _has(_PING, text):
        return Intent("ping")
    if _has(_SAY_AGAIN, text):
        return Intent("say_again")
    if _has(_SLOWER, text):
        return Intent("voice_rate", {"delta": -2})
    if _has(_FASTER, text):
        return Intent("voice_rate", {"delta": 2})

    match = re.search(_SETTINGS, text)
    if match:
        return Intent("open_settings", {"page": _strip_filler(text[match.end():])})

    intent = _mode_intent(raw, text)
    if intent:
        return intent

    if _has(_UNMUTE, text):
        return Intent("unmute")
    if _has(_MUTE, text):
        return Intent("mute")

    match = re.search(_SEARCH, text)
    if match:
        query = _strip_filler(match.group("query"), _SEARCH_FILLER)
        return Intent("search", {"query": original_words(raw, query) if query else ""})

    match = re.match(_CLOSE, text)
    if match:
        target = _strip_filler(match.group("rest"))
        if target in _WINDOW:
            return Intent("close_window")
        if target:
            return Intent("close_app", {"name": original_words(raw, target)})

    if _has(_TIME, text):
        return Intent("time")
    if _has(_DATE, text):
        return Intent("date")
    if _has(_BATTERY, text):
        return Intent("battery")

    if _has(_BRIGHTNESS, text):
        return _level_intent("brightness", text, step)
    if _has(_VOLUME, text):
        return _level_intent("volume", text, step)

    # Suites de réglage : « cinquante pour cent », « plus », « encore »
    # s'appliquent au dernier réglage utilisé (volume par défaut).
    if is_number_phrase(text):
        return Intent("level_set", {"level": max(0, min(100, find_number(text)))})
    if _has(_MORE, text):
        return Intent("level_change", {"delta": step})
    if _has(_LESS, text):
        return Intent("level_change", {"delta": -step})
    if _has(_AGAIN, text):
        return Intent("repeat")

    match = re.match(_LAUNCH, text)
    if match:
        # « ouvre chrome et fais… » : on ne garde que le nom.
        name = _strip_filler(match.group("rest").split(" et ")[0])
        if name:
            return Intent("launch_app", {"name": original_words(raw, name)})

    return Intent("unknown", {"text": raw})

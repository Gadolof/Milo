"""Normalisation du texte reconnu et lecture des nombres écrits en toutes lettres."""

import re
import unicodedata

from rapidfuzz import fuzz

_UNITS = {
    "zero": 0, "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4,
    "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
    "onze": 11, "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15,
    "seize": 16, "vingt": 20, "vingts": 20, "trente": 30, "quarante": 40,
    "cinquante": 50, "soixante": 60, "cent": 100,
}


def normalize(text: str) -> str:
    """Minuscules, sans accents, sans ponctuation, espaces simples."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9%]+", " ", text)
    return " ".join(text.split())


_TENS = {"vingt", "vingts", "trente", "quarante", "cinquante", "soixante"}


def _is_number_word(token: str) -> bool:
    return token.isdigit() or token in _UNITS


def is_number_phrase(text: str) -> bool:
    """« cinquante pour cent », « à quarante » : rien d'autre qu'un nombre."""
    words = [w for w in text.split() if w not in ("a", "au", "pour", "%", "et")]
    if not words or not all(_is_number_word(w) for w in words):
        return False
    # « un », « deux » seuls sont trop souvent du bruit mal reconnu.
    return "pour cent" in text or "%" in text or (find_number(text) or 0) >= 10


def find_number(text: str) -> int | None:
    """Premier nombre du texte normalisé, en chiffres ou en lettres (0 à 100).

    « quatre vingt dix sept » -> 97, « soixante et onze » -> 71, « 40 » -> 40.
    """
    tokens = text.split()
    for i, token in enumerate(tokens):
        if token.isdigit():
            return int(token)
        if token not in _UNITS:
            continue
        total = 0
        j = i
        while j < len(tokens):
            tok = tokens[j]
            nxt = tokens[j + 1] if j + 1 < len(tokens) else ""
            if tok == "quatre" and nxt in ("vingt", "vingts"):
                total += 80
                j += 2
            elif total == 0 and _UNITS.get(tok, 99) < 10 and nxt in _TENS:
                # « un cinquante » n'existe pas en français : c'est « à cinquante » mal entendu.
                j += 1
            elif tok in _UNITS:
                total += _UNITS[tok]
                j += 1
            elif tok == "et" and total and _is_number_word(nxt):
                j += 1
            else:
                break
        return total
    return None


_WORD_CUTOFF = 85
_ALL_WORDS_SCORE = 90


def similarity(query: str, candidate: str) -> float:
    """Score 0-100, volontairement strict : mieux vaut « pas trouvé » qu'une
    mauvaise appli ouverte sans que l'utilisateur puisse le voir."""
    # Vosk coupe parfois les noms (« fire fox ») : on compare aussi sans espaces.
    score = max(
        fuzz.ratio(query, candidate),
        fuzz.ratio(query.replace(" ", ""), candidate.replace(" ", "")),
    )
    # Chaque mot dit se retrouve dans le nom : « chrome » -> « google chrome ».
    words = candidate.split()
    if all(any(fuzz.ratio(q, w) >= _WORD_CUTOFF for w in words) for q in query.split()):
        score = max(score, _ALL_WORDS_SCORE)
    return score


def best_match(query: str, candidates, cutoff: float) -> str | None:
    """Candidat (déjà normalisé) le plus proche de `query`, ou None sous le seuil.

    À score égal, on préfère le candidat le plus court : « word » doit donner
    « word » plutôt que « wordpad ».
    """
    best, best_key = None, None
    for candidate in candidates:
        score = similarity(query, candidate)
        if score < cutoff:
            continue
        key = (score, -len(candidate))
        if best_key is None or key > best_key:
            best, best_key = candidate, key
    return best


def original_words(raw: str, fragment: str) -> str:
    """Retrouve dans `raw` les mots d'origine (accents compris) d'un fragment normalisé.

    original_words("Active le mode Réunion", "reunion") -> "réunion".
    """
    target = fragment.split()
    tokens = re.findall(r"[^\W_]+", raw.lower())
    norm = [normalize(t) for t in tokens]
    for i in range(len(norm) - len(target) + 1):
        if norm[i:i + len(target)] == target:
            return " ".join(tokens[i:i + len(target)])
    return fragment

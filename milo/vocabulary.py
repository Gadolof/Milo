"""Vocabulaire de la grammaire restreinte Vosk.

Limiter le décodeur aux mots des commandes évite les confusions du petit
modèle (« le son » -> « leçon », « Milo » -> « Millau »). Les mots inconnus du
modèle sont simplement ignorés par Vosk : on peut donc en mettre trop.
Les mots doivent garder accents, traits d'union et apostrophes, comme Vosk les écrit.
"""

COMMAND_WORDS = """
milo le la les de du des à au sur un une et moi pour d'un
est quel quelle il est-il s'il te plaît tu sais faire peux que qu'est-ce ce
mets mettre met règle régler monte monter augmente augmenter hausse baisse baisser
diminue diminuer réduis réduire plus moins fort cran crans maximum minimum max fond
volume son coupe couper sourdine silence remets remettre rétablis réactive enlève retire
luminosité lumière éclairage écran l'écran clair sombre éclaircis assombris
ouvre ouvrir ouvrez lance lancer lancez démarre démarrer exécute
paramètres paramètre réglages réglage configuration
heure l'heure jour date on combien sommes sommes-nous nous aujourd'hui batterie niveau autonomie
aide commandes au revoir quitte quitter arrête ferme fermer fermez éteins tue
mode modes thème enregistre enregistrer sauvegarde mémorise crée créer active activer passe
supprime efface oublie ajoute retire enlève décris liste quelles mes mon ma
travail soir jeux jeu nuit matin film films cinéma lecture réunion musique détente présentation
fenêtre cette application l'application appli logiciel programme
recherche rechercher cherche chercher fais internet web
es-tu tu es là prêt m'entends encore pareil
parle lentement vite rapidement doucement répète redis pardon quoi comment
""".split()

_UNITS = ["zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf",
          "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize"]
_TENS = {20: "vingt", 30: "trente", 40: "quarante", 50: "cinquante", 60: "soixante"}


def french_number(n: int) -> str:
    """Orthographe traditionnelle de 0 à 100 : 21 « vingt et un », 97 « quatre-vingt-dix-sept »."""
    if n <= 16:
        return _UNITS[n]
    if n < 20:
        return "dix-" + _UNITS[n - 10]
    if n == 100:
        return "cent"
    if n < 70:
        tens, unit = divmod(n, 10)
        base = _TENS[tens * 10]
        if unit == 0:
            return base
        return f"{base} et un" if unit == 1 else f"{base}-{_UNITS[unit]}"
    if n < 80:
        return "soixante et onze" if n == 71 else "soixante-" + french_number(n - 60)
    if n == 80:
        return "quatre-vingts"
    return "quatre-vingt-" + french_number(n - 80)


_VOWELS = "aeiouyéèêàâîôûh"


def build_grammar(phrases) -> list[str]:
    """Liste de mots pour KaldiRecognizer, à partir des commandes et des noms d'applis."""
    words = set(COMMAND_WORDS)
    for n in range(101):
        words.update(french_number(n).split())
    for phrase in phrases:
        words.update(phrase.lower().replace("’", "'").split())
    # Élisions : « l'écran », « d'accessibilité », « l'explorateur »…
    words.update(f"{article}'{w}" for w in list(words) if w[0] in _VOWELS for article in "ld")
    # Homophones qui font plus de mal que de bien (« le son » -> « le sons »).
    words -= {"sons", "aux", "quels", "dans"}
    return sorted(words) + ["[unk]"]


def fix_constrained(text: str) -> str:
    """Corrige la confusion « de » / « deux » du décodeur à grammaire.

    « deux » n'est gardé qu'en fin de phrase ou devant « cran(s) » / « pour » :
    « niveau deux batterie » -> « niveau de batterie », « deux vingt » -> « de vingt ».
    """
    words = text.split()
    for i, word in enumerate(words):
        nxt = words[i + 1] if i + 1 < len(words) else None
        if word == "deux" and nxt not in (None, "cran", "crans", "pour"):
            words[i] = "de"
    return " ".join(words)

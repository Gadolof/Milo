import pytest

from milo.intents import parse
from milo.text import find_number, normalize


@pytest.mark.parametrize("text, expected", [
    ("quarante", 40),
    ("vingt et un", 21),
    ("soixante dix", 70),
    ("soixante et onze", 71),
    ("quatre vingt", 80),
    ("quatre-vingt-dix-sept", 97),
    ("dix sept", 17),
    ("cent", 100),
    ("zéro", 0),
    ("volume à 35", 35),
    ("rien du tout", None),
])
def test_find_number(text, expected):
    assert find_number(normalize(text)) == expected


def test_normalize():
    assert normalize("Ouvre l'Éditeur, s'il-te-plaît !") == "ouvre l editeur s il te plait"


@pytest.mark.parametrize("text, name, params", [
    # volume
    ("volume à quarante", "volume_set", {"level": 40}),
    ("Milo, mets le son à cinquante", "volume_set", {"level": 50}),
    ("règle le volume sur vingt cinq", "volume_set", {"level": 25}),
    ("monte le son", "volume_change", {"delta": 10}),
    ("augmente le volume de vingt", "volume_change", {"delta": 20}),
    ("baisse le son d'un cran", "volume_change", {"delta": -10}),
    ("baisse le son de deux crans", "volume_change", {"delta": -20}),
    ("plus fort", "volume_change", {"delta": 10}),
    ("moins fort", "volume_change", {"delta": -10}),
    ("volume au maximum", "volume_set", {"level": 100}),
    ("mets le son à fond", "volume_set", {"level": 100}),
    ("quel est le volume", "volume_get", {}),
    ("coupe le son", "mute", {}),
    ("sourdine", "mute", {}),
    ("remets le son", "unmute", {}),
    ("enlève la sourdine", "unmute", {}),
    # luminosité
    ("luminosité à soixante dix", "brightness_set", {"level": 70}),
    ("baisse la luminosité", "brightness_change", {"delta": -10}),
    ("plus clair", "brightness_change", {"delta": 10}),
    ("assombris l'écran", "brightness_change", {"delta": -10}),
    ("quelle est la luminosité", "brightness_get", {}),
    # paramètres
    ("ouvre les paramètres du bluetooth", "open_settings", {"page": "bluetooth"}),
    ("paramètres son", "open_settings", {"page": "son"}),
    ("va dans les réglages wifi", "open_settings", {"page": "wifi"}),
    ("ouvre les paramètres", "open_settings", {"page": ""}),
    # applications
    ("ouvre le bloc-notes", "launch_app", {"name": "bloc notes"}),
    ("lance moi firefox", "launch_app", {"name": "firefox"}),
    ("démarre Word", "launch_app", {"name": "word"}),
    # infos
    ("quelle heure est-il", "time", {}),
    ("on est quel jour", "date", {}),
    ("niveau de batterie", "battery", {}),
    ("aide", "help", {}),
    ("aide sur les modes", "help", {"topic": "modes"}),
    ("qu'est-ce que tu sais faire", "help", {}),
    # divers
    ("au revoir Milo", "quit", {}),
    ("quitte Milo", "quit", {}),
    ("revoir milo", "quit", {}),
    ("au revoir Millau", "quit", {}),
    ("", "empty", {}),
    ("milo", "ping", {}),
    # cas réels d'utilisation
    ("ouvre chrome et fait une recherche sur la météo à Paris", "search", {"query": "météo à paris"}),
    ("recherche sur internet le prix du pain", "search", {"query": "prix du pain"}),
    ("cherche", "search", {"query": ""}),
    ("ferme l'application Google Chrome", "close_app", {"name": "google chrome"}),
    ("ferme la fenêtre", "close_window", {}),
    ("ferme Milo", "quit", {}),
    ("son un cinquante pour cent", "volume_set", {"level": 50}),
    ("cinquante pour cent", "level_set", {"level": 50}),
    ("un", "unknown", {"text": "un"}),
    ("plus", "level_change", {"delta": 10}),
    ("un peu moins", "level_change", {"delta": -10}),
    ("encore", "repeat", {}),
    ("Milo, es-tu prêt ?", "ping", {}),
    # modes
    ("enregistre le mode soir", "mode_save", {"name": "soir"}),
    ("crée un mode jeux s'il te plaît", "mode_save", {"name": "jeux"}),
    ("enregistre le mode silence", "mode_save", {"name": "silence"}),
    ("active le mode Réunion", "mode_activate", {"name": "réunion"}),
    ("passe en mode travail", "mode_activate", {"name": "travail"}),
    ("lance le mode jeux", "mode_activate", {"name": "jeux"}),
    ("mode jeux", "mode_activate", {"name": "jeux"}),
    ("ajoute Steam au mode jeux", "mode_add_app", {"name": "jeux", "app": "steam"}),
    ("retire Steam du mode jeux", "mode_remove_app", {"name": "jeux", "app": "steam"}),
    ("supprime le mode jeux", "mode_delete", {"name": "jeux"}),
    ("décris le mode soir", "mode_describe", {"name": "soir"}),
    ("quels sont mes modes", "mode_list", {}),
    ("mode sombre", "theme", {"theme": "sombre"}),
    ("passe en thème clair", "theme", {"theme": "clair"}),
    ("paramètres mode avion", "open_settings", {"page": "mode avion"}),
    ("ouvre l'application calculatrice", "launch_app", {"name": "calculatrice"}),
])
def test_parse(text, name, params):
    intent = parse(text)
    assert (intent.name, intent.params) == (name, params)


def test_unknown_keeps_raw_text():
    assert parse("raconte une blague").params == {"text": "raconte une blague"}


def test_step_is_configurable():
    assert parse("monte le son", step=5).params == {"delta": 5}

import pytest

from milo import assistant as assistant_module
from milo.actions.launcher import AppIndex, SettingsPages
from milo.actions.windows import Window
from milo.assistant import Assistant
from milo.modes import ModeStore


class FakeSystem:
    """Remplace volume, luminosité, thème, fenêtres et lancements : aucun effet réel."""

    def __init__(self):
        self.volume, self.muted, self.brightness, self.theme = 40, False, 50, "clair"
        self.opened, self.closed = [], []
        self.windows = [Window(1, "Gadolof - Google Chrome", "chrome"), Window(2, "Document1 - Word", "winword")]

    def install(self, mp):
        a = assistant_module
        mp.setattr(a.audio, "get_volume", lambda: self.volume)
        mp.setattr(a.audio, "set_volume", self._set_volume)
        mp.setattr(a.audio, "change_volume", lambda d: self._set_volume(self.volume + d))
        mp.setattr(a.audio, "is_muted", lambda: self.muted)
        mp.setattr(a.audio, "set_mute", lambda m: setattr(self, "muted", m))
        mp.setattr(a.display, "get_brightness", lambda: self.brightness)
        mp.setattr(a.display, "set_brightness", self._set_brightness)
        mp.setattr(a.display, "change_brightness", lambda d: self._set_brightness(self.brightness + d))
        mp.setattr(a.theme, "get_theme", lambda: self.theme)
        mp.setattr(a.theme, "set_theme", lambda t: setattr(self, "theme", t))
        mp.setattr(a, "open_target", self.opened.append)
        mp.setattr(a.windows, "list_windows", lambda: self.windows)
        mp.setattr(a.windows, "close", self.closed.append)

    def _set_volume(self, v):
        self.volume = max(0, min(100, v))
        return self.volume

    def _set_brightness(self, v):
        self.brightness = max(0, min(100, v))
        return self.brightness


@pytest.fixture
def system(monkeypatch):
    fake = FakeSystem()
    fake.install(monkeypatch)
    return fake


@pytest.fixture
def milo(tmp_path):
    return Assistant(SettingsPages({"bluetooth": "ms-settings:bluetooth"}),
                     AppIndex({"bloc-notes": "notepad.exe"}, {"Word": "Word", "Steam": "Steam"}),
                     ModeStore(tmp_path / "modes.json"))


def say(milo, *candidates):
    return milo.handle(list(candidates))[0]


# --- choix de la transcription ---------------------------------------------

def test_constrained_transcription_wins(milo):
    assert milo.interpret(["ouvre word", "rouvroy horde"])[0] == "ouvre word"


def test_unknown_word_falls_back_to_free_transcription(milo):
    assert milo.interpret(["ouvre les paramètres [unk]", "ouvre les paramètres bluetooth"])[0] == \
        "ouvre les paramètres bluetooth"


def test_app_must_exist_to_win(milo):
    # La grammaire a forcé « spotify » en « wifi » : pas d'appli, on prend la suite.
    assert milo.interpret(["ouvre wifi", "ouvre le bloc-notes"])[0] == "ouvre le bloc-notes"


def test_nothing_usable_keeps_free_text_for_the_answer(milo):
    text, intent = milo.interpret(["[unk]", "raconte une blague"])
    assert (text, intent.name) == ("raconte une blague", "unknown")


def test_silence(milo):
    assert milo.interpret(["", ""])[1].name == "empty"


def test_quit_and_failed_launch_answers(milo):
    assert milo.handle(["au revoir milo"]) == ("Au revoir.", True)
    assert say(milo, "ouvre photoshop") == "Je n'ai pas trouvé l'application photoshop."


def test_long_gibberish_is_not_read_back(milo):
    # Cas réel : une télé captée par le micro.
    assert say(milo, "[unk]", "le objets rétorsion contre vingt-neuf douze bodyboard hébraïque") == \
        "Je n'ai pas compris. Dites aide pour connaître les commandes."


def test_say_again_repeats_last_answer(milo, system):
    assert say(milo, "répète") == "Je n'ai encore rien dit."
    say(milo, "volume à trente")
    assert say(milo, "pardon") == "Volume à 30 pour cent."
    assert say(milo, "répète") == "Volume à 30 pour cent."


def test_voice_rate(milo):
    assert say(milo, "parle plus lentement") == "Je ne peux pas changer ma vitesse."
    rate = [0]

    def change(delta):
        rate[0] = max(-10, min(10, rate[0] + delta))
        return rate[0]

    milo.change_voice_rate = change
    assert say(milo, "parle plus lentement") == "D'accord, je parle plus lentement."
    assert rate == [-2]
    rate[0] = 9
    assert say(milo, "parle plus vite") == "Je parle déjà aussi vite que possible."


def test_bare_app_name_gets_a_hint(milo):
    assert say(milo, "word") == "Je n'ai pas compris. Pour ouvrir Word, dites : ouvre Word."


# --- réglages enchaînés ------------------------------------------------------

def test_bare_percentage_and_repeat_follow_last_setting(milo, system):
    assert say(milo, "cinquante pour cent") == "Volume à 50 pour cent."
    say(milo, "luminosité à trente")
    assert say(milo, "soixante pour cent") == "Luminosité à 60 pour cent."
    assert say(milo, "plus") == "Luminosité à 70 pour cent."
    assert say(milo, "baisse le son de vingt") == "Volume à 30 pour cent."
    assert say(milo, "encore") == "Volume à 10 pour cent."


def test_misheard_a_is_not_a_number(milo, system):
    # Cas réel : « son à cinquante pour cent » entendu « son un cinquante pour cent ».
    assert say(milo, "son un cinquante pour cent") == "Volume à 50 pour cent."


# --- modes ------------------------------------------------------------------

def test_mode_save_activate_describe(milo, system):
    system.volume, system.brightness, system.theme = 20, 30, "sombre"
    assert say(milo, "enregistre le mode soir") == \
        "Mode soir enregistré : volume 20 pour cent, luminosité 30 pour cent et thème sombre."
    system.volume, system.brightness, system.theme = 80, 90, "clair"
    assert say(milo, "active le mode soir") == \
        "Mode soir activé : volume 20 pour cent, luminosité 30 pour cent et thème sombre."
    assert (system.volume, system.brightness, system.theme) == (20, 30, "sombre")
    assert say(milo, "décris le mode soir") == \
        "Mode soir : volume 20 pour cent, luminosité 30 pour cent et thème sombre."
    assert say(milo, "enregistre le mode soir").startswith("Mode soir mis à jour")


def test_mode_with_sound_off(milo, system):
    system.muted = True
    assert say(milo, "enregistre le mode réunion").startswith("Mode réunion enregistré : son coupé")
    system.muted = False
    say(milo, "active le mode réunion")
    assert system.muted


def test_mode_apps(milo, system):
    say(milo, "enregistre le mode jeux")
    assert say(milo, "ajoute steam au mode jeux") == "Le mode jeux ouvrira aussi Steam."
    assert say(milo, "ajoute steam au mode jeux") == "Steam est déjà dans le mode jeux."
    say(milo, "passe en mode jeu")  # « jeu » retrouve « jeux »
    assert system.opened == ["shell:AppsFolder\\Steam"]
    assert say(milo, "retire steam du mode jeux") == "Le mode jeux n'ouvrira plus Steam."


def test_similar_name_does_not_overwrite_mode(milo, system):
    say(milo, "enregistre le mode soir")
    assert say(milo, "enregistre le mode soirée").startswith("Mode soirée enregistré")
    assert milo.modes.names() == ["soir", "soirée"]
    assert say(milo, "enregistre le mode soir").startswith("Mode soir mis à jour")


def test_mode_list_and_delete(milo, system):
    assert say(milo, "quels sont mes modes").startswith("Vous n'avez encore aucun mode")
    say(milo, "enregistre le mode travail")
    say(milo, "enregistre le mode réunion")
    assert say(milo, "quels sont mes modes") == "Vous avez 2 modes : travail et réunion."
    assert say(milo, "supprime le mode travail") == "Mode travail supprimé."
    assert milo.modes.names() == ["réunion"]


def test_unknown_mode(milo, system):
    assert say(milo, "active le mode film").startswith("Le mode film n'existe pas encore")
    say(milo, "enregistre le mode soir")
    assert say(milo, "active le mode film") == "Je ne connais pas le mode film. Vos modes sont : soir."


def test_modes_are_saved_to_disk(milo, system, tmp_path):
    say(milo, "enregistre le mode soir")
    assert ModeStore(tmp_path / "modes.json").names() == ["soir"]


def test_saving_a_mode_updates_vocabulary(milo, system):
    calls = []
    milo.on_vocabulary_change = lambda: calls.append(1)
    say(milo, "enregistre le mode soir")
    assert calls and "soir" in milo.vocabulary()


# --- fenêtres et recherche ----------------------------------------------------

def test_close_app(milo, system):
    assert say(milo, "ferme google chrome") == "Je ferme Google Chrome."
    assert [w.hwnd for w in system.closed] == [1]
    assert say(milo, "ferme word") == "Je ferme Word."


def test_close_app_not_open(milo, system):
    assert say(milo, "ferme steam") == "Je ne trouve pas de fenêtre ouverte pour steam."
    assert system.closed == []


def test_close_prefers_transcription_with_open_window(milo, system):
    # Cas réel : grammaire « ferme chrome », libre « sperme chrome ».
    assert milo.interpret(["ferme chrome", "sperme chrome"])[1].name == "close_app"


def test_search(milo, system):
    assert say(milo, "ouvre chrome et fais une recherche sur la météo à Paris") == "Je recherche météo à paris."
    assert system.opened == ["https://www.google.com/search?q=m%C3%A9t%C3%A9o+%C3%A0+paris"]

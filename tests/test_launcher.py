import pytest

from milo.actions.launcher import AppIndex, SettingsPages
from milo.config import load_commands

START_APPS = {
    "Firefox": "308046B0AF4A39CB",
    "Google Chrome": "Chrome",
    "Word": "Microsoft.Office.WINWORD.EXE.15",
    "WordPad": "Microsoft.Windows.WordPad",
    "Visual Studio Code": "Microsoft.VisualStudioCode",
    "Calculatrice": "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App",
    "Photos": "Microsoft.Windows.Photos_8wekyb3d8bbwe!App",
    "Spore": "Spore",
}


@pytest.fixture
def apps():
    return AppIndex(load_commands()["applications"], START_APPS)


@pytest.fixture
def settings():
    return SettingsPages(load_commands()["parametres"])


@pytest.mark.parametrize("query, label, target", [
    ("bloc notes", "bloc-notes", "notepad.exe"),
    ("bloc note", "bloc-notes", "notepad.exe"),
    ("firefox", "Firefox", "shell:AppsFolder\\308046B0AF4A39CB"),
    ("fire fox", "Firefox", "shell:AppsFolder\\308046B0AF4A39CB"),
    ("chrome", "Google Chrome", "shell:AppsFolder\\Chrome"),
    ("word", "Word", "shell:AppsFolder\\Microsoft.Office.WINWORD.EXE.15"),
    ("visual studio code", "Visual Studio Code", "shell:AppsFolder\\Microsoft.VisualStudioCode"),
])
def test_app_found(apps, query, label, target):
    match = apps.find(query)
    assert (match.label, match.target) == (label, target)


def test_alias_wins_over_start_menu(apps):
    assert apps.find("calculatrice").target == "calc.exe"


@pytest.mark.parametrize("query", ["photoshop", "sportif faille", "spotify", ""])
def test_app_not_found(apps, query):
    # Faux positifs constatés : « photoshop » ouvrait Photos, « sportif faille » Spore.
    assert apps.find(query) is None


@pytest.mark.parametrize("query, target", [
    ("bluetooth", "ms-settings:bluetooth"),
    ("wi-fi", "ms-settings:network-wifi"),
    ("son", "ms-settings:sound"),
    ("mise à jour", "ms-settings:windowsupdate"),
    ("narrateur", "ms-settings:easeofaccess-narrator"),
])
def test_settings_page(settings, query, target):
    assert settings.find(query).target == target


def test_settings_unknown_or_empty(settings):
    assert settings.find("") is None
    assert settings.find("xylophone") is None


def test_every_settings_target_is_an_uri():
    for target in load_commands()["parametres"].values():
        assert ":" in target

from milo.config import DEFAULTS, load_config, save_voice_rate
from milo.modes import ModeStore

BOM = "﻿"


def test_config_with_bom_is_read(tmp_path):
    # Le Bloc-notes enregistre parfois avec une marque BOM.
    path = tmp_path / "config.toml"
    path.write_text(BOM + 'raccourci = "ctrl+alt+f12"\n', encoding="utf-8")
    config = load_config(path)
    assert config["raccourci"] == "ctrl+alt+f12"
    assert config["avertissement"] is None


def test_invalid_config_falls_back_to_defaults_with_spoken_warning(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('pas = 10\nraccourci = ctrl+alt+m\n', encoding="utf-8")
    config = load_config(path)
    assert config["raccourci"] == DEFAULTS["raccourci"]
    assert config["avertissement"].startswith("Le fichier config point toml contient une erreur")


def test_defaults_are_not_mutated(tmp_path):
    load_config(tmp_path / "absent.toml")
    assert DEFAULTS["modele"] == "models/vosk-model-small-fr-0.22"


def test_save_voice_rate_keeps_the_rest(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(BOM + '# ma config\n[voix]\nvitesse = 0  # lent\nvolume = 80\n', encoding="utf-8")
    save_voice_rate(-4, path)
    assert path.read_text(encoding="utf-8") == '# ma config\n[voix]\nvitesse = -4  # lent\nvolume = 80\n'


def test_modes_with_bom(tmp_path):
    path = tmp_path / "modes.json"
    path.write_text(BOM + '{"soir": {"volume": 20}}', encoding="utf-8")
    assert ModeStore(path).names() == ["soir"]


def test_unreadable_modes_file_is_set_aside_not_overwritten(tmp_path):
    path = tmp_path / "modes.json"
    path.write_text('{"soir": {"volume": 20,}}', encoding="utf-8")
    store = ModeStore(path)
    assert store.names() == []
    assert (tmp_path / "modes.illisible.json").read_text(encoding="utf-8") == '{"soir": {"volume": 20,}}'

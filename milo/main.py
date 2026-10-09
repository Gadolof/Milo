"""Point d'entrée : python -m milo [--commande TEXTE | --analyse TEXTE | --wav FICHIER | --micros]."""

import argparse
import ctypes
import logging
import os
import queue
import sys
import threading
from pathlib import Path

import comtypes

from . import hotkey
from .actions.launcher import AppIndex, SettingsPages, load_start_apps
from .assistant import Assistant
from .config import load_commands, load_config, save_voice_rate
from .feedback import Speaker, beep_end, beep_start
from .actions import audio
from .intents import parse
from .modes import ModeStore
from .vocabulary import build_grammar

log = logging.getLogger("milo")

_ERROR_ALREADY_EXISTS = 183

_SPOKEN_KEYS = {"ctrl": "Contrôle", "control": "Contrôle", "alt": "Alt", "shift": "Majuscule",
                "maj": "Majuscule", "win": "Windows", "space": "Espace", "espace": "Espace"}


def spoken_hotkey(spec: str) -> str:
    return " ".join(_SPOKEN_KEYS.get(k, k.upper()) for k in spec.lower().split("+"))


def setup_logging() -> None:
    log_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Milo"
    log_dir.mkdir(parents=True, exist_ok=True)
    handlers = [logging.FileHandler(log_dir / "milo.log", encoding="utf-8")]
    if sys.stderr:  # absent quand Milo est lancé par pythonw (démarrage automatique)
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s : %(message)s",
        handlers=handlers,
    )


def single_instance_lock():
    """Verrou système ; None si un autre Milo tourne déjà (démarrage auto + lancement manuel)."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, "Local\\Milo")
    if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        return None
    return handle


def build_assistant(config: dict) -> Assistant:
    commands = load_commands()
    return Assistant(
        SettingsPages(commands["parametres"]),
        AppIndex(commands["applications"], load_start_apps()),
        ModeStore(config["modes"]),
        step=config["pas"],
        search_url=config["recherche"],
    )


def build_listener(config: dict, assistant: Assistant):
    from .stt import Listener  # import tardif : Vosk est lent à charger
    grammar = None
    if config["grammaire"]:
        grammar = build_grammar(assistant.vocabulary())
    listener = Listener(config["modele"], device=config["micro"] or None, grammar=grammar)
    if grammar:
        assistant.on_vocabulary_change = lambda: listener.set_grammar(build_grammar(assistant.vocabulary()))
    return listener


def ensure_audible(minimum: int) -> str | None:
    """Une personne aveugle n'a aucun retour si le son est coupé ou presque nul."""
    if minimum <= 0:
        return None
    level, muted = audio.get_volume(), audio.is_muted()
    if level >= minimum and not muted:
        return None
    audio.set_volume(max(level, minimum))
    audio.set_mute(False)
    state = "coupé" if muted else "très bas"
    return f"Le volume était {state}, je l'ai mis à {audio.get_volume()} pour cent."


def run(config: dict) -> int:
    speaker = Speaker(config["voix"]["langue"], config["voix"]["vitesse"], config["voix"]["volume"])
    lock = single_instance_lock()  # gardé ouvert jusqu'à la fin du processus
    if lock is None:
        log.info("Milo tourne déjà, deuxième lancement ignoré")
        speaker.say(f"Milo est déjà lancé. Appuyez sur {spoken_hotkey(config['raccourci'])} pour parler.", wait=True)
        speaker.close()
        return 0
    assistant = build_assistant(config)
    try:
        listener = build_listener(config, assistant)
    except FileNotFoundError:
        speaker.say("Le modèle de reconnaissance vocale est introuvable. "
                    "Lancez le script de téléchargement du modèle.", wait=True)
        log.error("Modèle Vosk introuvable : %s", config["modele"])
        return 1

    def change_voice_rate(delta: int) -> int:
        rate = speaker.change_rate(delta)
        save_voice_rate(rate)
        return rate

    assistant.change_voice_rate = change_voice_rate

    stop = threading.Event()
    busy = threading.Event()
    requests: queue.Queue = queue.Queue()

    def worker() -> None:
        comtypes.CoInitialize()  # pycaw et WMI ont besoin de COM dans ce thread
        try:
            while not stop.is_set():
                requests.get()
                try:
                    beep_start()
                    ecoute = config["ecoute"]
                    candidates = listener.listen(ecoute["delai_max"], ecoute["delai_silence"], ecoute["pause_fin"])
                    beep_end()
                    response, quit_ = assistant.handle(candidates)
                    speaker.say(response, wait=quit_)
                    if quit_:
                        stop.set()
                except Exception:
                    log.exception("Erreur pendant l'écoute")
                    speaker.say("Désolé, une erreur est survenue.")
                finally:
                    busy.clear()
        finally:
            comtypes.CoUninitialize()

    def on_press() -> None:
        if busy.is_set():
            return
        busy.set()
        speaker.stop()
        requests.put(True)

    threading.Thread(target=worker, name="milo-ecoute", daemon=True).start()

    spoken = spoken_hotkey(config["raccourci"])

    def on_ready() -> None:
        for warning in (ensure_audible(config["volume_minimum"]), config.get("avertissement")):
            if warning:
                speaker.say(warning)
        speaker.say(f"Milo est prêt. Appuyez sur {spoken} pour parler.")

    try:
        hotkey.run_loop(config["raccourci"], on_press, stop.is_set, on_ready=on_ready)
    except hotkey.HotkeyInUse:
        log.error("Raccourci déjà utilisé : %s", config["raccourci"])
        speaker.say(f"Le raccourci {spoken} est déjà utilisé par un autre programme. "
                    "Choisissez-en un autre dans le fichier config point toml.", wait=True)
        return 1
    except hotkey.HotkeyError as exc:
        log.error("%s", exc)
        speaker.say("Le raccourci clavier du fichier de configuration est invalide.", wait=True)
        return 1
    except KeyboardInterrupt:
        pass
    finally:
        speaker.close()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="milo", description="Assistant vocal Windows.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--commande", metavar="TEXTE", help="exécute une commande écrite, sans micro")
    group.add_argument("--analyse", metavar="TEXTE", help="affiche l'intention reconnue, sans rien exécuter")
    group.add_argument("--wav", metavar="FICHIER", type=Path, help="transcrit un fichier WAV et affiche l'intention")
    group.add_argument("--micros", action="store_true", help="liste les micros disponibles")
    group.add_argument("--installer-raccourcis", action="store_true",
                       help="démarrage automatique à l'ouverture de session + entrée du menu Démarrer")
    group.add_argument("--retirer-raccourcis", action="store_true", help="supprime ces raccourcis")
    args = parser.parse_args(argv)

    if sys.stdout and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    if args.installer_raccourcis or args.retirer_raccourcis:
        from . import install
        if args.installer_raccourcis:
            for path in install.create_shortcuts():
                print(f"Raccourci créé : {path}")
        else:
            removed = install.remove_shortcuts()
            print("\n".join(f"Raccourci supprimé : {p}" for p in removed) or "Aucun raccourci à supprimer.")
        return 0

    config = load_config()

    if args.analyse:
        intent = parse(args.analyse, config["pas"])
        print(intent.name, intent.params)
        return 0
    if args.micros:
        import sounddevice as sd
        print(sd.query_devices())
        return 0
    if args.wav:
        assistant = build_assistant(config)
        candidates = build_listener(config, assistant).transcribe_wav(args.wav)
        text, intent = assistant.interpret(candidates)
        print(f"Transcriptions : {candidates}")
        print(f"Retenue : {text} -> {intent.name} {intent.params}")
        return 0

    setup_logging()
    if config["avertissement"]:
        log.warning(config["avertissement"])
    if args.commande:
        response, _ = build_assistant(config).handle([args.commande])
        print(response)
        return 0
    try:
        return run(config)
    except Exception:
        # Lancé sans console (démarrage automatique), une erreur serait sinon silencieuse.
        log.exception("Milo n'a pas pu démarrer")
        Speaker().say("Milo n'a pas pu démarrer. Le détail est dans le journal de Milo.", wait=True)
        return 1

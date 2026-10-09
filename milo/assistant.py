"""Exécute une intention et rédige la phrase que Milo prononce en retour."""

import logging
import urllib.parse

from .actions import audio, display, info, theme, windows
from .actions.launcher import SETTINGS_HOME, AppIndex, SettingsPages, open_target
from .intents import Intent, parse
from .modes import ModeStore, describe
from .text import normalize

log = logging.getLogger(__name__)

HELP = (
    "Vous pouvez dire par exemple : volume à quarante, coupe le son, luminosité à soixante-dix, "
    "ouvre le bloc-notes, ferme Chrome, ouvre les paramètres Bluetooth, recherche la météo, "
    "quelle heure est-il. Pour les modes, dites : aide sur les modes. "
    "Pour quitter : au revoir Milo."
)
HELP_MODES = (
    "Un mode retient le volume, la luminosité et le thème. Réglez l'ordinateur, puis dites : "
    "enregistre le mode soir. Ensuite : active le mode soir. Vous pouvez aussi dire : "
    "ajoute Spotify au mode soir, décris le mode soir, quels sont mes modes, ou supprime le mode soir."
)
DEFAULT_SEARCH = "https://www.google.com/search?q={}"
# Fermer la fenêtre active depuis le terminal de Milo fermerait Milo lui-même.
_PROTECTED_EXE = {"windowsterminal", "conhost", "openconsole", "cmd", "powershell", "pwsh", "python", "pythonw"}
_NEEDS_MODE = {"mode_activate", "mode_describe", "mode_delete", "mode_add_app", "mode_remove_app"}


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " et " + items[-1]


class Assistant:
    def __init__(self, settings: SettingsPages, apps: AppIndex, modes: ModeStore,
                 step: int = 10, search_url: str = DEFAULT_SEARCH):
        self.settings = settings
        self.apps = apps
        self.modes = modes
        self.step = step
        self.search_url = search_url
        self.last_target = "volume"            # cible de « cinquante pour cent », « plus »…
        self.last_change: Intent | None = None  # rejoué par « encore »
        self.on_vocabulary_change = lambda: None
        self.change_voice_rate = None  # branché sur la voix par main.py
        self.last_answer = ""

    def vocabulary(self) -> list[str]:
        """Noms à ajouter à la grammaire de reconnaissance."""
        return [*self.settings.phrases(), *self.apps.phrases(), *self.modes.names()]

    def _usable(self, text: str, intent: Intent) -> bool:
        if intent.name in ("unknown", "empty") or "unk" in normalize(text).split():
            return False
        if intent.name == "launch_app":
            return self.apps.find(intent.params["name"]) is not None
        if intent.name in _NEEDS_MODE:
            return self.modes.find(intent.params["name"]) is not None
        if intent.name == "close_app":
            return bool(self._windows_for(intent.params["name"]))
        return True

    def interpret(self, candidates: list[str]) -> tuple[str, Intent]:
        """Première transcription qui donne une commande exécutable.

        Les candidats sont classés du plus fiable au moins fiable ; la grammaire
        restreinte rend « [unk] » pour les mots hors vocabulaire, on passe alors
        à la reconnaissance libre.
        """
        parsed = [(text, parse(text, self.step)) for text in candidates]
        for text, intent in parsed:
            if self._usable(text, intent):
                if intent.name == "search":
                    # La grammaire force le texte libre en mots connus (« météo à pareil ») :
                    # pour une recherche, la transcription libre (la dernière) est meilleure.
                    free_text, free = parsed[-1]
                    if free.name == "search" and free.params["query"]:
                        return free_text, free
                return text, intent
        # Rien d'exécutable : on garde la transcription la plus fiable qui a une
        # intention (pour un message d'erreur précis), sinon la libre.
        for text, intent in parsed:
            if intent.name not in ("unknown", "empty") and "unk" not in normalize(text).split():
                return text, intent
        heard = [(t, i) for t, i in parsed if i.name != "empty"]
        return heard[-1] if heard else parsed[-1]

    def handle(self, candidates: list[str]) -> tuple[str, bool]:
        """Renvoie (phrase à dire, faut-il quitter)."""
        text, intent = self.interpret(candidates)
        log.info("Entendu %s -> « %s » -> %s %s", candidates, text, intent.name, intent.params)
        if intent.name == "quit":
            return "Au revoir.", True
        if intent.name == "say_again":
            return self.last_answer or "Je n'ai encore rien dit.", False
        try:
            answer = self._run(intent)
        except Exception:
            log.exception("Échec de l'action %s", intent.name)
            answer = "Désolé, cette action a échoué."
        self.last_answer = answer
        return answer, False

    # --- volume et luminosité ---------------------------------------------

    def _level(self, name: str, p: dict) -> str:
        target, action = name.split("_", 1)
        self.last_target = target
        if action == "change":
            self.last_change = Intent(name, p)
        if target == "volume":
            if action == "set":
                level = audio.set_volume(p["level"])
            elif action == "change":
                level = audio.change_volume(p["delta"])
            else:
                level = audio.get_volume()
                if audio.is_muted():
                    return f"Le son est coupé. Volume à {level} pour cent."
            return f"Volume à {level} pour cent."
        try:
            if action == "set":
                level = display.set_brightness(p["level"])
            elif action == "change":
                level = display.change_brightness(p["delta"])
            else:
                level = display.get_brightness()
        except display.BrightnessUnavailable:
            return "Je ne peux pas régler la luminosité de cet écran."
        return f"Luminosité à {level} pour cent."

    # --- modes ---------------------------------------------------------------

    def _capture(self) -> dict:
        settings = {"volume": audio.get_volume(), "muet": audio.is_muted()}
        try:
            settings["luminosite"] = display.get_brightness()
        except display.BrightnessUnavailable:
            pass
        try:
            settings["theme"] = theme.get_theme()
        except OSError:
            log.warning("Thème Windows illisible, non enregistré dans le mode")
        return settings

    def _apply(self, mode: dict) -> list[str]:
        """Applique un mode ; renvoie les éléments qui n'ont pas pu l'être."""
        failed = []
        if "volume" in mode:
            audio.set_volume(mode["volume"])
        if "muet" in mode:
            audio.set_mute(bool(mode["muet"]))
        if mode.get("luminosite") is not None:
            try:
                display.set_brightness(mode["luminosite"])
            except display.BrightnessUnavailable:
                failed.append("la luminosité")
        if mode.get("theme") in (theme.DARK, theme.LIGHT) and theme.get_theme() != mode["theme"]:
            theme.set_theme(mode["theme"])
        for app in mode.get("applications") or []:
            match = self.apps.find(app)
            if match:
                open_target(match.target)
            else:
                failed.append(app)
        return failed

    def _mode(self, name: str, p: dict) -> str:
        if name == "mode_list":
            names = self.modes.names()
            if not names:
                return "Vous n'avez encore aucun mode. Dites par exemple : enregistre le mode travail."
            return f"Vous avez {len(names)} mode{'s' if len(names) > 1 else ''} : {_join(names)}."

        if name == "mode_save":
            saved, created = self.modes.save(p["name"], self._capture())
            self.on_vocabulary_change()
            verb = "enregistré" if created else "mis à jour"
            return f"Mode {saved} {verb} : {describe(self.modes.get(saved))}."

        found = self.modes.find(p["name"])
        if not found:
            if name != "mode_activate" or self.modes.names():
                known = f" Vos modes sont : {_join(self.modes.names())}." if self.modes.names() else ""
                return f"Je ne connais pas le mode {p['name']}.{known}"
            return (f"Le mode {p['name']} n'existe pas encore. Réglez l'ordinateur comme vous le souhaitez, "
                    f"puis dites : enregistre le mode {p['name']}.")
        mode = self.modes.get(found)

        if name == "mode_activate":
            failed = self._apply(mode)
            answer = f"Mode {found} activé : {describe(mode)}."
            if failed:
                answer += f" Je n'ai pas pu appliquer : {_join(failed)}."
            return answer
        if name == "mode_describe":
            return f"Mode {found} : {describe(mode)}."
        if name == "mode_delete":
            self.modes.delete(found)
            self.on_vocabulary_change()
            return f"Mode {found} supprimé."
        if name == "mode_add_app":
            match = self.apps.find(p["app"])
            if not match:
                return f"Je n'ai pas trouvé l'application {p['app']}."
            if not self.modes.add_app(found, match.label):
                return f"{match.label} est déjà dans le mode {found}."
            return f"Le mode {found} ouvrira aussi {match.label}."
        if name == "mode_remove_app":
            removed = self.modes.remove_app(found, p["app"])
            if not removed:
                return f"{p['app']} n'est pas dans le mode {found}."
            return f"Le mode {found} n'ouvrira plus {removed}."
        raise ValueError(name)

    # --- fenêtres --------------------------------------------------------------

    def _windows_for(self, name: str) -> list[windows.Window]:
        names = [name]
        match = self.apps.find(name)
        if match:
            names.append(match.label)
        return windows.find_windows(names, windows.list_windows())

    def _close_app(self, name: str) -> str:
        found = self._windows_for(name)
        if not found:
            return f"Je ne trouve pas de fenêtre ouverte pour {name}."
        for window in found:
            windows.close(window)
        label = found[0].app_name
        if len(found) > 1:
            return f"Je ferme les {len(found)} fenêtres de {label}."
        return f"Je ferme {label}."

    def _close_window(self) -> str:
        window = windows.foreground_window()
        if not window or not window.title:
            return "Aucune fenêtre n'est active."
        if window.exe in _PROTECTED_EXE:
            return "La fenêtre active est peut-être celle de Milo, je préfère ne pas la fermer."
        windows.close(window)
        return f"Je ferme {window.app_name}."

    # --- aiguillage ------------------------------------------------------------

    def _run(self, intent: Intent) -> str:
        name, p = intent.name, intent.params

        if name == "empty":
            return "Je n'ai rien entendu."
        if name == "help":
            return HELP_MODES if p.get("topic") == "modes" else HELP
        if name == "ping":
            return "Oui, je vous écoute."
        if name == "voice_rate":
            if not self.change_voice_rate:
                return "Je ne peux pas changer ma vitesse."
            rate = self.change_voice_rate(p["delta"])
            if abs(rate) == 10:
                return "Je parle déjà aussi vite que possible." if rate > 0 else "Je parle déjà aussi lentement que possible."
            return "D'accord, je parle plus vite." if p["delta"] > 0 else "D'accord, je parle plus lentement."

        if name == "level_set":
            name = f"{self.last_target}_set"
        elif name == "level_change":
            name = f"{self.last_target}_change"
        elif name == "repeat":
            if not self.last_change:
                return "Il n'y a rien à répéter."
            name, p = self.last_change.name, self.last_change.params
        if name.startswith(("volume_", "brightness_")):
            return self._level(name, p)

        if name == "mute":
            audio.set_mute(True)
            return "Son coupé."
        if name == "unmute":
            audio.set_mute(False)
            return f"Son rétabli, volume à {audio.get_volume()} pour cent."
        if name == "theme":
            theme.set_theme(p["theme"])
            return f"Thème {p['theme']} activé."

        if name.startswith("mode_"):
            return self._mode(name, p)

        if name == "open_settings":
            match = self.settings.find(p["page"])
            if match:
                open_target(match.target)
                return f"J'ouvre les paramètres {match.label}."
            open_target(SETTINGS_HOME)
            if p["page"]:
                return f"Je ne connais pas la page {p['page']}. J'ouvre les paramètres."
            return "J'ouvre les paramètres."

        if name == "launch_app":
            match = self.apps.find(p["name"])
            if not match:
                return f"Je n'ai pas trouvé l'application {p['name']}."
            open_target(match.target)
            return f"J'ouvre {match.label}."
        if name == "close_app":
            return self._close_app(p["name"])
        if name == "close_window":
            return self._close_window()

        if name == "search":
            if not p["query"]:
                return "Que voulez-vous chercher ? Dites par exemple : recherche la météo à Paris."
            open_target(self.search_url.format(urllib.parse.quote_plus(p["query"])))
            return f"Je recherche {p['query']}."

        if name == "time":
            return info.time_sentence()
        if name == "date":
            return info.date_sentence()
        if name == "battery":
            return info.battery_sentence()

        heard = p.get("text", "").replace("[unk]", "…")
        match = self.apps.find(heard)
        if match:
            return f"Je n'ai pas compris. Pour ouvrir {match.label}, dites : ouvre {match.label}."
        if len(heard.split()) > 6:
            # Souvent une télé ou une conversation captée : inutile de tout relire.
            return "Je n'ai pas compris. Dites aide pour connaître les commandes."
        return f"Je n'ai pas compris : {heard}."

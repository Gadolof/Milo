"""Retour vocal (SAPI) et signaux sonores.

La voix vit dans son propre thread COM : on peut lui envoyer des phrases depuis
n'importe quel thread, et l'interrompre quand l'utilisateur reprend la parole.
"""

import logging
import queue
import threading
import winsound

import comtypes
import comtypes.client

log = logging.getLogger(__name__)

_ASYNC = 1
_PURGE = 2


def beep_start() -> None:
    winsound.Beep(880, 90)


def beep_end() -> None:
    winsound.Beep(587, 90)


class Speaker:
    def __init__(self, language: str = "40C", rate: int = 0, volume: int = 100):
        self._language = language
        self._rate = rate
        self._volume = volume
        self._queue: queue.Queue = queue.Queue()
        self._interrupt = threading.Event()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="milo-voix", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=10)

    def say(self, text: str, wait: bool = False) -> None:
        log.info("Milo : %s", text)
        done = threading.Event()
        self._interrupt.clear()
        self._queue.put((text, done))
        if wait:
            done.wait()

    @property
    def rate(self) -> int:
        return self._rate

    def change_rate(self, delta: int) -> int:
        """Débit SAPI de -10 à 10, appliqué dès la phrase suivante."""
        self._rate = max(-10, min(10, self._rate + delta))
        return self._rate

    def stop(self) -> None:
        """Coupe la phrase en cours et vide la file d'attente."""
        while True:
            try:
                _, done = self._queue.get_nowait()
                done.set()
            except queue.Empty:
                break
        self._interrupt.set()

    def close(self) -> None:
        self._queue.put(None)
        self._thread.join(timeout=5)

    def _run(self) -> None:
        comtypes.CoInitialize()
        try:
            voice = comtypes.client.CreateObject("SAPI.SpVoice")
            voices = voice.GetVoices(f"Language={self._language}", "")
            if voices.Count:
                voice.Voice = voices.Item(0)
            else:
                log.warning("Aucune voix SAPI pour la langue %s, voix par défaut utilisée", self._language)
            voice.Rate = self._rate
            voice.Volume = self._volume
            self._ready.set()
            while (item := self._queue.get()) is not None:
                text, done = item
                try:
                    voice.Rate = self._rate
                    voice.Speak(text, _ASYNC)
                    while not voice.WaitUntilDone(50):
                        if self._interrupt.is_set():
                            voice.Speak("", _ASYNC | _PURGE)
                            break
                finally:
                    done.set()
        finally:
            self._ready.set()
            comtypes.CoUninitialize()

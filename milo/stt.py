"""Reconnaissance vocale hors ligne avec Vosk.

Deux décodeurs écoutent le même son :
- un décodeur à grammaire restreinte (mots des commandes), très fiable ;
- un décodeur libre, en secours pour les noms qu'il ne connaît pas.
`listen()` renvoie les deux transcriptions, la plus fiable en premier.
"""

import json
import logging
import queue
import time
import wave
from pathlib import Path

import sounddevice as sd
from vosk import KaldiRecognizer, Model, SetLogLevel

from .vocabulary import fix_constrained

log = logging.getLogger(__name__)


class _Decoder:
    def __init__(self, rec: KaldiRecognizer):
        self.rec = rec
        self.parts: list[str] = []

    def feed(self, data: bytes) -> bool:
        """True quand une phrase non vide vient de se terminer."""
        if self.rec.AcceptWaveform(data):
            text = json.loads(self.rec.Result()).get("text", "")
            if text:
                self.parts.append(text)
                return True
        return False

    def hearing(self) -> bool:
        return bool(json.loads(self.rec.PartialResult()).get("partial"))

    def finish(self) -> str:
        self.parts.append(json.loads(self.rec.FinalResult()).get("text", ""))
        return " ".join(p for p in self.parts if p)


class Listener:
    def __init__(self, model_path: Path, device=None, grammar: list[str] | None = None):
        if not model_path.is_dir():
            raise FileNotFoundError(model_path)
        SetLogLevel(-1)
        self.model = Model(str(model_path))
        self.device = device
        self.set_grammar(grammar)

    def set_grammar(self, grammar: list[str] | None) -> None:
        """Pris en compte à la prochaine écoute (nouveaux modes, nouvelles applis…)."""
        self.grammar = json.dumps(grammar, ensure_ascii=False) if grammar else None

    def _decoders(self, rate: float) -> list[_Decoder]:
        decoders = [_Decoder(KaldiRecognizer(self.model, rate))]
        if self.grammar:
            decoders.insert(0, _Decoder(KaldiRecognizer(self.model, rate, self.grammar)))
        return decoders

    def _results(self, decoders: list[_Decoder]) -> list[str]:
        texts = [d.finish() for d in decoders]
        if self.grammar:
            texts[0] = fix_constrained(texts[0])
        return texts

    def listen(self, timeout: float = 8.0, silence_timeout: float = 4.0, end_pause: float = 0.7) -> list[str]:
        """Écoute le micro jusqu'à la fin de la phrase (ou le délai).

        Après une fin de phrase détectée, on écoute encore `end_pause` secondes :
        « ouvre chrome et cherche… [hésitation] la météo » reste une seule commande.
        """
        rate = sd.query_devices(self.device, "input")["default_samplerate"]
        decoders = self._decoders(rate)
        blocks: queue.Queue = queue.Queue()

        def callback(indata, frames, time_info, status):
            blocks.put(bytes(indata))

        start = time.monotonic()
        heard = False
        ended_at = None
        with sd.RawInputStream(samplerate=rate, blocksize=int(rate * 0.1), device=self.device,
                               dtype="int16", channels=1, callback=callback):
            while True:
                now = time.monotonic()
                if now - start > timeout or (not heard and now - start > silence_timeout):
                    break
                if ended_at is not None and now - ended_at > end_pause:
                    break
                try:
                    data = blocks.get(timeout=0.5)
                except queue.Empty:
                    continue
                # Pas de any() : chaque décodeur doit recevoir le bloc.
                ended = [d.feed(data) for d in decoders]
                if any(ended):
                    ended_at = time.monotonic()
                elif any(d.hearing() for d in decoders):
                    heard = True
                    ended_at = None  # l'utilisateur a repris la parole
        return self._results(decoders)

    def transcribe_wav(self, path: Path) -> list[str]:
        """Transcrit un WAV mono 16 bits (pour les tests sans micro)."""
        with wave.open(str(path), "rb") as wav:
            if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                raise ValueError("Le fichier doit être un WAV mono 16 bits")
            decoders = self._decoders(wav.getframerate())
            while data := wav.readframes(4000):
                for d in decoders:
                    d.feed(data)
        return self._results(decoders)

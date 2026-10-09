"""Télécharge le modèle Vosk français (≈ 41 Mo) dans models/."""

import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

NAME = "vosk-model-small-fr-0.22"
URL = f"https://alphacephei.com/vosk/models/{NAME}.zip"
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


def main() -> int:
    target = MODELS_DIR / NAME
    if target.is_dir():
        print(f"Modèle déjà présent : {target}")
        return 0
    MODELS_DIR.mkdir(exist_ok=True)
    print(f"Téléchargement de {URL}…")
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "modele.zip"
        with urllib.request.urlopen(URL) as response, archive.open("wb") as out:
            shutil.copyfileobj(response, out)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(MODELS_DIR)
    print(f"Modèle installé : {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Installation de Milo

echo.
echo  Installation de Milo, assistant vocal. Cela peut prendre quelques minutes.
echo.
call :dire "Installation de Milo. Cela peut prendre quelques minutes, patientez."

rem --- Python 3.11 ou plus récent -------------------------------------------
set "PY="
py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>nul && set "PY=python"
if not defined PY goto sans_python

echo  [1/4] Environnement Python
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv || goto erreur

echo  [2/4] Bibliothèques
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt || goto erreur

echo  [3/4] Modèle de reconnaissance vocale, environ 40 Mo
".venv\Scripts\python.exe" scripts\telecharger_modele.py || goto erreur

if /i "%~1"=="--sans-demarrage" goto termine

echo  [4/4] Démarrage automatique et menu Démarrer
".venv\Scripts\python.exe" -m milo --installer-raccourcis || goto erreur

echo.
echo  Installation terminée. Milo démarrera tout seul à chaque ouverture de session.
call :dire "Installation terminée. Milo démarrera tout seul à chaque ouverture de session. Je le lance maintenant."
start "" ".venv\Scripts\pythonw.exe" -m milo
exit /b 0

:termine
echo.
echo  Installation terminée, sans démarrage automatique.
call :dire "Installation terminée."
exit /b 0

:sans_python
echo  Python 3.11 ou plus récent est introuvable.
echo  Installez-le depuis https://www.python.org/downloads/
echo  en cochant « Add python.exe to PATH », puis relancez ce fichier.
call :dire "Python est introuvable. Une personne voyante doit installer Python, puis relancer l'installation."
start "" https://www.python.org/downloads/
goto pause_erreur

:erreur
echo.
echo  L'installation a échoué : voir les messages ci-dessus.
call :dire "L'installation a échoué. Demandez de l'aide à une personne voyante."

:pause_erreur
pause
exit /b 1

rem --- Lecture à voix haute avec une voix française de Windows ---------------
:dire
set "MILO_TEXTE=%~1"
powershell -NoProfile -NonInteractive -Command "Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'fr*' } | Select-Object -First 1; if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }; $s.Speak($env:MILO_TEXTE)" >nul 2>nul
exit /b 0

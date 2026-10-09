@echo off
chcp 65001 >nul
setlocal
title Désinstallation de Milo

set "PROGRAMMES=%APPDATA%\Microsoft\Windows\Start Menu\Programs"
del "%PROGRAMMES%\Startup\Milo.lnk" >nul 2>nul
del "%PROGRAMMES%\Milo.lnk" >nul 2>nul

echo.
echo  Milo ne démarrera plus automatiquement et n'est plus dans le menu Démarrer.
echo  S'il tourne encore, dites « au revoir Milo ».
echo  Pour le supprimer complètement, supprimez ensuite ce dossier.
echo.
call :dire "Le démarrage automatique de Milo est désactivé. S'il tourne encore, dites : au revoir Milo."
pause
exit /b 0

:dire
set "MILO_TEXTE=%~1"
powershell -NoProfile -NonInteractive -Command "Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'fr*' } | Select-Object -First 1; if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }; $s.Speak($env:MILO_TEXTE)" >nul 2>nul
exit /b 0

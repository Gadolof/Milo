"""Thème clair / sombre de Windows (registre de l'utilisateur, sans droits admin)."""

import ctypes
import winreg

_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
_HWND_BROADCAST = 0xFFFF
_WM_SETTINGCHANGE = 0x001A
_SMTO_ABORTIFHUNG = 0x0002

DARK = "sombre"
LIGHT = "clair"


def get_theme() -> str:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY) as key:
        light, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
    return LIGHT if light else DARK


def set_theme(theme: str) -> None:
    light = 1 if theme == LIGHT else 0
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, light)
        winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, light)
    # Prévient les applis ouvertes pour qu'elles changent de thème tout de suite.
    result = ctypes.c_ulong()
    ctypes.windll.user32.SendMessageTimeoutW(_HWND_BROADCAST, _WM_SETTINGCHANGE, 0, "ImmersiveColorSet",
                                             _SMTO_ABORTIFHUNG, 200, ctypes.byref(result))

"""Fenêtres ouvertes : recherche par nom d'appli et fermeture douce (WM_CLOSE).

WM_CLOSE équivaut à cliquer sur la croix : l'appli peut encore proposer
d'enregistrer un document, rien n'est tué de force.
"""

import ctypes
import ctypes.wintypes as wt
import os
from dataclasses import dataclass

from ..text import normalize, similarity

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_dwmapi = ctypes.windll.dwmapi

_WM_CLOSE = 0x0010
_GW_OWNER = 4
_GWL_EXSTYLE = -20
_WS_EX_TOOLWINDOW = 0x80
_DWMWA_CLOAKED = 14
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_IGNORED_EXE = {"textinputhost", "shellexperiencehost", "searchhost", "startmenuexperiencehost"}
CUTOFF = 85


@dataclass
class Window:
    hwnd: int
    title: str
    exe: str  # nom de l'exécutable sans .exe, en minuscules

    @property
    def app_name(self) -> str:
        """« Document1 - Word » -> « Word » : le nom d'appli est souvent en fin de titre."""
        for sep in (" - ", " — ", " – "):
            if sep in self.title:
                return self.title.rsplit(sep, 1)[1].strip()
        return self.title

    def keys(self) -> list[str]:
        return [k for k in {normalize(self.exe), normalize(self.app_name), normalize(self.title)} if k]


def _exe_name(hwnd: int) -> str:
    pid = wt.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wt.DWORD(len(buf))
        if not _kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return ""
        return os.path.splitext(os.path.basename(buf.value))[0].lower()
    finally:
        _kernel32.CloseHandle(handle)


def _is_app_window(hwnd: int) -> bool:
    if not _user32.IsWindowVisible(hwnd) or _user32.GetWindow(hwnd, _GW_OWNER):
        return False
    if _user32.GetWindowLongW(hwnd, _GWL_EXSTYLE) & _WS_EX_TOOLWINDOW:
        return False
    cloaked = ctypes.c_int(0)
    _dwmapi.DwmGetWindowAttribute(hwnd, _DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    return not cloaked.value


def _title(hwnd: int) -> str:
    length = _user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def list_windows() -> list[Window]:
    windows = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def callback(hwnd, _):
        if _is_app_window(hwnd):
            title = _title(hwnd)
            exe = _exe_name(hwnd)
            if title and title != "Program Manager" and exe not in _IGNORED_EXE:
                windows.append(Window(hwnd, title, exe))
        return True

    _user32.EnumWindows(callback, 0)
    return windows


def foreground_window() -> Window | None:
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return None
    return Window(hwnd, _title(hwnd), _exe_name(hwnd))


def find_windows(names: list[str], windows: list[Window]) -> list[Window]:
    """Fenêtres qui correspondent le mieux à l'un des noms (toutes les fenêtres de Chrome…)."""
    queries = [normalize(n) for n in names if n]
    scored = []
    for window in windows:
        score = max((similarity(q, k) for q in queries for k in window.keys()), default=0)
        if score >= CUTOFF:
            scored.append((score, window))
    if not scored:
        return []
    best = max(score for score, _ in scored)
    return [w for score, w in scored if score == best]


def close(window: Window) -> None:
    _user32.PostMessageW(window.hwnd, _WM_CLOSE, 0, 0)

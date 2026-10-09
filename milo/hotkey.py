"""Raccourci clavier global via RegisterHotKey.

Pas de hook clavier bas niveau : on ne perturbe ni NVDA ni JAWS.
"""

import ctypes
import ctypes.wintypes as wt
import time

_MODIFIERS = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4, "maj": 0x4, "win": 0x8}
_MOD_NOREPEAT = 0x4000
_WM_HOTKEY = 0x0312
_PM_REMOVE = 0x1
_KEYS = {"space": 0x20, "espace": 0x20, "pause": 0x13, "insert": 0x2D, "home": 0x24, "end": 0x23}
_KEYS.update({f"f{i}": 0x6F + i for i in range(1, 13)})


class HotkeyError(Exception):
    pass


class HotkeyInUse(HotkeyError):
    pass


def parse_hotkey(spec: str) -> tuple[int, int]:
    """« ctrl+alt+space » -> (modificateurs, code de touche virtuelle)."""
    mods, vk = 0, None
    for part in spec.lower().replace(" ", "").split("+"):
        if part in _MODIFIERS:
            mods |= _MODIFIERS[part]
        elif part in _KEYS:
            vk = _KEYS[part]
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())
        else:
            raise HotkeyError(f"Touche inconnue : {part}")
    if vk is None:
        raise HotkeyError(f"Raccourci sans touche principale : {spec}")
    return mods, vk


def run_loop(spec: str, on_press, should_stop, on_ready=None) -> None:
    """Boucle de messages du thread courant ; appelle `on_press` à chaque appui."""
    mods, vk = parse_hotkey(spec)
    user32 = ctypes.windll.user32
    if not user32.RegisterHotKey(None, 1, mods | _MOD_NOREPEAT, vk):
        raise HotkeyInUse(spec)
    msg = wt.MSG()
    try:
        if on_ready:
            on_ready()
        while not should_stop():
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, _PM_REMOVE):
                if msg.message == _WM_HOTKEY:
                    on_press()
            time.sleep(0.05)
    finally:
        user32.UnregisterHotKey(None, 1)

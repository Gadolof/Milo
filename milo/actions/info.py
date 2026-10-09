"""Informations lues à voix haute : heure, date, batterie."""

import ctypes
from datetime import datetime

_DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]


def time_sentence(now: datetime | None = None) -> str:
    now = now or datetime.now()
    if now.minute == 0:
        return f"Il est {now.hour} heures."
    return f"Il est {now.hour} heures {now.minute}."


def date_sentence(now: datetime | None = None) -> str:
    now = now or datetime.now()
    day = "1er" if now.day == 1 else str(now.day)
    return f"Nous sommes le {_DAYS[now.weekday()]} {day} {_MONTHS[now.month - 1]} {now.year}."


class _PowerStatus(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    ]


def battery_sentence() -> str:
    status = _PowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return "Je n'arrive pas à lire l'état de la batterie."
    if status.BatteryFlag == 128 or status.BatteryLifePercent == 255:
        return "Cet ordinateur n'a pas de batterie."
    sentence = f"Batterie à {status.BatteryLifePercent} pour cent"
    if status.ACLineStatus == 1:
        return sentence + ", sur secteur."
    return sentence + ", sur batterie."

"""Luminosité de l'écran (WMI pour les portables, DDC/CI pour les écrans externes)."""

import screen_brightness_control as sbc


class BrightnessUnavailable(Exception):
    pass


def get_brightness() -> int:
    try:
        values = sbc.get_brightness()
    except Exception as exc:
        raise BrightnessUnavailable from exc
    if not values:
        raise BrightnessUnavailable
    return int(values[0])


def set_brightness(level: int) -> int:
    level = max(0, min(100, level))
    try:
        sbc.set_brightness(level)
    except Exception as exc:
        raise BrightnessUnavailable from exc
    return level


def change_brightness(delta: int) -> int:
    return set_brightness(get_brightness() + delta)

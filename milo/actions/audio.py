"""Volume et sourdine du périphérique de sortie par défaut (Core Audio via pycaw)."""

from pycaw.pycaw import AudioUtilities


def _endpoint():
    # Récupéré à chaque appel : le périphérique par défaut peut changer (casque branché…).
    return AudioUtilities.GetSpeakers().EndpointVolume


def get_volume() -> int:
    return round(_endpoint().GetMasterVolumeLevelScalar() * 100)


def set_volume(level: int) -> int:
    level = max(0, min(100, level))
    endpoint = _endpoint()
    endpoint.SetMasterVolumeLevelScalar(level / 100, None)
    if level > 0 and endpoint.GetMute():
        endpoint.SetMute(0, None)
    return level


def change_volume(delta: int) -> int:
    return set_volume(get_volume() + delta)


def is_muted() -> bool:
    return bool(_endpoint().GetMute())


def set_mute(muted: bool) -> None:
    _endpoint().SetMute(1 if muted else 0, None)

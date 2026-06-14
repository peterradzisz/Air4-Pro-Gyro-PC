"""Mute control for the default Windows audio endpoint.

Uses keybd_event(VK_VOLUME_MUTE) to toggle mute globally.
Tracks state internally (assumes unmuted at startup).
No COM interfaces needed — simpler and more reliable than comtypes.
"""
import ctypes

_user32 = ctypes.windll.user32
_VK_VOLUME_MUTE = 0xAD
_KEYEVENTF_KEYUP = 0x0002

# Track mute state internally
_muted = False


def _toggle():
    """Send Volume Mute keypress to toggle system mute."""
    _user32.keybd_event(_VK_VOLUME_MUTE, 0, 0, 0)
    _user32.keybd_event(_VK_VOLUME_MUTE, 0, _KEYEVENTF_KEYUP, 0)


def set_mute(mute):
    """Set mute state. Only toggles if current state differs."""
    global _muted
    if mute != _muted:
        _toggle()
        _muted = mute
    return True


def get_mute():
    """Return tracked mute state."""
    return _muted

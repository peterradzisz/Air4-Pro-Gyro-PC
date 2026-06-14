"""Mute control for the default Windows audio endpoint via comtypes.

Uses Windows Core Audio COM interfaces to mute/unmute the default
render endpoint. WASAPI loopback captures the mix buffer BEFORE
the mute is applied, so routing to other devices still works.
"""
import ctypes
import comtypes
from comtypes import GUID, HRESULT


class IAudioEndpointVolume(comtypes.IUnknown):
    _iid_ = GUID('{5CDF2C82-841E-4546-9722-0CF74078229A}')
    _methods_ = [
        comtypes.STDMETHOD(HRESULT, 'RegisterControlChangeNotify', [ctypes.c_void_p]),
        comtypes.STDMETHOD(HRESULT, 'UnregisterControlChangeNotify', [ctypes.c_void_p]),
        comtypes.STDMETHOD(HRESULT, 'GetChannelCount', [ctypes.POINTER(ctypes.c_uint)]),
        comtypes.STDMETHOD(HRESULT, 'SetMasterVolumeLevel', [ctypes.c_float, ctypes.c_void_p]),
        comtypes.STDMETHOD(HRESULT, 'SetMasterVolumeLevelScalar', [ctypes.c_float, ctypes.c_void_p]),
        comtypes.STDMETHOD(HRESULT, 'GetMasterVolumeLevel', [ctypes.POINTER(ctypes.c_float)]),
        comtypes.STDMETHOD(HRESULT, 'GetMasterVolumeLevelScalar', [ctypes.POINTER(ctypes.c_float)]),
        comtypes.STDMETHOD(HRESULT, 'SetChannelVolumeLevel', [ctypes.c_uint, ctypes.c_float, ctypes.c_void_p]),
        comtypes.STDMETHOD(HRESULT, 'SetChannelVolumeLevelScalar', [ctypes.c_uint, ctypes.c_float, ctypes.c_void_p]),
        comtypes.STDMETHOD(HRESULT, 'GetChannelVolumeLevel', [ctypes.c_uint, ctypes.POINTER(ctypes.c_float)]),
        comtypes.STDMETHOD(HRESULT, 'GetChannelVolumeLevelScalar', [ctypes.c_uint, ctypes.POINTER(ctypes.c_float)]),
        comtypes.STDMETHOD(HRESULT, 'SetMute', [ctypes.c_int, ctypes.c_void_p]),
        comtypes.STDMETHOD(HRESULT, 'GetMute', [ctypes.POINTER(ctypes.c_int)]),
        comtypes.STDMETHOD(HRESULT, 'GetVolumeStepInfo', [ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)]),
        comtypes.STDMETHOD(HRESULT, 'VolumeStepUp', [ctypes.c_void_p]),
        comtypes.STDMETHOD(HRESULT, 'VolumeStepDown', [ctypes.c_void_p]),
        comtypes.STDMETHOD(HRESULT, 'QueryHardwareSupport', [ctypes.POINTER(ctypes.c_uint)]),
        comtypes.STDMETHOD(HRESULT, 'GetVolumeRange', [ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float)]),
    ]


class IMMDevice(comtypes.IUnknown):
    _iid_ = GUID('{D666063F-1587-4E43-81F1-B948E807363F}')
    _methods_ = [
        comtypes.STDMETHOD(HRESULT, 'Activate', [ctypes.POINTER(GUID), ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)]),
        comtypes.STDMETHOD(HRESULT, 'OpenPropertyStore', [ctypes.c_uint, ctypes.c_void_p]),
        comtypes.STDMETHOD(HRESULT, 'GetId', [ctypes.POINTER(ctypes.c_wchar_p)]),
        comtypes.STDMETHOD(HRESULT, 'GetState', [ctypes.POINTER(ctypes.c_uint)]),
    ]


class IMMDeviceEnumerator(comtypes.IUnknown):
    _iid_ = GUID('{A95664D2-9614-4F35-A746-DE8DB63617E6}')
    _methods_ = [
        comtypes.STDMETHOD(HRESULT, 'EnumAudioEndpoints', [ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]),
        comtypes.STDMETHOD(HRESULT, 'GetDefaultAudioEndpoint', [ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(IMMDevice)]),
        comtypes.STDMETHOD(HRESULT, 'GetDevice', [ctypes.c_wchar_p, ctypes.POINTER(IMMDevice)]),
        comtypes.STDMETHOD(HRESULT, 'RegisterEndpointNotificationCallback', [ctypes.c_void_p]),
        comtypes.STDMETHOD(HRESULT, 'UnregisterEndpointNotificationCallback', [ctypes.c_void_p]),
    ]


CLSID_MMDeviceEnumerator = GUID('{BCDE0395-E52F-467C-8E3D-C4579291692E}')
IID_IAudioEndpointVolume = GUID('{5CDF2C82-841E-4546-9722-0CF74078229A}')

# eRender = 0, eConsole = 0


def _get_endpoint_volume():
    """Get IAudioEndpointVolume interface for the default render endpoint."""
    enumerator = comtypes.CoCreateInstance(
        CLSID_MMDeviceEnumerator,
        IMMDeviceEnumerator,
        comtypes.CLSCTX_INPROC_SERVER,
    )
    device = enumerator.GetDefaultAudioEndpoint(0, 0)
    pv = ctypes.c_void_p()
    device.Activate(ctypes.byref(IID_IAudioEndpointVolume), 1, 0, ctypes.byref(pv))
    return ctypes.cast(pv, ctypes.POINTER(IAudioEndpointVolume)).contents


def set_mute(mute):
    """Mute (True) or unmute (False) the default render endpoint. Returns bool."""
    try:
        vol = _get_endpoint_volume()
        vol.SetMute(1 if mute else 0, None)
        return True
    except Exception as e:
        print(f"  Audio: SetMute failed: {e}")
        return False


def get_mute():
    """Check if the default render endpoint is muted. Returns bool."""
    try:
        vol = _get_endpoint_volume()
        muted = ctypes.c_int()
        vol.GetMute(ctypes.byref(muted))
        return bool(muted.value)
    except Exception:
        return False

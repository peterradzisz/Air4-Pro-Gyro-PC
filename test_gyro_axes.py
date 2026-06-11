"""
Quick gyro axis diagnostic. Run with glasses connected.
Move your head LEFT-RIGHT and note which axis spikes.
Then move UP-DOWN and note which axis spikes.
"""
import time, ctypes, numpy as np
from ctypes import c_float, c_uint8, c_uint32, c_void_p, c_int, Structure, Union, byref, c_char, c_uint16

class RAYNEO_ImuSample(Structure):
    _fields_ = [
        ("acc", c_float * 3), ("gyroDps", c_float * 3), ("gyroRad", c_float * 3),
        ("magnet", c_float * 3), ("temperature", c_float), ("psensor", c_float),
        ("lsensor", c_float), ("tick", c_uint32), ("count", c_uint32),
        ("flag", c_uint8), ("checksum", c_uint8), ("valid", c_uint8), ("reserved", c_uint8),
    ]

class _NotifyData(Structure):
    _fields_ = [("code", c_int), ("message", c_char * 96)]
class _LogData(Structure):
    _fields_ = [("level", c_int), ("message", c_char * 96)]
class _ErrorData(Structure):
    _fields_ = [("code", c_int)]
class _EventUnion(Union):
    _fields_ = [("imu", RAYNEO_ImuSample), ("notify", _NotifyData), ("log", _LogData), ("error", _ErrorData)]

class RAYNEO_Event(Structure):
    _fields_ = [("type", c_int), ("data", _EventUnion)]

EVT_IMU = 0x65

sdk = ctypes.CDLL("RayNeoSDK.dll")
ctx = c_void_p()
assert sdk.Rayneo_Create(byref(ctx)) == 0
sdk.Rayneo_SetTargetVidPid(ctx, 0x1BBB, 0xAF50)
assert sdk.Rayneo_Start(ctx, 0) == 0
sdk.Rayneo_EnableImu(ctx)
print("Connected. Move head LEFT-RIGHT now!")
print("="*70)

evt = RAYNEO_Event()
max_g = [0.0, 0.0, 0.0]
samples = 0

try:
    for _ in range(2500):  # ~5 seconds
        rc = sdk.Rayneo_PollEvent(ctx, byref(evt), 100)
        if rc != 0:
            continue
        if evt.type != EVT_IMU or not evt.data.imu.valid:
            continue
        g = evt.data.imu.gyroRad
        for i in range(3):
            max_g[i] = max(max_g[i], abs(g[i]))
        samples += 1
        if samples % 100 == 0:
            print(f"  gyroRad[0]={g[0]:+.4f}  gyroRad[1]={g[1]:+.4f}  gyroRad[2]={g[2]:+.4f}  |  peak=[{max_g[0]:.4f}, {max_g[1]:.4f}, {max_g[2]:.4f}]")
except KeyboardInterrupt:
    pass

print("="*70)
print(f"Peak gyro magnitudes over {samples} samples:")
print(f"  gyroRad[0] (gx) = {max_g[0]:.4f} rad/s  {'<-- YAW?' if max_g[0] == max(max_g) else ''}")
print(f"  gyroRad[1] (gy) = {max_g[1]:.4f} rad/s  {'<-- YAW?' if max_g[1] == max(max_g) else ''}")
print(f"  gyroRad[2] (gz) = {max_g[2]:.4f} rad/s  {'<-- YAW?' if max_g[2] == max(max_g) else ''}")
print()
highest = max_g.index(max(max_g))
print(f"If you moved LEFT-RIGHT, the highest axis ({highest}) = YAW (left-right)")
print(f"Current mapping: gyro[{highest}] -> gz -> roll (WRONG!)")
print(f"Fix: map gyro[{highest}] -> yaw instead")

sdk.Rayneo_DisableImu(ctx)
sdk.Rayneo_Stop(ctx)
sdk.Rayneo_Destroy(ctx)

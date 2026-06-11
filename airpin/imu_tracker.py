"""
IMU tracker for RayNeo Air 4 Pro.
Reads gyro/accel via RayNeoSDK.dll, fuses into yaw/pitch/roll.
"""

import os
import ctypes
import threading
import time
import logging
import math
import numpy as np
from ctypes import (
    c_uint8, c_uint16, c_uint32, c_uint64, c_int, c_float,
    c_void_p, c_char, POINTER, Structure, Union, byref
)

import config

# ── SDK C types ──────────────────────────────────────────────────────────────

class RAYNEO_ImuSample(Structure):
    _fields_ = [
        ("acc", c_float * 3), ("gyroDps", c_float * 3), ("gyroRad", c_float * 3),
        ("magnet", c_float * 3), ("temperature", c_float), ("psensor", c_float),
        ("lsensor", c_float), ("tick", c_uint32), ("count", c_uint32),
        ("flag", c_uint8), ("checksum", c_uint8), ("valid", c_uint8), ("reserved", c_uint8),
    ]

class RAYNEO_DeviceInfoMini(Structure):
    _fields_ = [
        ("raw", c_uint8 * 60), ("valid", c_uint8), ("reserved", c_uint8 * 3),
        ("tick", c_uint32), ("value", c_uint8), ("cpuid", c_uint8 * 12),
        ("board_id", c_uint8), ("sensor_on", c_uint8), ("support_fov", c_uint8),
        ("date", c_char * 13), ("year", c_uint16), ("month", c_uint8), ("day", c_uint8),
        ("glasses_fps", c_uint8), ("luminance", c_uint8), ("volume", c_uint8),
        ("side_by_side", c_uint8), ("psensor_enable", c_uint8), ("audio_mode", c_uint8),
        ("dp_status", c_uint8), ("status3", c_uint8), ("psensor_valid", c_uint8),
        ("lsensor_valid", c_uint8), ("gyro_valid", c_uint8), ("magnet_valid", c_uint8),
        ("reserve1", c_float), ("reserve2", c_float), ("max_luminance", c_uint8),
        ("max_volume", c_uint8), ("support_panel_color_adjust", c_uint8), ("flag", c_uint8),
    ]

class _NotifyData(Structure):
    _fields_ = [("code", c_int), ("message", c_char * 96)]
class _LogData(Structure):
    _fields_ = [("level", c_int), ("message", c_char * 96)]
class _ErrorData(Structure):
    _fields_ = [("code", c_int)]
class _EventUnion(Union):
    _fields_ = [
        ("imu", RAYNEO_ImuSample), ("info", RAYNEO_DeviceInfoMini),
        ("error", _ErrorData), ("log", _LogData), ("notify", _NotifyData),
    ]
class RAYNEO_Event(Structure):
    _fields_ = [("type", c_int), ("seq", c_uint64), ("data", _EventUnion)]

EVT_IMU = 2
EVT_DETACHED = 1

# ── Config ───────────────────────────────────────────────────────────────────

# Gyro deadzone in rad/s. Filters noise when head is still.
# No deadzone on gyro INTEGRATION (prevents asymmetric drift).
GYRO_DEADZONE = 0.0

# Output deadzone on displayed yaw.
OUTPUT_DEADZONE_DEG = 0.5

# Auto-bias: update bias ONLY when head is VERY still for a LONG time.
# Much stricter than before: 0.01 rad/s threshold, 2 seconds of stillness,
# tiny learn rate. This prevents corrupting bias with movement data.
STILL_THRESHOLD = 0.01   # rad/s — very strict stillness detection
STILL_SAMPLES = 1000     # 2 seconds at 500Hz before updating
BIAS_LEARN_RATE = 0.0002 # very slow adaptation

# EMA smoothing alpha at 500Hz. Equivalent to ~0.25 at 60Hz.
EMA_ALPHA = 0.035

YAW_DECAY = 1.0  # No decay

# Fixed bias calibration at startup (first 500 samples = ~1 second).
# No auto-bias during use — it corrupts the bias with movement data.
# User can recenter with Ctrl+Alt+R.
BIAS_SAMPLES = 500

# ── IMU Tracker ──────────────────────────────────────────────────────────────

class ImuTracker:
    def __init__(self):
        self.sdk = None
        self.ctx = None
        self.connected = False
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        self._imu_count = 0

        # Raw integrated angles from complementary filter
        self._raw_yaw = 0.0
        self._raw_pitch = 0.0
        self._raw_roll = 0.0

        # EMA-smoothed output
        self._yaw = 0.0
        self._pitch = 0.0
        self._roll = 0.0

        # Reference (set on recenter)
        self._ref_yaw = 0.0
        self._ref_pitch = 0.0
        self._ref_roll = 0.0

        # Bias calibration
        self._gyro_bias = np.zeros(3)
        self._bias_count = 0
        self._bias_done = False
        self._last_tick = 0
        self._cf_initialized = False

        # Output deadzone state
        self._output_yaw = 0.0
        self._still_counter = 0

        # Thread-safe gyro magnitude for smooth follow
        self._last_gyro_mag = 0.0
        self._last_raw_gyro = np.zeros(3)

    def _find_dll(self):
        root = os.path.dirname(os.path.dirname(__file__))  # project root
        candidates = [
            os.path.join(root, "lib", "RayNeoSDK.dll"),
            os.path.join(os.path.dirname(__file__), "RayNeoSDK.dll"),
            os.path.join(root, "RayNeoSDK.dll"),
        ]
        if config.SDK_DLL_PATH and os.path.exists(config.SDK_DLL_PATH):
            return config.SDK_DLL_PATH
        for p in candidates:
            if os.path.exists(p):
                return p
        return None

    def start(self):
        dll_path = self._find_dll()
        if not dll_path:
            raise FileNotFoundError("RayNeoSDK.dll not found")
        dll_dir = os.path.dirname(dll_path)
        os.add_dll_directory(dll_dir)
        os.environ["PATH"] = dll_dir + ";" + os.environ.get("PATH", "")
        # Also add lib/ directory for libusb
        lib_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lib")
        if os.path.isdir(lib_dir):
            os.add_dll_directory(lib_dir)
            os.environ["PATH"] = lib_dir + ";" + os.environ.get("PATH", "")

        self.sdk = ctypes.CDLL(dll_path)
        s = self.sdk
        s.Rayneo_Create.restype = c_int
        s.Rayneo_Create.argtypes = [POINTER(c_void_p)]
        s.Rayneo_Destroy.argtypes = [c_void_p]
        s.Rayneo_SetTargetVidPid.restype = c_int
        s.Rayneo_SetTargetVidPid.argtypes = [c_void_p, c_uint16, c_uint16]
        s.Rayneo_Start.restype = c_int
        s.Rayneo_Start.argtypes = [c_void_p, c_uint32]
        s.Rayneo_Stop.restype = c_int
        s.Rayneo_Stop.argtypes = [c_void_p]
        s.Rayneo_PollEvent.restype = c_int
        s.Rayneo_PollEvent.argtypes = [c_void_p, POINTER(RAYNEO_Event), c_uint32]
        s.Rayneo_EnableImu.restype = c_int
        s.Rayneo_EnableImu.argtypes = [c_void_p]
        s.Rayneo_DisableImu.restype = c_int
        s.Rayneo_DisableImu.argtypes = [c_void_p]

        self.ctx = c_void_p()
        if s.Rayneo_Create(byref(self.ctx)) != 0:
            raise RuntimeError("Rayneo_Create failed")
        s.Rayneo_SetTargetVidPid(self.ctx, config.RAYNEO_VID, config.RAYNEO_PID)
        if s.Rayneo_Start(self.ctx, 0) != 0:
            s.Rayneo_Destroy(self.ctx)
            raise RuntimeError("Rayneo_Start failed (glasses not connected?)")
        s.Rayneo_EnableImu(self.ctx)

        # Additional init from reference implementation (verncat/RayNeo-Air-3S-Pro-OpenVR examples)
        # These calls may be needed to fully activate the device
        if hasattr(s, 'Rayneo_RequestDeviceInfo'):
            s.Rayneo_RequestDeviceInfo.restype = c_int
            s.Rayneo_RequestDeviceInfo.argtypes = [c_void_p]
            rc_info = s.Rayneo_RequestDeviceInfo(self.ctx)
            print(f"  SDK RequestDeviceInfo: rc={rc_info}")

        self.connected = True
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

        # Wait for first IMU sample (up to 3 seconds)
        print("  Waiting for IMU data...")
        for i in range(30):
            if self._imu_count > 0:
                print(f"  Got first IMU sample after {i*0.1:.1f}s")
                break
            time.sleep(0.1)
        else:
            print(f"  WARNING: No IMU data after 3s (imu_count={self._imu_count}, connected={self.connected})")

        # Ensure SDK cleanup on any exit (crash, Ctrl+C, sys.exit)
        import atexit
        atexit.register(self._cleanup_sdk)

    def _poll_loop(self):
        evt = RAYNEO_Event()
        last_data_count = 0
        stall_start = None
        reconnect_attempts = 0

        while self._running:
            rc = self.sdk.Rayneo_PollEvent(self.ctx, byref(evt), 100)
            if rc != 0:
                # Check for stall: no IMU data for too long
                if self._imu_count == last_data_count:
                    if stall_start is None:
                        stall_start = time.monotonic()
                    elif time.monotonic() - stall_start > 3.0:
                        reconnect_attempts += 1
                        print(f"  IMU stalled ({reconnect_attempts}x), reconnecting...")
                        logging.warning(f"IMU stalled after {self._imu_count} samples, reconnecting (attempt {reconnect_attempts})")
                        self._reconnect()
                        stall_start = None
                else:
                    last_data_count = self._imu_count
                    stall_start = None
                    reconnect_attempts = 0
                continue
            if evt.type == EVT_DETACHED:
                self.connected = False
                print("  IMU: device detached, reconnecting...")
                logging.warning("IMU device detached, reconnecting")
                self._reconnect()
                continue
            if evt.type != EVT_IMU or not evt.data.imu.valid:
                continue

            s = evt.data.imu
            self._imu_count += 1
            gyro = np.array([s.gyroRad[0], s.gyroRad[1], s.gyroRad[2]])
            accel = np.array([s.acc[0], s.acc[1], s.acc[2]])

            # ── Initialize orientation from accel on first sample ──
            if not self._cf_initialized:
                ax, ay, az = accel
                self._raw_pitch = np.arctan2(-ax, np.sqrt(ay*ay + az*az))
                self._raw_roll = np.arctan2(ay, az)
                self._raw_yaw = 0.0
                with self._lock:
                    self._yaw = 0.0
                    self._pitch = self._raw_pitch
                    self._roll = self._raw_roll
                    self._ref_yaw = 0.0
                    self._ref_pitch = self._raw_pitch
                    self._ref_roll = self._raw_roll
                self._cf_initialized = True
                continue

            # ── Subtract bias ──
            gc = gyro - self._gyro_bias
            gc = np.where(np.abs(gc) > GYRO_DEADZONE, gc, 0.0)
            # Save gyro magnitude for movement detection
            self._last_gyro_mag = float(np.sqrt(np.sum(gc * gc)))

            self._last_raw_gyro = gyro.copy()
            # Track peak gyro values for axis identification
            if not hasattr(self, '_peak_gyro'):
                self._peak_gyro = [0.0, 0.0, 0.0]
            for i in range(3):
                if abs(gc[i]) > abs(self._peak_gyro[i]):
                    self._peak_gyro[i] = gc[i]
            # Gyro axis diagnostic (every 500 samples = ~1 sec)
            if self._imu_count % 500 == 0:
                logging.info(f"GYRO_DIAG: gx={gc[0]:+.4f} gy={gc[1]:+.4f} gz={gc[2]:+.4f} | peaks: [{self._peak_gyro[0]:+.4f}, {self._peak_gyro[1]:+.4f}, {self._peak_gyro[2]:+.4f}] | yaw={math.degrees(self._raw_yaw):+.1f} pitch={math.degrees(self._raw_pitch):+.1f} roll={math.degrees(self._raw_roll):+.1f} | mag={self._last_gyro_mag:.4f}")

            # ── Compute dt ──
            dt = 0.002
            if self._last_tick > 0 and s.tick > self._last_tick:
                dt_t = (s.tick - self._last_tick) / 1000.0
                if 0.0001 < dt_t < 0.1:
                    dt = dt_t
            self._last_tick = s.tick

            gx, gy, gz = gc

            # ── Complementary filter ──
            pitch_gyro = self._raw_pitch + gx * dt  # gx confirmed working for pitch
            yaw_gyro   = self._raw_yaw   + gy * dt  # gy -> try yaw again (gz is dead on Air 4 Pro)
            roll_gyro  = self._raw_roll  + gz * dt  # gz=0 on Air 4 Pro

            ax, ay, az = accel
            g_norm = np.sqrt(ax*ax + ay*ay + az*az)
            if g_norm > 0.5:
                pitch_accel = np.arctan2(-ax, np.sqrt(ay*ay + az*az))
                roll_accel = np.arctan2(ay, az)
            else:
                pitch_accel = self._raw_pitch
                roll_accel = self._raw_roll

            CF_ALPHA = 0.999
            self._raw_pitch = CF_ALPHA * pitch_gyro + (1 - CF_ALPHA) * pitch_accel
            self._raw_roll = CF_ALPHA * roll_gyro + (1 - CF_ALPHA) * roll_accel
            self._raw_yaw = yaw_gyro * YAW_DECAY

            # ── Output update ──
            a = EMA_ALPHA
            with self._lock:
                self._yaw = self._raw_yaw
                self._pitch = a * self._raw_pitch + (1 - a) * self._pitch
                rd = (self._raw_roll - self._roll + np.pi) % (2*np.pi) - np.pi
                self._roll += rd * a

    def _reconnect(self):
        """Destroy and recreate the SDK connection when IMU stalls."""
        try:
            self.sdk.Rayneo_DisableImu(self.ctx)
        except Exception:
            pass
        try:
            self.sdk.Rayneo_Stop(self.ctx)
        except Exception:
            pass
        try:
            self.sdk.Rayneo_Destroy(self.ctx)
        except Exception:
            pass

        time.sleep(0.5)

        try:
            self.ctx = c_void_p()
            if self.sdk.Rayneo_Create(byref(self.ctx)) != 0:
                print("  Reconnect: Create failed")
                return
            self.sdk.Rayneo_SetTargetVidPid(self.ctx, config.RAYNEO_VID, config.RAYNEO_PID)
            if self.sdk.Rayneo_Start(self.ctx, 0) != 0:
                print("  Reconnect: Start failed")
                self.sdk.Rayneo_Destroy(self.ctx)
                self.ctx = c_void_p()
                return
            self.sdk.Rayneo_EnableImu(self.ctx)
            if hasattr(self.sdk, 'Rayneo_RequestDeviceInfo'):
                self.sdk.Rayneo_RequestDeviceInfo(self.ctx)
            self.connected = True
            self._cf_initialized = False  # Re-init orientation on first new sample
            self._last_tick = 0
            print("  IMU reconnected successfully")
            logging.info("IMU reconnected successfully")
        except Exception as e:
            print(f"  Reconnect failed: {e}")
            logging.warning(f"IMU reconnect failed: {e}")

    def get_orientation(self):
        """Get raw (yaw, pitch, roll) in radians, relative to reference."""
        with self._lock:
            dy = (self._yaw - self._ref_yaw + np.pi) % (2*np.pi) - np.pi
            dp = self._pitch - self._ref_pitch
            dr = (self._roll - self._ref_roll + np.pi) % (2*np.pi) - np.pi
            return (dy, dp, dr)

    def get_gyro_magnitude(self):
        """Thread-safe getter for gyro magnitude (used by SmoothFollow)."""
        with self._lock:
            return self._last_gyro_mag

    def get_raw_gyro(self):
        """Thread-safe getter for latest raw gyro values (gx, gy, gz)."""
        with self._lock:
            return (self._last_raw_gyro[0], self._last_raw_gyro[1], self._last_raw_gyro[2])

    def recenter(self):
        with self._lock:
            self._ref_yaw = self._yaw
            self._ref_pitch = self._pitch
            self._ref_roll = self._roll

    @property
    def imu_count(self):
        return self._imu_count

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self._cleanup_sdk()
        self.connected = False

    def _cleanup_sdk(self):
        """Release SDK resources. Safe to call multiple times."""
        if self.sdk and self.ctx:
            try:
                self.sdk.Rayneo_DisableImu(self.ctx)
            except Exception:
                pass
            try:
                self.sdk.Rayneo_Stop(self.ctx)
            except Exception:
                pass
            try:
                self.sdk.Rayneo_Destroy(self.ctx)
            except Exception:
                pass
            self.ctx = None

    def __del__(self):
        """Destructor: ensure SDK is released even on crash/GC."""
        self._running = False
        self._cleanup_sdk()

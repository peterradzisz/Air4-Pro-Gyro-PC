"""
Settings persistence for AirPin.

Loads from and saves runtime-adjustable settings to a JSON file
in the project root, so they survive restarts without touching config.py.
"""

import os
import json
import time
import atexit
import threading
import logging

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "airpin_settings.json")
_log = logging.getLogger(__name__)

# ── Debounced save state ──────────────────────────────────────────────────────
_dirty = False
_last_change_time = 0.0
_save_lock = threading.Lock()

# ── Default values ────────────────────────────────────────────────────────────

DEFAULTS = {
    # Head tracking
    "sensitivity":         0.5,   # 0.1 (very little) → 1.5 (very responsive)
    "invert_yaw":          False,
    "invert_pitch":        False,
    "pitch_enabled":       True,
    "yaw_decay":           1.0,
    # Movement detection (smooth follow)
    "move_start_rad":      0.052,  # ~3 deg/s — threshold to start tracking
    "move_stop_rad":       0.015,  # ~0.9 deg/s — threshold to stop tracking
    "still_time_sec":      2.0,   # seconds still before drift correction
    # Spatial
    "zoom":                1.0,
    # Display targeting
    "target_monitor":       0,     # monitor index to capture and track
    "hide_cursor":          False,  # default OFF - keep system cursor visible
    # Tracking sliders (Movies preset as default)
    "yaw_range":            1.0,
    "pitch_range":          1.0,
    "deadzone":             0.035,
    "gain":                 0.87,
    "decay":                1.0,
    "edge_zoom":            0.0,
    "snap_speed":           2.5,
    # USB reset
    "usb_reset":            False,
}


# ── Runtime state (lives in memory, synced to disk on change) ─────────────────

_settings = DEFAULTS.copy()


def _load():
    """Load settings from JSON file, merging with defaults for missing keys."""
    if not os.path.exists(_CONFIG_PATH):
        return
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        # Merge so new keys get defaults
        for k, v in DEFAULTS.items():
            _settings.setdefault(k, v)
        _settings.update(loaded)
    except (json.JSONDecodeError, IOError, OSError) as e:
        _log.warning(f"Settings load failed, using defaults: {e}")


def _save():
    """Write current settings to JSON file."""
    try:
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(_settings, f, indent=2)
    except Exception:
        pass


def get(key, default=None):
    """Return a setting value."""
    return _settings.get(key, default)


def set(key, value):
    """Set a setting value. Disk write is debounced (500ms after last change)."""
    global _dirty, _last_change_time
    _settings[key] = value
    _dirty = True
    _last_change_time = time.monotonic()


def get_all():
    """Return a copy of all current settings."""
    return dict(_settings)


def reset_all():
    """Reset every setting to its default and persist."""
    global _dirty, _last_change_time
    _settings.clear()
    _settings.update(DEFAULTS.copy())
    _dirty = True
    _last_change_time = time.monotonic()


def flush():
    """Force-save pending changes now (used by atexit on shutdown)."""
    global _dirty
    with _save_lock:
        if _dirty:
            _save()
            _dirty = False


def _debounce_loop():
    """Background thread: save 500ms after the last change."""
    global _dirty
    while True:
        time.sleep(0.5)
        if not _dirty:
            continue
        if (time.monotonic() - _last_change_time) < 0.5:
            continue
        with _save_lock:
            if _dirty:
                _save()
                _dirty = False


# Background debounce thread (daemon — dies with the process)
_debounce_thread = threading.Thread(target=_debounce_loop, daemon=True)
_debounce_thread.start()

# Ensure pending writes are flushed on normal interpreter shutdown
atexit.register(flush)


# Load on module import
_load()

"""
Settings persistence for AirPin.

Loads from and saves runtime-adjustable settings to a JSON file
in the project root, so they survive restarts without touching config.py.
"""

import os
import json

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "airpin_settings.json")

# ── Default values ────────────────────────────────────────────────────────────

DEFAULTS = {
    # Head tracking
    "sensitivity":         0.5,   # 0.1 (very little) → 1.5 (very responsive)
    "invert_yaw":          False,
    "invert_pitch":        False,
    "pitch_enabled":       False,
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
    except Exception:
        pass


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
    """Set a setting value and persist to disk immediately."""
    _settings[key] = value
    _save()


def get_all():
    """Return a copy of all current settings."""
    return dict(_settings)


def reset_all():
    """Reset every setting to its default and save."""
    _settings.clear()
    _settings.update(DEFAULTS.copy())
    _save()


# Load on module import
_load()

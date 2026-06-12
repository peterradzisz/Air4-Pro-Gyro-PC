# AirPin Extended -- Project State & Technical Notes

> Living doc for implementation details, tuning, and known issues.

---

## Architecture Overview

```
PC Monitor (game/desktop)
    |
    | DXGI Desktop Duplication (dxcam, GPU-level capture)
    | Falls back to BitBlt if dxcam unavailable
    | Auto-switches to DXGI when BitBlt returns black frames (exclusive fullscreen)
    |
    v
Main render loop (60Hz)
    |
    | raw gyro (bias-corrected) from IMU thread (500Hz)
    |
    v
SpatialTrackingFilter (4-layer anti-drift pipeline)
    |
    v
OpenGL fullscreen overlay on glasses display
    - WDA_EXCLUDEFROMCAPTURE (overlay invisible to screen capture)
    - WS_EX_LAYERED + TRANSPARENT (mouse passes through)
    - GL cursor drawn at shifted position (only when cursor on glasses)
    - Edge zoom: progressive zoom at screen edges for readability
```

### Axis Mapping (Air 4 Pro, confirmed from logs)

| gyroRad index | Physical motion | Notes |
|---|---|---|
| [0] (gx) | Pitch (up/down nod) | Strong signal, up to 2.6 rad/s |
| [1] (gy) | Yaw (left/right turn) | Strong signal, up to 3.1 rad/s |
| [2] (gz) | Roll (head tilt) | Active, not used for display shift |

NOTE: Reference implementation (Air 3S Pro) maps gz->yaw. Air 4 Pro has different IMU.
We confirmed gy->yaw empirically from log data.

---

## Filter Pipeline (SpatialTrackingFilter)

4-layer anti-drift system. Each layer catches what the previous misses:

```
Per frame (~60Hz):

  1. Input deadzone (speed_dead):
     - if |gyro_speed| < deadzone: resp=0, no integration
     - smoothstep curve from deadzone to speed_full (hardcoded 0.60)
     - Per-axis: yaw uses |gy| only, pitch uses |gx| only

  2. Directional clamp:
     - If output > 90% of max AND delta pushes further out: reject delta
     - Movement back toward center always accepted
     - Prevents bias from pressing against the wall at edges

  3. Output deadzone (hidden, 0.3px):
     - If |delta_px| < 0.3 AND gyro_speed < 2x input deadzone: reject
     - Catches residual bias that leaks past input deadzone
     - A 0.038 rad/s bias = ~0.18 px/frame, below 0.3 threshold = swallowed

  4. Still-lock:
     - When head is still (gyro_speed < 2x deadzone) for X seconds: freeze
     - No integration at all while locked
     - Resumes instantly on movement (gyro_speed > 2x deadzone)
     - Default 0.5s, configurable 0.0-2.0s

  5. Hard clamp:
     - output = clamp(output, -max_offset, +max_offset)
     - Max offset = yaw_range * screen_width, pitch_range * screen_height

  6. Decay (only when < 1.0):
     - output *= decay each frame
     - decay=1.0 = image stays where you left it (default)
```

---

## Capture System

| Method | Exclusive Fullscreen | Speed | Notes |
|--------|---------------------|-------|-------|
| **DXGI** (dxcam, primary) | YES | GPU-level | Captures everything. Same as OBS/Discord |
| **BitBlt** (fallback) | NO | GDI-level | Fails on exclusive fullscreen (black frame) |
| **Auto-switch** | YES | - | 5+ consecutive black BitBlt frames -> switch to DXGI |

dxcam is imported at module level (not lazily) to avoid comtypes threading lock crash.

---

## Settings (7 Sliders)

| # | Slider | Key | Range | Default | What it does |
|---|--------|-----|-------|---------|-------------|
| 0 | Yaw Range | yaw_range | 0.05-1.00 | 1.0 | Max horizontal shift as fraction of screen |
| 1 | Pitch Range | pitch_range | 0.05-1.00 | 1.0 | Max vertical shift as fraction of screen |
| 2 | Deadzone | deadzone | 0.01-0.20 | 0.035 | Gyro speed below which input ignored. Noise floor ~0.03 |
| 3 | Gain | gain | 0.10-1.00 | 0.99 | Pixels per radian. Higher = more shift per degree |
| 4 | Return Speed | decay | 0.990-1.000 | 1.0 | 1.000 = image stays put. <1.0 = drifts back to center |
| 5 | Edge Zoom | edge_zoom | 0.00-0.30 | 0.0 | Progressive zoom at edges (0% at center, X% at max offset) |
| 6 | Still Lock | still_lock_time | 0.0-2.0 | 0.5 | Seconds of stillness before position freezes. 0.0 = off |

Hidden params (no slider, set in code):
- `output_deadzone`: 0.3px (anti-drift safety net)
- `speed_full`: 0.60 (responsiveness curve upper bound, was slider, now hardcoded)

### Working Tuned Values (June 2026)

```json
{
  "deadzone": 0.035,
  "gain": 0.99,
  "yaw_range": 1.0,
  "pitch_range": 1.0,
  "decay": 1.0,
  "edge_zoom": 0.0,
  "still_lock_time": 0.5
}
```

---

## Key Files

| File | Purpose |
|------|---------|
| main.py | Entry point, render loop, edge zoom, cursor management |
| config.py | FOV=46, hotkeys, IMU params, edge zoom default |
| airpin/smooth_follow.py | SpatialTrackingFilter: 4-layer anti-drift, still-lock, directional clamp |
| airpin/imu_tracker.py | RayNeoSDK USB HID, bias calibration, auto-reconnect (3 retries + backoff) |
| airpin/spatial_renderer.py | OpenGL overlay, ortho projection, GL cursor, scissor clip |
| airpin/window_capture.py | DXGI (dxcam) primary + BitBlt fallback, auto-switch on black frames |
| airpin/settings_panel.py | 7 sliders + monitor dropdown + cursor toggle |
| airpin/settings_manager.py | JSON persistence for settings |

---

## Bugs Fixed

| Bug | Cause | Fix |
|-----|-------|-----|
| Yaw left-right didn't work | Wrong axis mapping (gz vs gy) | gy->yaw confirmed empirically |
| Image drifts back after movement | Combined gyro_mag opened gate for noise + tanh compression | Per-axis speed gate + hard clamp (removed tanh) |
| Movement limited to ~60% screen | tanh asymptotic curve compresses output | Hard clamp replaces tanh |
| Pitch drifts upward over time | get_raw_gyro() returned pre-bias gyro values | Returns gc.copy() (bias-corrected) |
| Edge zoom compounds infinitely | zoom *= edge_factor each frame | Separate display_zoom variable |
| Exclusive fullscreen shows black | BitBlt can't capture DX fullscreen | DXGI Desktop Duplication via dxcam |
| Double cursor on glasses | System cursor + GL cursor both visible | Per-monitor cursor hiding + GL cursor at shifted position |
| comtypes crash on import | dxcam imported lazily after threads start | Import dxcam at module level |
| capture_screen ImportError | Renamed to capture_screen_bitblt but main.py not updated | Fixed import |
| dxcam output_info() returns string | _find_dxcam_output parsed it as dict | Probe cameras directly via create+grab |

---

## Known Issues

### IMU Stall After ~10 Seconds (CRITICAL)

The RayNeoSDK stalls after several seconds of use. Auto-reconnect fires (Destroy+Create+Start+EnableImu), reports success, but no new IMU samples arrive. The SDK does not properly release the USB HID handle.

**Pattern in logs:**
```
IMU stalled after 8065 samples, reconnecting (attempt 1)
IMU reconnected successfully (attempt 1)
IMU stalled after 8065 samples  <-- imu_count STILL 8065!
```

**Workaround:** Unplug and replug glasses USB between runs.
**Root cause:** RayNeoSDK.dll USB HID handle management. Cannot be fixed in Python.
**Reconnect logic:** 3 attempts with 0.5s/1.0s/1.5s backoff. Handles zombie handles from previous runs but not mid-session stalls.

### Cursor Offset with Pitch

Image shifts vertically but mouse clicks go to real screen coordinates. Only yaw tracking is safe for clicking.

---

## Tuning Guide

| Symptom | Fix |
|---------|-----|
| Image drifts when still | Raise deadzone or still-lock time |
| Not enough shift range | Raise gain or yaw/pitch range |
| Too much shift | Lower gain |
| Jittery when still | Raise deadzone above noise floor (~0.03) |
| Image returns to center | Set Return Speed to 1.000 |
| Text hard to read at edges | Raise Edge Zoom (10-20%) |
| Small movements feel sticky | Lower still-lock time or deadzone |
| Wrong direction | Ctrl+Alt+I to invert yaw |
| Full reset | Ctrl+Alt+R to recenter |
| Game shows black screen | Should auto-switch to DXGI. If not, restart app |

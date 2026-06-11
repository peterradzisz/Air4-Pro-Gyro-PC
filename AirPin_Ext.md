# AirPin Extended -- Project State & Technical Notes

> Living doc for implementation details, tuning, and known issues.
> CLAUDE.md is kept pristine. This is the working reference.

---

## Architecture Overview

```
IMU (RayNeoSDK) -> raw gyro (gx, gy, gz) -> SpatialTrackingFilter -> pixel offset
```

The filter uses **raw gyro angular velocity** directly. No complementary filter.
This eliminates yaw drift and wrapping issues.

### Per-Axis Speed Gate (KEY DESIGN)

Each axis has its own speed gate:
- Yaw gate: opens when |gy| > deadzone
- Pitch gate: opens when |gx| > deadzone

Cross-axis noise does NOT bleed through. Pitch movement won't open the yaw gate.

### Axis Mapping (Air 4 Pro, confirmed from logs)

| gyroRad index | Physical motion | Notes |
|---|---|---|
| [0] (gx) | Pitch (up/down nod) | Strong signal, up to 2.6 rad/s |
| [1] (gy) | Yaw (left/right turn) | Strong signal, up to 3.1 rad/s |
| [2] (gz) | Roll (head tilt) | Active, not used for display shift |

NOTE: Reference implementation (Air 3S Pro) maps gz->yaw. Air 4 Pro has different IMU.
We confirmed gy->yaw empirically from log data.

---

## Filter Pipeline

```
Per frame (~60Hz):
  1. raw_gy = yaw angular velocity (rad/s)
  2. yaw_speed = abs(raw_gy)
  3. if yaw_speed < deadzone: skip (head still)
  4. resp = smoothstep(yaw_speed, deadzone, speed_full)
  5. delta_px = raw_gy * dt * ppr * gain * resp
  6. output += delta_px
  7. if decay < 1.0: output *= decay
  8. output = max_offset * tanh(output / max_offset)
```

---

## Settings (5 Sliders)

| Slider | Key | Range | What it does |
|--------|-----|-------|-------------|
| Yaw Range | yaw_range | 0.05-1.00 | Max horizontal shift as fraction of screen |
| Pitch Range | pitch_range | 0.05-1.00 | Max vertical shift as fraction of screen |
| Deadzone | deadzone | 0.01-0.20 (step 0.005) | Gyro speed below which delta ignored. Noise floor ~0.03 |
| Gain | gain | 0.10-1.00 | Pixels per radian. Higher = more shift per degree |
| Return Speed | decay | 0.990-1.000 | 1.000 = image stays put. <1.0 = drifts back |

### Working Tuned Values (June 2026)

```json
{
  "deadzone": 0.035,
  "gain": 0.87,
  "yaw_range": 1.0,
  "pitch_range": 1.0,
  "decay": 1.0
}
```

---

## Key Files

| File | Purpose |
|------|---------|
| main.py | Entry, render loop, wires raw gyro to filter |
| config.py | FOV=46, hotkeys, IMU params |
| airpin/smooth_follow.py | SpatialTrackingFilter: raw gyro integration |
| airpin/imu_tracker.py | RayNeoSDK USB HID, auto-reconnect |
| airpin/spatial_renderer.py | OpenGL overlay, ortho, scissor clip |
| airpin/settings_panel.py | 5 sliders + monitor dropdown |

---

## Bugs Fixed

| Bug | Cause | Fix |
|-----|-------|-----|
| Yaw left-right didn't work | Wrong axis mapping (gz vs gy) | gy->yaw confirmed empirically |
| Image drifts back after movement | Combined gyro_mag opened gate for noise + cross-axis bleed | Per-axis speed gate: yaw uses |gy| only |
| Movement limited to 10-15% screen | gain=1.0 with dead=0.01 let noise through, gain=0.15 too low | Tuned gain=0.87, dead=0.035 |
| update_pitch crash | Method missing | Added update_pitch() |
| Mirror/feedback | Overlay captured itself | WDA_EXCLUDEFROMCAPTURE |
| Image wrap-around | No clipping | GL_SCISSOR_TEST |

---

## Tuning Guide

| Symptom | Fix |
|---------|-----|
| Drifts back after movement | Raise deadzone (noise leaking through) |
| Not enough shift | Raise gain or yaw/pitch range |
| Too much shift | Lower gain |
| Jittery when still | Raise deadzone above noise floor (~0.03) |
| Image returns to center | Set Return Speed to 1.000 |
| Wrong direction | Ctrl+Alt+I to invert yaw |
| Full reset | Ctrl+Alt+R to recenter |
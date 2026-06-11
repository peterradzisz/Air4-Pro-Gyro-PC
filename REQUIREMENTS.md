# AirPin — Requirements Document

## Overview

AR spatial display app for RayNeo Air 4 Pro glasses. Pins the desktop screen in 3D space using head tracking, so content stays fixed when you turn your head. Supports both **extended mode** (glasses as separate display) and **duplicate mode** (glasses mirror laptop).

---

## Architecture & Display Setup

### Hardware Setup
- **PC Monitor** (4K, 3840×2160): Main development display. Python console, IDE, normal desktop. NOT affected by head tracking.
- **AR Glasses** (RayNeo Air 4 Pro, 1920×1080 or 4K): Connected via USB-C (DisplayPort Alt Mode + USB HID). In extended mode, appears as a separate Windows display. THIS is where the overlay and head tracking apply.
- **IMU**: Inside the glasses, communicates via USB HID (separate from display). Works regardless of whether the glasses display is active.

### App Responsibility Map

| Component | Location | Purpose |
|-----------|----------|---------|
| Transparent overlay | AR glasses display ONLY | Head-tracked shifted content + HUD + Settings panel |
| IMU thread | Background | Reads gyro/accel from glasses via USB HID |
| Screen capture | Background thread | Captures glasses display content via BitBlt |
| Python console | PC monitor | App output, hotkey feedback, logging |
| PC monitor display | **Untouched** | No overlay, no black box, no artifacts |

**Future TODO**: May move settings panel to PC monitor as a separate window for easier configuration without wearing glasses.

### Important Notes
- The app targets the AR glasses display by monitor index (configurable in settings)
- When glasses display is disconnected, only the PC monitor exists. App should handle gracefully.
- The target_monitor setting MUST point to the glasses display index when glasses are connected in extended mode.
- Glasses may appear as any monitor index depending on Windows display arrangement.
- IMU works via USB HID independently of the glasses display being active.

---

## Functional Requirements

### FR-1: Head Tracking
- **FR-1.1**: Track yaw (horizontal) and pitch (vertical) head movement via RayNeo Air 4 Pro IMU (USB HID, 500Hz)
- **FR-1.2**: Yaw tracking enabled by default. Pitch disabled by default (user toggle via Ctrl+Alt+P)
- **FR-1.3**: Complementary filter (gyro 99.9% + accel 0.1%) for orientation. EMA smoothing at 500Hz
- **FR-1.4**: Smooth Follow algorithm: masks gyro drift when head is still, instant 1:1 response when moving
- **FR-1.5**: Auto-bias calibration at startup (first 500 samples). Recenter with Ctrl+Alt+R

### FR-2: Spatial Display Rendering
- **FR-2.1**: Overlay renders captured screen content with pixel offset from head tracking
- **FR-2.2**: Overlay covers ONLY the target display (AR glasses), NOT the full virtual desktop
- **FR-2.3**: In extended mode: laptop display is completely untouched (no overlay, no artifacts)
- **FR-2.4**: In duplicate mode: both displays see the same overlay (unavoidable)
- **FR-2.5**: Transparent overlay (WS_EX_LAYERED + WS_EX_TRANSPARENT) — mouse clicks pass through to applications underneath
- **FR-2.6**: Overlay is TOPMOST so it stays above all other windows

### FR-3: Head Tracking Dampening
- **FR-3.1**: Maximum head-tracking shift: ±1 screen width (yaw), ±1 screen height (pitch)
- **FR-3.2**: Center zone (0 to ±half screen): 1:1 tracking — no dampening, full responsiveness
- **FR-3.3**: Edge zone (±half to ±full screen): cubic ease-out dampening — progressively slower
- **FR-3.4**: Hard clamp at ±1 full screen — no movement beyond this boundary
- **FR-3.5**: Smooth transition between zones (continuous first derivative, zero derivative at clamp)

### FR-4: Display Targeting
- **FR-4.1**: User selects which monitor is the AR glasses display (via settings panel or --monitor CLI arg)
- **FR-4.2**: App captures content from the target display only
- **FR-4.3**: App renders overlay on the target display only
- **FR-4.4**: Default target: monitor 1 (AR glasses). User can change and persist setting
- **FR-4.5**: App enumerates all displays at startup with GPU adapter info

### FR-5: Settings & Persistence
- **FR-5.1**: Settings panel accessible via Ctrl+Alt+S (OpenGL overlay on the glasses display)
- **FR-5.2**: Settings persist to `airpin_settings.json` — survive app restarts
- **FR-5.3**: Settings live-update: changes take effect immediately, no restart required
- **FR-5.4**: Adjustable settings:
  - Sensitivity (0.1 to 1.5, default 0.5) — head tracking responsiveness multiplier
  - Target monitor selection (dropdown)
  - Pitch enabled/disabled
  - Yaw invert
  - Hide system cursor on/off
  - Reset all to defaults button
- **FR-5.5**: When settings panel is open: mouse clicks are captured by overlay (WS_EX_TRANSPARENT temporarily removed)
- **FR-5.6**: When settings panel is closed: mouse clicks pass through normally

### FR-6: Screen Capture
- **FR-6.1**: BitBlt screen capture via GetDC(None) — works with any GPU (NVIDIA, AMD, Intel)
- **FR-6.2**: Captures the target display region at native resolution
- **FR-6.3**: Capture thread runs in background at configurable FPS (default 120)
- **FR-6.4**: Returns BGRA data directly to OpenGL (no channel swap)

### FR-7: Zoom
- **FR-7.1**: Zoom in/out via Ctrl+Alt++/- (10% steps, range 50%-300%)
- **FR-7.2**: Zoom reset via Ctrl+Alt+0

### FR-8: Audio Routing
- **FR-8.1**: Route system audio to glasses speaker (SmartGlasses via WASAPI)
- **FR-8.2**: Disable with --no-audio flag

### FR-9: Multi-Monitor Support
- **FR-9.1**: Supports monitors at any position (including negative coordinates)
- **FR-9.2**: Supports different resolutions per monitor
- **FR-9.3**: Supports mixed GPU adapters (e.g., NVIDIA primary + Intel for glasses)
- **FR-9.4**: GPU-agnostic: works with NVIDIA, AMD, Intel (uses BitBlt, not DXGI)

### FR-10: Cross-Platform Notes
- **FR-10.1**: Currently Windows-only (uses Win32 API for overlay, capture, hotkeys)
- **FR-10.2**: Linux/macOS would require different overlay and capture implementations
- **FR-10.3**: IMU communication (USB HID) is platform-independent via RayNeoSDK

---

## Non-Functional Requirements

### NFR-1: Performance
- **NFR-1.1**: Render loop at target FPS (default 120)
- **NFR-1.2**: IMU polling at 500Hz on separate thread
- **NFR-1.3**: Screen capture on separate thread (no blocking of render loop)
- **NFR-1.4**: OpenGL orthographic projection for 1:1 pixel quality (no perspective distortion)

### NFR-2: Compatibility
- **NFR-2.1**: Windows 10/11
- **NFR-2.2**: Python 3.10+
- **NFR-2.3**: Any GPU: NVIDIA GeForce, AMD Radeon, Intel UHD/Arc
- **NFR-2.4**: RayNeo Air 4 Pro (VID=0x1BBB PID=0xAF50, board_id=0x3A)
- **NFR-2.5**: RayNeo Air 3S Pro (same SDK, should work)

### NFR-3: Reliability
- **NFR-3.1**: Logging to `airpin.log` — startup info, display detection, hotkey actions, periodic status, crash tracebacks
- **NFR-3.2**: Graceful cleanup on exit (restore cursor, release SDK, stop threads)
- **NFR-3.3**: atexit handler ensures SDK cleanup even on crash

### NFR-4: Usability
- **NFR-4.1**: Global hotkeys work regardless of which window has focus
- **NFR-4.2**: Console output for immediate feedback
- **NFR-4.3**: HUD overlay shows tracking status, yaw/pitch values, zoom, FPS
- **NFR-4.4**: First-time user guidance: console prints hotkey list on startup

---

## Hotkeys

All hotkeys are Ctrl+Alt+... and work globally.

| Key | Action | Notes |
|-----|--------|-------|
| R | Recenter head tracking | Resets reference yaw/pitch to current orientation |
| T | Toggle yaw tracking | Enable/disable horizontal tracking |
| P | Toggle pitch tracking | Enable/disable vertical tracking (persisted) |
| I | Invert yaw direction | Flip horizontal tracking direction (persisted) |
| +/= | Zoom in | 10% steps |
| - | Zoom out | 10% steps |
| 0 | Reset zoom | Back to 100% |
| H | Toggle HUD | Show/hide status overlay |
| S | Settings panel | Opens interactive settings (mouse-enabled) |
| C | Toggle cursor | Hide/show system cursor |
| Shift+F | Focus game | Give keyboard focus to foreground window |
| Left | Add virtual display left | Requires Parsec VDD |
| Right | Add virtual display right | Requires Parsec VDD |
| Q | Quit | Clean shutdown |

---

## Settings File (`airpin_settings.json`)

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| sensitivity | float | 0.5 | Head tracking multiplier (0.1–1.5) |
| invert_yaw | bool | false | Flip horizontal tracking direction |
| invert_pitch | bool | false | Flip vertical tracking direction |
| pitch_enabled | bool | false | Enable pitch tracking |
| yaw_decay | float | 1.0 | Yaw decay factor (1.0 = no decay) |
| move_start_rad | float | 0.052 | Gyro threshold to start tracking (~3°/s) |
| move_stop_rad | float | 0.015 | Gyro threshold to stop tracking (~0.9°/s) |
| still_time_sec | float | 2.0 | Seconds still before drift correction |
| zoom | float | 1.0 | Default zoom level |
| target_monitor | int | 1 | Monitor index for AR glasses |
| hide_cursor | bool | false | Hide system cursor globally |

---

## Known Issues

1. **IMU may require USB replug** — if previous run didn't clean up SDK properly, device may be stale. Unplug/replug glasses before testing.
2. **Duplicate mode shows overlay on laptop** — unavoidable, both displays see the same content.
3. **Cursor offset with pitch** — vertical tracking shifts image but not cursor position.
4. **Yaw drift** — no magnetometer reference. Use Ctrl+Alt+R to recenter.
5. **Game capture** — BitBlt may not capture exclusive fullscreen games. Use borderless windowed.
6. **Parsec VDD** — virtual display features require Parsec Virtual Display Adapter installed.

---

## Tested Hardware

| Component | Details |
|-----------|---------|
| Glasses | RayNeo Air 4 Pro (board_id 0x3A) |
| GPU

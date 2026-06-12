# AirPin Extended

Fork of [AirPin](https://github.com/nomi-san/airpin) by nomi-san. Adds head-tracked spatial display for **RayNeo Air 4 Pro** AR glasses used as an **extended monitor** alongside your regular desktop/laptop screen.

> **Experimental** -- built for personal use on a specific hardware setup. Expect rough edges.

## What it does

You connect RayNeo Air 4 Pro glasses to your PC as a second display. AirPin runs a fullscreen overlay on the glasses that captures your desktop and applies head-tracking offset -- so the screen feels **pinned in 3D space**. Turn your head and the content stays where it is.

Your main monitor is completely untouched -- the overlay only covers the glasses display.

### Hardware required

- **RayNeo Air 4 Pro** AR glasses
- **HDMI + USB-A to USB-C cable** (or USB-C from GPU with DisplayPort Alt Mode -- rare)
  - HDMI carries video to the glasses (extended display)
  - USB-C carries IMU data (head tracking sensor)
- Windows 10/11 PC with a dedicated monitor

## Quick start

```
pip install -r requirements.txt
python main.py
```

The app should just work with defaults. Put on the glasses, turn your head.

If head tracking feels wrong, press `Ctrl+Alt+S` to open the settings panel.

### First-time setup

1. Connect glasses via HDMI + USB-C to your PC
2. In Windows Settings > Display, set glasses as **Extended display** (not duplicate)
3. Note which monitor number the glasses are (usually 0 or 1)
4. Run `python main.py` -- if the overlay is on the wrong screen, change it in the settings panel (`Ctrl+Alt+S`)

## Settings

Press `Ctrl+Alt+S` to open the settings panel. Defaults work well, but you can tune:

| Setting | Default | What it does |
|---------|---------|-------------|
| **Yaw Range** | 1.00 | Max horizontal shift (1.0 = full screen width) |
| **Pitch Range** | 1.00 | Max vertical shift (1.0 = full screen height) |
| **Deadzone** | 0.035 | Minimum head speed to trigger tracking. Higher = less sensitive to tiny movements |
| **Gain** | 0.87 | How much the image shifts per degree of head turn. Higher = more shift |
| **Return Speed** | 1.000 | 1.000 = image stays where you left it. Lower = slowly drifts back to center |

## Controls

All hotkeys are `Ctrl+Alt+...` and work globally:

| Key | Action |
|-----|--------|
| `R` | Recenter head tracking |
| `T` | Toggle yaw tracking on/off |
| `P` | Toggle pitch tracking on/off |
| `I` | Invert yaw direction |
| `S` | Open settings panel |
| `H` | Toggle HUD |
| `+` / `-` | Zoom in/out |
| `0` | Reset zoom |
| `Q` | Quit |

## How head tracking works

```
RayNeo Air 4 Pro IMU (500 Hz)
    |
    | Raw gyro angular velocity (gx, gy, gz)
    v
SpatialTrackingFilter
    |
    | Per-axis speed gate (deadzone filter)
    | Smoothstep responsiveness curve
    | Integration -> tanh soft clamp
    v
Pixel offset -> OpenGL overlay shifts the captured screen
```

Key design decisions:
- **Raw gyro, no complementary filter** -- avoids yaw drift and wrapping artifacts
- **Per-axis speed gate** -- yaw only tracks when yaw axis moves, pitch only when pitch axis moves. Cross-axis noise does not bleed through.
- **Speed-gated integration** -- below the deadzone, movement is ignored. This filters out heartbeat, breathing, and micro-sway.
- **Return Speed (decay)** -- at 1.0 the image stays pinned exactly where you left it. Set lower if you want it to drift back to center.

## Project structure

```
main.py                  Entry point, render loop
config.py                FOV, hotkeys, IMU params
airpin/
  imu_tracker.py         RayNeoSDK -> raw gyro via USB HID
  smooth_follow.py       SpatialTrackingFilter
  spatial_renderer.py    OpenGL fullscreen overlay
  window_capture.py      BitBlt screen capture
  settings_panel.py      Settings UI (5 sliders)
  settings_manager.py    JSON persistence
  hotkey_manager.py      Global hotkeys
  audio_router.py        WASAPI audio to glasses
  virtual_display.py     Parsec VDD virtual monitors
lib/
  RayNeoSDK.dll          IMU SDK
  libusb-1.0.dll         USB communication
airpin_settings.json     Saved settings
```

## Command-line options

```
python main.py [--no-imu] [--no-audio] [--monitor N]
```

| Option | Description |
|--------|-------------|
| `--no-imu` | Run without head tracking (fixed display) |
| `--no-audio` | Disable audio routing to glasses |
| `--monitor N` | Capture monitor N (default: 0) |

## Known limitations

- **RayNeo Air 4 Pro only** -- other glasses may need axis mapping changes
- **BitBlt capture** -- may not capture exclusive fullscreen games. Use borderless windowed
- **USB replug between runs** -- the SDK does not clean up USB HID cleanly. Unplug and replug glasses if IMU stalls
- **Yaw has no magnetometer** -- no absolute reference. Recenter with `Ctrl+Alt+R` if drift accumulates
- **Pitch causes cursor mismatch** -- image shifts vertically but mouse clicks go to real screen coordinates

## Credits

- **nomi-san** -- original [AirPin](https://github.com/nomi-san/airpin) project
- **[verncat](https://github.com/verncat/RayNeo-Air-3S-Pro-OpenVR)** -- RayNeoSDK and reference IMU implementation
- **[Parsec VDD](https://github.com/nomi-san/parsec-vdd)** -- Virtual display driver

## License

[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) — Peter Radziszewski

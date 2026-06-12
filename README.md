# AirPin Extended

<p align=center>
  <strong>Pin your desktop in 3D space with RayNeo Air 4 Pro AR glasses.</strong>
</p>

Put on the glasses. See your desktop floating in front of you. Turn your head — the screen stays where it is, like a virtual monitor pinned to the wall.

---

## Quick Start

### 1. What you need

- **RayNeo Air 4 Pro** AR glasses
- **HDMI + USB-A to USB-C** cable (both connections required)
- **Windows 10/11** PC with a dedicated monitor
- **Python 3.10+** ([download here](https://www.python.org/downloads/))

### 2. Download

Go to **[Releases](https://github.com/peterradzisz/Air4-Pro-Gyro-PC/releases/latest)** and download the **Source code (zip)**.

Or clone:


### 3. Install dependencies



### 4. Get the DLLs

Head tracking requires two DLLs. Download them and place in the project folder:

| DLL | Source |
|-----|--------|
|  | [verncat/RayNeo-Air-3S-Pro-OpenVR](https://github.com/verncat/RayNeo-Air-3S-Pro-OpenVR) — find in  folder |
|  | Same repo — find in  folder |

Both DLLs go in the **root folder** (next to ).

### 5. Connect the glasses

1. Plug **HDMI** into your GPU — glasses appear as a second display
2. Plug **USB-C** into your PC — sends head tracking data
3. Open **Windows Settings > System > Display**
4. Set glasses to **Extend** (not Duplicate)

### 6. Run

pygame 2.6.1 (SDL 2.28.4, Python 3.10.11)
Hello from the pygame community. https://www.pygame.org/contribute.html
  Found 2 display(s):
    [0] Monitor 0 @ (3840,0) 1920x1080 <-- target
    [1] Monitor 1 @ (0,0) 3840x2160 (primary)
Starting Virtual Display Manager...
  VDD: Parsec Virtual Display Adapter not found!
  Install from: https://github.com/nomi-san/parsec-vdd
  WARNING: Virtual displays not available. Side panels disabled.
Starting screen capture (monitor 0)...
  Screen capture: 1920x1080 DXGI
Connecting to RayNeo Air 4 Pro...
  SDK RequestDeviceInfo: rc=0
  Waiting for IMU data...
  IMU stalled (1x), reconnecting...
  WARNING: No IMU data after 3s (imu_count=0, connected=True)
  Connected!
  Waiting for first frame...
  Got first frame: 1920x1080
Starting audio routing...
  Audio: Output -> SmartGlasses (NVIDIA High Defin
  Audio: No loopback device found. Trying WASAPI loopback...
  Audio: If no sound, set glasses as default audio device in Windows Settings.
  Overlay: 1920x1080, LAYERED+TRANSPARENT, custom cursor
  IMU reconnected successfully (attempt 1)
  Focus -> Program Manager
  Focus release failed: (127, 'SetForegroundWindow', 'The specified procedure could not be found.')

=== AirPin Running ===
Ctrl+Alt+...
  R        Recenter        T   Track on/off
  P        Pitch on/off    I   Invert yaw
  Left     Add display L   Right  Add display R
  +/-      Zoom            0   Zoom reset
  H        HUD            Shift+F  Focus game
  S        Settings panel
  Q        Quit (removes virtual displays)

  IMU stalled (2x), reconnecting...
  IMU reconnected successfully (attempt 1)
  IMU stalled (3x), reconnecting...
  IMU reconnected successfully (attempt 1)
  IMU stalled (4x), reconnecting...
  IMU reconnected successfully (attempt 1)
  IMU stalled (5x), reconnecting...
  IMU reconnected successfully (attempt 1)
  IMU stalled (6x), reconnecting...
  IMU reconnected successfully (attempt 1)
  IMU stalled (7x), reconnecting...
  IMU reconnected successfully (attempt 1)
  IMU stalled (8x), reconnecting...
  IMU reconnected successfully (attempt 1)
  IMU stalled (9x), reconnecting...
  IMU reconnected successfully (attempt 1)
  IMU stalled (10x), reconnecting...
  IMU reconnected successfully (attempt 1)
  IMU stalled (11x), reconnecting...
  IMU reconnected successfully (attempt 1)
  IMU stalled (12x), reconnecting...
  IMU reconnected successfully (attempt 1)
  IMU stalled (13x), reconnecting...
  IMU reconnected successfully (attempt 1)
  IMU stalled (14x), reconnecting...
  IMU reconnected successfully (attempt 1)
  IMU stalled (15x), reconnecting...
  IMU reconnected successfully (attempt 1)
  IMU stalled (16x), reconnecting...
  IMU reconnected successfully (attempt 1)
  IMU stalled (17x), reconnecting...
  IMU reconnected successfully (attempt 1)
  IMU stalled (18x), reconnecting...
  IMU reconnected successfully (attempt 1)
  IMU stalled (19x), reconnecting...
  IMU reconnected successfully (attempt 1)

Shutting down...
Done.

Put on the glasses. You should see your desktop. Turn your head left — the image shifts right.

> **Wrong screen?** Press , change the monitor dropdown, restart.

---

## Controls

All shortcuts: hold  then press the key.

| Key | Action | When to use |
|-----|--------|-------------|
| **R** | **Recenter** | Screen drifted? Press this |
| **S** | **Settings** | Open/close settings panel |
| **T** | **Toggle tracking** | Pause/resume head tracking |
| **H** | **Toggle HUD** | Show/hide status info |
| **+/-** | **Zoom** | Make screen bigger/smaller |
| **0** | **Reset zoom** | Back to 100% |
| **Q** | **Quit** | Exit app |

**The 3 keys you need:**  (recenter),  (settings),  (pause tracking).

---

## Settings

Press  to open. Two presets available:

| Preset | Best for | Settings |
|--------|----------|----------|
| **Movies** | Watching video | Wide range, smooth, no edge zoom |
| **Games** | Gaming | Tight range, snappy, edge zoom on |

### Tracking sliders

| Setting | What it does |
|---------|-------------|
| **Yaw Range** | How far left/right the image can shift |
| **Pitch Range** | How far up/down (default OFF — see below) |
| **Deadzone** | Ignore tiny head movements. Higher = less jitter |
| **Gain** | How much image moves per degree of head turn |
| **Return Speed** | 1.000 = stays put. Lower = drifts back to center |
| **Edge Zoom** | Zooms in at edges so text stays readable |
| **Snap Speed** | How fast image returns to center when you stop moving |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| **Head tracking not working** | Check USB cable is connected. Try  to recenter |
| **Screen drifts to one side** |  to recenter. Unplug/replug USB if it persists |
| **Overlay on wrong screen** |  > change monitor dropdown > restart app |
| **Cursor clicks miss target** | This happens when pitch tracking is ON. Keep pitch OFF for gaming |
| **No sound in glasses** | Set glasses as default audio device in Windows Settings |
| **Black screen** | Make sure game is running in borderless windowed mode |

---

## Known Limitations

1. **Cursor offset** — head tracking shifts the image but mouse clicks go to real coordinates. Keep pitch OFF for gaming
2. **Yaw drift** — no magnetometer, so yaw drifts over time. Press  to recenter
3. **Duplicate mode not supported** — glasses must be set to Extend, not Duplicate

---

## Credits

- **nomi-san** — original [AirPin](https://github.com/nomi-san/airpin) project
- **[arigandores](https://github.com/arigandores)** — extended display support
- **[verncat](https://github.com/verncat/RayNeo-Air-3S-Pro-OpenVR)** — RayNeoSDK and IMU implementation
- **[Parsec VDD](https://github.com/nomi-san/parsec-vdd)** — Virtual display driver

## License

[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) — Peter Radziszewski

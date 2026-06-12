# AirPin Extended

**Pin your desktop in 3D space with RayNeo Air 4 Pro AR glasses.**

Put on the glasses. See your desktop floating in front of you. Turn your head - the screen stays where it is, like a virtual monitor pinned to the wall.

---

## Quick Start

### 1. What you need

- **RayNeo Air 4 Pro** AR glasses
- **HDMI + USB-A to USB-C** cable (both connections required)
- **Windows 10/11** PC or laptop
- **Python 3.10+** (download from python.org)

### 2. Download

Go to [Releases](https://github.com/peterradzisz/Air4-Pro-Gyro-PC/releases/latest) and download **Source code (zip)**.

Or clone the repo:

    git clone https://github.com/peterradzisz/Air4-Pro-Gyro-PC.git
    cd Air4-Pro-Gyro-PC

### 3. Install dependencies

    pip install -r requirements.txt

### 4. Get the DLLs

Head tracking requires two DLLs from [verncat/RayNeo-Air-3S-Pro-OpenVR](https://github.com/verncat/RayNeo-Air-3S-Pro-OpenVR):

- **RayNeoSDK.dll** - find in the bin/ folder
- **libusb-1.0.dll** - find in the examples/ folder

Place both in the project root (next to main.py).

### 5. Connect the glasses

1. Plug **HDMI** into your GPU - glasses appear as a second display
2. Plug **USB-C** into your PC - sends head tracking data
3. Open **Windows Settings > System > Display**
4. Set glasses to **Extend** (not Duplicate)

### 6. Run

    python main.py

Put on the glasses. You should see your desktop. Turn your head left - the image shifts right.

> Wrong screen? Press Ctrl+Alt+S, change monitor dropdown, restart.

---

## Controls

All shortcuts: hold **Ctrl+Alt** then press the key.

| Key | Action | When to use |
|-----|--------|-------------|
| **R** | Recenter | Screen drifted |
| **S** | Settings | Open/close settings panel |
| **T** | Toggle tracking | Pause/resume head tracking |
| **H** | Toggle HUD | Show/hide status info |
| **+/-** | Zoom | Bigger/smaller |
| **0** | Reset zoom | Back to 100% |
| **Q** | Quit | Exit |

**You need:** R (recenter), S (settings), T (pause tracking).

---

## Settings

Press **Ctrl+Alt+S** to open. Two presets:

| Preset | Best for | Settings |
|--------|----------|----------|
| **Movies** | Watching video | Wide range, smooth, no edge zoom |
| **Games** | Gaming | Tight range, snappy, edge zoom on |

### Tracking sliders

| Setting | What it does |
|---------|-------------|
| **Yaw Range** | How far left/right the image can shift |
| **Pitch Range** | How far up/down |
| **Deadzone** | Ignore tiny head movements. Higher = less jitter |
| **Gain** | How much image moves per degree of head turn |
| **Return Speed** | 1.000 = stays put. Lower = drifts back to center |
| **Edge Zoom** | Zooms in at edges so text stays readable |
| **Snap Speed** | How fast image returns to center when you stop moving |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Head tracking not working | Check USB cable. Ctrl+Alt+R to recenter |
| Screen drifts to one side | Ctrl+Alt+R to recenter. Unplug/replug USB |
| Overlay on wrong screen | Ctrl+Alt+S > change monitor > restart |
| Cursor clicks miss target | Pitch tracking shifts image but not cursor |
| No sound in glasses | Set glasses as default audio in Windows |
| Black screen | Use borderless windowed mode in game |

---

## Credits

- **nomi-san** - original [AirPin](https://github.com/nomi-san/airpin) project
- **[arigandores](https://github.com/arigandores)** - extended display support
- **[verncat](https://github.com/verncat/RayNeo-Air-3S-Pro-OpenVR)** - RayNeoSDK and IMU
- **[Parsec VDD](https://github.com/nomi-san/parsec-vdd)** - Virtual display driver

## License

[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) - Peter Radziszewski
# AirPin Extended

Head-tracked spatial display for **RayNeo Air 4 Pro** AR glasses.

Put on the glasses, see your desktop floating in space. Turn your head — the screen stays where it is, like a virtual monitor pinned to the wall.

## Setup

### What you need

- RayNeo Air 4 Pro AR glasses
- HDMI + USB-A to USB-C cable
- Windows 10/11 PC with a dedicated monitor

### Install

```
pip install -r requirements.txt
```

### Connect the glasses

1. Plug HDMI into your GPU — glasses get video as a **second display**
2. Plug USB-C into your PC — glasses send head tracking data
3. In Windows Settings > Display, make sure glasses are set to **Extend** (not duplicate)
4. Note which monitor number the glasses are (usually 0 or 1)

### First run

```
python main.py
```

Put on the glasses. You should see your desktop. Turn your head left — the image shifts right, as if the screen is floating in front of you.

If the overlay appears on the wrong screen, press `Ctrl+Alt+S` and change the monitor in the dropdown.

## Controls

All shortcuts use `Ctrl+Alt+` + key:

| Shortcut | What it does |
|----------|-------------|
| **R** | **Recenter** — reset the screen position to where you're looking |
| **S** | **Settings** — open the settings panel |
| **T** | **Toggle tracking** — pause/resume head tracking |
| **H** | **Toggle HUD** — show/hide debug info |
| **+/-** | **Zoom** in/out |
| **0** | Reset zoom to 100% |
| **Q** | **Quit** |

**Most useful:** `R` to recenter, `S` for settings, `T` to pause tracking.

## Settings

Press `Ctrl+Alt+S` to open the settings panel.

| Setting | What it does |
|---------|-------------|
| **Yaw Range** | How far the image can shift left/right. Higher = more room to look around |
| **Pitch Range** | How far the image can shift up/down |
| **Deadzone** | How still you need to be. Higher = less sensitive to tiny head movements |
| **Gain** | How much the image moves per degree of head turn. Higher = more responsive |
| **Return Speed** | 1.000 = image stays pinned where you left it. Lower = slowly drifts back to center |
| **Edge Zoom** | Zooms in at the edges of the screen so text stays readable |
| **Snap Speed** | How fast the image returns to center after you move your head back. 0 = disabled |

### Presets

Two presets at the top of the settings panel:

- **Movies** — wide view range, smooth movement, no edge zoom. Good for watching content
- **Games** — tight range, snappy response, edge zoom on. Good for gaming where you need precision

## Troubleshooting

**Head tracking not working / drifts to one side**
Press `Ctrl+Alt+R` to recenter. If it keeps drifting, unplug and replug the glasses USB cable.

**Overlay on wrong screen**
Press `Ctrl+Alt+S`, change the monitor in the dropdown, restart the app.

**Cursor in wrong place**
This happens with pitch tracking (looking up/down). The image shifts but mouse clicks go to the real position. Pitch is disabled by default for this reason.

## Credits

- **nomi-san** — original [AirPin](https://github.com/nomi-san/airpin) project
- **[arigandores](https://github.com/arigandores)** — extended display support
- **[verncat](https://github.com/verncat/RayNeo-Air-3S-Pro-OpenVR)** — RayNeoSDK and IMU implementation
- **[Parsec VDD](https://github.com/nomi-san/parsec-vdd)** — Virtual display driver

## License

[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) — Peter Radziszewski

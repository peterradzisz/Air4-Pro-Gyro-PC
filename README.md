# AirPin Extended

**Pin your desktop in 3D space with RayNeo Air 4 Pro AR glasses.**

Put on the glasses. See your desktop floating in front of you. Turn your head - the screen stays where it is, like a virtual monitor pinned to the wall.

![3DOF spatial pin working](docs/img/spatial_3dof.png)

---

## Download

### ✅ Portable Edition (recommended — no install needed)

**[⬇ AirPin-portable-v1.3.1.zip](https://github.com/peterradzisz/Air4-Pro-Gyro-PC/releases/download/v1.3.1/AirPin-portable-v1.3.1.zip)** (45 MB)

Includes Python and all dependencies. Just extract and double-click `run.bat`.

### From source (developers)

[Source code](https://github.com/peterradzisz/Air4-Pro-Gyro-PC/releases/latest) — requires Python 3.10-3.12.

---

## Features

**Tracking**
- Head tracking with drift prevention (gyro deadzone + continuous auto-calibration)
- Yaw (left/right) always on, pitch (up/down) toggleable
- Smooth follow filter with snap-back and deadzone
- Recenter anytime with Ctrl+Alt+R

**Display Quality** *(Ctrl+Alt+S > Display tab)*
- Brightness, Gamma, Sharpness adjustment
- Vignette correction for lens edges
- Chromatic aberration fix
- HDR boost (ACES tone mapping)
- Color temperature control

**Multi-Device Audio** *(Ctrl+Alt+S > Sound tab)*
- Route system audio to glasses + TV simultaneously
- Per-device on/off, volume, and delay controls
- Mute source (TV) to listen only through glasses
- VB-Cable auto-detect for zero-latency sync (see Audio Setup)
- Works at any sample rate (48kHz recommended)

**Virtual Displays** *(Ctrl+Alt+Left/Right)* ⚠️ *not tested by maintainer*
- Add virtual screens left/right via Parsec VDD
- Each display captured and rendered independently
- Windows manages cursor between displays natively

**Other**
- Screenshots: Ctrl+Alt+X saves glasses view to screenshots/
- Edge zoom: text stays readable at screen edges
- Cursor adjusts for head tracking offset (no swim with zoom)
- Settings persist across restarts
- Two presets: Movies (wide, smooth) and Games (tight, snappy)

---

## Quick Start

### Portable Edition (recommended)

1. **Download** [AirPin-portable-v1.3.1.zip](https://github.com/peterradzisz/Air4-Pro-Gyro-PC/releases/download/v1.3.1/AirPin-portable-v1.3.1.zip) (45 MB)
2. **Unblock**: Right-click `.zip` → Properties → check **Unblock** → OK
3. **Extract** anywhere
4. **Connect glasses**: HDMI → GPU, USB-C → PC
5. **Set display**: Windows Settings → System → Display → glasses to **Extend**
6. **Double-click `run.bat`**

No Python installation. No setup. Just works.

> 💡 If your display ever gets stuck, double-click **`reset.bat`** to fix it instantly.

### From source (developers)

1. Install **Python 3.11** (64-bit) from [python.org](https://www.python.org/downloads/release/python-3119/)
   - ⚠️ NOT 3.13+ · NOT from Microsoft Store
2. Download **Source code** from [Releases](https://github.com/peterradzisz/Air4-Pro-Gyro-PC/releases/latest)
3. Unblock + extract
4. Double-click **`setup.bat`** (installs dependencies)
5. Double-click **`run.bat`**

---

## Controls

All shortcuts: hold **Ctrl+Alt** then press the key.

| Key | Action | When to use |
|-----|--------|-------------|
| **R** | Recenter | Screen drifted |
| **Shift+R** | Reset settings | Back to defaults |
| **S** | Settings | Open/close settings panel |
| **T** | Toggle tracking | Pause/resume head tracking |
| **P** | Toggle pitch | Enable/disable vertical tracking |
| **I** | Invert yaw | Flip left/right direction |
| **C** | Cursor on glasses | Show/hide cursor on AR display |
| **X** | Screenshot | Save glasses view to screenshots/ folder |
| **H** | Toggle HUD | Show/hide status info |
| **+/-** | Zoom in/out | Bigger/smaller image |
| **0** | Reset zoom | Back to 100% |
| **Left/Right** | Add display | Add virtual display panel left/right |
| **Shift+F** | Focus game | Give keyboard focus to the game |
| **Q** | Quit | Exit (removes virtual displays) |

**The 3 keys you need:** R (recenter), S (settings), T (pause tracking).

---

## Settings

Press **Ctrl+Alt+S** to open. Three tabs:

### Presets

| Preset | Best for | Settings |
|--------|----------|----------|
| **Movies** | Watching video | Wide range, smooth, edge zoom for text |
| **Games** | Gaming / RTS | Tight range, snappy, mild edge zoom |

### Tracking tab

| Setting | What it does |
|---------|-------------|
| **Yaw Range** | How far left/right the image can shift |
| **Pitch Range** | How far up/down (enable pitch with Ctrl+Alt+P) |
| **Deadzone** | Ignore tiny head movements. Higher = less jitter + less drift |
| **Gain** | How much image moves per degree of head turn |
| **Return Speed** | 1.000 = stays put. Lower = drifts back to center (prevents drift) |
| **Edge Zoom** | Zooms in at edges so text stays readable |
| **Snap Speed** | How fast image returns to center when you stop moving |

### Display tab

| Setting | What it does |
|---------|-------------|
| **Brightness** | Overall image brightness |
| **Gamma** | Mid-tone brightness curve |
| **Sharpness** | Edge enhancement for text clarity |
| **Vignette** | Darken edges to hide lens distortion |
| **Chromatic** | Fix color fringing at edges |
| **HDR Boost** | ACES tone mapping for expanded dynamic range |
| **Temperature** | Warm/cool color adjustment |

### Sound tab

| Control | What it does |
|---------|-------------|
| **Device on/off** | Enable audio routing to each output (glasses, TV, speakers) |
| **Volume** | Per-device volume slider |
| **Delay** | Per-device audio delay (0-500ms) |
| **MUTE** | Mute the source device (TV) so only glasses play |

---

## Audio Setup

### Option A: Simple (no install needed)

AirPin captures system audio and routes it to your glasses. Works on any PC.

**Limitation:** The glasses receive audio slightly after the TV. If both are audible, you hear a slight echo.

**To remove echo:** Press MUTE in Settings > Sound. Listen only through the glasses.

### Option B: VB-Cable (perfect TV + glasses sync)

[VB-Cable](https://vb-audio.com/Cable/) is a free virtual audio device that eliminates echo. AirPin auto-detects it.

**Setup (2 minutes):**

1. Download **VB-Cable** from <https://vb-audio.com/Cable/>
2. Run  as administrator
3. Reboot
4. Set Windows output to **CABLE Input**
5. Run AirPin - it shows: 
6. In Settings > Sound, enable both **TV** and **Glasses**

Now both play at the same latency. No echo.

---

## 3D games (optional)

AirPin shows a 2D screen. For real 3D, you need a tool that renders the game twice. The good news: they just work with AirPin. Enable 3D in the game, and AirPin captures the side-by-side output like any other frame.

### Easiest: drop-in DLL

Get [wiz3D](https://github.com/effcol/wiz3D), copy the matching DLL folder next to your game’s `.exe`, launch the game. Stereo turns on automatically.

Works great for DirectX 9 (hundreds of games). DirectX 10/11 is growing — Tomb Raider, Hitman Absolution, Battlefield 3, and more. DirectX 12 is coming. See the wiz3D page for the full list.

### Other options

- [Rendepth](https://github.com/outmode/rendepth-reshade) — ReShade add-on. Works on almost any modern game. More setup, broader coverage.
- [VRto3D](https://github.com/oneup03/VRto3D) — for games with VR mods (mostly Unreal Engine). Most setup, but true stereo with head tracking.

### Note

In 3D mode the mouse cursor stays a single dot, which can look odd on menus. wiz3D and Rendepth both have fixes for this.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Display messed up / overlay stuck | Double-click **reset.bat** in the folder. Or press Ctrl+Alt+Q to quit, then Ctrl+Alt+Shift+R is for in-app reset. |
| "AirPin cannot start" message | You need: HDMI cable in GPU (display) + USB-C cable in PC (tracking) + Windows set to Extend mode |
| Head tracking not working | Check USB cable. Ctrl+Alt+R to recenter |
| Screen drifts | Ctrl+Alt+R to recenter. Increase Deadzone. Lower Return Speed |
| Overlay on wrong screen | Ctrl+Alt+S > change monitor > restart |
| Cursor clicks miss target | Turn off pitch (Ctrl+Alt+P). Keep pitch OFF for gaming |
| No sound in glasses | Settings (Ctrl+Alt+S) > Sound > enable device |
| Audio jitters/stutters | Set Windows output to 48000Hz (not 192000Hz) |
| Audio echo vs TV | Install VB-Cable (see Audio Setup) or mute TV |
| Black screen | Use borderless windowed mode in game. For 3D, see [3D games](#3d-games-optional) above. |
| Double-click setup.bat does nothing | You have the Microsoft Store Python stub. Uninstall it, install real Python 3.11 from [python.org](https://www.python.org/downloads/release/python-3119/) |
| "dxcam has no pre-built wheel" in setup | You have Python 3.13+. Uninstall it, install Python 3.11 or 3.12 |
| "64-bit Python required" in setup | You have 32-bit Python. Uninstall it, install the 64-bit installer from python.org |
| DLL load failed / WinError 126 | Right-click the .zip > Properties > Unblock > re-extract. Or run setup.bat which auto-unblocks |
| Wrong display captured | Ctrl+Alt+S > monitor dropdown > pick glasses > restart |

---

## Credits

- **nomi-san** - original [AirPin](https://github.com/nomi-san/airpin) project
- **[arigandores](https://github.com/arigandores)** - extended display support
- **[verncat](https://github.com/verncat/RayNeo-Air-3S-Pro-OpenVR)** - RayNeoSDK and IMU
- **[Parsec VDD](https://github.com/nomi-san/parsec-vdd)** - Virtual display driver

## License

[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) - Peter Radziszewski

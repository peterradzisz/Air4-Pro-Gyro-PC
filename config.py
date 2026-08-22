"""
Global configuration for AirPin.
"""

# Supported RayNeo glasses.
RAYNEO_DEVICES = (
    {"name": "RayNeo Air 4 Pro", "vid": 0x1BBB, "pid": 0xAF50, "interface": None},
    {"name": "RayNeo GT",        "vid": 0x3941, "pid": 0xAF50, "interface": 5},
)

RAYNEO_DEVICE_NAME = RAYNEO_DEVICES[0]["name"]
RAYNEO_VID = RAYNEO_DEVICES[0]["vid"]
RAYNEO_PID = RAYNEO_DEVICES[0]["pid"]
RAYNEO_INTERFACE = RAYNEO_DEVICES[0]["interface"]


def select_rayneo_device(device):
    """Select a device profile detected during preflight."""
    global RAYNEO_DEVICE_NAME, RAYNEO_VID, RAYNEO_PID, RAYNEO_INTERFACE
    RAYNEO_DEVICE_NAME = device["name"]
    RAYNEO_VID = device["vid"]
    RAYNEO_PID = device["pid"]
    RAYNEO_INTERFACE = device["interface"]


# Path to RayNeoSDK.dll (auto-detected)
SDK_DLL_PATH = None  # set at runtime

# Display settings
RENDER_WIDTH = None   # None = auto-detect from glasses display
RENDER_HEIGHT = None  # None = auto-detect from glasses display
TARGET_FPS = 120
GLASSES_DISPLAY_INDEX = None  # None = auto-detect (last display), or set 0,1,2...

# IMU / Head tracking
IMU_RATE_HZ = 500
HEAD_TRACKING_SENSITIVITY = 1.0  # CLI override only; runtime value is in settings_manager
INVERT_YAW = False
INVERT_PITCH = False
PITCH_ENABLED = False  # False = only track yaw (recommended, avoids cursor offset bug)
COMPLEMENTARY_ALPHA = 0.999

# Spatial windows
DEFAULT_WINDOW_DISTANCE = 3.0
DEFAULT_WINDOW_SCALE = 1.5
WINDOW_CAPTURE_FPS = 120
MAX_WINDOWS = 6

# Virtual space
FOV_HORIZONTAL_DEG = 46.0
FOV_VERTICAL_DEG = 25.0
NEAR_PLANE = 0.1
FAR_PLANE = 100.0

# Audio routing
AUDIO_ENABLED = True
GLASSES_AUDIO_DEVICE = "SmartGlasses"  # substring match for output device name
AUDIO_BUFFER_FRAMES = 1024
AUDIO_SAMPLE_RATE = 48000

# Global hotkeys (modifier, key) — only active when game has focus
# Modifiers: 0x0001=ALT, 0x0002=CTRL, 0x0004=SHIFT, 0x0008=WIN
MOD_CTRL = 0x0002
MOD_ALT = 0x0001
MOD_SHIFT = 0x0004
HOTKEYS = {
    'recenter':       (MOD_CTRL | MOD_ALT, ord('R')),
    'reset_settings': (MOD_CTRL | MOD_ALT | MOD_SHIFT, ord('R')),  # Ctrl+Alt+Shift+R
    'toggle_hud':     (MOD_CTRL | MOD_ALT, ord('H')),
    'toggle_tracking':(MOD_CTRL | MOD_ALT, ord('T')),
    'focus_game':     (MOD_CTRL | MOD_ALT | MOD_SHIFT, ord('F')),
    'invert_yaw':     (MOD_CTRL | MOD_ALT, ord('I')),
    'zoom_in':        (MOD_CTRL | MOD_ALT, 0xBB),  # Ctrl+Alt+=  (VK_OEM_PLUS)
    'zoom_out':       (MOD_CTRL | MOD_ALT, 0xBD),  # Ctrl+Alt+-  (VK_OEM_MINUS)
    'zoom_reset':     (MOD_CTRL | MOD_ALT, ord('0')),
    'toggle_pitch':   (MOD_CTRL | MOD_ALT, ord('P')),
    'panel_left':     (MOD_CTRL | MOD_ALT, 0x25),  # Ctrl+Alt+Left arrow (VK_LEFT)
    'panel_right':    (MOD_CTRL | MOD_ALT, 0x27),  # Ctrl+Alt+Right arrow (VK_RIGHT)
    'toggle_settings':(MOD_CTRL | MOD_ALT, ord('S')),  # ← Settings panel
    'toggle_cursor':   (MOD_CTRL | MOD_ALT, ord('C')),
    'quit':           (MOD_CTRL | MOD_ALT, ord('Q')),
    'screenshot':     (MOD_CTRL | MOD_ALT, ord('X')),  # Ctrl+Alt+X
}

# Zoom settings
ZOOM_DEFAULT = 1.0
ZOOM_STEP = 0.1
ZOOM_MIN = 0.5
ZOOM_MAX = 3.0

# Edge zoom: progressive zoom at screen edges based on head offset
EDGE_ZOOM_MAX = 0.30  # max additional zoom (30%) at max offset

# Panel spacing (pixels between panels)
PANEL_GAP = 50

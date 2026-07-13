"""
AirPin — Multi-monitor AR workspace for RayNeo Air 4 Pro.

Creates virtual displays via Parsec VDD. Windows natively manages
cursor movement between monitors. Each monitor is captured via DXGI
and rendered with head-tracking offset.

Global Hotkeys (Ctrl+Alt+...):
  R          Recenter         T   Track on/off
  P          Pitch on/off     I   Invert yaw
  Left/Right Add virtual display left/right
  +/-        Zoom             0   Reset zoom
  H          HUD              Shift+F  Focus game
  Q          Quit (removes all virtual displays)
"""

import ctypes
import ctypes.wintypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import sys
import os
import time
import math
import argparse
import logging

import numpy as np
import pygame
from pygame.locals import *

import config
from airpin.imu_tracker import ImuTracker
from airpin.window_capture import WindowManager
from airpin.spatial_renderer import SpatialRenderer
from airpin.smooth_follow import SpatialTrackingFilter
from airpin.hotkey_manager import HotkeyManager
from airpin.multi_audio import MultiAudioRouter
from airpin.virtual_display import VirtualDisplayManager
from airpin import settings_manager
from airpin.settings_panel import SettingsPanel, PANEL_X, PANEL_Y, PANEL_W
from OpenGL.GL import *

# Module-level Windows API access
user32 = ctypes.windll.user32

# Logging setup
log_path = os.path.join(os.path.dirname(__file__), 'airpin.log')
logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger('airpin')


def enumerate_displays():
    """List all active monitors with their positions and sizes.
    Returns list of dicts: {index, x, y, w, h, name, is_primary}
    """
    import ctypes
    import ctypes.wintypes

    results = []
    
    # Use EnumDisplayMonitors for accurate monitor rects
    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_int,
        ctypes.c_void_p,  # hMonitor
        ctypes.c_void_p,  # hdcMonitor
        ctypes.POINTER(ctypes.wintypes.RECT),  # lprcMonitor
        ctypes.wintypes.LPARAM,  # dwData
    )
    
    monitors_found = []
    
    def _enum_callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
        rect = lprcMonitor.contents
        monitors_found.append({
            'x': rect.left,
            'y': rect.top,
            'w': rect.right - rect.left,
            'h': rect.bottom - rect.top,
        })
        return 1  # continue
    
    callback = MONITORENUMPROC(_enum_callback)
    user32.EnumDisplayMonitors(None, None, callback, 0)
    
    # Get device names via EnumDisplayDevicesW
    class DISPLAY_DEVICE(ctypes.Structure):
        _fields_ = [
            ('cb', ctypes.wintypes.DWORD),
            ('DeviceName', ctypes.c_wchar * 32),
            ('DeviceString', ctypes.c_wchar * 128),
            ('StateFlags', ctypes.wintypes.DWORD),
            ('DeviceID', ctypes.c_wchar * 128),
            ('DeviceKey', ctypes.c_wchar * 128),
        ]
    
    device_names = {}
    for i in range(20):
        dev = DISPLAY_DEVICE()
        dev.cb = ctypes.sizeof(DISPLAY_DEVICE)
        if user32.EnumDisplayDevicesW(None, i, ctypes.byref(dev), 0):
            if dev.StateFlags & 2:  # DISPLAY_DEVICE_ATTACHED
                gpu_name = dev.DeviceString
                # Get monitor for this device
                mon_dev = DISPLAY_DEVICE()
                mon_dev.cb = ctypes.sizeof(DISPLAY_DEVICE)
                if user32.EnumDisplayDevicesW(dev.DeviceName, 0, ctypes.byref(mon_dev), 0):
                    gpu_name = mon_dev.DeviceString or dev.DeviceString
                device_names[len(device_names)] = f"{dev.DeviceName} ({gpu_name})"
    
    primary_w = user32.GetSystemMetrics(0)
    primary_h = user32.GetSystemMetrics(1)
    
    for idx, m in enumerate(monitors_found):
        is_primary = (m['x'] == 0 and m['y'] == 0 and m['w'] == primary_w and m['h'] == primary_h)
        name = device_names.get(idx, f"Monitor {idx}")
        results.append({
            'index': idx,
            'x': m['x'],
            'y': m['y'],
            'w': m['w'],
            'h': m['h'],
            'name': name,
            'is_primary': is_primary,
        })
    
    return results


def preflight_checks():
    """Safety checks before creating any overlay. Returns (passed: bool, message: str)."""
    import config

    # --- Check 1: At least 2 displays ---
    displays = enumerate_displays()
    if len(displays) < 2:
        msg = (
            f"Not enough displays ({len(displays)} found). AirPin needs your glasses as a second display.\n"
            f"\n"
            f"Fix:\n"
            f"  1. Connect HDMI cable from glasses to GPU\n"
            f"  2. Windows Settings > System > Display\n"
            f"  3. Set glasses to 'Extend' (not 'Duplicate')\n"
            f"  4. Run AirPin again"
        )
        return False, msg

    # --- Check 2: At least one non-primary (extended) display ---
    non_primary = [d for d in displays if not d['is_primary']]
    if not non_primary:
        msg = (
            "No extended display found. Glasses are set to 'Duplicate' mode.\n"
            "\n"
            "Fix:\n"
            "  Windows Settings > System > Display > set glasses to 'Extend'"
        )
        return False, msg

    # --- Check 3: RayNeo glasses detected on USB ---
    try:
        import usb.core
        dev = usb.core.find(idVendor=config.RAYNEO_VID, idProduct=config.RAYNEO_PID)
        if dev is None:
            msg = (
                "RayNeo glasses not detected on USB.\n"
                "\n"
                "The HDMI cable provides the display, but the USB-C cable provides head tracking.\n"
                "\n"
                "Fix:\n"
                "  1. Connect the USB-C cable from glasses to your PC\n"
                "  2. Run AirPin again"
            )
            return False, msg
    except ImportError:
        pass  # pyusb not available — don't block, SDK will catch it
    except Exception as e:
        logging.warning(f"USB check failed: {e}")
        # Don't block — the IMU tracker will handle the real error

    return True, "OK"


def main():
    # === PREFLIGHT SAFETY CHECKS ===
    # Run BEFORE any windows/overlays are created to prevent display corruption
    ok, msg = preflight_checks()
    if not ok:
        print()
        print("=" * 60)
        print("  AirPin cannot start")
        print("=" * 60)
        print()
        print(msg)
        print()
        print("=" * 60)
        log.info(f"Preflight check failed: {msg[:80]}")
        # Keep window open so user can read the message
        import time
        time.sleep(2)
        return

    parser = argparse.ArgumentParser(description="AirPin for RayNeo Air 4 Pro")
    parser.add_argument("--no-imu", action="store_true")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--monitor", type=int, default=0)
    parser.add_argument("--sensitivity", type=float, default=None)
    parser.add_argument("--fps", type=int, default=None)
    args = parser.parse_args()

    if args.sensitivity is not None:
        config.HEAD_TRACKING_SENSITIVITY = args.sensitivity
    capture_fps = args.fps or config.WINDOW_CAPTURE_FPS

    log.info("=" * 60)
    log.info("AirPin starting...")
    log.info(f"Args: {args}")

    # -- Enumerate displays --
    displays = enumerate_displays()
    target_mon = settings_manager.get("target_monitor", None)
    print(f"  Found {len(displays)} display(s):")
    for d in displays:
        print(f"    [{d['index']}] {d['name']} @ ({d['x']},{d['y']}) {d['w']}x{d['h']}{' (primary)' if d['is_primary'] else ''}")
    
    # Auto-pick rightmost display when target_monitor is None.
    # Windows typically places newly-extended displays to the right (highest X),
    # so this matches user intent when glasses are added as an extended display.
    if target_mon is None:
        if not displays:
            print("  ERROR: No displays found.")
            return
        rightmost = max(displays, key=lambda d: (d['x'], d['y'], d['index']))
        target_mon = rightmost['index']
        print(f"  Auto-selected rightmost display: [{target_mon}] {rightmost['name']} @ X={rightmost['x']}")
        log.info(f"target_monitor=None, auto-picked rightmost display index={target_mon}")
    else:
        # Validate explicit target_monitor
        if target_mon >= len(displays):
            print(f"  WARNING: target_monitor={target_mon} not found, falling back to 0")
            target_mon = 0
    
    # Re-print with target marker now that target_mon is finalized
    for d in displays:
        if d['index'] == target_mon:
            print(f"    [{d['index']}] {d['name']} <-- target")

    target_disp = displays[target_mon]
    log.info(f"Displays found: {len(displays)}, target_monitor={target_mon}")
    for d in displays:
        log.info(f"  [{d['index']}] {d['name']} @ ({d['x']},{d['y']}) {d['w']}x{d['h']}")

    # ── Virtual Display Manager (Parsec VDD) ─────────────────────────────
    vdd = VirtualDisplayManager()
    print("Starting Virtual Display Manager...")
    if not vdd.start():
        print("  WARNING: Virtual displays not available. Side panels disabled.")
        vdd = None


    # ── Screen capture (DXGI — primary monitor) ──────────────────────────
    # IMPORTANT: DXGI capture must start BEFORE the IMU tracker.
    # dxcam uses comtypes which initializes COM as MTA. Starting IMU before
    # DXGI can cause COM apartment model to interfere with USB HID polling.
    print(f"Starting screen capture (monitor {args.monitor})...")
    win_mgr = WindowManager(
        capture_fps=capture_fps,
        monitor_index=args.monitor,
        monitor_x=target_disp['x'],
        monitor_y=target_disp['y'],
        monitor_w=target_disp['w'],
        monitor_h=target_disp['h'],
    )
    if not win_mgr.start():
        print("ERROR: Screen capture failed.")
        if vdd:
            vdd.stop()
        return

    log.info(f"Screen capture started: {win_mgr.capture.width}x{win_mgr.capture.height}")

    # ── IMU tracker ──────────────────────────────────────────────────────
    # Apply persisted settings to config
    config.PITCH_ENABLED = settings_manager.get('pitch_enabled', False)
    config.INVERT_YAW = settings_manager.get('invert_yaw', False)
    config.INVERT_PITCH = settings_manager.get('invert_pitch', False)

    tracker = None
    if not args.no_imu:
        print("Connecting to RayNeo Air 4 Pro...")
        tracker = ImuTracker()
        try:
            tracker.start()
            time.sleep(0.1)
            tracker.recenter()
            print("  Connected!")
        except Exception as e:
            print(f"  WARNING: IMU failed: {e}")
            tracker = None

    if tracker:
        log.info("IMU tracker started and recentered")

    # Wait for first frame
    print("  Waiting for first frame...")
    for _ in range(50):
        if win_mgr.slot.pixel_data is not None:
            break
        time.sleep(0.1)
    if win_mgr.slot.pixel_data is not None:
        print(f"  Got first frame: {win_mgr.slot.width}x{win_mgr.slot.height}")
    else:
        print("  WARNING: No frame captured yet, continuing anyway")

    # ── Side panel captures (background thread) ─────────────────────────
    from airpin.window_capture import WindowSlot, capture_screen_bitblt
    import threading
    side_captures = {}  # vdd_index -> (info_dict, WindowSlot)
    side_capture_running = True

    def side_capture_loop():
        while side_capture_running:
            for vdd_idx, (info, slot) in list(side_captures.items()):
                result = capture_screen_bitblt(info['x'], 0, info['width'], info['height'])
                if result is not None:
                    w, h, data = result
                    slot.width = w
                    slot.height = h
                    slot.pixel_data = data
                    slot.texture_dirty = True
            time.sleep(1.0 / config.WINDOW_CAPTURE_FPS)

    side_thread = threading.Thread(target=side_capture_loop, daemon=True)
    side_thread.start()

    # ── Audio ────────────────────────────────────────────────────────────
    audio = MultiAudioRouter()
    if not args.no_audio and config.AUDIO_ENABLED:
        print("Starting audio routing...")
        if not audio.start():
            print("  Tip: Set 'SmartGlasses' as audio output in Windows Settings")

    # ── Renderer ─────────────────────────────────────────────────────────
    renderer = SpatialRenderer(
        target_x=target_disp['x'],
        target_y=target_disp['y'],
        target_w=target_disp['w'],
        target_h=target_disp['h'],
    )
    renderer.init()
    log.info(f"Renderer initialized: {renderer.width}x{renderer.height} at ({renderer.virt_x},{renderer.virt_y}), hwnd={renderer._hwnd}")
    log.info(f"Target display: {target_disp['name']} ({target_disp['w']}x{target_disp['h']}) at ({target_disp['x']},{target_disp['y']})")

    # Cursor state

    # ── Hotkeys ──────────────────────────────────────────────────────────
    hotkeys = HotkeyManager()
    for name, (mod, key) in config.HOTKEYS.items():
        hotkeys.register(name, mod, key)

    time.sleep(0.3)
    renderer.release_focus_once()

    print("\n=== AirPin Running ===")
    print("Ctrl+Alt+...")
    print("  R        Recenter        T   Track on/off")
    print("  Shift+R  Reset settings   (back to defaults)")
    print("  P        Pitch on/off    I   Invert yaw")
    print("  Left     Add display L   Right  Add display R")
    print("  +/-      Zoom            0   Zoom reset")
    print("  H        HUD            Shift+F  Focus game")
    print("  S        Settings         C   Cursor on/off")
    print("  X        Screenshot      Q   Quit")
    print()

    # First-run welcome toast
    if not settings_manager.get('first_run_done', False):
        renderer.show_toast("Welcome! Turn head to look around. Ctrl+Alt+S for settings.")
        settings_manager.set('first_run_done', True)

    # ── Main loop ────────────────────────────────────────────────────────
    clock = pygame.time.Clock()
    running = True
    show_hud = True
    tracking_enabled = True
    zoom = config.ZOOM_DEFAULT
    ppd_init = target_disp['w'] / math.radians(config.FOV_HORIZONTAL_DEG)
    yaw_range = settings_manager.get('yaw_range', 0.15)
    deadzone = settings_manager.get('deadzone', 0.08)
    resp = settings_manager.get('responsiveness', 0.40)
    follow = SpatialTrackingFilter(ppd_init, target_disp['w'],
                                    yaw_max_offset_frac=yaw_range,
                                    pitch_max_offset_frac=settings_manager.get('pitch_range', 0.10),
                                    speed_dead=deadzone,
                                    speed_full=0.40 + resp * 0.60)
    settings_panel = SettingsPanel(audio_router=audio)
    settings_panel.update_monitors(displays)
    # Settings start visible: remove WS_EX_TRANSPARENT so clicks reach panels
    if settings_panel.visible and renderer._hwnd:
        import win32gui, win32con
        ex_style = win32gui.GetWindowLong(renderer._hwnd, win32con.GWL_EXSTYLE)
        ex_style &= ~win32con.WS_EX_TRANSPARENT
        win32gui.SetWindowLong(renderer._hwnd, win32con.GWL_EXSTYLE, ex_style)
        # SWP_FRAMECHANGED forces Windows to re-evaluate hit-testing for the whole window
        win32gui.SetWindowPos(renderer._hwnd, 0, 0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOZORDER |
            win32con.SWP_NOACTIVATE | win32con.SWP_FRAMECHANGED)
        log.info('Settings visible at startup: click-through OFF')
    last_time = time.time()
    frame_count = 0
    _prev_mouse_down = False
    _screenshot_req = False

    while running:
        pygame.event.pump()
        triggered = hotkeys.poll()

        # Live-sync settings to config (so renderer reads current values)
        config.PITCH_ENABLED = settings_manager.get('pitch_enabled', False)
        config.INVERT_YAW = settings_manager.get('invert_yaw', False)
        config.INVERT_PITCH = settings_manager.get('invert_pitch', False)

        if triggered:
            log.info(f"Hotkeys triggered: {triggered}")

        frame_count += 1
        if frame_count % 600 == 0:
            has_frame = win_mgr.slot.pixel_data is not None
            log.info(f"Loop OK - px_off={pixel_offset_x:.0f}px, zoom={zoom}, tracking={tracking_enabled}, fps={clock.get_fps():.0f}, has_frame={has_frame}")

        if 'quit' in triggered:
            log.info("Quit requested")
            running = False
        if 'recenter' in triggered and tracker:
            tracker.recenter()
            follow.recenter()
            print("  Recentered!")
            log.info("Recentered")
            renderer.show_toast("Recentered")
        if 'reset_settings' in triggered:
            settings_manager.reset_all()
            for k in ["yaw_range", "pitch_range", "deadzone", "gain", "decay", "edge_zoom", "snap_speed", "usb_reset"]:
                setattr(settings_panel, "_" + k, settings_manager.get(k))
            settings_panel._display.reset_all()
            renderer.show_toast("Settings reset to defaults")
            print("  Settings reset to defaults!")
            log.info("Settings reset to defaults via Ctrl+Alt+Shift+R")
        if 'toggle_tracking' in triggered:
            tracking_enabled = not tracking_enabled
            if tracking_enabled and tracker:
                tracker.recenter()
            print(f"  Tracking: {'ON' if tracking_enabled else 'OFF'}")
            log.info(f"Tracking: {'ON' if tracking_enabled else 'OFF'}")
            renderer.show_toast(f"Tracking: {'ON' if tracking_enabled else 'OFF'}")
        if 'toggle_hud' in triggered:
            show_hud = not show_hud
            log.info(f"HUD: {'ON' if show_hud else 'OFF'}")
            renderer.show_toast(f"HUD: {'ON' if show_hud else 'OFF'}")
        if 'invert_yaw' in triggered:
            config.INVERT_YAW = not config.INVERT_YAW
            settings_manager.set('invert_yaw', config.INVERT_YAW)
            print(f"  Yaw invert: {config.INVERT_YAW}")
            log.info(f"Yaw invert: {config.INVERT_YAW}")
            renderer.show_toast(f"Yaw Invert: {'ON' if config.INVERT_YAW else 'OFF'}")
        if 'focus_game' in triggered:
            renderer.release_focus_once()
            log.info("Focus released to game")
        if 'zoom_in' in triggered:
            zoom = min(zoom + config.ZOOM_STEP, config.ZOOM_MAX)
            log.info(f"Zoom: {zoom}")
            renderer.show_toast(f"Zoom: {zoom:.0%}")
        if 'zoom_out' in triggered:
            zoom = max(zoom - config.ZOOM_STEP, config.ZOOM_MIN)
            log.info(f"Zoom: {zoom}")
            renderer.show_toast(f"Zoom: {zoom:.0%}")
        if 'zoom_reset' in triggered:
            zoom = config.ZOOM_DEFAULT
            log.info(f"Zoom reset: {zoom}")
            renderer.show_toast(f"Zoom: {zoom:.0%}")
        if 'toggle_pitch' in triggered:
            config.PITCH_ENABLED = not config.PITCH_ENABLED
            settings_manager.set('pitch_enabled', config.PITCH_ENABLED)
            print(f"  Pitch: {'ON' if config.PITCH_ENABLED else 'OFF'}")
            log.info(f"Pitch: {'ON' if config.PITCH_ENABLED else 'OFF'}")
            renderer.show_toast(f"Pitch: {'ON' if config.PITCH_ENABLED else 'OFF'}")
        if 'toggle_settings' in triggered:
            settings_panel.toggle()
            # Toggle mouse click-through: when panel is visible, remove WS_EX_TRANSPARENT so clicks reach us
            if renderer._hwnd:
                import win32gui, win32con
                ex_style = win32gui.GetWindowLong(renderer._hwnd, win32con.GWL_EXSTYLE)
                if settings_panel.visible:
                    ex_style &= ~win32con.WS_EX_TRANSPARENT  # allow clicks
                else:
                    ex_style |= win32con.WS_EX_TRANSPARENT   # pass through
                win32gui.SetWindowLong(renderer._hwnd, win32con.GWL_EXSTYLE, ex_style)
                win32gui.SetWindowPos(renderer._hwnd, 0, 0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOZORDER |
                    win32con.SWP_NOACTIVATE | win32con.SWP_FRAMECHANGED)
            log.info(f"Settings panel: {'shown' if settings_panel.visible else 'hidden'} (click-through: {'OFF' if settings_panel.visible else 'ON'})")
        if 'toggle_cursor' in triggered:
            current = settings_manager.get("hide_cursor", True)
            settings_manager.set("hide_cursor", not current)
            if not current:
                print("  Cursor on glasses: ON (GL cursor drawn)")
            else:
                print("  Cursor on glasses: OFF (no cursor on glasses)")
            log.info(f"Show GL cursor: {not current}")
        if 'screenshot' in triggered:
            _screenshot_req = True
            log.info("Screenshot requested")

        # ── Add virtual displays ──
        if ('panel_left' in triggered or 'panel_right' in triggered) and vdd:
            direction = 'left' if 'panel_left' in triggered else 'right'
            # Match primary monitor resolution for consistent quality
            primary_w = ctypes.windll.user32.GetSystemMetrics(0)
            primary_h = ctypes.windll.user32.GetSystemMetrics(1)
            info = vdd.add_display(primary_w, primary_h, 120, position=direction)
            if info:
                slot = WindowSlot(f"VDD-{direction}")
                side_captures[info['index']] = (info, slot)
                time.sleep(1.0)  # let Windows settle
                # Resize overlay (recreates GL context — all textures invalidated)
                renderer.reinit_size()
                # Reset all slot texture references (old GL context is dead)
                win_mgr.slot.gl_texture_id = None
                win_mgr.slot.texture_dirty = True
                for _, (_, s) in side_captures.items():
                    s.gl_texture_id = None
                    s.texture_dirty = True
                print(f"  Use Win+Shift+{'Left' if direction == 'left' else 'Right'} to move windows to it.")

        # ── Head orientation with Smooth Follow ──
        now = time.time()
        dt_ms = (now - last_time) * 1000.0
        last_time = now

        if tracker:
            tracker.usb_reset_enabled = settings_manager.get('usb_reset', True)
            tracker.gyro_deadzone = max(0.005, settings_manager.get('deadzone', 0.08) * 0.25)
            tracker.gyro_deadzone = max(0.005, settings_manager.get('deadzone', 0.08) * 0.25)

        if tracker and tracking_enabled and tracker.imu_count > 0:
            gyro_mag = tracker.get_gyro_magnitude()
            # Get raw gyro angular velocities (rad/s) -- bypass complementary filter
            # Air 4 Pro axis mapping: gx=[0] pitch, gy=[1] yaw, gz=[2] roll
            raw_gx, raw_gy, raw_gz = tracker.get_raw_gyro()
            # Update filter params from settings
            follow.yaw_max_offset = settings_manager.get('yaw_range', 0.15) * target_disp['w']
            follow.pitch_max_offset = settings_manager.get('pitch_range', 0.10) * target_disp['h']
            follow.speed_dead = settings_manager.get('deadzone', 0.08)
            follow.speed_full = 0.60  # hardcoded, responsiveness slider removed
            follow.gain = settings_manager.get('gain', 0.40)
            follow.decay = settings_manager.get('decay', 1.0)
            follow.snap_speed = settings_manager.get('snap_speed', 2.5)
            follow.snap_return = settings_manager.get('snap_return', 0.5)
            # Yaw: raw gyro[1] = yaw angular velocity (rad/s)
            # Use per-axis speed for gate: yaw gate uses |gy| only
            yaw_sign = -1.0 if config.INVERT_YAW else 1.0
            yaw_speed = abs(raw_gy)
            pixel_offset_x = follow.update(yaw_sign * raw_gy, yaw_speed)
            # Pitch: raw gyro[0] = pitch angular velocity (rad/s)
            if settings_manager.get('pitch_enabled', False):
                pitch_sign = -1.0 if config.INVERT_PITCH else 1.0
                pitch_speed = abs(raw_gx)
                follow.update_pitch(pitch_sign * raw_gx, pitch_speed)
                pixel_offset_y = follow.pitch_output
            else:
                pixel_offset_y = 0.0
            # Diagnostic
            if frame_count % 600 == 0:
                resp_val = follow._responsiveness(gyro_mag)
                log.info(f"IMU diag: gy={raw_gy:+.4f} gx={raw_gx:+.4f} px_off={pixel_offset_x:.0f}px gain={follow.gain:.2f} decay={follow.decay:.4f} dead={settings_manager.get('deadzone', 0.08):.2f} mag={gyro_mag:.4f} resp={resp_val:.3f} yaw_out={follow.output:.0f} imu={tracker.imu_count}")
        else:
            pixel_offset_x, pixel_offset_y = 0.0, 0.0
            # Diagnostic: why is head tracking not active?
            if frame_count % 600 == 0 and tracker is not None:
                log.info(f"IMU inactive: tracking_enabled={tracking_enabled}, imu_count={tracker.imu_count if tracker else 'no tracker'}, connected={tracker.connected if tracker else 'N/A'}")
                if tracker and not tracker.connected:
                    renderer.show_toast("Head tracking lost - Ctrl+Alt+R to recenter")

        # Edge zoom: progressive zoom based on distance from center
        # Applied to a separate display_zoom so it doesn't compound into base zoom
        display_zoom = zoom
        edge_zoom_setting = settings_manager.get('edge_zoom', 0.0)
        if edge_zoom_setting > 0.0 and follow.yaw_max_offset > 0:
            offset_ratio = abs(pixel_offset_x) / follow.yaw_max_offset
            offset_ratio = min(1.0, offset_ratio)
            display_zoom = zoom * (1.0 + edge_zoom_setting * offset_ratio)

        # ── Build panel list: main + virtual displays ──
        panels_render = []
        main_slot = win_mgr.slot
        panels_render.append((0, main_slot))

        if vdd:
            gap = getattr(config, 'PANEL_GAP', 50)
            left_count = 0
            right_count = 0
            for idx, device_name, position, actual_x, actual_w, actual_h in vdd.get_displays():
                # Visual gap: increases with each panel in that direction
                # so gap exists between ALL panels, not just main<->side
                if position == 'left':
                    left_count += 1
                    offset = actual_x - gap * left_count
                else:
                    right_count += 1
                    offset = actual_x + gap * right_count

                if idx in side_captures:
                    panels_render.append((offset, side_captures[idx][1]))
                else:
                    panels_render.append((offset, main_slot))

        # ── Render all panels ──
        offsets = [p[0] for p in panels_render]
        slots = [p[1] for p in panels_render]

        # Sync display quality settings to shader pipeline
        dp = settings_panel.display
        pipeline = renderer.pipeline
        pipeline.brightness = dp.brightness
        pipeline.gamma = dp.gamma
        pipeline.sharpness = dp.sharpness
        pipeline.vignette = dp.vignette
        pipeline.chromatic = dp.chromatic
        pipeline.temperature = dp.temperature
        pipeline.enable_brightness = dp.enable_brightness
        pipeline.enable_gamma = dp.enable_gamma
        pipeline.enable_sharpness = dp.enable_sharpness
        pipeline.enable_vignette = dp.enable_vignette
        pipeline.enable_chromatic = dp.enable_chromatic
        pipeline.enable_temperature = dp.enable_temperature
        pipeline.hdr = dp.hdr
        pipeline.enable_hdr = dp.enable_hdr

        renderer.render_panels(slots, offsets, pixel_offset_x, pixel_offset_y, display_zoom)

        # -- Cursor --
        # The overlay window has a NULL class cursor so Windows never draws
        # the system cursor over our window. We only draw the GL cursor here.
        pt = ctypes.wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        cursor_on_glasses = (target_disp['x'] <= pt.x < target_disp['x'] + target_disp['w'] and
                             target_disp['y'] <= pt.y < target_disp['y'] + target_disp['h'])
        if cursor_on_glasses and settings_manager.get("hide_cursor", True):
            if settings_panel.visible:
                # Settings open: cursor at real position (panels are at fixed pos)
                renderer.draw_cursor(0, 0, 1.0)
            else:
                # Settings closed: cursor tracks with shifted/zoomed image
                renderer.draw_cursor(pixel_offset_x, pixel_offset_y, zoom)
        # ── HUD ──
        if show_hud:
            n_vdd = len(vdd.get_displays()) if vdd else 0
            # Determine IMU status for HUD indicator
            imu_status = 'disabled'
            if tracker:
                if tracker.connected and tracker.imu_count > 0:
                    imu_status = 'connected'
                else:
                    imu_status = 'stalled'
            renderer.draw_hud({
                'tracking': tracking_enabled,
                'pitch_enabled': config.PITCH_ENABLED,
                'zoom': zoom,
                'yaw': pixel_offset_x,
                'pitch': pixel_offset_y,
                'cap_w': win_mgr.capture.width,
                'cap_h': win_mgr.capture.height,
                'panels': [f"Main"] + [f"VDD-{d[2]}" for d in (vdd.get_displays() if vdd else [])],
                'imu_status': imu_status,
            })
        renderer.draw_toast()

        # -- Settings panel mouse handling --
        # Track mouse state every frame (prevents stale _prev_mouse_down)
        # Use GetAsyncKeyState instead of pygame.mouse.get_pressed()
        # pygame events dont reach LAYERED+NOACTIVATE windows reliably
        mouse_down_now = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
        if settings_panel.visible:
            # Get actual cursor position (GetCursorPos works even with transparent windows)
            pt = ctypes.wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            clicked = mouse_down_now and not _prev_mouse_down  # edge detection

            # Calculate mouse coords for each panel
            p1_mx = pt.x - renderer.virt_x - PANEL_X
            p1_my = pt.y - renderer.virt_y - PANEL_Y
            p2_x = PANEL_X + PANEL_W + 10
            p2_mx = pt.x - renderer.virt_x - p2_x
            p2_my = pt.y - renderer.virt_y - PANEL_Y
            p3_x = PANEL_X + 2 * (PANEL_W + 10)
            p3_mx = pt.x - renderer.virt_x - p3_x
            p3_my = pt.y - renderer.virt_y - PANEL_Y

            # Route to correct panel
            if 0 <= p3_mx <= PANEL_W and 0 <= p3_my <= 600:
                settings_panel.handle_sound_mouse(p3_mx, p3_my, clicked)
                if not mouse_down_now:
                    settings_panel.handle_mouse_up()
            elif 0 <= p2_mx <= PANEL_W and 0 <= p2_my <= 420:
                settings_panel.handle_display_mouse(p2_mx, p2_my, clicked)
                if not mouse_down_now:
                    settings_panel.handle_mouse_up()
            else:
                settings_panel.handle_mouse(p1_mx, p1_my, clicked)
                if not mouse_down_now:
                    settings_panel.handle_mouse_up()
        _prev_mouse_down = mouse_down_now

        # -- Settings panel render --
        if settings_panel.visible:
            panel_result = settings_panel.render()
            if panel_result:
                # panel_result is now two tuples: (tracking_panel, display_panel)
                if not isinstance(panel_result[0], tuple):
                    # Fallback: single panel
                    panels_to_draw = [panel_result]
                else:
                    panels_to_draw = list(panel_result)
                for i, pdata in enumerate(panels_to_draw):
                    surf, px, py, pw, ph = pdata
                    data = pygame.image.tostring(surf, "RGBA", True)
                    tex_id_name = f"_gl_tex_{i}"
                    tex_id = getattr(settings_panel, tex_id_name, None)
                    if tex_id is None:
                        tex_id = glGenTextures(1)
                        setattr(settings_panel, tex_id_name, tex_id)
                    glBindTexture(GL_TEXTURE_2D, tex_id)
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, pw, ph, 0,
                                 GL_RGBA, GL_UNSIGNED_BYTE, data)
                    glEnable(GL_TEXTURE_2D)
                    glColor4f(1, 1, 1, 1)
                    gpx = renderer.virt_x + px
                    gpy = renderer.virt_y + py
                    glBegin(GL_QUADS)
                    glTexCoord2f(0, 1); glVertex2f(gpx, gpy)
                    glTexCoord2f(1, 1); glVertex2f(gpx + pw, gpy)
                    glTexCoord2f(1, 0); glVertex2f(gpx + pw, gpy + ph)
                    glTexCoord2f(0, 0); glVertex2f(gpx, gpy + ph)
                    glEnd()

        if _screenshot_req:
            _screenshot_req = False
            import datetime, os
            os.makedirs("screenshots", exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = f"screenshots/airpin_{ts}.png"
            renderer.capture_screenshot(path)
            renderer.show_toast(f"Screenshot saved")

        pygame.display.flip()
        clock.tick(config.TARGET_FPS)

    # ── Cleanup (cursor first, then VDD, then everything else) ───────────
    print("\nShutting down...")

    side_capture_running = False
    time.sleep(0.05)  # let background thread exit before clearing
    side_captures.clear()
    if vdd:
        vdd.stop()
    hotkeys.unregister_all()
    audio.stop()
    win_mgr.stop()
    renderer.cleanup()
    if tracker:
        tracker.stop()
    pygame.quit()
    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nCRASH: {e}")
        import traceback
        traceback.print_exc()
        logging.critical(f"CRASH: {e}", exc_info=True)
    finally:
        # ALWAYS restore cursor + remove virtual displays
        try:
            ctypes.windll.user32.SystemParametersInfoW(0x0057, 0, None, 0)
        except Exception:
            pass

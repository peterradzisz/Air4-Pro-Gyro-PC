"""Settings panel overlay for AirPin. Toggle with Ctrl+Alt+S."""

import math
import pygame
from airpin import settings_manager
from airpin.display_settings import DisplayQualityTab
from airpin.sound_settings import SoundPanel

PANEL_W = 400
PANEL_H = 810
PANEL_X = 40
PANEL_Y = 280
SLIDER_X = 20
SLIDER_W = 360
SLIDER_H = 8
KNOB_R = 12
BTN_X = 20
BTN_Y = 580
BTN_W = 360
BTN_H = 36
DROP_X = 20
DROP_W = 360
DROP_H = 28

PRESETS = {
    "movies": {
        "yaw_range": 1.0,
        "pitch_range": 1.0,
        "deadzone": 0.04,
        "gain": 0.87,
        "decay": 0.997,
        "edge_zoom": 0.2,
        "snap_speed": 2.5,
    },
    "games": {
        "yaw_range": 0.45,
        "pitch_range": 0.4,
        "deadzone": 0.04,
        "gain": 1.0,
        "decay": 0.999,
        "edge_zoom": 0.15,
        "snap_speed": 4.6,
    },
}

class SettingsPanel:
    def __init__(self, audio_router=None):
        self._visible = True
        self._dragging = None
        self._reset_hovered = False
        self._gl_tex = None
        self._font = None
        self._font_sm = None
        self._monitors = []
        self._selected_monitor = 0
        self._drop_open = False
        self._hide_cursor = settings_manager.get("hide_cursor", True)
        self._yaw_range = settings_manager.get("yaw_range", 0.15)
        self._pitch_range = settings_manager.get("pitch_range", 0.10)
        self._deadzone = settings_manager.get("deadzone", 0.08)
        self._gain = settings_manager.get("gain", 0.40)
        self._decay = settings_manager.get("decay", 1.0)
        self._edge_zoom = settings_manager.get("edge_zoom", 0.0)
        self._snap_speed = settings_manager.get("snap_speed", 2.5)
        self._usb_reset = settings_manager.get("usb_reset", True)
        self._display = DisplayQualityTab()
        self._sound = SoundPanel(router=audio_router)

    @property
    def visible(self): return self._visible
    @property
    def yaw_range(self): return self._yaw_range
    @property
    def pitch_range(self): return self._pitch_range
    @property
    def deadzone(self): return self._deadzone
    @property
    def gain(self): return self._gain
    @property
    def decay(self): return self._decay
    @property
    def edge_zoom(self): return self._edge_zoom
    @property
    def snap_speed(self): return self._snap_speed
    @property
    def usb_reset(self): return self._usb_reset
    @property
    def display(self): return self._display
    @property
    def sound(self): return self._sound

    def show(self): self._visible = True
    def hide(self): self._visible = False
    def toggle(self): self.hide() if self._visible else self.show()

    def _ensure_font(self):
        if not self._font:
            self._font = pygame.font.SysFont("segoeui", 20, bold=True)
            self._font_sm = pygame.font.SysFont("segoeui", 16)

    @staticmethod
    def _slider_geom(idx): return (SLIDER_X, 55 + idx * 70, SLIDER_W, SLIDER_H)

    @staticmethod
    def _knob_x(val, idx):
        mins = [0.05, 0.05, 0.01, 0.10, 0.990, 0.00, 0.0]
        maxes = [1.00, 1.00, 0.20, 1.00, 1.000, 0.49, 5.0]
        return SLIDER_X + (val - mins[idx]) / (maxes[idx] - mins[idx]) * SLIDER_W

    @staticmethod
    def _val_from_x(mx, idx):
        mins = [0.05, 0.05, 0.01, 0.10, 0.990, 0.00, 0.0]
        maxes = [1.00, 1.00, 0.20, 1.00, 1.000, 0.49, 5.0]
        frac = max(0.0, min(1.0, (mx - SLIDER_X) / SLIDER_W))
        steps = [100, 100, 200, 100, 1000, 100, 10]
        raw = mins[idx] + frac * (maxes[idx] - mins[idx])
        return round(raw * steps[idx]) / steps[idx]

    @staticmethod
    def _label(idx, val):
        names = ["Yaw Range", "Pitch Range", "Deadzone", "Gain", "Return Speed", "Edge Zoom", "Snap Speed"]
        if idx < 2: return f"{names[idx]}: {val:.2f} ({int(val/0.50*100)}%% screen)"
        if idx == 2: return f"Deadzone: {val:.3f} (noise floor ~0.03)"
        if idx == 3: return f"Gain: {val:.2f} (higher = more shift)"
        if idx == 4: return f"Return Speed: {val:.3f} (1.0 = stays put)"
        if idx == 5: return f"Edge Zoom: {val:.0%} (zoom at edges)"
        if idx == 6: return f"Snap Speed: {val:.1f} (0.0 = no snap-back)"

    @staticmethod
    def _minmax(idx):
        return ([0.05, 0.05, 0.01, 0.10, 0.990, 0.00, 0.0][idx], [1.00, 1.00, 0.20, 1.00, 1.000, 0.49, 5.0][idx])

    def update_monitors(self, monitors):
        self._monitors = monitors
        t = settings_manager.get("target_monitor", 0)
        self._selected_monitor = min(t, len(monitors) - 1) if monitors else 0

    def handle_mouse(self, mx, my, clicked):
        if not self._visible: return False
        if DROP_X <= mx <= DROP_X + DROP_W and 725 <= my <= 753:
            if clicked:
                self._usb_reset = not self._usb_reset
                settings_manager.set("usb_reset", self._usb_reset)
            return True
        if DROP_X <= mx <= DROP_X + DROP_W and 690 <= my <= 718:
            if clicked:
                self._hide_cursor = not self._hide_cursor
                settings_manager.set("hide_cursor", self._hide_cursor)
            return True
        dy = 620
        if self._drop_open:
            for i in range(len(self._monitors)):
                iy = dy + DROP_H + i * 28
                if DROP_X <= mx <= DROP_X + DROP_W and iy <= my <= iy + 28:
                    if clicked:
                        self._selected_monitor = i
                        settings_manager.set("target_monitor", i)
                        self._drop_open = False
                    return True
            if clicked: self._drop_open = False
            return True
        if DROP_X <= mx <= DROP_X + DROP_W and dy <= my <= dy + DROP_H:
            if clicked: self._drop_open = not self._drop_open
            return True
        # Close button (X) click
        x_btn_size = 30
        x_btn_x = PANEL_W - x_btn_size - 10
        x_btn_y = 8
        if x_btn_x <= mx <= x_btn_x + x_btn_size and x_btn_y <= my <= x_btn_y + x_btn_size:
            if clicked:
                self._visible = False
            return True

        vals = [self._yaw_range, self._pitch_range, self._deadzone, self._gain, self._decay, self._edge_zoom, self._snap_speed]
        keys = ["yaw_range", "pitch_range", "deadzone", "gain", "decay", "edge_zoom", "snap_speed"]
        for idx in range(7):
            sx, sy, sw, sh = self._slider_geom(idx)
            kx = self._knob_x(vals[idx], idx)
            ky = sy + sh // 2
            if self._dragging == keys[idx]:
                v = self._val_from_x(mx, idx)
                setattr(self, "_" + keys[idx], v)
                settings_manager.set(keys[idx], v)
                return True
            if math.hypot(mx - kx, my - ky) < KNOB_R + 6 and clicked:
                self._dragging = keys[idx]
                v = self._val_from_x(mx, idx)
                setattr(self, "_" + keys[idx], v)
                settings_manager.set(keys[idx], v)
                return True
        # Preset buttons
        if 20 <= mx <= 190 and 545 <= my <= 575:
            if clicked:
                self._apply_preset("movies")
            return True
        if 210 <= mx <= 380 and 545 <= my <= 575:
            if clicked:
                self._apply_preset("games")
            return True
        self._reset_hovered = BTN_X <= mx <= BTN_X + BTN_W and BTN_Y <= my <= BTN_Y + BTN_H
        if self._reset_hovered and clicked:
            settings_manager.reset_all()
            self._display.reset_all()
            for k in ["yaw_range", "pitch_range", "deadzone", "gain", "decay", "edge_zoom", "snap_speed", "usb_reset"]:
                setattr(self, "_" + k, settings_manager.get(k, 0.15))
            self._hide_cursor = settings_manager.get("hide_cursor", True)
            self._usb_reset = settings_manager.get("usb_reset", True)
            t = settings_manager.get("target_monitor", 0)
            self._selected_monitor = min(t, len(self._monitors) - 1) if self._monitors else 0
            return True
        return False

    def handle_display_mouse(self, mx, my, clicked):
        """Route mouse events to the Display Quality panel (panel 2)."""
        if not self._visible: return False
        return self._display.handle_mouse(mx, my, clicked)

    def handle_sound_mouse(self, mx, my, clicked):
        """Route mouse events to Sound panel (panel 3)."""
        if not self._visible: return False
        return self._sound.handle_mouse(mx, my, clicked)

    def handle_mouse_up(self): self._dragging = None; self._display.handle_mouse_up(); self._sound.handle_mouse_up()

    def _apply_preset(self, name):
        """Apply a named preset to all slider values and persist."""
        if name not in PRESETS:
            return
        for key, val in PRESETS[name].items():
            setattr(self, "_" + key, val)
            settings_manager.set(key, val)

    def render(self):
        if not self._visible: return None
        self._ensure_font()

        # ── Panel 1: Tracking Settings ──
        p1_h = 780
        s = pygame.Surface((PANEL_W, p1_h), pygame.SRCALPHA)
        pygame.draw.rect(s, (15, 15, 25, 210), (0, 0, PANEL_W, p1_h), border_radius=10)
        pygame.draw.rect(s, (60, 130, 220, 120), (0, 0, PANEL_W, p1_h), width=2, border_radius=10)
        s.blit(self._font.render("Settings", True, (100, 180, 255)), (20, 16))
        # Close button
        x_btn_size = 30
        x_btn_x = PANEL_W - x_btn_size - 10
        x_btn_y = 8
        pygame.draw.rect(s, (50, 50, 60, 150), (x_btn_x, x_btn_y, x_btn_size, x_btn_size), border_radius=4)
        x_txt = self._font.render("X", True, (180, 180, 190))
        s.blit(x_txt, (x_btn_x + (x_btn_size - x_txt.get_width()) // 2,
                        x_btn_y + (x_btn_size - x_txt.get_height()) // 2))

        # Tracking sliders
        vals = [self._yaw_range, self._pitch_range, self._deadzone, self._gain, self._decay, self._edge_zoom, self._snap_speed]
        for idx in range(7):
            sx, sy, sw, sh = self._slider_geom(idx)
            kx = self._knob_x(vals[idx], idx)
            mn, mx2 = self._minmax(idx)
            s.blit(self._font_sm.render(self._label(idx, vals[idx]), True, (200, 220, 255)), (20, sy - 22))
            pygame.draw.rect(s, (50, 60, 80, 200), (sx, sy, sw, sh), border_radius=4)
            fw = kx - sx
            if fw > 0: pygame.draw.rect(s, (60, 140, 220, 220), (sx, sy, int(fw), sh), border_radius=4)
            pygame.draw.circle(s, (255, 255, 255), (int(kx), sy + sh // 2), KNOB_R)
            pygame.draw.circle(s, (60, 140, 220), (int(kx), sy + sh // 2), KNOB_R - 3)
            s.blit(self._font_sm.render(str(mn), True, (120, 130, 150)), (sx, sy + 16))
            s.blit(self._font_sm.render(str(mx2), True, (120, 130, 150)), (sx + sw - 15, sy + 16))

        # Preset buttons
        pygame.draw.rect(s, (40, 80, 120, 200), (20, 545, 170, 30), border_radius=6)
        pt1 = self._font_sm.render("Movies", True, (200, 220, 255))
        s.blit(pt1, (20 + (170 - pt1.get_width()) // 2, 550))
        pygame.draw.rect(s, (120, 60, 40, 200), (210, 545, 170, 30), border_radius=6)
        pt2 = self._font_sm.render("Games", True, (200, 220, 255))
        s.blit(pt2, (210 + (170 - pt2.get_width()) // 2, 550))

        # Reset
        bc = (80, 50, 50, 220) if self._reset_hovered else (50, 50, 60, 200)
        pygame.draw.rect(s, bc, (BTN_X, BTN_Y, BTN_W, BTN_H), border_radius=6)
        pygame.draw.rect(s, (100, 100, 120, 150), (BTN_X, BTN_Y, BTN_W, BTN_H), width=1, border_radius=6)
        bt = self._font_sm.render("Reset All", True, (220, 200, 200))
        tw, th = bt.get_size()
        s.blit(bt, (BTN_X + (BTN_W - tw) // 2, BTN_Y + (BTN_H - th) // 2))

        # Monitor dropdown
        y = 620
        s.blit(self._font_sm.render("Target Monitor:", True, (170, 200, 230)), (20, y))
        y += 20
        ddy = y
        mon = self._monitors[self._selected_monitor]["name"] if self._monitors else "No monitors"
        mt = f"[{self._selected_monitor}] {mon}"
        pygame.draw.rect(s, (50, 50, 70, 200), (DROP_X, ddy, DROP_W, DROP_H), border_radius=4)
        pygame.draw.rect(s, (80, 90, 110, 180), (DROP_X, ddy, DROP_W, DROP_H), width=1, border_radius=4)
        s.blit(self._font_sm.render(mt[:40], True, (200, 220, 255)), (DROP_X + 8, ddy + 5))
        s.blit(self._font_sm.render("v", True, (150, 160, 180)), (DROP_X + DROP_W - 20, ddy + 3))
        y += DROP_H
        if self._drop_open:
            for i, m in enumerate(self._monitors):
                c = (40, 60, 90, 220) if i == self._selected_monitor else (30, 35, 50, 200)
                pygame.draw.rect(s, c, (DROP_X, y, DROP_W, 28))
                mn = m["name"]; mw = m["w"]; mh = m["h"]
                it = self._font_sm.render(f"[{i}] {mn[:35]} {mw}x{mh}", True, (200, 220, 255))
                y += 28
        y = 690
        on_off = "ON" if self._hide_cursor else "OFF"
        cl = f"Show Cursor: {on_off}"
        cc = (40, 120, 60, 180) if self._hide_cursor else (100, 50, 50, 180)
        pygame.draw.rect(s, cc, (20, y, DROP_W, 28), border_radius=6)
        s.blit(self._font_sm.render(cl, True, (220, 220, 220)), (28, y + 4))
        y = 725
        usb_on_off = "ON" if self._usb_reset else "OFF"
        usb_label = f"USB Reset: {usb_on_off}"
        usb_cc = (40, 120, 60, 180) if self._usb_reset else (100, 50, 50, 180)
        pygame.draw.rect(s, usb_cc, (20, y, DROP_W, 28), border_radius=6)
        s.blit(self._font_sm.render(usb_label, True, (220, 220, 220)), (28, y + 4))
        s.blit(self._font_sm.render("* Restart for monitor change", True, (120, 120, 140)), (20, 758))

        # ── Panel 2: Display Quality ──
        p2_w = PANEL_W
        p2_h = 420
        s2 = pygame.Surface((p2_w, p2_h), pygame.SRCALPHA)
        pygame.draw.rect(s2, (15, 15, 25, 210), (0, 0, p2_w, p2_h), border_radius=10)
        pygame.draw.rect(s2, (60, 130, 220, 120), (0, 0, p2_w, p2_h), width=2, border_radius=10)
        s2.blit(self._font.render("Display Quality", True, (100, 180, 255)), (20, 10))
        s2.blit(self._font_sm.render("Toggle ON/OFF, then adjust slider", True, (140, 150, 170)), (20, 32))
        # Render display quality controls onto s2 (offset by 50px for header)
        # We use a subsurface trick: blit display controls at y offset
        self._display.render(s2)

        # Panel 3: Sound Output
        p3_w = PANEL_W
        p3_h = self._sound.panel_height()
        s3 = pygame.Surface((p3_w, p3_h), pygame.SRCALPHA)
        pygame.draw.rect(s3, (15, 15, 25, 210), (0, 0, p3_w, p3_h), border_radius=10)
        pygame.draw.rect(s3, (60, 130, 220, 120), (0, 0, p3_w, p3_h), width=2, border_radius=10)
        s3.blit(self._font.render("Sound Output", True, (100, 180, 255)), (20, 10))
        s3.blit(self._font_sm.render(f"Source: {self._sound.router.capture_device_name[:30]}", True, (140, 150, 170)), (20, 32))
        self._sound.render(s3)
        p3_x = PANEL_X + 2 * (PANEL_W + 10)
        return (s, PANEL_X, PANEL_Y, PANEL_W, p1_h), (s2, PANEL_X + PANEL_W + 10, PANEL_Y, p2_w, p2_h), (s3, p3_x, PANEL_Y, p3_w, p3_h)

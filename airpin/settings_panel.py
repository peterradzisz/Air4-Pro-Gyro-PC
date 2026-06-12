"""Settings panel overlay for AirPin. Toggle with Ctrl+Alt+S."""

import math
import pygame
from airpin import settings_manager

PANEL_W = 400
PANEL_H = 800
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

class SettingsPanel:
    def __init__(self):
        self._visible = False
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
        self._responsiveness = settings_manager.get("responsiveness", 0.40)
        self._gain = settings_manager.get("gain", 0.40)
        self._decay = settings_manager.get("decay", 1.0)
        self._edge_zoom = settings_manager.get("edge_zoom", 0.0)
        self._output_deadzone = settings_manager.get("output_deadzone", 0.3)

    @property
    def visible(self): return self._visible
    @property
    def yaw_range(self): return self._yaw_range
    @property
    def pitch_range(self): return self._pitch_range
    @property
    def deadzone(self): return self._deadzone
    @property
    def responsiveness(self): return self._responsiveness
    @property
    def gain(self): return self._gain
    @property
    def decay(self): return self._decay
    @property
    def edge_zoom(self): return self._edge_zoom
    @property
    def output_deadzone(self): return self._output_deadzone

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
        mins = [0.05, 0.05, 0.01, 0.05, 0.10, 0.990, 0.00, 0.00]
        maxes = [1.00, 1.00, 0.20, 1.00, 1.00, 1.000, 0.30, 1.00]
        return SLIDER_X + (val - mins[idx]) / (maxes[idx] - mins[idx]) * SLIDER_W

    @staticmethod
    def _val_from_x(mx, idx):
        mins = [0.05, 0.05, 0.01, 0.05, 0.10, 0.990, 0.00, 0.00]
        maxes = [1.00, 1.00, 0.20, 1.00, 1.00, 1.000, 0.30, 1.00]
        frac = max(0.0, min(1.0, (mx - SLIDER_X) / SLIDER_W))
        steps = [100, 100, 200, 100, 100, 1000, 100, 10]  # divisors for rounding
        raw = mins[idx] + frac * (maxes[idx] - mins[idx])
        return round(raw * steps[idx]) / steps[idx]

    @staticmethod
    def _label(idx, val):
        names = ["Yaw Range", "Pitch Range", "Deadzone", "Responsiveness", "Gain", "Return Speed", "Edge Zoom", "Output Deadzone"]
        if idx < 2: return f"{names[idx]}: {val:.2f} ({int(val/0.50*100)}%% screen)"
        if idx == 2: return f"Deadzone: {val:.3f} (noise floor ~0.03)"
        if idx == 3: return f"Responsiveness: {val:.2f} (higher = faster)"
        if idx == 4: return f"Gain: {val:.2f} (higher = more shift)"
        if idx == 5: return f"Return Speed: {val:.3f} (1.0 = stays put)"
        if idx == 6: return f"Edge Zoom: {val:.0%} (zoom at edges for readability)"
        if idx == 7: return f"Output Deadzone: {val:.1f}px (anti-drift, 0=off)"

    @staticmethod
    def _minmax(idx):
        return ([0.05, 0.05, 0.01, 0.05, 0.10, 0.990, 0.00, 0.00][idx], [1.00, 1.00, 0.20, 1.00, 1.00, 1.000, 0.30, 1.00][idx])

    def update_monitors(self, monitors):
        self._monitors = monitors
        t = settings_manager.get("target_monitor", 0)
        self._selected_monitor = min(t, len(monitors) - 1) if monitors else 0

    def handle_mouse(self, mx, my, clicked):
        if not self._visible: return False
        if DROP_X <= mx <= DROP_X + DROP_W and 695 <= my <= 723:
            if clicked:
                self._hide_cursor = not self._hide_cursor
                settings_manager.set("hide_cursor", self._hide_cursor)
            return True
        dy = 630
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
        vals = [self._yaw_range, self._pitch_range, self._deadzone, self._responsiveness, self._gain, self._decay, self._edge_zoom, self._output_deadzone]
        keys = ["yaw_range", "pitch_range", "deadzone", "responsiveness", "gain", "decay", "edge_zoom", "output_deadzone"]
        for idx in range(8):
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
        self._reset_hovered = BTN_X <= mx <= BTN_X + BTN_W and BTN_Y <= my <= BTN_Y + BTN_H
        if self._reset_hovered and clicked:
            settings_manager.reset_all()
            for k in ["yaw_range", "pitch_range", "deadzone", "responsiveness", "gain", "decay", "edge_zoom", "output_deadzone"]:
                setattr(self, "_" + k, settings_manager.get(k, 0.15))
            self._hide_cursor = settings_manager.get("hide_cursor", True)
            t = settings_manager.get("target_monitor", 0)
            self._selected_monitor = min(t, len(self._monitors) - 1) if self._monitors else 0
            return True
        return False

    def handle_mouse_up(self): self._dragging = None

    def render(self):
        if not self._visible: return None
        self._ensure_font()
        s = pygame.Surface((PANEL_W, PANEL_H), pygame.SRCALPHA)
        pygame.draw.rect(s, (15, 15, 25, 210), (0, 0, PANEL_W, PANEL_H), border_radius=10)
        pygame.draw.rect(s, (60, 130, 220, 120), (0, 0, PANEL_W, PANEL_H), width=2, border_radius=10)
        s.blit(self._font.render("Settings", True, (100, 180, 255)), (20, 16))
        vals = [self._yaw_range, self._pitch_range, self._deadzone, self._responsiveness, self._gain, self._decay, self._edge_zoom, self._output_deadzone]
        for idx in range(8):
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
        bc = (80, 50, 50, 220) if self._reset_hovered else (50, 50, 60, 200)
        pygame.draw.rect(s, bc, (BTN_X, BTN_Y, BTN_W, BTN_H), border_radius=6)
        pygame.draw.rect(s, (100, 100, 120, 150), (BTN_X, BTN_Y, BTN_W, BTN_H), width=1, border_radius=6)
        bt = self._font_sm.render("Reset All to Defaults", True, (220, 200, 200))
        tw, th = bt.get_size()
        s.blit(bt, (BTN_X + (BTN_W - tw) // 2, BTN_Y + (BTN_H - th) // 2))
        y = 630
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
        y = 695
        on_off = "ON" if self._hide_cursor else "OFF"
        cl = f"Hide System Cursor: {on_off}"
        cc = (40, 120, 60, 180) if self._hide_cursor else (100, 50, 50, 180)
        pygame.draw.rect(s, cc, (20, y, DROP_W, 28), border_radius=6)
        s.blit(self._font_sm.render(cl, True, (220, 220, 220)), (28, y + 4))
        s.blit(self._font_sm.render("* Restart for monitor change", True, (120, 120, 140)), (20, y + 36))
        return s, PANEL_X, PANEL_Y, PANEL_W, PANEL_H

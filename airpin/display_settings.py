"""
Display quality settings tab for AirPin.
Separate tab in the settings panel - 6 post-processing effects
with individual ON/OFF toggles. All default to OFF.
"""

import math
import pygame
from airpin import settings_manager


# Layout constants (local to display tab)
SLIDER_X = 20
SLIDER_W = 260  # narrower than tracking sliders (room for toggle)
SLIDER_H = 8
KNOB_R = 12
TOGGLE_X = 310
TOGGLE_W = 70
TOGGLE_H = 24

# Effect definitions: (key, label_func, min, max, step, default_val)
_EFFECTS = [
    ("brightness",  lambda v: f"Brightness: {v:.2f} (1.0 = default)",   0.70, 1.40,  100,  1.0),
    ("gamma",       lambda v: f"Gamma: {v:.2f} (1.0 = default)",        0.80, 1.40,  100,  1.0),
    ("sharpness",   lambda v: f"Sharpness: {v:.0%} (edge clarity)",     0.00, 1.00,  100,  0.0),
    ("vignette",    lambda v: f"Vignette Fix: {v:.2f} (brighten edges)",0.00, 0.50,  100,  0.0),
    ("chromatic",   lambda v: f"Chroma Fix: {v:.3f} (color fringing)",  0.000,0.030, 1000, 0.0),
    ("temperature", lambda v: f"Color Temp: {v:.0f}K (6500=neutral)",  4000, 9000,  100,  6500),
]


class DisplayQualityTab:
    """Display quality tab with 6 ON/OFF toggle + slider effects."""

    def __init__(self):
        self._dragging = None  # key of effect being dragged
        self._font = None
        self._font_sm = None

        # Load saved values
        self._values = {}
        self._enabled = {}
        for key, _, _, _, _, default in _EFFECTS:
            self._values[key] = settings_manager.get(key, default)
            self._enabled[key] = settings_manager.get(f"enable_{key}", False)

    # ── Public properties ──────────────────────────────────────────────────

    @property
    def brightness(self): return self._values["brightness"]
    @property
    def gamma(self): return self._values["gamma"]
    @property
    def sharpness(self): return self._values["sharpness"]
    @property
    def vignette(self): return self._values["vignette"]
    @property
    def chromatic(self): return self._values["chromatic"]
    @property
    def temperature(self): return self._values["temperature"]

    @property
    def enable_brightness(self): return self._enabled["brightness"]
    @property
    def enable_gamma(self): return self._enabled["gamma"]
    @property
    def enable_sharpness(self): return self._enabled["sharpness"]
    @property
    def enable_vignette(self): return self._enabled["vignette"]
    @property
    def enable_chromatic(self): return self._enabled["chromatic"]
    @property
    def enable_temperature(self): return self._enabled["temperature"]

    def reset_all(self):
        """Reset all display quality settings to defaults."""
        for key, _, _, _, _, default in _EFFECTS:
            self._values[key] = default
            self._enabled[key] = False
            settings_manager.set(key, default)
            settings_manager.set(f"enable_{key}", False)

    # ── Internal helpers ───────────────────────────────────────────────────

    def _ensure_font(self):
        if not self._font:
            self._font = pygame.font.SysFont("segoeui", 20, bold=True)
            self._font_sm = pygame.font.SysFont("segoeui", 16)

    def _effect_y(self, idx):
        """Y position for effect row (label at y-22, slider at y, min/max at y+16)."""
        return 70 + idx * 65

    def _knob_x(self, key, val):
        """Calculate knob X position from value."""
        for entry in _EFFECTS:
            k, _, mn, mx, _, _ = entry
            if k == key:
                return SLIDER_X + (val - mn) / (mx - mn) * SLIDER_W
        return SLIDER_X

    def _val_from_x(self, key, mx_pos):
        """Calculate value from mouse X position."""
        for entry in _EFFECTS:
            k, _, mn, mx, step, _ = entry
            if k == key:
                frac = max(0.0, min(1.0, (mx_pos - SLIDER_X) / SLIDER_W))
                raw = mn + frac * (mx - mn)
                return round(raw * step) / step
        return 0.0

    # ── Mouse handling ────────────────────────────────────────────────────

    def handle_mouse(self, mx, my, clicked):
        """Handle mouse events within the display tab area.
        Returns True if event was consumed."""
        for idx, (key, _, mn, mx_val, _, _) in enumerate(_EFFECTS):
            y = self._effect_y(idx)
            toggle_y = y - 2

            # Toggle click
            if (TOGGLE_X <= mx <= TOGGLE_X + TOGGLE_W and
                toggle_y <= my <= toggle_y + TOGGLE_H and clicked):
                self._enabled[key] = not self._enabled[key]
                settings_manager.set(f"enable_{key}", self._enabled[key])
                return True

            # Slider drag (only if enabled)
            if not self._enabled[key]:
                continue

            kx = self._knob_x(key, self._values[key])
            ky = y + SLIDER_H // 2

            if self._dragging == key:
                v = self._val_from_x(key, mx)
                self._values[key] = v
                settings_manager.set(key, v)
                return True

            if math.hypot(mx - kx, my - ky) < KNOB_R + 6 and clicked:
                self._dragging = key
                v = self._val_from_x(key, mx)
                self._values[key] = v
                settings_manager.set(key, v)
                return True

        return False

    def handle_mouse_up(self):
        """Release any active drag."""
        self._dragging = None

    # ── Rendering ──────────────────────────────────────────────────────────

    def render(self, surface):
        """Draw display quality controls onto the given pygame surface."""
        self._ensure_font()

        for idx, (key, label_fn, mn, mx_val, _, _) in enumerate(_EFFECTS):
            val = self._values[key]
            enabled = self._enabled[key]
            y = self._effect_y(idx)

            # Label
            label_color = (200, 220, 255) if enabled else (100, 110, 130)
            surface.blit(self._font_sm.render(label_fn(val), True, label_color),
                         (20, y - 22))

            # ON/OFF toggle switch
            toggle_y = y - 2
            toggle_color = (40, 120, 60, 180) if enabled else (80, 40, 40, 180)
            pygame.draw.rect(surface, toggle_color,
                             (TOGGLE_X, toggle_y, TOGGLE_W, TOGGLE_H),
                             border_radius=12)
            toggle_text = "ON" if enabled else "OFF"
            toggle_surf = self._font_sm.render(toggle_text, True, (220, 220, 220))
            surface.blit(toggle_surf,
                         (TOGGLE_X + (TOGGLE_W - toggle_surf.get_width()) // 2,
                          toggle_y + (TOGGLE_H - toggle_surf.get_height()) // 2))

            # Slider track
            if enabled:
                pygame.draw.rect(surface, (50, 60, 80, 200),
                                 (SLIDER_X, y, SLIDER_W, SLIDER_H),
                                 border_radius=4)
                kx = self._knob_x(key, val)
                fw = kx - SLIDER_X
                if fw > 0:
                    pygame.draw.rect(surface, (60, 140, 220, 220),
                                     (SLIDER_X, y, int(fw), SLIDER_H),
                                     border_radius=4)
                pygame.draw.circle(surface, (255, 255, 255),
                                   (int(kx), y + SLIDER_H // 2), KNOB_R)
                pygame.draw.circle(surface, (60, 140, 220),
                                   (int(kx), y + SLIDER_H // 2), KNOB_R - 3)
                # Min/max labels
                mn_str = f"{mn:.2f}" if mn < 1 else f"{mn:.0f}"
                mx_str = f"{mx_val:.2f}" if mx_val < 10 else f"{mx_val:.0f}"
                surface.blit(self._font_sm.render(mn_str, True, (120, 130, 150)),
                             (SLIDER_X, y + 16))
                surface.blit(self._font_sm.render(mx_str, True, (120, 130, 150)),
                             (SLIDER_X + SLIDER_W - 20, y + 16))
            else:
                # Disabled slider - greyed out
                pygame.draw.rect(surface, (35, 35, 45, 150),
                                 (SLIDER_X, y, SLIDER_W, SLIDER_H),
                                 border_radius=4)

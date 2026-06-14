"""Sound output settings panel for AirPin."""
import math
import time
import pygame
from airpin.multi_audio import MultiAudioRouter

SLIDER_X = 20
SLIDER_W = 220
SLIDER_H = 8
KNOB_R = 10
TOGGLE_X = 310
TOGGLE_W = 70
TOGGLE_H = 24
ROW_H = 70
MAX_DELAY_MS = 500
START_Y = 50


class SoundPanel:
    """Sound output panel: list of devices with ON/OFF + volume."""

    def __init__(self, router=None):
        self._router = router if router is not None else MultiAudioRouter()
        self._devices = []
        self._dragging = None  # device_id being dragged
        self._font = None
        self._font_sm = None
        self._last_refresh = 0.0
        self._refresh()

    def _refresh(self):
        """Refresh device list from router (throttled to 1/sec)."""
        now = time.monotonic()
        if now - self._last_refresh < 1.0:
            return
        self._last_refresh = now
        self._devices = self._router.list_devices()

    def _ensure_font(self):
        if not self._font:
            self._font = pygame.font.SysFont("segoeui", 20, bold=True)
            self._font_sm = pygame.font.SysFont("segoeui", 16)

    @property
    def router(self):
        return self._router

    def panel_height(self):
        return START_Y + len(self._devices) * ROW_H + 20

    def handle_mouse(self, mx, my, clicked):
        """Handle mouse in sound panel coords."""
        self._refresh()
        for i, dev in enumerate(self._devices):
            y = START_Y + i * ROW_H
            toggle_y = y - 2
            # Toggle click
            if (TOGGLE_X <= mx <= TOGGLE_X + TOGGLE_W and
                toggle_y <= my <= toggle_y + TOGGLE_H and clicked):
                self._router.toggle_device(dev["id"])
                return True
            # Slider drag
            if not dev["enabled"]:
                continue
            vol = dev["volume"]
            kx = SLIDER_X + vol * SLIDER_W
            ky = y + SLIDER_H // 2
            if self._dragging == dev["id"]:
                v = max(0.0, min(1.0, (mx - SLIDER_X) / SLIDER_W))
                self._router.set_volume(dev["id"], v)
                return True
            if math.hypot(mx - kx, my - ky) < KNOB_R + 6 and clicked:
                self._dragging = dev["id"]
                v = max(0.0, min(1.0, (mx - SLIDER_X) / SLIDER_W))
                self._router.set_volume(dev["id"], v)
                return True
            # Delay slider drag (offset 22px below volume)
            delay_y = y + 22
            dky = delay_y + SLIDER_H // 2
            dly = dev.get("delay_ms", 0)
            dkx = SLIDER_X + (dly / MAX_DELAY_MS) * SLIDER_W
            if self._dragging == ("delay", dev["id"]):
                dv = max(0, min(MAX_DELAY_MS, int((mx - SLIDER_X) / SLIDER_W * MAX_DELAY_MS)))
                self._router.set_delay(dev["id"], dv)
                return True
            if math.hypot(mx - dkx, my - dky) < KNOB_R + 6 and clicked:
                self._dragging = ("delay", dev["id"])
                dv = max(0, min(MAX_DELAY_MS, int((mx - SLIDER_X) / SLIDER_W * MAX_DELAY_MS)))
                self._router.set_delay(dev["id"], dv)
                return True
        return False

    def handle_mouse_up(self):
        self._dragging = None  # clears both volume and delay drags

    def render(self, surface):
        """Draw sound panel onto given surface."""
        self._ensure_font()
        self._refresh()
        for i, dev in enumerate(self._devices):
            y = START_Y + i * ROW_H
            enabled = dev["enabled"]
            vol = dev["volume"]
            # Device name
            name = dev["name"][:35]
            color = (200, 220, 255) if enabled else (100, 110, 130)
            surface.blit(self._font_sm.render(name, True, color), (20, y - 22))
            # ON/OFF toggle
            toggle_y = y - 2
            tc = (40, 120, 60, 180) if enabled else (80, 40, 40, 180)
            pygame.draw.rect(surface, tc, (TOGGLE_X, toggle_y, TOGGLE_W, TOGGLE_H), border_radius=12)
            tt = self._font_sm.render("ON" if enabled else "OFF", True, (220, 220, 220))
            surface.blit(tt, (TOGGLE_X + (TOGGLE_W - tt.get_width()) // 2,
                             toggle_y + (TOGGLE_H - tt.get_height()) // 2))
            # Volume slider
            if enabled:
                pygame.draw.rect(surface, (50, 60, 80, 200), (SLIDER_X, y, SLIDER_W, SLIDER_H), border_radius=4)
                kx = SLIDER_X + vol * SLIDER_W
                fw = kx - SLIDER_X
                if fw > 0:
                    pygame.draw.rect(surface, (60, 140, 220, 220), (SLIDER_X, y, int(fw), SLIDER_H), border_radius=4)
                pygame.draw.circle(surface, (255, 255, 255), (int(kx), y + SLIDER_H // 2), KNOB_R)
                pygame.draw.circle(surface, (60, 140, 220), (int(kx), y + SLIDER_H // 2), KNOB_R - 3)
                surface.blit(self._font_sm.render(f"{vol:.0%}", True, (120, 130, 150)), (SLIDER_X + SLIDER_W + 5, y - 2))
                # Delay slider (below volume)
                dy = y + 22
                dly = dev.get("delay_ms", 0)
                pygame.draw.rect(surface, (50, 60, 80, 200), (SLIDER_X, dy, SLIDER_W, SLIDER_H), border_radius=4)
                dkx = SLIDER_X + (dly / MAX_DELAY_MS) * SLIDER_W
                dfw = dkx - SLIDER_X
                if dfw > 0:
                    pygame.draw.rect(surface, (140, 100, 60, 220), (SLIDER_X, dy, int(dfw), SLIDER_H), border_radius=4)
                pygame.draw.circle(surface, (255, 255, 255), (int(dkx), dy + SLIDER_H // 2), KNOB_R)
                pygame.draw.circle(surface, (140, 100, 60), (int(dkx), dy + SLIDER_H // 2), KNOB_R - 3)
                dlabel = f"{dly}ms" if dly > 0 else "no delay"
                surface.blit(self._font_sm.render(f"Delay: {dlabel}", True, (140, 140, 160)), (SLIDER_X, dy + 10))
            else:
                pygame.draw.rect(surface, (35, 35, 45, 150), (SLIDER_X, y, SLIDER_W, SLIDER_H), border_radius=4)

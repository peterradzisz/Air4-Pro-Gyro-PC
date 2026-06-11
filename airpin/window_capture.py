"""
Screen capture with DXGI Desktop Duplication (via dxcam) as primary method
and BitBlt as fallback. Auto-switches to DXGI at runtime when BitBlt returns
mostly-black frames (e.g. exclusive fullscreen games).
"""

import ctypes
import ctypes.wintypes
import logging
import threading
import time
import numpy as np

log = logging.getLogger(__name__)

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
SRCCOPY = 0x00CC0020
BI_RGB = 0
DIB_RGB_COLORS = 0

# Black-frame detection: how many consecutive black frames before we try DXGI.
BLACK_FRAME_THRESHOLD = 5
# Pixel-intensity cutoff for "black" (0-255). Anything below counts as black.
BLACK_PIXEL_VALUE = 10
# Sample ratio for the black-frame test (5% of pixels).
BLACK_SAMPLE_RATIO = 0.05


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.wintypes.DWORD), ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long), ("biPlanes", ctypes.wintypes.WORD),
        ("biBitCount", ctypes.wintypes.WORD), ("biCompression", ctypes.wintypes.DWORD),
        ("biSizeImage", ctypes.wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", ctypes.wintypes.DWORD),
        ("biClrImportant", ctypes.wintypes.DWORD),
    ]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER)]


def list_windows():
    """List all visible, capturable windows."""
    results = []
    def enum_callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if ex_style & WS_EX_TOOLWINDOW:
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if not title or title in ("Program Manager", "Windows Input Experience"):
            return True
        rect = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w > 0 and h > 0:
            results.append((hwnd, title, (rect.left, rect.top, w, h)))
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
    return results


def capture_screen_bitblt(x=0, y=0, w=None, h=None):
    """
    Capture a screen region as BGRA numpy array using GDI BitBlt.
    Returns (w, h, data) or None.
    """
    try:
        if w is None:
            w = user32.GetSystemMetrics(0)
        if h is None:
            h = user32.GetSystemMetrics(1)
        if w <= 0 or h <= 0:
            return None

        hwnd_dc = user32.GetDC(None)
        mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
        bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
        old_bmp = gdi32.SelectObject(mem_dc, bitmap)

        gdi32.BitBlt(mem_dc, 0, 0, w, h, hwnd_dc, x, y, SRCCOPY)

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(mem_dc, bitmap, 0, h, buf, ctypes.byref(bmi), DIB_RGB_COLORS)

        gdi32.SelectObject(mem_dc, old_bmp)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, hwnd_dc)

        data = np.frombuffer(buf.raw, dtype=np.uint8).reshape(h, w, 4).copy()
        return w, h, data
    except Exception as e:
        log.debug("BitBlt capture failed: %s", e)
        return None


def _find_dxcam_output(target_w, target_h):
    """
    Probe dxcam output enumeration to find one matching the target resolution.
    Returns (device_idx, output_idx) or None.
    """
    try:
        import dxcam
    except ImportError:
        return None
    try:
        devices = dxcam.output_info()
    except Exception as e:
        log.debug("dxcam.output_info() failed: %s", e)
        return None
    if not devices:
        return None
    for dev_idx, outputs in enumerate(devices):
        for out_idx, out in enumerate(outputs):
            res = out.get("resolution") if isinstance(out, dict) else None
            if res is None and len(out) >= 2:
                # Older dxcam returns tuples/lists like (w, h)
                try:
                    res = (int(out[0]), int(out[1]))
                except Exception:
                    continue
            if res is None:
                continue
            ow, oh = int(res[0]), int(res[1])
            if (ow, oh) == (int(target_w), int(target_h)):
                return dev_idx, out_idx
    return None


def _is_mostly_black(data, threshold=BLACK_PIXEL_VALUE, sample_ratio=BLACK_SAMPLE_RATIO):
    """
    Sample a fraction of pixels; return True if >= 95% of them are below threshold.
    Fast, allocation-free enough for the capture loop.
    """
    if data is None or data.size == 0:
        return True
    h, w = data.shape[:2]
    n_pixels = h * w
    n_samples = max(1, int(n_pixels * sample_ratio))
    # Deterministic stride sample (no RNG overhead).
    stride = max(1, n_pixels // n_samples)
    flat = data.reshape(n_pixels, data.shape[2])[::stride]
    # Use max of RGB channels (ignore alpha). BGRA layout, so R = index 2.
    rgb_max = flat[:, :3].max(axis=1)
    black_frac = (rgb_max < threshold).sum() / rgb_max.size
    return black_frac >= 0.95


class ScreenCapture:
    """
    Captures a screen region. Prefers DXGI Desktop Duplication via dxcam
    (works with exclusive fullscreen games); falls back to BitBlt.
    Auto-promotes to DXGI at runtime if BitBlt keeps returning black frames.
    """

    def __init__(self, x=0, y=0, width=None, height=None, monitor_index=0):
        self.x = x
        self.y = y
        self.width = width or user32.GetSystemMetrics(0)
        self.height = height or user32.GetSystemMetrics(1)
        self.monitor_index = monitor_index
        self._method = "bitblt"
        self._dxcam = None
        self._black_frame_count = 0
        self._dxgi_tried = False

    # --- DXGI init -------------------------------------------------------

    def _try_init_dxcam(self):
        """Attempt to create a dxcam camera at this capture's resolution."""
        if self._dxcam is not None:
            return True
        if self._dxgi_tried and self._dxcam is None:
            # We already tried once this session and it failed; don't spam.
            return False
        self._dxgi_tried = True
        try:
            import dxcam  # noqa: F401
        except ImportError:
            log.info("dxcam not installed; using BitBlt only")
            return False
        match = _find_dxcam_output(self.width, self.height)
        if match is None:
            log.info("No dxcam output matches %dx%d", self.width, self.height)
            return False
        dev_idx, out_idx = match
        try:
            import dxcam as _dx
            self._dxcam = _dx.create(
                device_idx=dev_idx,
                output_idx=out_idx,
                output_color="BGRA",
                processor_backend="numpy",
            )
            self._method = "dxgi"
            log.info("DXGI capture initialised (dev=%d out=%d %dx%d)",
                     dev_idx, out_idx, self.width, self.height)
            return True
        except Exception as e:
            log.warning("dxcam.create() failed: %s", e)
            self._dxcam = None
            return False

    # --- Lifecycle --------------------------------------------------------

    def start(self):
        """Try DXGI first, then BitBlt. Returns True if either works."""
        if self._try_init_dxcam():
            # Smoke-test the DXGI path
            try:
                frame = self._dxcam.grab()
                if frame is not None:
                    return True
                log.warning("dxcam.grab() returned None on start; falling back to BitBlt")
            except Exception as e:
                log.warning("dxcam.grab() failed on start: %s", e)
            self._method = "bitblt"
            self._dxcam = None

        # BitBlt fallback
        result = capture_screen_bitblt(self.x, self.y, self.width, self.height)
        return result is not None

    def grab(self):
        """Return (w, h, bgra_array) or None."""
        if self._method == "dxgi" and self._dxcam is not None:
            try:
                frame = self._dxcam.grab()
            except Exception as e:
                log.warning("dxcam.grab() failed mid-run, switching to BitBlt: %s", e)
                self._method = "bitblt"
                self._dxcam = None
                return self.grab()
            if frame is None:
                return None
            # dxcam returns (h, w, 4) BGRA
            if frame.ndim == 3 and frame.shape[2] == 4:
                fh, fw = frame.shape[:2]
                return fw, fh, frame
            return None

        # BitBlt path. Also check for black frames to auto-promote to DXGI.
        result = capture_screen_bitblt(self.x, self.y, self.width, self.height)
        if result is None:
            self._black_frame_count = 0
            return None
        w, h, data = result
        if _is_mostly_black(data):
            self._black_frame_count += 1
            if (self._black_frame_count >= BLACK_FRAME_THRESHOLD
                    and not (self._dxgi_tried and self._dxcam is None)):
                log.info("BitBlt returned %d consecutive black frames; promoting to DXGI",
                         self._black_frame_count)
                if self._try_init_dxcam():
                    # Hand back a fresh DXGI frame immediately if we can.
                    try:
                        frame = self._dxcam.grab()
                        if frame is not None and frame.ndim == 3 and frame.shape[2] == 4:
                            self._black_frame_count = 0
                            fh, fw = frame.shape[:2]
                            return fw, fh, frame
                    except Exception as e:
                        log.debug("DXGI grab after promote failed: %s", e)
        else:
            self._black_frame_count = 0
        return w, h, data

    def reinit(self):
        """Stop and restart the capture pipeline (e.g. after display change)."""
        self.stop()
        # Reset black-frame state so the new pipeline gets a fair shot.
        self._black_frame_count = 0
        self._dxgi_tried = False
        self._method = "bitblt"
        return self.start()

    def stop(self):
        if self._dxcam is not None:
            try:
                self._dxcam.release()
            except Exception:
                pass
            self._dxcam = None
        self._method = "bitblt"


class WindowSlot:
    """A captured screen region with its texture data."""
    def __init__(self, title="Screen"):
        self.title = title
        self.width = 0
        self.height = 0
        self.pixel_data = None
        self.texture_dirty = True
        self.gl_texture_id = None
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.pos_z = -3.0
        self.scale = 1.0


class WindowManager:
    """Manages screen capture and periodic updates."""

    def __init__(self, capture_fps=30, monitor_index=0, monitor_x=0, monitor_y=0, monitor_w=None, monitor_h=None):
        self.capture = ScreenCapture(
            x=monitor_x,
            y=monitor_y,
            width=monitor_w or user32.GetSystemMetrics(0),
            height=monitor_h or user32.GetSystemMetrics(1),
            monitor_index=monitor_index,
        )
        self.slot = WindowSlot("Primary Monitor")
        self.capture_interval = 1.0 / capture_fps
        self._thread = None
        self._running = False

    def get_slots(self):
        return [self.slot]

    def start(self):
        if not self.capture.start():
            return False
        method = self.capture._method.upper()
        print(f"  Screen capture: {self.capture.width}x{self.capture.height} {method}")
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        return True

    def _capture_loop(self):
        while self._running:
            result = self.capture.grab()
            if result is not None:
                w, h, data = result
                self.slot.width = w
                self.slot.height = h
                self.slot.pixel_data = data
                self.slot.texture_dirty = True
            time.sleep(self.capture_interval)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self.capture.stop()

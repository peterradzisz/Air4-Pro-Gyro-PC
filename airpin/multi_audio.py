"""
Multi-device audio router for AirPin.

Captures system audio via WASAPI loopback (captures whatever the default
output device is playing) and routes to multiple output devices.
Falls back to Stereo Mix if WASAPI loopback is unavailable.
"""

import threading
import time
import collections
import numpy as np

try:
    import sounddevice as sd
    HAS_SD = True
except ImportError:
    HAS_SD = False

import config
from airpin.endpoint_mute import set_mute, get_mute


class MultiAudioRouter:
    """Captures system audio and routes to multiple output devices."""

    def __init__(self):
        self._running = False
        self._capture_stream = None
        self._output_streams = {}
        self._device_queues = {}
        self._lock = threading.Lock()
        self._devices = []
        self._device_states = {}
        self._capture_device_id = None
        self._capture_device_name = ""
        self._capture_method = ""
        self.active = False
        self._source_muted = False
        self._samplerate = getattr(config, "AUDIO_SAMPLE_RATE", 48000)
        self._capture_sr = 48000
        self._device_output_sr = {}
        self._blocksize = getattr(config, "AUDIO_BUFFER_FRAMES", 1024)
        if HAS_SD:
            self._detect_devices()

    @property
    def capture_device_name(self):
        return self._capture_device_name

    @property
    def capture_available(self):
        return HAS_SD and self._capture_device_id is not None

    @property
    def source_muted(self):
        return self._source_muted

    def toggle_source_mute(self):
        """Toggle mute on the default Windows audio endpoint.
        WASAPI loopback captures before the mute, so routing still works."""
        self._source_muted = not self._source_muted
        ok = set_mute(self._source_muted)
        if ok:
            print(f"  Audio: Source device {'MUTED' if self._source_muted else 'UNMUTED'}")
        else:
            self._source_muted = not self._source_muted  # revert on failure
        return self._source_muted

    def _find_wasapi_output(self):
        """Find the default WASAPI output device for loopback capture."""
        try:
            hostapis = sd.query_hostapis()
            for api in hostapis:
                if "WASAPI" in api["name"]:
                    dev_idx = api.get("default_output_device", -1)
                    if dev_idx is not None and dev_idx >= 0:
                        return dev_idx, sd.query_devices(dev_idx)
                    for di in api["devices"]:
                        info = sd.query_devices(di)
                        if info["max_output_channels"] > 0:
                            return di, info
        except Exception:
            pass
        return None, None

    def _detect_devices(self):
        """Set up capture via WASAPI loopback, enumerate output devices."""
        devices = sd.query_devices()
        capture_ids = set()

        wasapi_dev, wasapi_info = self._find_wasapi_output()
        if wasapi_dev is not None:
            self._capture_device_id = wasapi_dev
            self._capture_device_name = wasapi_info["name"]
            self._capture_method = "wasapi_loopback"
            capture_ids.add(wasapi_dev)

        if self._capture_device_id is None:
            _KW = ["stereo mix", "wave out", "what u hear", "loopback", "mix"]
            best = None
            best_score = -1
            for i, d in enumerate(devices):
                if d["max_input_channels"] <= 0:
                    continue
                nl = d["name"].lower()
                for kw in _KW:
                    if kw in nl:
                        if len(kw) > best_score:
                            best_score = len(kw)
                            best = i
                        break
            if best is not None:
                self._capture_device_id = best
                self._capture_device_name = devices[best]["name"]
                self._capture_method = "stereo_mix"
                capture_ids.add(best)

        # Dedup: WASAPI first, then WDM-KS for devices not in WASAPI
        # Skip MME/DirectSound (legacy duplicates of the same hardware)
        hostapis = sd.query_hostapis()
        api_priority = []
        for ai, api in enumerate(hostapis):
            n = api["name"]
            if "WASAPI" in n:
                api_priority.append((ai, 0))
            elif "WDM" in n:
                api_priority.append((ai, 1))
        if not api_priority:
            api_priority = [(ai, 0) for ai in range(len(hostapis))]
        api_priority.sort(key=lambda x: x[1])
        preferred_apis = {ai for ai, _ in api_priority}

        def _is_valid(name):
            nl = name.lower()
            if "sound mapper" in nl or "primary sound" in nl:
                return False
            if not name.strip() or "()" in name or name.strip() == "Output":
                return False
            return True

        def _brand(name):
            return name.split()[0].lower() if name.split() else name.lower()

        seen_brands = set()
        for ai, _ in api_priority:
            for i, d in enumerate(devices):
                if d["hostapi"] != ai:
                    continue
                if d["max_output_channels"] <= 0 or i in capture_ids:
                    continue
                if not _is_valid(d["name"]):
                    continue
                brand = _brand(d["name"])
                if brand in seen_brands:
                    continue
                seen_brands.add(brand)
                self._devices.append({
                    "id": i, "name": d["name"],
                    "channels": min(d["max_output_channels"], 2),
                    "sample_rate": self._samplerate,
                })
                self._device_states[i] = {"enabled": False, "volume": 0.8, "delay_ms": 0}

    def list_devices(self):
        result = []
        for d in self._devices:
            st = self._device_states.get(d["id"], {})
            result.append({
                "id": d["id"], "name": d["name"],
                "enabled": st.get("enabled", False),
                "volume": st.get("volume", 0.8),
                "delay_ms": st.get("delay_ms", 0),
                "is_source": any(name_part.lower() in d["name"].lower()
                                  for name_part in self._capture_device_name.split()[:1])
                              if self._capture_device_name else False,
                "channels": d["channels"],
                "sample_rate": d["sample_rate"],
            })
        return result

    def start(self):
        if not HAS_SD:
            print("  Audio: sounddevice not installed")
            return False
        if self._capture_device_id is None:
            print("  Audio: No capture device available")
            return False
        if self._running:
            return True
        try:
            di = sd.query_devices(self._capture_device_id)

            if self._capture_method == "wasapi_loopback":
                sr = int(di["default_samplerate"])
                ch = min(di["max_output_channels"] or 2, 2)
            else:
                sr = int(di["default_samplerate"])
                ch = min(di["max_input_channels"], 2)
            self._capture_sr = sr

            def capture_cb(indata, frames, ti, status):
                chunk = indata[:, :ch].copy()
                ts = time.monotonic()
                with self._lock:
                    for dq in self._device_queues.values():
                        dq.append((ts, chunk))

            if self._capture_method == "wasapi_loopback":
                self._capture_stream = sd.InputStream(
                    device=self._capture_device_id, samplerate=sr,
                    channels=ch, dtype="float32", callback=capture_cb,
                    blocksize=self._blocksize,
                    extra_settings=sd.WasapiSettings(loopback=True))
            else:
                self._capture_stream = sd.InputStream(
                    device=self._capture_device_id, samplerate=sr,
                    channels=ch, dtype="float32", callback=capture_cb,
                    blocksize=self._blocksize)

            self._capture_stream.start()
            self._running = True
            self.active = True
            print(f"  Audio: Capturing via {self._capture_method} from {self._capture_device_name} at {sr}Hz")
            return True
        except Exception as e:
            print(f"  Audio: Capture failed ({self._capture_method}): {e}")
            if self._capture_method == "wasapi_loopback":
                print("  Audio: Trying Stereo Mix fallback...")
                self._capture_method = ""
                self._capture_device_id = None
                self._detect_stereo_mix()
                if self._capture_device_id is not None:
                    return self._start_stereo_mix()
            self.active = False
            return False

    def _detect_stereo_mix(self):
        _KW = ["stereo mix", "wave out", "what u hear", "mix"]
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            if d["max_input_channels"] <= 0:
                continue
            nl = d["name"].lower()
            for kw in _KW:
                if kw in nl:
                    self._capture_device_id = i
                    self._capture_device_name = devices[i]["name"]
                    self._capture_method = "stereo_mix"
                    return

    def _start_stereo_mix(self):
        try:
            di = sd.query_devices(self._capture_device_id)
            sr = int(di["default_samplerate"])
            self._capture_sr = sr
            ch = min(di["max_input_channels"], 2)
            def cb(indata, frames, ti, status):
                chunk = indata[:, :ch].copy()
                ts = time.monotonic()
                with self._lock:
                    for dq in self._device_queues.values():
                        dq.append((ts, chunk))
            self._capture_stream = sd.InputStream(
                device=self._capture_device_id, samplerate=sr,
                channels=ch, dtype="float32", callback=cb,
                blocksize=self._blocksize)
            self._capture_stream.start()
            self._running = True
            self.active = True
            print(f"  Audio: Stereo Mix OK: {self._capture_device_name}")
            return True
        except Exception as e:
            print(f"  Audio: Stereo Mix failed: {e}")
            self.active = False
            return False

    def stop(self):
        self._running = False
        for s in [self._capture_stream] + list(self._output_streams.values()):
            try:
                if s: s.close()
            except Exception:
                pass
        self._capture_stream = None
        self._output_streams.clear()
        with self._lock:
            self._device_queues.clear()
        self.active = False

    def toggle_device(self, device_id):
        if device_id not in self._device_states:
            return False
        st = self._device_states[device_id]
        if st["enabled"]:
            st["enabled"] = False
            if device_id in self._output_streams:
                try: self._output_streams[device_id].close()
                except Exception: pass
                del self._output_streams[device_id]
            with self._lock:
                if device_id in self._device_queues:
                    del self._device_queues[device_id]
            print(f"  Audio: Stopped output [{device_id}]")
            return False
        else:
            try:
                di = sd.query_devices(device_id)
                ch = min(di["max_output_channels"], 2)
                sr = int(di["default_samplerate"])
                self._device_output_sr[device_id] = sr
                with self._lock:
                    self._device_queues[device_id] = collections.deque(maxlen=100)
                cb = self._make_output_cb(device_id, ch)
                stream = sd.OutputStream(device=device_id, samplerate=sr,
                    channels=ch, dtype="float32", callback=cb,
                    blocksize=self._blocksize)
                stream.start()
                self._output_streams[device_id] = stream
                st["enabled"] = True
                print(f"  Audio: Output -> [{device_id}] {di['name']} at {sr}Hz (capture: {self._running})")
                return True
            except Exception as e:
                print(f"  Audio: Device {device_id} failed: {e}")
                return False

    def set_volume(self, device_id, volume):
        if device_id in self._device_states:
            self._device_states[device_id]["volume"] = max(0.0, min(1.0, volume))

    def _make_output_cb(self, device_id, channels):
        def cb(outdata, frames, ti, status):
            vol = self._device_states[device_id]["volume"]
            delay = self._device_states[device_id].get("delay_ms", 0) / 1000.0
            now = time.monotonic()
            cap_sr = self._capture_sr
            out_sr = self._device_output_sr.get(device_id, cap_sr)
            # How many capture-rate samples needed to fill output frames
            needed = int(frames * cap_sr / out_sr) + 1 if cap_sr != out_sr else frames
            chunks = []
            total = 0
            with self._lock:
                dq = self._device_queues.get(device_id)
                if dq:
                    while total < needed and len(dq) > 0:
                        ts, c = dq[0]
                        if now - ts < delay:
                            break
                        dq.popleft()
                        chunks.append(c)
                        total += c.shape[0]
            if chunks:
                data = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
                # Resample if capture and output rates differ
                if cap_sr != out_sr:
                    n_out = max(1, int(data.shape[0] * out_sr / cap_sr))
                    idx = np.linspace(0, data.shape[0] - 1, n_out).astype(np.intp)
                    data = data[idx]
                n = min(frames, data.shape[0])
                co = min(channels, data.shape[1])
                outdata[:n, :co] = data[:n, :co] * vol
                if n < frames: outdata[n:] = 0
                if co < outdata.shape[1]: outdata[:, co:] = 0
            else:
                outdata.fill(0)
        return cb

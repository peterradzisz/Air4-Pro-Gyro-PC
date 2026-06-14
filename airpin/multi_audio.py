"""
Multi-device audio router for AirPin.

Captures system audio via PyAudioWPatch WASAPI loopback (works on all
Windows PCs without Stereo Mix). Routes to multiple output devices via
sounddevice. Handles sample rate differences with numpy resampling.
"""

import threading
import collections
import time
import numpy as np
try:
    import soxr
    HAS_SOXR = True
except ImportError:
    HAS_SOXR = False

try:
    import pyaudiowpatch as pyaudio
    HAS_PA = True
except ImportError:
    HAS_PA = False

try:
    import sounddevice as sd
    HAS_SD = True
except ImportError:
    HAS_SD = False

import config


class MultiAudioRouter:
    """Captures system audio via WASAPI loopback, routes to output devices."""

    def __init__(self):
        self._running = False
        self._pyaudio = None
        self._capture_stream = None
        self._capture_thread = None
        self._output_streams = {}
        self._device_queues = {}
        self._lock = threading.Lock()
        self._devices = []
        self._device_states = {}
        self._capture_device_name = ""
        self._capture_sr = 48000
        self._dist_sr = 48000
        self._capture_channels = 2
        self._device_output_sr = {}
        self.active = False
        self._source_muted = False
        self._blocksize = getattr(config, "AUDIO_BUFFER_FRAMES", 1024)
        self._capture_blocksize = self._blocksize  # larger blocks = fewer callbacks
        if HAS_SD:
            self._detect_devices()

    @property
    def capture_device_name(self):
        return self._capture_device_name

    @property
    def capture_available(self):
        return HAS_PA or HAS_SD

    @property
    def needs_format_fix(self):
        """True if capture rate > 48000 (causes CPU + quality issues)."""
        return self._capture_sr > 48000

    @staticmethod
    def open_sound_settings():
        """Open Windows Sound control panel for format change."""
        import subprocess
        subprocess.Popen(['cmd', '/c', 'start', 'control', 'mmsys.cpl', 'sounds'])
        print("  Audio: Opened Sound settings. Right-click device -> Properties -> Advanced -> 48000 Hz")

    @property
    def source_muted(self):
        return self._source_muted

    def toggle_source_mute(self):
        """Toggle mute on the default Windows audio endpoint."""
        self._source_muted = not self._source_muted
        try:
            from airpin.endpoint_mute import set_mute
            ok = set_mute(self._source_muted)
        except Exception:
            ok = True
        if ok:
            print(f"  Audio: Source {'MUTED' if self._source_muted else 'UNMUTED'}")
        else:
            self._source_muted = not self._source_muted
        return self._source_muted

    def _detect_devices(self):
        """Auto-detect capture source and enumerate output devices."""
        capture_ids = set()

        # --- Capture: PyAudioWPatch WASAPI loopback (universal) ---
        if HAS_PA:
            try:
                pa = pyaudio.PyAudio()
                loopback = pa.get_default_wasapi_loopback()
                self._capture_device_name = loopback["name"].replace(" [Loopback]", "")
                self._capture_sr = int(loopback["defaultSampleRate"])
                self._dist_sr = min(self._capture_sr, 48000)
                self._capture_channels = min(int(loopback["maxInputChannels"]), 2)
                self._pa_loopback_index = loopback["index"]
                pa.terminate()
                print(f"  Audio: WASAPI loopback = {self._capture_device_name} ({self._capture_sr}Hz)")
            except Exception as e:
                print(f"  Audio: WASAPI loopback failed: {e}")

        # --- Capture fallback: Stereo Mix via sounddevice ---
        if not self._capture_device_name and HAS_SD:
            _KW = ["stereo mix", "wave out", "what u hear", "mix"]
            devices = sd.query_devices()
            best = None
            for i, d in enumerate(devices):
                if d["max_input_channels"] <= 0:
                    continue
                nl = d["name"].lower()
                for kw in _KW:
                    if kw in nl:
                        best = i
                        break
                if best is not None:
                    break
            if best is not None:
                self._capture_device_name = devices[best]["name"]
                self._capture_sr = int(devices[best]["default_samplerate"])
                self._capture_channels = min(devices[best]["max_input_channels"], 2)
                self._sd_capture_id = best
                capture_ids.add(best)
                print(f"  Audio: Stereo Mix fallback = {self._capture_device_name}")

        # --- Output devices: WASAPI only (most reliable) ---
        if not HAS_SD:
            return

        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        api_names = {i: a["name"] for i, a in enumerate(hostapis)}

        # Prefer WASAPI, then WDM-KS, skip MME/DirectSound
        api_order = []
        for ai, api in enumerate(hostapis):
            n = api["name"]
            if "WASAPI" in n:
                api_order.append((ai, 0))
            elif "WDM" in n:
                api_order.append((ai, 1))
        if not api_order:
            api_order = [(ai, 0) for ai in range(len(hostapis))]
        api_order.sort(key=lambda x: x[1])

        seen_brands = set()
        for ai, _ in api_order:
            for i, d in enumerate(devices):
                if d["hostapi"] != ai or d["max_output_channels"] <= 0:
                    continue
                if i in capture_ids:
                    continue
                name = d["name"]
                nl = name.lower()
                if "sound mapper" in nl or "primary sound" in nl:
                    continue
                if not name.strip() or "()" in name:
                    continue
                brand = name.split()[0].lower() if name.split() else nl
                if brand in seen_brands:
                    continue
                seen_brands.add(brand)
                self._devices.append({
                    "id": i, "name": name,
                    "channels": min(d["max_output_channels"], 2),
                    "sample_rate": int(d["default_samplerate"]),
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
                "channels": d["channels"],
                "sample_rate": d["sample_rate"],
            })
        return result

    def start(self):
        """Start system audio capture."""
        if not self._capture_device_name:
            print("  Audio: No capture method available")
            return False
        if self._running:
            return True

        # PyAudioWPatch capture
        if HAS_PA and hasattr(self, '_pa_loopback_index'):
            try:
                self._pyaudio = pyaudio.PyAudio()

                self._capture_stream = self._pyaudio.open(
                    format=pyaudio.paFloat32,
                    channels=self._capture_channels,
                    rate=self._capture_sr,
                    input=True,
                    input_device_index=self._pa_loopback_index,
                    frames_per_buffer=self._capture_blocksize,
                )
                self._capture_stream.start_stream()
                self._running = True
                self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
                self._capture_thread.start()
                self.active = True
                print(f"  Audio: Capturing {self._capture_sr}Hz via WASAPI loopback")
                if self._capture_sr > 96000:
                    print(f"  Audio: WARNING - {self._capture_sr}Hz causes heavy CPU + resampling artifacts")
                    print(f"  Audio: TIP: Set this device to 48000Hz in Windows Sound > Device Properties > Advanced")
                return True
            except Exception as e:
                print(f"  Audio: PyAudio capture failed: {e}")
                if self._pyaudio:
                    self._pyaudio.terminate()
                    self._pyaudio = None

        # Stereo Mix fallback
        if HAS_SD and hasattr(self, '_sd_capture_id'):
            try:
                ch = self._capture_channels
                def sd_cb(indata, frames, ti, status):
                    chunk = indata[:, :ch].copy()
                    ts = time.monotonic()
                    for dq in list(self._device_queues.values()):
                        dq.append((ts, chunk))

                self._capture_stream = sd.InputStream(
                    device=self._sd_capture_id, samplerate=self._capture_sr,
                    channels=ch, dtype="float32", callback=sd_cb,
                    blocksize=self._blocksize)
                self._capture_stream.start()
                self._running = True
                self.active = True
                print(f"  Audio: Capturing {self._capture_sr}Hz via Stereo Mix")
                return True
            except Exception as e:
                print(f"  Audio: Stereo Mix failed: {e}")

        self.active = False
        return False

    def _capture_loop(self):
        bs = self._capture_blocksize
        while self._running:
            try:
                avail = self._capture_stream.get_read_available()
                if avail < bs:
                    time.sleep(0.002)
                    continue
                raw = self._capture_stream.read(bs, exception_on_overflow=False)
                chunk = np.frombuffer(raw, dtype=np.float32)
                if self._capture_channels > 1:
                    chunk = chunk.reshape(-1, self._capture_channels)
                else:
                    chunk = chunk.reshape(-1, 1)
                # Resample to 48kHz in capture thread if capture rate is higher
                if self._capture_sr > self._dist_sr:
                    if HAS_SOXR:
                        chunk = soxr.resample(chunk, self._capture_sr, self._dist_sr, quality='HQ').astype(np.float32)
                    else:
                        try:
                            from scipy.signal import resample_poly
                            from math import gcd
                            g = gcd(self._capture_sr, self._dist_sr)
                            chunk = resample_poly(chunk, self._dist_sr // g, self._capture_sr // g, axis=0).astype(np.float32)
                        except ImportError:
                            ratio = self._capture_sr // self._dist_sr
                            if ratio > 1 and self._capture_sr % self._dist_sr == 0:
                                chunk = chunk[:len(chunk)//ratio*ratio].reshape(-1, ratio, chunk.shape[1]).mean(axis=0)
                ts = time.monotonic()
                for dq in list(self._device_queues.values()):
                    dq.append((ts, chunk))
            except Exception:
                if self._running:
                    time.sleep(0.1)

    def stop(self):
        """Stop all audio streams."""
        if self._source_muted:
            try:
                from airpin.endpoint_mute import set_mute
                set_mute(False)
            except:
                pass
            self._source_muted = False
        self._running = False

        # Close capture
        if self._capture_stream:
            try:
                if HAS_PA and isinstance(self._capture_stream, object) and hasattr(self._capture_stream, 'stop_stream'):
                    self._capture_stream.stop_stream()
                    self._capture_stream.close()
                else:
                    self._capture_stream.close()
            except:
                pass
        self._capture_stream = None
        if self._capture_thread:
            self._capture_thread.join(timeout=2.0)
            self._capture_thread = None
        if self._pyaudio:
            try:
                self._pyaudio.terminate()
            except:
                pass
            self._pyaudio = None

        # Close outputs
        for s in list(self._output_streams.values()):
            try:
                s.close()
            except:
                pass
        self._output_streams.clear()
        with self._lock:
            self._device_queues.clear()
        self.active = False

    def toggle_device(self, device_id):
        """Toggle output device on/off."""
        if device_id not in self._device_states:
            return False
        st = self._device_states[device_id]
        if st["enabled"]:
            st["enabled"] = False
            if device_id in self._output_streams:
                try:
                    self._output_streams[device_id].close()
                except:
                    pass
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
                cap_sr = self._capture_sr
                print(f"  Audio: Output -> [{device_id}] {di['name'][:30]} {sr}Hz (capture: {cap_sr}Hz)")
                return True
            except Exception as e:
                print(f"  Audio: Device {device_id} failed: {e}")
                return False

    def set_volume(self, device_id, volume):
        if device_id in self._device_states:
            self._device_states[device_id]["volume"] = max(0.0, min(1.0, volume))

    def set_delay(self, device_id, delay_ms):
        """Set output delay 0-500ms."""
        if device_id in self._device_states:
            self._device_states[device_id]["delay_ms"] = max(0, min(500, int(delay_ms)))

    def _make_output_cb(self, device_id, channels):
        """Create output callback with resampling and delay support."""
        def cb(outdata, frames, ti, status):
            vol = self._device_states[device_id]["volume"]
            delay = self._device_states[device_id].get("delay_ms", 0) / 1000.0
            now = time.monotonic()
            cap_sr = self._dist_sr
            out_sr = self._device_output_sr.get(device_id, cap_sr)

            # How many capture-rate samples needed to fill output frames
            needed = int(frames * cap_sr / out_sr) + 1 if cap_sr != out_sr else frames
            chunks = []
            total = 0
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
                # Resample using soxr (C-level, GIL-released, 50x faster than scipy)
                if cap_sr != out_sr:
                    if HAS_SOXR:
                        data = soxr.resample(data, cap_sr, out_sr, quality='HQ').astype(np.float32)
                    else:
                        try:
                            from scipy.signal import resample_poly
                            from math import gcd
                            g = gcd(cap_sr, out_sr)
                            data = resample_poly(data, out_sr // g, cap_sr // g, axis=0).astype(np.float32)
                        except ImportError:
                            ratio = cap_sr // out_sr
                            if ratio > 1 and cap_sr % out_sr == 0:
                                data = data[:len(data)//ratio*ratio].reshape(-1, ratio, data.shape[1]).mean(axis=0)
                                data = data.reshape(-1, data.shape[-1])
                n = min(frames, data.shape[0])
                co = min(channels, data.shape[1])
                outdata[:n, :co] = data[:n, :co] * vol
                if n < frames:
                    outdata[n:] = 0
                if co < outdata.shape[1]:
                    outdata[:, co:] = 0
            else:
                outdata.fill(0)
        return cb

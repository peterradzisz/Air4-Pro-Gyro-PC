"""
Audio router: WASAPI loopback capture -> queue -> sounddevice output
Uses blocking read thread (callback mode does not work for loopback)
"""

import threading
import time
import queue as queue_module
import numpy as np
import logging

log = logging.getLogger("airpin.audio")

try:
    import pyaudiowpatch as pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False

try:
    import sounddevice as sd
    HAS_SD = True
except ImportError:
    HAS_SD = False

import config

QUEUE_MAXSIZE = 30
PREFILL_BLOCKS = 3
BLOCKSIZE = 1024


def _get_wasapi_host_api_index():
    if not HAS_SD:
        return None
    for i, api in enumerate(sd.query_hostapis()):
        if 'WASAPI' in api['name']:
            return i
    return None


def list_wasapi_output_devices():
    if not HAS_SD:
        return []
    wasapi_idx = _get_wasapi_host_api_index()
    if wasapi_idx is None:
        return []
    result = []
    for i, dev in enumerate(sd.query_devices()):
        if dev['max_output_channels'] > 0 and dev['hostapi'] == wasapi_idx:
            result.append({
                'index': i,
                'name': dev['name'],
                'rate': int(dev['default_samplerate']),
                'channels': min(dev['max_output_channels'], 2),
            })
    return result


class AudioRouter:

    def __init__(self):
        self._pa = None
        self._capture_stream = None
        self._capture_thread = None
        self._devices = {}
        self._running = False
        self.active = False
        self._capture_rate = 48000
        self._channels = 2
        self._lock = threading.Lock()

    def start(self):
        if not HAS_PYAUDIO:
            print('  Audio: pyaudiowpatch not installed')
            return False
        if not HAS_SD:
            print('  Audio: sounddevice not installed')
            return False

        try:
            self._pa = pyaudio.PyAudio()
        except Exception as e:
            print(f'  Audio: Failed to init PyAudio: {e}')
            return False

        try:
            loopback = self._pa.get_default_wasapi_loopback()
        except Exception as e:
            print(f'  Audio: No WASAPI loopback: {e}')
            self._pa.terminate()
            self._pa = None
            return False

        self._capture_rate = int(loopback['defaultSampleRate'])
        self._channels = min(int(loopback['maxInputChannels']), 2)
        print(f'  Audio: Loopback <- {loopback["name"][:50]} ({self._capture_rate}Hz, {self._channels}ch)')

        wasapi_outs = list_wasapi_output_devices()
        if not wasapi_outs:
            print('  Audio: No WASAPI output devices found')
            self._pa.terminate()
            self._pa = None
            return False

        print(f'  Audio: {len(wasapi_outs)} WASAPI output device(s):')
        for dev in wasapi_outs:
            print(f'    [{dev["index"]}] {dev["name"][:50]} ({dev["rate"]}Hz)')

        self._running = True
        try:
            self._capture_stream = self._pa.open(
                format=pyaudio.paFloat32,
                channels=self._channels,
                rate=self._capture_rate,
                input=True,
                input_device_index=loopback['index'],
                frames_per_buffer=BLOCKSIZE,
            )
            self._capture_stream.start_stream()

            self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._capture_thread.start()
        except Exception as e:
            print(f'  Audio: Failed to open capture: {e}')
            self._pa.terminate()
            self._pa = None
            return False

        target_name = getattr(config, 'GLASSES_AUDIO_DEVICE', 'SmartGlasses')
        auto_dev = None
        for dev in wasapi_outs:
            if target_name.lower() in dev['name'].lower():
                auto_dev = dev['index']
                break
        if auto_dev is None:
            auto_dev = wasapi_outs[0]['index']

        if self.enable_device(auto_dev):
            dev_name = next(d['name'] for d in wasapi_outs if d['index'] == auto_dev)
            print(f'  Audio: Auto-enabled [{auto_dev}] {dev_name[:50]}')
        else:
            print('  Audio: WARNING - Failed to enable output device')

        self.active = True
        return True

    def _capture_loop(self):
        while self._running:
            try:
                avail = self._capture_stream.get_read_available()
                if avail < BLOCKSIZE:
                    time.sleep(0.002)
                    continue

                data = self._capture_stream.read(BLOCKSIZE, exception_on_overflow=False)
                chunk = np.frombuffer(data, dtype=np.float32).reshape(-1, self._channels)

                for dev_id, dev in list(self._devices.items()):
                    if not dev['enabled'] or dev['queue'] is None:
                        continue
                    try:
                        dev['queue'].put_nowait(chunk.copy())
                    except queue_module.Full:
                        try:
                            dev['queue'].get_nowait()
                            dev['queue'].put_nowait(chunk.copy())
                        except (queue_module.Empty, queue_module.Full):
                            pass
            except Exception as e:
                if self._running:
                    log.warning(f'Capture loop error: {e}')
                    time.sleep(0.1)

    def enable_device(self, sd_index):
        with self._lock:
            if sd_index in self._devices and self._devices[sd_index]['enabled']:
                return True

            try:
                dev_info = sd.query_devices(sd_index)
            except Exception as e:
                log.warning(f'Device {sd_index} not found: {e}')
                return False

            out_rate = int(dev_info['default_samplerate'])
            out_channels = min(dev_info['max_output_channels'], 2)

            q = queue_module.Queue(maxsize=QUEUE_MAXSIZE)

            silence = np.zeros((BLOCKSIZE, self._channels), dtype=np.float32)
            for _ in range(PREFILL_BLOCKS):
                try:
                    q.put_nowait(silence)
                except queue_module.Full:
                    break

            def output_callback(outdata, frames, time_info, status):
                try:
                    data = q.get_nowait()
                    n = min(len(data), frames)
                    if data.shape[1] >= out_channels:
                        outdata[:n] = data[:n, :out_channels]
                    else:
                        outdata[:n, :data.shape[1]] = data[:n]
                        outdata[:n, data.shape[1]:] = 0
                    if n < frames:
                        outdata[n:] = 0
                except queue_module.Empty:
                    outdata.fill(0)

            try:
                stream = sd.OutputStream(
                    samplerate=out_rate,
                    blocksize=BLOCKSIZE,
                    device=sd_index,
                    channels=out_channels,
                    dtype='float32',
                    callback=output_callback,
                )
                stream.start()
            except Exception as e:
                log.warning(f'Failed to open output [{sd_index}]: {e}')
                return False

            self._devices[sd_index] = {
                'queue': q,
                'stream': stream,
                'enabled': True,
                'name': dev_info['name'],
                'rate': out_rate,
                'channels': out_channels,
            }
            log.info(f'Enabled output [{sd_index}] {dev_info["name"][:40]}')
            return True

    def disable_device(self, sd_index):
        with self._lock:
            if sd_index not in self._devices:
                return False
            dev = self._devices[sd_index]
            dev['enabled'] = False
            try:
                dev['stream'].stop()
                dev['stream'].close()
            except Exception:
                pass
            dev['queue'] = None
            dev['stream'] = None
            log.info(f'Disabled output [{sd_index}]')
            return True

    def is_device_enabled(self, sd_index):
        dev = self._devices.get(sd_index)
        return dev is not None and dev['enabled']

    def get_output_devices(self):
        return list_wasapi_output_devices()

    @property
    def active_device_count(self):
        return sum(1 for d in self._devices.values() if d['enabled'])

    def stop(self):
        self._running = False
        with self._lock:
            for sd_index, dev in list(self._devices.items()):
                dev['enabled'] = False
                try:
                    if dev['stream']:
                        dev['stream'].stop()
                        dev['stream'].close()
                except Exception:
                    pass
            self._devices.clear()

        try:
            if self._capture_stream:
                self._capture_stream.stop_stream()
                self._capture_stream.close()
        except Exception:
            pass

        if self._capture_thread:
            self._capture_thread.join(timeout=2.0)

        try:
            if self._pa:
                self._pa.terminate()
        except Exception:
            pass

        self._pa = None
        self._capture_stream = None
        self._capture_thread = None
        self.active = False

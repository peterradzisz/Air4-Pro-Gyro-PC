"""
Spatial Tracking Filter for AR head tracking.

Tracks DELTA yaw (rate of change), not absolute position.
This prevents yaw drift from pushing the image off-screen.

Pipeline: raw gyro -> speed gate -> directional clamp -> output deadzone -> still-lock -> hard clamp -> output

Anti-drift layers:
  1. Input deadzone (speed_dead): filters gyro noise
  2. Directional clamp: rejects movement pushing past max offset
  3. Output deadzone: rejects tiny pixel changes when near-still
  4. Still-lock: freezes position after X seconds of stillness
"""

import math
import time


class SpatialTrackingFilter:
    def __init__(self, pixels_per_radian, screen_width,
                 yaw_max_offset_frac=0.15,
                 pitch_max_offset_frac=0.10,
                 speed_dead=0.08,
                 speed_full=0.60,
                 gain=0.30):

        self.ppr = pixels_per_radian
        self.screen_width = screen_width
        self.yaw_max_offset = yaw_max_offset_frac * screen_width
        self.pitch_max_offset = pitch_max_offset_frac * screen_width

        self.speed_dead = speed_dead
        self.speed_full = speed_full
        self.gain = gain
        self.decay = 1.0
        self.output_deadzone = 0.3  # hidden param, no slider

        # Still-lock: freeze position when head is still for this long
        self.still_lock_time = 0.5  # seconds, 0.0 = disabled
        self._last_movement_time = time.monotonic()
        self._locked = False

        self.output = 0.0
        self.pitch_output = 0.0

    def _responsiveness(self, gyro_speed):
        """Smoothstep: 0 at speed_dead -> 1.0 at speed_full."""
        if gyro_speed <= self.speed_dead:
            return 0.0
        if gyro_speed >= self.speed_full:
            return 1.0
        t = (gyro_speed - self.speed_dead) / (self.speed_full - self.speed_dead)
        s = t * t * (3.0 - 2.0 * t)
        return s

    def _directional_clamp(self, current, delta, max_offset):
        """Reject delta that pushes output further past max offset.
        Always allows movement back toward center."""
        if max_offset <= 0 or delta == 0.0:
            return delta
        # Near positive max and pushing further positive
        if current > max_offset * 0.9 and delta > 0:
            return 0.0
        # Near negative max and pushing further negative
        if current < -max_offset * 0.9 and delta < 0:
            return 0.0
        return delta

    def update(self, yaw_angular_vel, gyro_speed, dt=1/60):
        """Per-frame update (~60Hz)."""
        # Reject spikes
        if abs(yaw_angular_vel) > math.radians(200):
            yaw_angular_vel = 0.0

        # Still-lock: freeze when head is still for still_lock_time seconds
        now = time.monotonic()
        if gyro_speed > self.speed_dead * 2.0:
            self._last_movement_time = now
            self._locked = False
        elif self.still_lock_time > 0.0 and not self._locked:
            if now - self._last_movement_time > self.still_lock_time:
                self._locked = True

        if self._locked:
            return self.output

        # Speed-gated integration
        resp = self._responsiveness(gyro_speed)
        delta_rad = yaw_angular_vel * dt
        delta_px = delta_rad * self.ppr * self.gain * resp

        # Directional clamp: reject pushing past max
        delta_px = self._directional_clamp(self.output, delta_px, self.yaw_max_offset)

        # Output deadzone: reject tiny changes when near-still
        if self.output_deadzone > 0.0 and abs(delta_px) < self.output_deadzone:
            if gyro_speed < self.speed_dead * 2.0:
                delta_px = 0.0

        self.output += delta_px

        # Decay (only when < 1.0)
        if self.decay < 1.0:
            self.output *= self.decay

        # Hard clamp to max offset
        if self.yaw_max_offset > 0:
            self.output = max(-self.yaw_max_offset, min(self.yaw_max_offset, self.output))

        return self.output

    def update_pitch(self, pitch_angular_vel, gyro_speed, dt=1/60):
        """Per-frame pitch update."""
        if abs(pitch_angular_vel) > math.radians(200):
            pitch_angular_vel = 0.0

        # Still-lock applies to pitch too
        if self._locked:
            return

        resp = self._responsiveness(gyro_speed)
        delta_rad = pitch_angular_vel * dt
        delta_px = delta_rad * self.ppr * self.gain * resp

        # Directional clamp for pitch
        delta_px = self._directional_clamp(self.pitch_output, delta_px, self.pitch_max_offset)

        # Output deadzone
        if self.output_deadzone > 0.0 and abs(delta_px) < self.output_deadzone:
            if gyro_speed < self.speed_dead * 2.0:
                delta_px = 0.0

        self.pitch_output += delta_px

        if self.decay < 1.0:
            self.pitch_output *= self.decay

        if self.pitch_max_offset > 0:
            self.pitch_output = max(-self.pitch_max_offset, min(self.pitch_max_offset, self.pitch_output))

    def recenter(self):
        """Snap output to zero (hotkey action)."""
        self.output = 0.0
        self.pitch_output = 0.0
        self._locked = False
        self._last_movement_time = time.monotonic()

"""
Spatial Tracking Filter for AR head tracking.

Tracks DELTA yaw (rate of change), not absolute position.
This prevents yaw drift from pushing the image off-screen.

Pipeline: delta_yaw -> speed-gated integrator -> output deadzone -> hard clamp -> output
"""

import math
from airpin import settings_manager


class SpatialTrackingFilter:
    def __init__(self, pixels_per_radian, screen_width,
                 yaw_max_offset_frac=0.15,    # max horizontal shift as fraction of screen width
                 pitch_max_offset_frac=0.10,   # max vertical shift as fraction of screen height
                 speed_dead=0.08,             # rad/s - below this, delta ignored (deadzone)
                 speed_full=0.40,             # rad/s - full tracking above this
                 gain=0.30):                  # base responsiveness multiplier

        self.ppr = pixels_per_radian
        self.screen_width = screen_width
        self.yaw_max_offset = yaw_max_offset_frac * screen_width
        self.pitch_max_offset = pitch_max_offset_frac * screen_width  # overridden at runtime with screen_height

        self.speed_dead = speed_dead
        self.speed_full = speed_full
        self.gain = gain
        self.decay = 1.0
        self.output_deadzone = 0.0  # px — reject tiny pixel changes when near-still

        self.output = 0.0
        self.pitch_output = 0.0
        # No _last_yaw/_last_pitch needed -- using raw gyro directly

    def _responsiveness(self, gyro_speed):
        """Smoothstep: 0 at speed_dead -> 1.0 at speed_full."""
        if gyro_speed <= self.speed_dead:
            return 0.0
        if gyro_speed >= self.speed_full:
            return 1.0
        t = (gyro_speed - self.speed_dead) / (self.speed_full - self.speed_dead)
        s = t * t * (3.0 - 2.0 * t)
        return s

    def update(self, yaw_angular_vel, gyro_speed, dt=1/60):
        """
        Per-frame update (~60Hz).
        Uses raw gyro angular velocity directly.

        The output accumulates head movement and holds position.
        When you turn back, the image stays put (doesn't return).
        Only Ctrl+Alt+R resets.

        Args:
            yaw_angular_vel: raw yaw gyro in rad/s
            gyro_speed: total angular velocity magnitude (rad/s), for speed gate
            dt: time step in seconds

        Returns:
            Pixel offset for OpenGL rendering.
        """
        # Reject spikes
        if abs(yaw_angular_vel) > math.radians(200):
            yaw_angular_vel = 0.0

        # Speed-gated: only integrate when head is moving fast enough
        resp = self._responsiveness(gyro_speed)
        delta_rad = yaw_angular_vel * dt
        delta_px = delta_rad * self.ppr * self.gain * resp

        # Output deadzone: reject tiny changes when head is near-still
        if self.output_deadzone > 0.0 and abs(delta_px) < self.output_deadzone:
            # Only swallow if head is also near-still (speed < 2x input deadzone)
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
        """Per-frame pitch update -- uses raw gyro angular velocity directly."""
        if abs(pitch_angular_vel) > math.radians(200):
            pitch_angular_vel = 0.0

        resp = self._responsiveness(gyro_speed)
        delta_rad = pitch_angular_vel * dt
        delta_px = delta_rad * self.ppr * self.gain * resp

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
        # No _last_yaw/_last_pitch needed -- using raw gyro directly

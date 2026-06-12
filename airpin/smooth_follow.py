"""
Spatial Tracking Filter for AR head tracking.

Tracks DELTA yaw (rate of change), not absolute position.

Pipeline: raw gyro -> speed gate -> integration -> directional clamp
          -> output deadzone -> hard clamp -> output

Snap-back: when head is still after significant movement,
exponentially decays output toward zero. Cancelled by any movement.
"""

import math
import time


TRACKING = 0
SNAP_BACK = 1


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
        self.output_deadzone = 0.3

        # Snap-back config
        self.snap_speed = 2.5
        self._snap_still_time = 0.4
        self._snap_threshold = 60.0
        self.snap_return = 0.5   # fraction of peak user must return before snap triggers

        # Per-axis state
        self._yaw_state = TRACKING
        self._yaw_stillness = 0.0
        self._yaw_peak = 0.0

        self._pitch_state = TRACKING
        self._pitch_stillness = 0.0
        self._pitch_peak = 0.0

        self.output = 0.0
        self.pitch_output = 0.0

    def _responsiveness(self, gyro_speed):
        if gyro_speed <= self.speed_dead:
            return 0.0
        if gyro_speed >= self.speed_full:
            return 1.0
        t = (gyro_speed - self.speed_dead) / (self.speed_full - self.speed_dead)
        s = t * t * (3.0 - 2.0 * t)
        return s

    def _directional_clamp(self, current, delta, max_offset):
        if max_offset <= 0 or delta == 0.0:
            return delta
        if current > max_offset * 0.9 and delta > 0:
            return 0.0
        if current < -max_offset * 0.9 and delta < 0:
            return 0.0
        return delta

    def update(self, yaw_angular_vel, gyro_speed, dt=1/60):
        if abs(yaw_angular_vel) > math.radians(200):
            yaw_angular_vel = 0.0

        # Snap-back state machine
        if self._yaw_state == SNAP_BACK:
            if gyro_speed > self.speed_dead * 1.5:
                self._yaw_state = TRACKING
                self._yaw_stillness = 0.0
                self._yaw_peak = abs(self.output)
            else:
                decay_factor = max(0.0, 1.0 - self.snap_speed * dt)
                self.output *= decay_factor
                if abs(self.output) < 0.5:
                    self.output = 0.0
                    self._yaw_state = TRACKING
                    self._yaw_stillness = 0.0
                    self._yaw_peak = 0.0
                return self.output

        # TRACKING: normal integration
        resp = self._responsiveness(gyro_speed)
        delta_rad = yaw_angular_vel * dt
        delta_px = delta_rad * self.ppr * self.gain * resp
        delta_px = self._directional_clamp(self.output, delta_px, self.yaw_max_offset)

        if self.output_deadzone > 0.0 and abs(delta_px) < self.output_deadzone:
            if gyro_speed < self.speed_dead * 2.0:
                delta_px = 0.0

        self.output += delta_px

        if self.decay < 1.0:
            self.output *= self.decay

        if self.yaw_max_offset > 0:
            self.output = max(-self.yaw_max_offset, min(self.yaw_max_offset, self.output))

        # Trigger tracking
        self._yaw_peak = max(self._yaw_peak, abs(self.output))
        if gyro_speed < self.speed_dead * 2.0:
            self._yaw_stillness += dt
        else:
            self._yaw_stillness = 0.0

        if (self._yaw_stillness > self._snap_still_time
                and self._yaw_peak > self._snap_threshold
                and abs(self.output) < self._yaw_peak * self.snap_return
                and self.snap_speed > 0.0):
            self._yaw_state = SNAP_BACK

        return self.output

    def update_pitch(self, pitch_angular_vel, gyro_speed, dt=1/60):
        if abs(pitch_angular_vel) > math.radians(200):
            pitch_angular_vel = 0.0

        if self._pitch_state == SNAP_BACK:
            if gyro_speed > self.speed_dead * 1.5:
                self._pitch_state = TRACKING
                self._pitch_stillness = 0.0
                self._pitch_peak = abs(self.pitch_output)
            else:
                decay_factor = max(0.0, 1.0 - self.snap_speed * dt)
                self.pitch_output *= decay_factor
                if abs(self.pitch_output) < 0.5:
                    self.pitch_output = 0.0
                    self._pitch_state = TRACKING
                    self._pitch_stillness = 0.0
                    self._pitch_peak = 0.0
                return

        resp = self._responsiveness(gyro_speed)
        delta_rad = pitch_angular_vel * dt
        delta_px = delta_rad * self.ppr * self.gain * resp
        delta_px = self._directional_clamp(self.pitch_output, delta_px, self.pitch_max_offset)

        if self.output_deadzone > 0.0 and abs(delta_px) < self.output_deadzone:
            if gyro_speed < self.speed_dead * 2.0:
                delta_px = 0.0

        self.pitch_output += delta_px

        if self.decay < 1.0:
            self.pitch_output *= self.decay

        if self.pitch_max_offset > 0:
            self.pitch_output = max(-self.pitch_max_offset, min(self.pitch_max_offset, self.pitch_output))

        self._pitch_peak = max(self._pitch_peak, abs(self.pitch_output))
        if gyro_speed < self.speed_dead * 2.0:
            self._pitch_stillness += dt
        else:
            self._pitch_stillness = 0.0

        if (self._pitch_stillness > self._snap_still_time
                and self._pitch_peak > self._snap_threshold
                and abs(self.pitch_output) < self._pitch_peak * self.snap_return
                and self.snap_speed > 0.0):
            self._pitch_state = SNAP_BACK

    def recenter(self):
        self.output = 0.0
        self.pitch_output = 0.0
        self._yaw_state = TRACKING
        self._yaw_stillness = 0.0
        self._yaw_peak = 0.0
        self._pitch_state = TRACKING
        self._pitch_stillness = 0.0
        self._pitch_peak = 0.0

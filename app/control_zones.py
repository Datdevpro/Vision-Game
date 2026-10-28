"""Shared normalized geometry for gesture recognition and the camera overlay."""
from dataclasses import dataclass
from typing import Optional

from app.calibration import BaselineData


@dataclass(frozen=True)
class ControlZones:
    left_boundary: float
    right_boundary: float
    center_y: float
    jump_y: float
    crouch_y: float

    @classmethod
    def from_baseline(cls, baseline: Optional[BaselineData], sensitivity: float = 1.0,
                      lane_center_half_width: float = 0.10,
                      auto_calibrate_lanes: bool = True,
                      lane_shoulder_width_factor: float = 0.8):
        sensitivity = max(0.5, min(2.5, sensitivity))
        lane_center_half_width = max(0.02, min(0.30, lane_center_half_width))
        center_x = 0.5
        if auto_calibrate_lanes and baseline and baseline.is_calibrated:
            # Use the horizontal shoulder span, not its diagonal length when one
            # shoulder is higher. The captured baseline stays fixed during play.
            span = baseline.shoulder_width
            if baseline.shoulder_left_x is not None and baseline.shoulder_right_x is not None:
                span = abs(baseline.shoulder_right_x - baseline.shoulder_left_x)
            factor = max(0.25, min(1.5, lane_shoulder_width_factor))
            lane_center_half_width = max(0.02, min(0.15, span * factor / 2))
            center_x = max(lane_center_half_width, min(1 - lane_center_half_width, baseline.body_center_x))
        center_y = (baseline.shoulder_center_y + baseline.hip_center_y) / 2 if baseline else 0.5
        torso = max(0.05, baseline.torso_length) if baseline else 0.3
        jump = baseline.jump_threshold if baseline else 0.12
        crouch = baseline.crouch_threshold if baseline else 0.14
        return cls(center_x - lane_center_half_width, center_x + lane_center_half_width, center_y,
                   max(0.0, center_y - jump * torso / sensitivity),
                   min(1.0, center_y + crouch * torso / sensitivity))

    def lane_at(self, x: float) -> int:
        return 0 if x < self.left_boundary else 2 if x > self.right_boundary else 1

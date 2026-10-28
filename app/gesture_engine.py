"""Convert tracked body position into a target lane and vertical action."""
from enum import Enum
from typing import Dict, Tuple

from app.calibration import BaselineData
from app.control_zones import ControlZones
from app.landmarks import BodyMetrics


class GestureType(Enum):
    NONE = "NONE"
    MOVE_LEFT = "MOVE_LEFT"
    MOVE_RIGHT = "MOVE_RIGHT"
    JUMP = "JUMP"
    CROUCH = "CROUCH"


class ControlMode(Enum):
    ZONES = "zones"
    SIDE_STEP = "zones"  # Compatibility for callers using the former name.
    LEAN = "lean"


class GestureEngine:
    def __init__(
        self, mode: ControlMode = ControlMode.ZONES, sensitivity: float = 1.0,
        mirrored: bool = True, hysteresis_factor: float = 0.55,
        lane_center_half_width: float = 0.10,
        auto_calibrate_lanes: bool = True, lane_shoulder_width_factor: float = 0.8,
    ):
        self.mode = mode
        self.sensitivity = max(0.5, min(2.5, sensitivity))
        self.mirrored = mirrored
        self.hysteresis_factor = hysteresis_factor
        self.lane_center_half_width = lane_center_half_width
        self.auto_calibrate_lanes = auto_calibrate_lanes
        self.lane_shoulder_width_factor = lane_shoulder_width_factor

    def set_sensitivity(self, sensitivity: float):
        self.sensitivity = max(0.5, min(2.5, sensitivity))

    def set_mode(self, mode: ControlMode):
        self.mode = mode

    def set_mirrored(self, mirrored: bool):
        self.mirrored = mirrored

    def get_zones(self, baseline: BaselineData = None) -> ControlZones:
        return ControlZones.from_baseline(
            baseline, self.sensitivity, self.lane_center_half_width,
            self.auto_calibrate_lanes, self.lane_shoulder_width_factor,
        )

    def evaluate(self, metrics: BodyMetrics, baseline: BaselineData) -> Tuple[GestureType, Dict[str, float]]:
        debug = {"target_lane": 1.0, "is_neutral_x": 1.0, "is_neutral_y": 1.0,
                 "disp_x": 0.0, "disp_y_up": 0.0, "disp_y_down": 0.0}
        if not metrics.is_valid or not baseline or not baseline.is_calibrated:
            return GestureType.NONE, debug

        zones = self.get_zones(baseline)
        # Inference sees the displayed image, including camera mirroring.
        # Image LEFT means lane LEFT; never flip coordinates a second time.
        lane = zones.lane_at(metrics.body_center.x)
        if self.mode == ControlMode.LEAN:
            threshold = baseline.lean_threshold / self.sensitivity
            lane = 0 if metrics.lean_angle_deg < -threshold else 2 if metrics.lean_angle_deg > threshold else 1
        debug["target_lane"] = float(lane)
        debug["is_neutral_x"] = float(lane == 1)
        debug["disp_x"] = (baseline.body_center_x - metrics.body_center.x) / max(0.05, baseline.torso_length)

        y = metrics.body_center.y
        torso = max(0.05, baseline.torso_length)
        debug["disp_y_up"] = (zones.center_y - y) / torso
        debug["disp_y_down"] = (y - zones.center_y) / torso
        upper_reset = zones.center_y - (zones.center_y - zones.jump_y) * self.hysteresis_factor
        lower_reset = zones.center_y + (zones.crouch_y - zones.center_y) * self.hysteresis_factor
        debug["is_neutral_y"] = float(upper_reset <= y <= lower_reset)

        if y < zones.jump_y:
            return GestureType.JUMP, debug
        if y > zones.crouch_y:
            return GestureType.CROUCH, debug
        gesture = (GestureType.MOVE_LEFT, GestureType.NONE, GestureType.MOVE_RIGHT)[lane]
        return gesture, debug

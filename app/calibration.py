"""
Calibration system for Subway Surfers AI Body Controller.
Collects neutral baseline poses, computes median metrics, derives adaptive
relative thresholds, and provides step-by-step verification in Vietnamese.
"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple, Dict
import numpy as np
from app.landmarks import BodyMetrics

class CalibrationState(Enum):
    IDLE = "IDLE"
    COUNTDOWN = "COUNTDOWN"
    COLLECTING = "COLLECTING"
    VERIFY_LEFT = "VERIFY_LEFT"
    VERIFY_RIGHT = "VERIFY_RIGHT"
    VERIFY_JUMP = "VERIFY_JUMP"
    VERIFY_CROUCH = "VERIFY_CROUCH"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@dataclass
class BaselineData:
    body_center_x: float
    shoulder_center_y: float
    hip_center_y: float
    torso_length: float
    shoulder_width: float
    # Adaptive relative thresholds (normalized by torso_length)
    step_threshold: float = 0.16
    jump_threshold: float = 0.12
    crouch_threshold: float = 0.14
    lean_threshold: float = 10.0
    is_calibrated: bool = False
    # Ordered by displayed image X, independently of anatomical left/right.
    shoulder_left_x: Optional[float] = None
    shoulder_right_x: Optional[float] = None

class CalibrationManager:
    """
    Guides the user through countdown and baseline capture, computing
    median geometric metrics for adaptive gesture detection.
    """
    def __init__(self, countdown_s: float = 3.0, sample_count: int = 30,
                 jump_threshold: float = 0.12, crouch_threshold: float = 0.14,
                 lean_threshold: float = 10.0):
        self.countdown_duration = countdown_s
        self.sample_count = sample_count
        self.jump_threshold = jump_threshold
        self.crouch_threshold = crouch_threshold
        self.lean_threshold = lean_threshold
        
        self.state = CalibrationState.IDLE
        self.timer: float = 0.0
        self.samples: List[BodyMetrics] = []
        self.baseline: Optional[BaselineData] = None
        self.status_message: str = "Nhấn 'Bắt đầu Hiệu chỉnh' (Calibrate) để bắt đầu"
        self.progress: float = 0.0  # 0.0 to 1.0

    def start_calibration(self):
        """Begin 3-second countdown for standing straight."""
        self.state = CalibrationState.COUNTDOWN
        self.timer = self.countdown_duration
        self.samples.clear()
        self.progress = 0.0
        self.status_message = "Đứng thẳng trước camera, nhìn thẳng..."

    def recalibrate(self):
        self.start_calibration()

    def reset(self):
        self.state = CalibrationState.IDLE
        self.timer = 0.0
        self.samples.clear()
        self.baseline = None
        self.progress = 0.0
        self.status_message = "Chưa hiệu chỉnh. Vui lòng bấm Calibrate."

    def update(self, metrics: BodyMetrics, dt: float) -> Tuple[CalibrationState, str, float]:
        """
        Advance calibration by dt seconds given current frame metrics.
        Returns (state, status_message, progress).
        """
        if self.state == CalibrationState.IDLE:
            return self.state, self.status_message, self.progress

        if not metrics.is_valid:
            if self.state in [CalibrationState.COUNTDOWN, CalibrationState.COLLECTING]:
                self.status_message = "⚠️ KHÔNG TÌM THẤY NGƯỜI CHƠI! Vui lòng đứng rõ trước camera"
                return self.state, self.status_message, self.progress

        if self.state in (CalibrationState.COUNTDOWN, CalibrationState.COLLECTING):
            shoulders = [metrics.raw_landmarks[i] for i in (11, 12)] if len(metrics.raw_landmarks) > 12 else []
            if len(shoulders) != 2 or any(
                point.visibility < 0.5 or not (0 <= point.x <= 1 and 0 <= point.y <= 1)
                for point in shoulders
            ):
                self.status_message = "Vui lòng để camera thấy rõ cả hai vai, không che vai hoặc quay nghiêng."
                return self.state, self.status_message, self.progress

        if self.state == CalibrationState.COUNTDOWN:
            self.timer -= dt
            self.progress = max(0.0, min(1.0, 1.0 - (self.timer / self.countdown_duration)))
            sec_left = max(1, int(np.ceil(self.timer)))
            self.status_message = f"Đứng thẳng trước camera... {sec_left}s"
            
            if self.timer <= 0.0:
                self.state = CalibrationState.COLLECTING
                self.timer = 0.0
                self.samples.clear()
                self.status_message = "Đang thu thập tư thế chuẩn (giữ nguyên vị trí)..."

        elif self.state == CalibrationState.COLLECTING:
            if metrics.is_valid:
                self.samples.append(metrics)
                self.progress = len(self.samples) / self.sample_count
                self.status_message = f"Đang thu thập dữ liệu... ({len(self.samples)}/{self.sample_count})"
                
                if len(self.samples) >= self.sample_count:
                    self._compute_baseline()
                    self.state = CalibrationState.COMPLETED
                    self.progress = 1.0
                    self.status_message = "CALIBRATION COMPLETE! Sẵn sàng chơi!"

        return self.state, self.status_message, self.progress

    def _compute_baseline(self):
        """Calculate robust median metrics across collected valid frames."""
        if not self.samples:
            self.state = CalibrationState.FAILED
            self.status_message = "Lỗi thu thập: không đủ dữ liệu. Vui lòng thử lại!"
            return

        body_xs = [s.body_center.x for s in self.samples]
        shoulder_ys = [s.shoulder_center.y for s in self.samples]
        hip_ys = [s.hip_center.y for s in self.samples]
        torso_lens = [s.torso_length for s in self.samples]
        shoulder_widths = [s.shoulder_width for s in self.samples]
        shoulder_pairs = [sorted((s.raw_landmarks[11].x, s.raw_landmarks[12].x))
                          for s in self.samples if len(s.raw_landmarks) > 12]

        median_body_x = float(np.median(body_xs))
        median_shoulder_y = float(np.median(shoulder_ys))
        median_hip_y = float(np.median(hip_ys))
        median_torso_len = max(0.05, float(np.median(torso_lens)))
        median_shoulder_width = max(0.04, float(np.median(shoulder_widths)))

        # Adaptive relative thresholds:
        # Step threshold: ~40% of shoulder width or ~35% of torso length
        step_threshold = max(0.12, min(0.24, 0.45 * (median_shoulder_width / median_torso_len) * 0.35))
        # Jump threshold: ~12% of torso length
        jump_threshold = self.jump_threshold
        # Crouch threshold: ~14% of torso length
        crouch_threshold = self.crouch_threshold
        lean_threshold = self.lean_threshold

        self.baseline = BaselineData(
            body_center_x=median_body_x,
            shoulder_center_y=median_shoulder_y,
            hip_center_y=median_hip_y,
            torso_length=median_torso_len,
            shoulder_width=median_shoulder_width,
            step_threshold=step_threshold,
            jump_threshold=jump_threshold,
            crouch_threshold=crouch_threshold,
            lean_threshold=lean_threshold,
            is_calibrated=True,
            shoulder_left_x=float(np.median([pair[0] for pair in shoulder_pairs])) if shoulder_pairs else None,
            shoulder_right_x=float(np.median([pair[1] for pair in shoulder_pairs])) if shoulder_pairs else None,
        )

    def is_calibrated(self) -> bool:
        return self.baseline is not None and self.baseline.is_calibrated

    def get_baseline(self) -> Optional[BaselineData]:
        return self.baseline

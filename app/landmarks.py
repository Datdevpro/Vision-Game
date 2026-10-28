"""
Landmark definitions, body geometry metrics extraction, angle calculation,
and temporal smoothing for MediaPipe Pose Landmarker.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
import math
import numpy as np

# MediaPipe Pose Landmark Indices (0 to 32)
NOSE = 0
LEFT_EYE_INNER = 1
LEFT_EYE = 2
LEFT_EYE_OUTER = 3
RIGHT_EYE_INNER = 4
RIGHT_EYE = 5
RIGHT_EYE_OUTER = 6
LEFT_EAR = 7
RIGHT_EAR = 8
MOUTH_LEFT = 9
MOUTH_RIGHT = 10
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_PINKY = 17
RIGHT_PINKY = 18
LEFT_INDEX = 19
RIGHT_INDEX = 20
LEFT_THUMB = 21
RIGHT_THUMB = 22
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28
LEFT_HEEL = 29
RIGHT_HEEL = 30
LEFT_FOOT_INDEX = 31
RIGHT_FOOT_INDEX = 32

# Standard skeleton connections for visualization
SKELETON_CONNECTIONS = [
    # Face
    (NOSE, LEFT_EYE), (LEFT_EYE, LEFT_EAR),
    (NOSE, RIGHT_EYE), (RIGHT_EYE, RIGHT_EAR),
    # Torso
    (LEFT_SHOULDER, RIGHT_SHOULDER),
    (LEFT_SHOULDER, LEFT_HIP),
    (RIGHT_SHOULDER, RIGHT_HIP),
    (LEFT_HIP, RIGHT_HIP),
    # Arms
    (LEFT_SHOULDER, LEFT_ELBOW), (LEFT_ELBOW, LEFT_WRIST),
    (RIGHT_SHOULDER, RIGHT_ELBOW), (RIGHT_ELBOW, RIGHT_WRIST),
    # Legs
    (LEFT_HIP, LEFT_KNEE), (LEFT_KNEE, LEFT_ANKLE),
    (RIGHT_HIP, RIGHT_KNEE), (RIGHT_KNEE, RIGHT_ANKLE),
    # Feet
    (LEFT_ANKLE, LEFT_FOOT_INDEX),
    (RIGHT_ANKLE, RIGHT_FOOT_INDEX),
]

@dataclass
class Point2D:
    x: float
    y: float

@dataclass
class PoseLandmark:
    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0
    presence: float = 1.0

@dataclass
class BodyMetrics:
    shoulder_center: Point2D
    hip_center: Point2D
    body_center: Point2D
    torso_length: float
    shoulder_width: float
    lean_angle_deg: float      # angle relative to vertical (- is left lean, + is right lean)
    lean_offset: float         # (shoulder.x - hip.x) normalized by torso_length
    knee_angle_left: float     # degrees (approx 180 standing, < 140 crouching)
    knee_angle_right: float
    confidence: float
    is_valid: bool
    is_tracked: bool
    raw_landmarks: List[PoseLandmark]

def calculate_angle(p1: Point2D, p2: Point2D, p3: Point2D) -> float:
    """Calculate the interior angle (in degrees) at vertex p2 between (p1->p2) and (p3->p2)."""
    v1 = np.array([p1.x - p2.x, p1.y - p2.y], dtype=np.float32)
    v2 = np.array([p3.x - p2.x, p3.y - p2.y], dtype=np.float32)
    
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 < 1e-6 or norm2 < 1e-6:
        return 180.0
    
    cosine = np.dot(v1, v2) / (norm1 * norm2)
    cosine = np.clip(cosine, -1.0, 1.0)
    angle_rad = np.arccos(cosine)
    return float(np.degrees(angle_rad))

class LandmarkProcessor:
    """
    Extracts high-level body metrics, applies exponential moving average (EMA)
    smoothing, and verifies landmark presence and confidence.
    """
    def __init__(self, ema_alpha: float = 0.40, min_confidence: float = 0.45):
        self.ema_alpha = ema_alpha
        self.min_confidence = min_confidence
        self.prev_landmarks: Optional[List[PoseLandmark]] = None
        self.prev_body_center_y: Optional[float] = None
        self.prev_timestamp: Optional[float] = None
        self.vertical_velocity: float = 0.0

    def reset(self):
        self.prev_landmarks = None
        self.prev_body_center_y = None
        self.prev_timestamp = None
        self.vertical_velocity = 0.0

    def set_ema_alpha(self, alpha: float):
        self.ema_alpha = max(0.05, min(1.0, alpha))

    def process(self, raw_points: List[PoseLandmark], timestamp_s: float = None) -> BodyMetrics:
        """
        Process 33 normalized landmarks into smoothed BodyMetrics.
        If landmarks are missing or confidence is too low, returns invalid metrics.
        """
        if not raw_points or len(raw_points) < 29:
            self.reset()
            return self._empty_metrics()

        # Key landmarks required for reliable tracking
        required_indices = [LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP]
        visibilities = [raw_points[idx].visibility for idx in required_indices]
        avg_confidence = float(np.mean(visibilities))

        if avg_confidence < self.min_confidence:
            return self._empty_metrics(confidence=avg_confidence)

        # Temporal EMA smoothing on normalized landmark coordinates
        smoothed: List[PoseLandmark] = []
        if self.prev_landmarks is None or len(self.prev_landmarks) != len(raw_points):
            smoothed = [PoseLandmark(p.x, p.y, p.z, p.visibility, p.presence) for p in raw_points]
        else:
            alpha = self.ema_alpha
            for p, prev in zip(raw_points, self.prev_landmarks):
                sx = alpha * p.x + (1.0 - alpha) * prev.x
                sy = alpha * p.y + (1.0 - alpha) * prev.y
                sz = alpha * p.z + (1.0 - alpha) * prev.z
                smoothed.append(PoseLandmark(sx, sy, sz, p.visibility, p.presence))

        self.prev_landmarks = smoothed

        # Calculate geometric centers
        ls = smoothed[LEFT_SHOULDER]
        rs = smoothed[RIGHT_SHOULDER]
        lh = smoothed[LEFT_HIP]
        rh = smoothed[RIGHT_HIP]

        shoulder_center = Point2D(x=(ls.x + rs.x) / 2.0, y=(ls.y + rs.y) / 2.0)
        hip_center = Point2D(x=(lh.x + rh.x) / 2.0, y=(lh.y + rh.y) / 2.0)
        body_center = Point2D(
            x=(shoulder_center.x + hip_center.x) / 2.0,
            y=(shoulder_center.y + hip_center.y) / 2.0,
        )

        # Scale metrics: torso length & shoulder width
        dx_torso = shoulder_center.x - hip_center.x
        dy_torso = shoulder_center.y - hip_center.y
        torso_length = float(math.sqrt(dx_torso * dx_torso + dy_torso * dy_torso))
        torso_length = max(torso_length, 0.05)  # Guard against division by zero

        dx_shoulder = ls.x - rs.x
        dy_shoulder = ls.y - rs.y
        shoulder_width = float(math.sqrt(dx_shoulder * dx_shoulder + dy_shoulder * dy_shoulder))
        shoulder_width = max(shoulder_width, 0.04)

        # Lean metrics
        # Negative angle = tilted left, Positive angle = tilted right
        # In image coordinates: Y is positive down.
        # Vector from hip to shoulder: dx = shoulder_center.x - hip_center.x, dy = shoulder_center.y - hip_center.y (negative)
        lean_angle_rad = math.atan2(dx_torso, -dy_torso)
        lean_angle_deg = float(math.degrees(lean_angle_rad))
        lean_offset = dx_torso / torso_length

        # Knee angles if legs are visible
        lk = smoothed[LEFT_KNEE]
        la = smoothed[LEFT_ANKLE]
        rk = smoothed[RIGHT_KNEE]
        ra = smoothed[RIGHT_ANKLE]

        knee_left = 180.0
        if lk.visibility > 0.35 and la.visibility > 0.35:
            knee_left = calculate_angle(Point2D(lh.x, lh.y), Point2D(lk.x, lk.y), Point2D(la.x, la.y))

        knee_right = 180.0
        if rk.visibility > 0.35 and ra.visibility > 0.35:
            knee_right = calculate_angle(Point2D(rh.x, rh.y), Point2D(rk.x, rk.y), Point2D(ra.x, ra.y))

        # Vertical velocity estimation (normalized units per second, positive UPWARDS)
        # Note: image Y is down, so upward motion corresponds to decreasing Y.
        if timestamp_s is not None and self.prev_timestamp is not None and self.prev_body_center_y is not None:
            dt = timestamp_s - self.prev_timestamp
            if 0.005 < dt < 0.5:
                # dy_up > 0 when body moves UP
                dy_up = (self.prev_body_center_y - body_center.y) / torso_length
                raw_velocity = dy_up / dt
                # Smooth velocity
                self.vertical_velocity = 0.5 * self.vertical_velocity + 0.5 * raw_velocity

        self.prev_body_center_y = body_center.y
        self.prev_timestamp = timestamp_s

        return BodyMetrics(
            shoulder_center=shoulder_center,
            hip_center=hip_center,
            body_center=body_center,
            torso_length=torso_length,
            shoulder_width=shoulder_width,
            lean_angle_deg=lean_angle_deg,
            lean_offset=lean_offset,
            knee_angle_left=knee_left,
            knee_angle_right=knee_right,
            confidence=avg_confidence,
            is_valid=True,
            is_tracked=True,
            raw_landmarks=smoothed,
        )

    def _empty_metrics(self, confidence: float = 0.0) -> BodyMetrics:
        return BodyMetrics(
            shoulder_center=Point2D(0.5, 0.5),
            hip_center=Point2D(0.5, 0.5),
            body_center=Point2D(0.5, 0.5),
            torso_length=0.25,
            shoulder_width=0.20,
            lean_angle_deg=0.0,
            lean_offset=0.0,
            knee_angle_left=180.0,
            knee_angle_right=180.0,
            confidence=confidence,
            is_valid=False,
            is_tracked=False,
            raw_landmarks=[],
        )

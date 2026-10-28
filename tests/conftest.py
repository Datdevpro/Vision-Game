"""
Pytest fixtures and synthetic landmark generators for Subway Surfers AI Body Controller.
Generates full 33-point realistic body skeletons with customizable positions and scale.
"""
import pytest
from typing import List
from app.landmarks import PoseLandmark

def create_synthetic_landmarks(
    center_x: float = 0.5,
    shoulder_y: float = 0.35,
    hip_y: float = 0.65,
    shoulder_width: float = 0.20,
    hip_width: float = 0.14,
    lean_offset_x: float = 0.0,
    knee_angle_deg: float = 180.0,
    confidence: float = 0.95,
) -> List[PoseLandmark]:
    """
    Constructs a complete 33-landmark pose based on specified geometry.
    """
    lms = [PoseLandmark(x=center_x, y=shoulder_y - 0.15, z=0.0, visibility=confidence, presence=confidence) for _ in range(33)]

    # Shoulders (11=left, 12=right)
    # Left shoulder is on image right or left depending on viewing
    # In standard MediaPipe: left side of body is person's left (viewer's right if facing camera)
    half_sw = shoulder_width / 2.0
    sh_center_x = center_x + lean_offset_x
    lms[11] = PoseLandmark(x=sh_center_x + half_sw, y=shoulder_y, z=0.0, visibility=confidence, presence=confidence)
    lms[12] = PoseLandmark(x=sh_center_x - half_sw, y=shoulder_y, z=0.0, visibility=confidence, presence=confidence)

    # Hips (23=left, 24=right)
    half_hw = hip_width / 2.0
    lms[23] = PoseLandmark(x=center_x + half_hw, y=hip_y, z=0.0, visibility=confidence, presence=confidence)
    lms[24] = PoseLandmark(x=center_x - half_hw, y=hip_y, z=0.0, visibility=confidence, presence=confidence)

    # Knees (25=left, 26=right)
    knee_y = hip_y + 0.15
    lms[25] = PoseLandmark(x=center_x + half_hw, y=knee_y, z=0.0, visibility=confidence, presence=confidence)
    lms[26] = PoseLandmark(x=center_x - half_hw, y=knee_y, z=0.0, visibility=confidence, presence=confidence)

    # Ankles (27=left, 28=right)
    ankle_y = knee_y + 0.15
    lms[27] = PoseLandmark(x=center_x + half_hw, y=ankle_y, z=0.0, visibility=confidence, presence=confidence)
    lms[28] = PoseLandmark(x=center_x - half_hw, y=ankle_y, z=0.0, visibility=confidence, presence=confidence)

    # Nose (0)
    lms[0] = PoseLandmark(x=sh_center_x, y=shoulder_y - 0.12, z=0.0, visibility=confidence, presence=confidence)

    return lms

@pytest.fixture
def neutral_pose():
    return create_synthetic_landmarks(center_x=0.5, shoulder_y=0.35, hip_y=0.65)

@pytest.fixture
def left_step_pose():
    # The left third of the displayed frame.
    return create_synthetic_landmarks(center_x=0.25, shoulder_y=0.35, hip_y=0.65)

@pytest.fixture
def right_step_pose():
    # The right third of the displayed frame.
    return create_synthetic_landmarks(center_x=0.75, shoulder_y=0.35, hip_y=0.65)

@pytest.fixture
def jump_pose():
    # Upward motion: shoulder and hip Y move upwards (smaller Y)
    return create_synthetic_landmarks(center_x=0.5, shoulder_y=0.28, hip_y=0.58)

@pytest.fixture
def crouch_pose():
    # Downward motion: shoulder and hip Y move downwards (larger Y)
    return create_synthetic_landmarks(center_x=0.5, shoulder_y=0.43, hip_y=0.71, knee_angle_deg=135.0)

@pytest.fixture
def low_confidence_pose():
    return create_synthetic_landmarks(center_x=0.5, shoulder_y=0.35, hip_y=0.65, confidence=0.20)

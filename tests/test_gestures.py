"""
Unit tests for Gesture Engine.
Verifies MOVE_LEFT, MOVE_RIGHT, JUMP, CROUCH, Lean mode, and prioritization.
"""
import pytest
from app.landmarks import LandmarkProcessor
from app.calibration import BaselineData
from app.gesture_engine import GestureEngine, GestureType, ControlMode
from tests.conftest import create_synthetic_landmarks

@pytest.fixture
def baseline():
    # Standard baseline: body center at (0.50, 0.50), torso length = 0.30
    return BaselineData(
        body_center_x=0.50,
        shoulder_center_y=0.35,
        hip_center_y=0.65,
        torso_length=0.30,
        shoulder_width=0.20,
        step_threshold=0.16,
        jump_threshold=0.12,
        crouch_threshold=0.14,
        is_calibrated=True,
    )

def test_neutral_pose_no_gesture(baseline):
    processor = LandmarkProcessor(ema_alpha=1.0)
    engine = GestureEngine(mode=ControlMode.SIDE_STEP, mirrored=True)

    lms = create_synthetic_landmarks(center_x=0.50, shoulder_y=0.35, hip_y=0.65)
    metrics = processor.process(lms)
    gesture, debug = engine.evaluate(metrics, baseline)

    assert gesture == GestureType.NONE
    assert debug["is_neutral_x"] == 1.0
    assert debug["is_neutral_y"] == 1.0

def test_move_left_mirrored(baseline):
    # The left third of the displayed frame selects lane 0.
    processor = LandmarkProcessor(ema_alpha=1.0)
    engine = GestureEngine(mode=ControlMode.SIDE_STEP, mirrored=True)

    lms = create_synthetic_landmarks(center_x=0.25, shoulder_y=0.35, hip_y=0.65)
    metrics = processor.process(lms)
    gesture, debug = engine.evaluate(metrics, baseline)

    assert gesture == GestureType.MOVE_LEFT
    assert debug["target_lane"] == 0
    assert debug["disp_x"] > 0.16

def test_move_right_mirrored(baseline):
    # The right third selects lane 2.
    processor = LandmarkProcessor(ema_alpha=1.0)
    engine = GestureEngine(mode=ControlMode.SIDE_STEP, mirrored=True)

    lms = create_synthetic_landmarks(center_x=0.75, shoulder_y=0.35, hip_y=0.65)
    metrics = processor.process(lms)
    gesture, debug = engine.evaluate(metrics, baseline)

    assert gesture == GestureType.MOVE_RIGHT
    assert debug["target_lane"] == 2
    assert debug["disp_x"] < -0.16

def test_jump_detection(baseline):
    # Jumping upward: shoulder moves from 0.35 to 0.28 (upward displacement = 0.07 / 0.30 = 0.23 > 0.12)
    processor = LandmarkProcessor(ema_alpha=1.0)
    engine = GestureEngine()

    lms = create_synthetic_landmarks(center_x=0.50, shoulder_y=0.28, hip_y=0.58)
    metrics = processor.process(lms)
    gesture, debug = engine.evaluate(metrics, baseline)

    assert gesture == GestureType.JUMP
    assert debug["disp_y_up"] > 0.12

def test_crouch_detection(baseline):
    # Crouching: shoulder moves from 0.35 to 0.42 (downward displacement = 0.07 / 0.30 = 0.23 > 0.14)
    processor = LandmarkProcessor(ema_alpha=1.0)
    engine = GestureEngine()

    lms = create_synthetic_landmarks(center_x=0.50, shoulder_y=0.42, hip_y=0.70)
    metrics = processor.process(lms)
    gesture, debug = engine.evaluate(metrics, baseline)

    assert gesture == GestureType.CROUCH
    assert debug["disp_y_down"] > 0.14

def test_lean_mode(baseline):
    processor = LandmarkProcessor(ema_alpha=1.0)
    engine = GestureEngine(mode=ControlMode.LEAN, mirrored=True)

    # Lean left: shoulders tilt towards image left (- lean_offset_x)
    lms_lean_left = create_synthetic_landmarks(center_x=0.50, lean_offset_x=-0.08)
    m_left = processor.process(lms_lean_left)
    g_left, _ = engine.evaluate(m_left, baseline)
    assert g_left == GestureType.MOVE_LEFT

    # Lean right: shoulders tilt towards image right (+ lean_offset_x)
    lms_lean_right = create_synthetic_landmarks(center_x=0.50, lean_offset_x=0.08)
    m_right = processor.process(lms_lean_right)
    g_right, _ = engine.evaluate(m_right, baseline)
    assert g_right == GestureType.MOVE_RIGHT

def test_priority_crouch_over_lateral(baseline):
    """If user crouches while slightly stepping sideways, CROUCH must take priority!"""
    processor = LandmarkProcessor(ema_alpha=1.0)
    engine = GestureEngine(mode=ControlMode.SIDE_STEP, mirrored=True)

    # Crouching down AND slightly to the left
    lms = create_synthetic_landmarks(center_x=0.25, shoulder_y=0.42, hip_y=0.70)
    metrics = processor.process(lms)
    gesture, _ = engine.evaluate(metrics, baseline)

    assert gesture == GestureType.CROUCH

def test_low_confidence_suppression(baseline):
    processor = LandmarkProcessor(ema_alpha=1.0)
    engine = GestureEngine()

    lms = create_synthetic_landmarks(center_x=0.35, confidence=0.20)
    metrics = processor.process(lms)
    gesture, _ = engine.evaluate(metrics, baseline)

    assert not metrics.is_valid
    assert gesture == GestureType.NONE


@pytest.mark.parametrize("sensitivity", [0.5, 1.0, 2.5])
def test_manual_horizontal_zones_remain_fixed_despite_calibration_position_or_vertical_sensitivity(baseline, sensitivity):
    baseline.body_center_x = 0.2
    engine = GestureEngine(sensitivity=sensitivity, auto_calibrate_lanes=False)
    processor = LandmarkProcessor(ema_alpha=1)
    for x, lane in ((0.1, 0), (0.4, 1), (0.6, 1), (0.9, 2)):
        _, debug = engine.evaluate(processor.process(create_synthetic_landmarks(center_x=x)), baseline)
        assert debug["target_lane"] == lane


@pytest.mark.parametrize("x,expected_lane", [(0.41, 0), (0.43, 1), (0.5, 1), (0.57, 1), (0.59, 2)])
def test_small_side_steps_cross_calibrated_shoulder_boundaries(baseline, x, expected_lane):
    engine = GestureEngine()
    metrics = LandmarkProcessor(ema_alpha=1).process(create_synthetic_landmarks(center_x=x))
    _, debug = engine.evaluate(metrics, baseline)
    assert debug["target_lane"] == expected_lane
    assert engine.get_zones(baseline).left_boundary == pytest.approx(0.42)
    assert engine.get_zones(baseline).right_boundary == pytest.approx(0.58)


def test_configured_lane_spacing_changes_detection_and_overlay_geometry_together(baseline):
    engine = GestureEngine(lane_center_half_width=0.05, auto_calibrate_lanes=False)
    zones = engine.get_zones(baseline)
    assert zones.left_boundary == 0.45
    assert zones.right_boundary == 0.55
    metrics = LandmarkProcessor(ema_alpha=1).process(create_synthetic_landmarks(center_x=0.44))
    assert engine.evaluate(metrics, baseline)[1]["target_lane"] == 0


@pytest.mark.parametrize("sensitivity", [0.5, 1.0, 2.5])
def test_horizontal_lines_exactly_match_body_center_trigger_thresholds(baseline, sensitivity):
    engine = GestureEngine(sensitivity=sensitivity)
    zones = engine.get_zones(baseline)
    processor = LandmarkProcessor(ema_alpha=1)
    for y, expected in ((zones.jump_y - 0.001, GestureType.JUMP),
                        (zones.jump_y + 0.001, GestureType.NONE),
                        (zones.crouch_y - 0.001, GestureType.NONE),
                        (zones.crouch_y + 0.001, GestureType.CROUCH)):
        offset = y - 0.5
        metrics = processor.process(create_synthetic_landmarks(
            shoulder_y=0.35 + offset, hip_y=0.65 + offset))
        assert engine.evaluate(metrics, baseline)[0] == expected

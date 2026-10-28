"""
Unit tests for Calibration System.
Verifies countdown progression, median baseline derivation, adaptive thresholds
across different body proportions, and reset/recalibration.
"""
import pytest
from app.landmarks import LandmarkProcessor
from app.calibration import CalibrationManager, CalibrationState
from tests.conftest import create_synthetic_landmarks

def test_calibration_workflow():
    processor = LandmarkProcessor(ema_alpha=1.0) # no lag for unit tests
    calib = CalibrationManager(countdown_s=1.0, sample_count=10)

    # 1. Start calibration
    calib.start_calibration()
    assert calib.state == CalibrationState.COUNTDOWN
    assert not calib.is_calibrated()

    # 2. Advance countdown
    neutral_lms = create_synthetic_landmarks(center_x=0.50, shoulder_y=0.35, hip_y=0.65)
    metrics = processor.process(neutral_lms, timestamp_s=0.0)

    state, msg, prog = calib.update(metrics, dt=0.5)
    assert state == CalibrationState.COUNTDOWN
    assert 0.0 < prog < 1.0

    # Advance past countdown duration -> enters COLLECTING
    state, msg, prog = calib.update(metrics, dt=0.6)
    assert state == CalibrationState.COLLECTING

    # 3. Supply 10 frames
    for i in range(10):
        # Slightly vary coordinate to test median
        dx = 0.002 * (i % 3 - 1)
        lms = create_synthetic_landmarks(center_x=0.50 + dx, shoulder_y=0.35, hip_y=0.65)
        m = processor.process(lms, timestamp_s=1.0 + i * 0.03)
        state, msg, prog = calib.update(m, dt=0.03)

    assert state == CalibrationState.COMPLETED
    assert calib.is_calibrated()
    
    baseline = calib.get_baseline()
    assert baseline is not None
    assert abs(baseline.body_center_x - 0.50) < 0.01
    assert abs(baseline.shoulder_center_y - 0.35) < 0.01
    assert abs(baseline.hip_center_y - 0.65) < 0.01
    assert abs(baseline.torso_length - 0.30) < 0.01
    assert baseline.step_threshold > 0.0
    assert baseline.jump_threshold > 0.0
    assert baseline.crouch_threshold > 0.0

def test_calibration_different_body_proportions():
    """Verify adaptive baseline adapts to tall vs short players."""
    processor = LandmarkProcessor(ema_alpha=1.0)

    # Tall player (torso = 0.40)
    calib_tall = CalibrationManager(countdown_s=0.1, sample_count=5)
    calib_tall.start_calibration()
    calib_tall.update(processor.process(create_synthetic_landmarks(shoulder_y=0.25, hip_y=0.65)), dt=0.2)
    for _ in range(5):
        calib_tall.update(processor.process(create_synthetic_landmarks(shoulder_y=0.25, hip_y=0.65)), dt=0.05)
    base_tall = calib_tall.get_baseline()

    # Short player (torso = 0.20)
    calib_short = CalibrationManager(countdown_s=0.1, sample_count=5)
    calib_short.start_calibration()
    calib_short.update(processor.process(create_synthetic_landmarks(shoulder_y=0.40, hip_y=0.60)), dt=0.2)
    for _ in range(5):
        calib_short.update(processor.process(create_synthetic_landmarks(shoulder_y=0.40, hip_y=0.60)), dt=0.05)
    base_short = calib_short.get_baseline()

    assert base_tall.torso_length > base_short.torso_length
    assert abs(base_tall.torso_length - 0.40) < 0.02
    assert abs(base_short.torso_length - 0.20) < 0.02

def test_calibration_reset():
    calib = CalibrationManager(countdown_s=0.1, sample_count=2)
    calib.start_calibration()
    calib.reset()
    assert calib.state == CalibrationState.IDLE
    assert not calib.is_calibrated()
    assert calib.get_baseline() is None


def test_configured_vertical_thresholds_survive_calibration():
    calib = CalibrationManager(countdown_s=0.1, sample_count=2,
                               jump_threshold=0.2, crouch_threshold=0.25)
    metrics = LandmarkProcessor(ema_alpha=1).process(create_synthetic_landmarks())
    calib.start_calibration()
    for _ in range(3):
        calib.update(metrics, dt=0.1)
    assert calib.is_calibrated()
    assert calib.baseline.jump_threshold == 0.2
    assert calib.baseline.crouch_threshold == 0.25

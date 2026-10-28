"""Calibration adapts horizontal lanes to shoulder size and standing position."""
from dataclasses import replace

import pytest

from app.calibration import BaselineData, CalibrationManager, CalibrationState
from app.control_zones import ControlZones
from app.gesture_engine import GestureEngine, GestureType
from app.landmarks import LandmarkProcessor
from tests.conftest import create_synthetic_landmarks


def calibrate(x=0.5, width=0.2):
    manager = CalibrationManager(countdown_s=0.1, sample_count=5)
    processor = LandmarkProcessor(ema_alpha=1)
    manager.start_calibration()
    for _ in range(6):
        manager.update(processor.process(create_synthetic_landmarks(center_x=x, shoulder_width=width)), 0.1)
    assert manager.state == CalibrationState.COMPLETED
    return manager.get_baseline()


@pytest.mark.parametrize("x,width", [(0.43, 0.12), (0.5, 0.2), (0.57, 0.3)])
def test_different_players_have_centered_personal_boundaries(x, width):
    baseline = calibrate(x, width)
    zones = ControlZones.from_baseline(baseline)
    assert baseline.shoulder_left_x == pytest.approx(x - width / 2)
    assert baseline.shoulder_right_x == pytest.approx(x + width / 2)
    assert zones.left_boundary == pytest.approx(x - width * 0.4)
    assert zones.right_boundary == pytest.approx(x + width * 0.4)
    assert zones.lane_at(x) == 1


def test_smaller_shoulders_require_smaller_movements():
    narrow = ControlZones.from_baseline(calibrate(width=0.12))
    wide = ControlZones.from_baseline(calibrate(width=0.3))
    assert narrow.lane_at(0.43) == 0
    assert wide.lane_at(0.43) == 1


def test_calibration_uses_median_shoulder_positions_despite_outlier():
    manager = CalibrationManager(countdown_s=0.1, sample_count=5)
    processor = LandmarkProcessor(ema_alpha=1)
    manager.start_calibration()
    manager.update(processor.process(create_synthetic_landmarks()), 0.1)
    for x, width in ((0.5, 0.2), (0.501, 0.202), (0.9, 0.1), (0.499, 0.198), (0.5, 0.2)):
        manager.update(processor.process(create_synthetic_landmarks(center_x=x, shoulder_width=width)), 0.1)
    assert manager.baseline.shoulder_left_x == pytest.approx(0.4)
    assert manager.baseline.shoulder_right_x == pytest.approx(0.6)


def test_horizontal_span_is_not_inflated_by_vertical_shoulder_separation():
    baseline = BaselineData(0.5, 0.35, 0.65, 0.3, 0.3, is_calibrated=True,
                            shoulder_left_x=0.44, shoulder_right_x=0.56)
    zones = ControlZones.from_baseline(baseline)
    assert zones.right_boundary - zones.left_boundary == pytest.approx(0.12 * 0.8)


def test_calibration_pauses_when_a_shoulder_is_obscured():
    manager = CalibrationManager(countdown_s=0.1, sample_count=2)
    points = create_synthetic_landmarks()
    points[11].visibility = 0.1
    metrics = LandmarkProcessor(ema_alpha=1).process(points)
    assert metrics.is_valid  # Averaged torso confidence alone is insufficient.
    manager.start_calibration()
    manager.update(metrics, 0.2)
    assert manager.state == CalibrationState.COUNTDOWN
    assert not manager.samples
    assert "vai" in manager.status_message


def test_playing_does_not_move_the_calibrated_lines():
    baseline = calibrate(x=0.43, width=0.16)
    engine = GestureEngine()
    zones = engine.get_zones(baseline)
    moving = LandmarkProcessor(ema_alpha=1).process(create_synthetic_landmarks(center_x=0.7, shoulder_width=0.25))
    assert engine.evaluate(moving, baseline)[0] == GestureType.MOVE_RIGHT
    assert engine.get_zones(baseline) == zones


def test_preview_remains_fixed_until_calibration_finishes():
    baseline = calibrate(x=0.43, width=0.16)
    preview = ControlZones.from_baseline(replace(baseline, is_calibrated=False))
    assert preview.left_boundary == 0.4
    assert preview.right_boundary == 0.6


@pytest.mark.parametrize("center,width", [(0.02, 0.02), (0.98, 0.02), (0.5, 0.8)])
def test_extreme_measurements_keep_lanes_inside_the_image(center, width):
    baseline = BaselineData(center, 0.35, 0.65, 0.3, width, is_calibrated=True)
    zones = ControlZones.from_baseline(baseline)
    assert 0 <= zones.left_boundary < zones.right_boundary <= 1
    assert zones.lane_at(center) == 1

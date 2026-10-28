"""Zone coordinates refer to the visible camera frame, with either mirror setting."""
import pytest
from app.landmarks import LandmarkProcessor
from app.calibration import BaselineData
from app.gesture_engine import GestureEngine, GestureType
from tests.conftest import create_synthetic_landmarks


@pytest.mark.parametrize("mirrored", [True, False])
@pytest.mark.parametrize("x,lane,gesture", [
    (0.25, 0, GestureType.MOVE_LEFT),
    (0.45, 1, GestureType.NONE),
    (0.50, 1, GestureType.NONE),
    (0.55, 1, GestureType.NONE),
    (0.75, 2, GestureType.MOVE_RIGHT),
])
def test_visible_zone_matches_lane_without_double_mirroring(mirrored, x, lane, gesture):
    baseline = BaselineData(0.5, 0.35, 0.65, 0.3, 0.2, is_calibrated=True)
    engine = GestureEngine(mirrored=mirrored)
    metrics = LandmarkProcessor(ema_alpha=1).process(create_synthetic_landmarks(center_x=x))
    detected, debug = engine.evaluate(metrics, baseline)
    assert detected == gesture
    assert debug["target_lane"] == lane

"""Behavioral checks for three absolute lanes and vertical line crossings."""
import pytest

from app.gesture_engine import GestureType
from app.gesture_state_machine import GestureStateMachine, MachineState


def tick(sm, lane=1, raw=GestureType.NONE, neutral_y=True, dt=0.04, **kwargs):
    return sm.update(raw, {"target_lane": float(lane), "is_neutral_y": float(neutral_y)},
                     kwargs.pop("is_player_tracked", True),
                     kwargs.pop("is_calibrated", True), dt, **kwargs)


def settle(sm, lane, frames=15, **kwargs):
    return [event for _ in range(frames) if (event := tick(sm, lane, **kwargs))]


def test_center_never_sends_a_key_when_game_is_already_centered():
    sm = GestureStateMachine()
    assert settle(sm, 1) == []
    assert sm.current_lane == 1
    assert sm.current_state == MachineState.NEUTRAL


def test_confirmation_filters_brief_zone_crossing():
    sm = GestureStateMachine(confirmation_time_ms=70)
    assert tick(sm, 0, dt=0.03) is None
    assert tick(sm, 1, dt=0.03) is None
    assert settle(sm, 1) == []
    assert sm.current_lane == 1
    assert sm.accepted_actions_count == 0


def test_hold_left_sends_once_and_stays_in_left_lane():
    sm = GestureStateMachine()
    assert settle(sm, 0, frames=50) == [GestureType.MOVE_LEFT]
    assert sm.current_lane == 0


def test_return_to_center_moves_character_to_center():
    sm = GestureStateMachine()
    assert settle(sm, 0) == [GestureType.MOVE_LEFT]
    # This intentionally replaces the former "neutral never sends right" behavior.
    assert settle(sm, 1) == [GestureType.MOVE_RIGHT]
    assert sm.current_lane == 1


@pytest.mark.parametrize("first,last,direction", [
    (0, 2, GestureType.MOVE_RIGHT), (2, 0, GestureType.MOVE_LEFT),
])
def test_direct_outer_zone_transition_sends_two_keys_without_center_pose(first, last, direction):
    sm = GestureStateMachine()
    settle(sm, first)
    assert settle(sm, last) == [direction, direction]
    assert sm.current_lane == last
    assert settle(sm, last) == []


def test_reversing_mid_transition_cancels_the_old_destination():
    sm = GestureStateMachine(confirmation_time_ms=30, horizontal_cooldown_ms=120)
    settle(sm, 0)
    assert tick(sm, 2) == GestureType.MOVE_RIGHT
    assert sm.current_lane == 1
    assert tick(sm, 0) is None
    assert settle(sm, 0) == [GestureType.MOVE_LEFT]
    assert sm.current_lane == 0


def test_rejected_keyboard_dispatch_does_not_advance_lane_or_action_count():
    sm = GestureStateMachine(confirmation_time_ms=30)
    assert tick(sm, 0, dispatch=lambda gesture: False) is None
    assert sm.current_lane == 1
    assert sm.accepted_actions_count == 0
    sent = []
    assert tick(sm, 0, dispatch=lambda gesture: sent.append(gesture) or True) == GestureType.MOVE_LEFT
    assert sent == [GestureType.MOVE_LEFT]
    assert sm.current_lane == 0


@pytest.mark.parametrize("gate,state", [
    ({"is_player_tracked": False}, MachineState.NO_PERSON),
    ({"is_calibrated": False}, MachineState.CALIBRATING),
    ({"can_dispatch": False}, MachineState.PAUSED),
])
def test_tracking_calibration_and_focus_clear_pending_destination(gate, state):
    sm = GestureStateMachine(confirmation_time_ms=30)
    settle(sm, 0)
    assert tick(sm, 2) == GestureType.MOVE_RIGHT
    for _ in range(10):
        assert tick(sm, 2, **gate) is None
    assert sm.current_state == state
    assert sm.target_lane is None
    assert sm.current_lane == 1


@pytest.mark.parametrize("gesture", [GestureType.JUMP, GestureType.CROUCH])
def test_vertical_action_fires_once_until_body_returns_between_lines(gesture):
    sm = GestureStateMachine(confirmation_time_ms=30)
    assert tick(sm, raw=gesture, neutral_y=False) == gesture
    assert settle(sm, 1, frames=30, raw=gesture, neutral_y=False) == []
    tick(sm, neutral_y=True)
    assert tick(sm, raw=gesture, neutral_y=False) == gesture


def test_jump_and_lane_change_are_both_delivered_without_horizontal_reset():
    sm = GestureStateMachine(confirmation_time_ms=30)
    assert tick(sm, 0, raw=GestureType.JUMP, neutral_y=False) == GestureType.JUMP
    assert tick(sm, 0, raw=GestureType.JUMP, neutral_y=False) == GestureType.MOVE_LEFT
    assert sm.current_lane == 0


def test_pause_preserves_lane_and_new_game_reset_restores_center():
    sm = GestureStateMachine()
    settle(sm, 0)
    sm.pause()
    assert settle(sm, 2) == []
    assert sm.current_lane == 0
    sm.resume()
    assert settle(sm, 2) == [GestureType.MOVE_RIGHT, GestureType.MOVE_RIGHT]
    sm.reset()
    assert sm.current_lane == 1
    assert sm.target_lane is None

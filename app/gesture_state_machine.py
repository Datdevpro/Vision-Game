"""Confirm target zones, follow three game lanes, and debounce vertical actions."""
from enum import Enum
from typing import Callable, Dict, Optional

from app.gesture_engine import GestureType


class MachineState(Enum):
    NO_PERSON = "NO_PERSON"
    CALIBRATING = "CALIBRATING"
    READY = "READY"
    NEUTRAL = "NEUTRAL"
    MOVING_LEFT = "MOVING_LEFT"
    MOVING_RIGHT = "MOVING_RIGHT"
    JUMPING = "JUMPING"
    CROUCHING = "CROUCHING"
    COOLDOWN = "COOLDOWN"
    PAUSED = "PAUSED"


class GestureStateMachine:
    def __init__(self, confirmation_time_ms: float = 70.0, horizontal_cooldown_ms: float = 120.0,
                 jump_cooldown_ms: float = 400.0, crouch_cooldown_ms: float = 350.0):
        self.confirmation_time_s = confirmation_time_ms / 1000
        self.horizontal_cooldown_s = horizontal_cooldown_ms / 1000
        self.jump_cooldown_s = jump_cooldown_ms / 1000
        self.crouch_cooldown_s = crouch_cooldown_ms / 1000
        self.reset()

    def reset(self):
        """A new game starts in the center lane; the browser game is not observed."""
        self.current_lane = 1
        self.current_state = MachineState.NO_PERSON
        self.is_paused = False
        self.is_jump_armed = self.is_crouch_armed = True
        self.last_dispatched_gesture = GestureType.NONE
        self.accepted_actions_count = self.debounced_actions_count = 0
        self._horizontal_wait = 0.0
        self.cooldown_timers = {GestureType.JUMP: 0.0, GestureType.CROUCH: 0.0}
        self.clear_candidates()

    def clear_candidates(self):
        self._lane_candidate = None
        self._lane_confirmation = 0.0
        self.target_lane = None
        self.candidate_gesture = GestureType.NONE
        self.confirmation_timer = 0.0

    def pause(self):
        self.is_paused = True
        self.current_state = MachineState.PAUSED
        self.clear_candidates()

    def resume(self):
        self.is_paused = False
        self.current_state = MachineState.READY
        self.clear_candidates()

    def set_timing(self, confirmation_time_ms=None, horizontal_cooldown_ms=None,
                   jump_cooldown_ms=None, crouch_cooldown_ms=None):
        for name, value in (("confirmation_time_s", confirmation_time_ms),
                            ("horizontal_cooldown_s", horizontal_cooldown_ms),
                            ("jump_cooldown_s", jump_cooldown_ms),
                            ("crouch_cooldown_s", crouch_cooldown_ms)):
            if value is not None:
                setattr(self, name, max(0.0, value / 1000))

    def update(self, raw_gesture: GestureType, debug_signals: Dict[str, float],
               is_player_tracked: bool, is_calibrated: bool, dt: float,
               can_dispatch: bool = True,
               dispatch: Optional[Callable[[GestureType], bool]] = None) -> Optional[GestureType]:
        dt = max(0.0, dt)
        self._horizontal_wait = max(0.0, self._horizontal_wait - dt)
        for gesture in self.cooldown_timers:
            self.cooldown_timers[gesture] = max(0.0, self.cooldown_timers[gesture] - dt)

        blocked = (MachineState.NO_PERSON if not is_player_tracked else
                   MachineState.CALIBRATING if not is_calibrated else
                   MachineState.PAUSED if self.is_paused or not can_dispatch else None)
        if blocked is not None:
            self.current_state = blocked
            self.clear_candidates()
            return None

        observed_lane = int(debug_signals["target_lane"])
        if observed_lane not in (0, 1, 2):
            self.clear_candidates()
            return None
        if observed_lane != self._lane_candidate:
            self._lane_candidate = observed_lane
            self._lane_confirmation = dt
            self.target_lane = None  # Cancel the previous destination immediately.
        else:
            self._lane_confirmation += dt
        if self._lane_confirmation >= self.confirmation_time_s:
            self.target_lane = observed_lane

        if debug_signals.get("is_neutral_y", 0.0) > 0.5:
            self.is_jump_armed = self.is_crouch_armed = True

        vertical = raw_gesture if raw_gesture in (GestureType.JUMP, GestureType.CROUCH) else GestureType.NONE
        armed = self.is_jump_armed if vertical == GestureType.JUMP else self.is_crouch_armed
        if vertical != GestureType.NONE and armed:
            if self.candidate_gesture != vertical:
                self.candidate_gesture = vertical
                self.confirmation_timer = dt
            else:
                self.confirmation_timer += dt
            if self.confirmation_timer >= self.confirmation_time_s and self.cooldown_timers[vertical] <= 0:
                return self._emit(vertical, dispatch)
            return None
        self.candidate_gesture = GestureType.NONE
        self.confirmation_timer = 0.0

        if self.target_lane is not None and self.target_lane != self.current_lane:
            if self._horizontal_wait <= 0:
                direction = GestureType.MOVE_LEFT if self.target_lane < self.current_lane else GestureType.MOVE_RIGHT
                return self._emit(direction, dispatch)
            self.debounced_actions_count += 1
        elif vertical == GestureType.NONE:
            self.current_state = MachineState.NEUTRAL if self.current_lane == 1 else MachineState.READY
        return None

    def _emit(self, gesture, dispatch):
        # Advance the estimated lane only when the keyboard accepts the key.
        if dispatch is not None and not dispatch(gesture):
            return None
        self.accepted_actions_count += 1
        self.last_dispatched_gesture = gesture
        if gesture in (GestureType.MOVE_LEFT, GestureType.MOVE_RIGHT):
            self.current_lane += -1 if gesture == GestureType.MOVE_LEFT else 1
            self._horizontal_wait = self.horizontal_cooldown_s
            self.current_state = MachineState.MOVING_LEFT if gesture == GestureType.MOVE_LEFT else MachineState.MOVING_RIGHT
        else:
            self.candidate_gesture = GestureType.NONE
            self.confirmation_timer = 0.0
            if gesture == GestureType.JUMP:
                self.is_jump_armed = False
                self.cooldown_timers[gesture] = self.jump_cooldown_s
                self.current_state = MachineState.JUMPING
            else:
                self.is_crouch_armed = False
                self.cooldown_timers[gesture] = self.crouch_cooldown_s
                self.current_state = MachineState.CROUCHING
        return gesture

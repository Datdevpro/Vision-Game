"""
Unit tests for Keyboard Controller and Key Mapping.
Verifies event mapping, test mode, focus suppression, and emergency stop.
"""
import pytest
import threading
import time
from types import SimpleNamespace
from app.gesture_engine import GestureType
from app.keyboard_controller import KeyboardController
from app.window_manager import WindowManager


def test_busy_dispatch_has_no_key_queue_and_emergency_stop_cancels_pulse(monkeypatch):
    from app import keyboard_controller as module
    events = []
    pressed = threading.Event()

    def key_event(vk, scan, flags, extra):
        events.append((vk, flags))
        if flags == 0:
            pressed.set()

    monkeypatch.setattr(module, "user32", SimpleNamespace(keybd_event=key_event))
    monkeypatch.setattr(module, "HAS_PYAUTOGUI", False)
    ctrl = KeyboardController(use_send_input=True, pulse_duration_ms=500)
    try:
        assert ctrl.dispatch(GestureType.MOVE_LEFT)
        assert pressed.wait(1)
        assert not ctrl.dispatch(GestureType.MOVE_RIGHT)
        ctrl.emergency_stop()
        deadline = time.perf_counter() + 1
        while ctrl._dispatch_lock.locked() and time.perf_counter() < deadline:
            time.sleep(0.002)
        assert not ctrl._dispatch_lock.locked()
        assert not ctrl.dispatch(GestureType.MOVE_RIGHT)
        assert [vk for vk, flags in events if flags == 0] == [module.VK_LEFT]
        assert (module.VK_LEFT, module.KEYEVENTF_KEYUP) in events
        ctrl.resume()
        ctrl.set_test_mode(True)
        assert ctrl.dispatch(GestureType.MOVE_RIGHT)
    finally:
        ctrl.emergency_stop()

class MockWindowManager(WindowManager):
    def __init__(self, focused: bool = True):
        super().__init__(require_focus=True)
        self._focused = focused

    def is_game_focused(self) -> bool:
        if not self.require_focus:
            return True
        return self._focused

def test_key_mapping():
    keys_sent = []
    ctrl = KeyboardController(
        test_mode=True,
        on_key_sent=lambda k: keys_sent.append(k),
    )

    assert ctrl.dispatch(GestureType.MOVE_LEFT) is True
    assert ctrl.last_key_sent == "LEFT"

    assert ctrl.dispatch(GestureType.MOVE_RIGHT) is True
    assert ctrl.last_key_sent == "RIGHT"

    assert ctrl.dispatch(GestureType.JUMP) is True
    assert ctrl.last_key_sent == "UP"

    assert ctrl.dispatch(GestureType.CROUCH) is True
    assert ctrl.last_key_sent == "DOWN"

    assert keys_sent == ["LEFT", "RIGHT", "UP", "DOWN"]

def test_focus_suppression():
    """When target game is not focused, key event must be blocked."""
    mock_wm = MockWindowManager(focused=False)
    ctrl = KeyboardController(window_manager=mock_wm, test_mode=False)

    success = ctrl.dispatch(GestureType.MOVE_LEFT)
    assert success is False

    # When focused, dispatch succeeds
    mock_wm._focused = True
    success_focused = ctrl.dispatch(GestureType.MOVE_LEFT)
    assert success_focused is True

def test_emergency_stop():
    ctrl = KeyboardController(test_mode=True)
    ctrl.dispatch(GestureType.JUMP)
    assert ctrl.last_key_sent == "UP"

    ctrl.emergency_stop()
    assert ctrl.last_key_sent == "STOPPED"

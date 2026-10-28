"""
Keyboard event dispatcher for Subway Surfers AI Body Controller.
Supports asynchronous non-blocking pulses, PyAutoGUI, Windows direct keybd_event
for 100% reliable canvas/WebGL game input, Test Mode, and Emergency Stop.
"""
import sys
import time
import threading
from typing import Dict, Optional, Callable
from app.gesture_engine import GestureType
from app.window_manager import WindowManager

try:
    import pyautogui
    pyautogui.PAUSE = 0.001
    pyautogui.FAILSAFE = False
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

# Windows direct virtual key codes
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
KEYEVENTF_KEYUP = 0x0002

if sys.platform == "win32":
    import ctypes
    user32 = ctypes.windll.user32
else:
    user32 = None

class KeyboardController:
    """
    Translates discrete GestureType events into rapid, non-blocking
    keyboard pulses dispatched to the game.
    """
    def __init__(
        self,
        window_manager: WindowManager = None,
        pulse_duration_ms: float = 65.0,
        test_mode: bool = False,
        use_send_input: bool = True,
        on_key_sent: Optional[Callable[[str], None]] = None,
    ):
        self.window_manager = window_manager
        self.pulse_duration_s = pulse_duration_ms / 1000.0
        self.test_mode = test_mode
        self.use_send_input = use_send_input and (user32 is not None)
        self.on_key_sent = on_key_sent

        self.key_map: Dict[GestureType, str] = {
            GestureType.MOVE_LEFT: "left",
            GestureType.MOVE_RIGHT: "right",
            GestureType.JUMP: "up",
            GestureType.CROUCH: "down",
        }

        self.win_vk_map: Dict[str, int] = {
            "left": VK_LEFT,
            "right": VK_RIGHT,
            "up": VK_UP,
            "down": VK_DOWN,
        }

        self.last_key_sent: str = "None"
        self._lock = threading.Lock()
        self._dispatch_lock = threading.Lock()
        self._pulse_cancel = threading.Event()
        self._next_dispatch_at = 0.0
        self._stopped = False

    def resume(self):
        with self._lock:
            self._stopped = False

    def set_test_mode(self, enabled: bool):
        self.test_mode = enabled

    def set_pulse_duration(self, duration_ms: float):
        self.pulse_duration_s = max(0.02, duration_ms / 1000.0)

    def dispatch(self, gesture: GestureType) -> bool:
        """
        Dispatches keyboard action asynchronously without blocking caller.
        Returns True if action was accepted for dispatch, False otherwise.
        """
        if gesture not in self.key_map:
            return False
        if self._stopped:
            return False

        if not self.test_mode and self.window_manager and not self.window_manager.is_game_focused():
            return False
        key_name = self.key_map[gesture]
        if not self.test_mode:
            # Reject busy input instead of building a delayed queue of key presses.
            if not self._dispatch_lock.acquire(blocking=False):
                return False
            if time.perf_counter() < self._next_dispatch_at:
                self._dispatch_lock.release()
                return False
            with self._lock:
                if self._stopped:
                    self._dispatch_lock.release()
                    return False
                self._pulse_cancel = threading.Event()

        self.last_key_sent = key_name.upper()
        if self.on_key_sent:
            try:
                self.on_key_sent(self.last_key_sent)
            except Exception:
                pass
        if self.test_mode:
            return True

        # Asynchronous non-blocking dispatch in background thread
        threading.Thread(
            target=self._send_key_pulse,
            args=(key_name, self.pulse_duration_s, self._pulse_cancel),
            daemon=True,
        ).start()
        return True

    def _send_key_pulse(self, key_name: str, duration_s: float, cancelled: threading.Event):
        """Press key, hold briefly, then release."""
        pressed = False
        try:
            with self._lock:
                if cancelled.is_set():
                    return
                if self.use_send_input:
                    user32.keybd_event(self.win_vk_map[key_name], 0, 0, 0)
                elif HAS_PYAUTOGUI:
                    pyautogui.keyDown(key_name)
                pressed = True
            cancelled.wait(duration_s)
        finally:
            try:
                if pressed:
                    with self._lock:
                        if self.use_send_input:
                            user32.keybd_event(self.win_vk_map[key_name], 0, KEYEVENTF_KEYUP, 0)
                        elif HAS_PYAUTOGUI:
                            pyautogui.keyUp(key_name)
            finally:
                self._next_dispatch_at = time.perf_counter() + 0.025
                self._dispatch_lock.release()

    def emergency_stop(self):
        """Release all possible arrow keys immediately."""
        with self._lock:
            self._stopped = True
            self._pulse_cancel.set()
            self._release_keys()

    def _release_keys(self):
        self.last_key_sent = "STOPPED"
        if self.use_send_input:
            for vk in self.win_vk_map.values():
                try:
                    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
                except Exception:
                    pass
        if HAS_PYAUTOGUI:
            for key in ["left", "right", "up", "down", "space", "esc"]:
                try:
                    pyautogui.keyUp(key)
                except Exception:
                    pass

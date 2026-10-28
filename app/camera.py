"""
Camera capture module for Subway Surfers AI Body Controller.
Features dedicated capture thread, zero-lag single-frame buffer,
DirectShow on Windows, camera enumeration, mirroring, and synthetic Mock Camera mode.
"""
import sys
import time
import math
import threading
from collections import deque
from typing import Optional, Tuple, List
import numpy as np
import cv2

class CameraCapture:
    """
    High-performance webcam capture thread with zero-backlog buffer.
    Ensures AI and UI always receive the latest frame captured.
    """
    def __init__(
        self,
        camera_index: int = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 60,
        mirrored: bool = True,
        is_mock: bool = False,
    ):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        self.mirrored = mirrored
        self.is_mock = is_mock

        self.cap: Optional[cv2.VideoCapture] = None
        self.running: bool = False
        self.thread: Optional[threading.Thread] = None
        
        self._lock = threading.Lock()
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_timestamp: float = 0.0
        self.startup_error: Optional[str] = None
        self.first_frame_ms: Optional[float] = None
        self.reported_fps: float = 0.0
        self._frame_times = deque(maxlen=120)
        self._stop_event = threading.Event()
        self._started_at = 0.0

        # Mock animation state
        self._mock_step = 0

    def start(self) -> bool:
        if self.running:
            return True
        if self.is_alive():
            return False

        with self._lock:
            self.latest_frame = None
            self.latest_timestamp = 0.0
            self._frame_times.clear()
        self.reported_fps = float(self.fps) if self.is_mock else 0.0
        self.startup_error = None
        self.first_frame_ms = None
        self._started_at = time.perf_counter()
        self._stop_event.clear()
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return True

    def is_alive(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def _open_device(self):
        if not self.is_mock:
            # Opening and configuring drivers may block; only do this on the capture thread.
            backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
            self.cap = cv2.VideoCapture(self.camera_index, backend)
            if self._stop_event.is_set():
                return
            if not self.cap.isOpened():
                raise RuntimeError(f"Không mở được Webcam {self.camera_index}. Kiểm tra quyền camera hoặc ứng dụng khác đang sử dụng.")
            else:
                # Crucial for Windows USB webcams: set MJPG codec to unlock full 30-60 FPS at 720p/1080p
                if sys.platform == "win32":
                    self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                self.cap.set(cv2.CAP_PROP_FPS, self.fps)
                self.reported_fps = max(0.0, self.cap.get(cv2.CAP_PROP_FPS))
                # Read actual dimensions
                actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if actual_w > 0 and actual_h > 0:
                    self.width = actual_w
                    self.height = actual_h
                print(f"[Camera] Requested: {self.fps} FPS | Driver: {self.reported_fps:g} FPS | {self.width}x{self.height}")

    def stop(self, wait: bool = True):
        self._stop_event.set()
        self.running = False
        if wait and self.is_alive():
            self.thread.join(timeout=1.0)
        # The capture thread owns the device, including release(). Never release during read/open.

    def _run(self):
        try:
            self._open_device()
            self._capture_loop()
        except Exception as exc:
            if not self._stop_event.is_set():
                self.startup_error = str(exc)
                print(f"[Camera] {exc}")
        finally:
            try:
                if self.cap is not None:
                    self.cap.release()
            finally:
                self.cap = None
                self.running = False

    def _capture_loop(self):
        target_delay = 1.0 / max(10, self.fps)
        while not self._stop_event.is_set():
            frame = None

            if self.is_mock:
                t_mock_start = time.perf_counter()
                frame = self._generate_mock_frame()
                elapsed = time.perf_counter() - t_mock_start
                sleep_time = target_delay - elapsed
                if sleep_time > 0:
                    self._stop_event.wait(sleep_time)
            elif self.cap and self.cap.isOpened():
                # Hardware read is inherently paced by camera sensor clock
                ret, raw = self.cap.read()
                if ret and raw is not None:
                    if self.mirrored:
                        frame = cv2.flip(raw, 1)
                    else:
                        frame = raw
                else:
                    self._stop_event.wait(0.005)

            if frame is None and self.first_frame_ms is None and time.perf_counter() - self._started_at > 10.0:
                raise RuntimeError("Camera không trả về khung hình sau 10 giây. Thử camera hoặc cổng USB khác.")

            if frame is not None and not self._stop_event.is_set():
                with self._lock:
                    self.latest_frame = frame
                    self.latest_timestamp = time.perf_counter()
                    self._frame_times.append(self.latest_timestamp)
                    if self.first_frame_ms is None:
                        self.first_frame_ms = (self.latest_timestamp - self._started_at) * 1000.0
                        print(f"[Camera] First frame: {self.first_frame_ms:.0f} ms")

    def read(self, copy: bool = True, after_timestamp: float = 0.0) -> Tuple[bool, Optional[np.ndarray], float]:
        """
        Retrieve the latest captured frame and its timestamp without blocking.
        """
        with self._lock:
            if self.latest_frame is None or self.latest_timestamp <= after_timestamp:
                return False, None, 0.0
            # Published arrays are never modified by capture. Internal consumers may share
            # a reference; callers that mutate pixels must keep the default copy=True.
            frame = self.latest_frame
            timestamp = self.latest_timestamp
        return True, frame.copy() if copy else frame, timestamp

    def measured_fps(self) -> float:
        """Measure successful camera reads, independently of inference and UI polling."""
        now = time.perf_counter()
        with self._lock:
            times = [stamp for stamp in self._frame_times if now - stamp <= 1.0]
        if len(times) < 2:
            return 0.0
        duration = max(times[-1] - times[0], now - times[0])
        return (len(times) - 1) / duration if duration > 0 else 0.0

    def _generate_mock_frame(self) -> np.ndarray:
        """
        Generates a synthetic animated humanoid frame for headless / camera-less environments.
        Animates a moving mannequin cycling through idle, left step, right step, jump, crouch.
        """
        self._mock_step += 1
        w, h = self.width, self.height
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        
        # Cyberpunk / AI Lab Grid background
        frame[:] = (20, 15, 12)  # Dark navy background
        for y in range(0, h, 40):
            cv2.line(frame, (0, y), (w, y), (35, 25, 20), 1)
        for x in range(0, w, 40):
            cv2.line(frame, (x, 0), (x, h), (35, 25, 20), 1)

        # Simulation cycle over 240 frames (~8 seconds)
        cycle = self._mock_step % 240
        center_x = w // 2
        center_y = int(h * 0.45)
        
        # Idle (0-60), Left (60-100), Neutral (100-120), Right (120-160), Jump (160-200), Crouch (200-240)
        action_text = "MOCK CAMERA: STAND STRAIGHT"
        if 60 <= cycle < 100:
            shift_x = int(math.sin((cycle - 60) * math.pi / 40) * (w * 0.15))
            center_x -= shift_x
            action_text = "MOCK CAMERA: STEP LEFT"
        elif 120 <= cycle < 160:
            shift_x = int(math.sin((cycle - 120) * math.pi / 40) * (w * 0.15))
            center_x += shift_x
            action_text = "MOCK CAMERA: STEP RIGHT"
        elif 160 <= cycle < 200:
            shift_y = int(math.sin((cycle - 160) * math.pi / 40) * (h * 0.12))
            center_y -= shift_y
            action_text = "MOCK CAMERA: JUMP"
        elif 200 <= cycle < 240:
            shift_y = int(math.sin((cycle - 200) * math.pi / 40) * (h * 0.10))
            center_y += shift_y
            action_text = "MOCK CAMERA: CROUCH"

        # Draw simulated silhouette (head, torso, arms, legs)
        head_radius = int(h * 0.06)
        head_center = (center_x, center_y - int(h * 0.18))
        cv2.circle(frame, head_center, head_radius, (210, 180, 140), -1)
        
        # Torso
        torso_top = (center_x, center_y - int(h * 0.10))
        torso_bottom = (center_x, center_y + int(h * 0.12))
        cv2.line(frame, torso_top, torso_bottom, (0, 200, 255), 14)
        
        # Shoulders
        shoulder_span = int(w * 0.12)
        ls = (center_x - shoulder_span, torso_top[1] + 10)
        rs = (center_x + shoulder_span, torso_top[1] + 10)
        cv2.line(frame, ls, rs, (255, 180, 0), 10)
        
        # Hips
        hip_span = int(w * 0.08)
        lh = (center_x - hip_span, torso_bottom[1])
        rh = (center_x + hip_span, torso_bottom[1])
        cv2.line(frame, lh, rh, (255, 180, 0), 10)

        # Legs
        leg_len = int(h * 0.22)
        cv2.line(frame, lh, (lh[0] - 10, lh[1] + leg_len), (0, 160, 220), 8)
        cv2.line(frame, rh, (rh[0] + 10, rh[1] + leg_len), (0, 160, 220), 8)

        # Overlay text
        cv2.putText(frame, action_text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(frame, f"FPS: {self.fps} | Synthetic Mode", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        return frame

    @staticmethod
    def list_available_cameras(max_test: int = 4) -> List[int]:
        """Find index numbers of available webcam devices."""
        available = []
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        for i in range(max_test):
            cap = cv2.VideoCapture(i, backend)
            if cap.isOpened():
                available.append(i)
            cap.release()
        return available or [0]

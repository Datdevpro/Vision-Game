"""Qt lifecycle and model ownership checks using simulated camera/model delays."""
import os
import threading
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from app.pose_detector import PoseDetector
from mediapipe.tasks.python.core.base_options import BaseOptions
from ui.main_window import MainWindow
from app.calibration import BaselineData
from tests.conftest import create_synthetic_landmarks


def pump_until(app, predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    app.processEvents()
    assert predicate(), "Qt lifecycle did not reach the expected state"


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model_factory(monkeypatch):
    calls = []
    errors = []
    entered = threading.Event()
    unblock = threading.Event()
    unblock.set()
    caller = threading.get_ident()
    inference_delay = [0.0]
    timestamps = []

    class Landmarker:
        def detect_for_video(self, image, timestamp):
            assert threading.get_ident() != caller
            timestamps.append(timestamp)
            if inference_delay[0]:
                time.sleep(inference_delay[0])
            return SimpleNamespace(pose_landmarks=[])

        def close(self):
            pass

    def create(options):
        entered.set()
        assert unblock.wait(3)
        assert options.base_options.delegate == BaseOptions.Delegate.CPU
        landmarker = Landmarker()
        landmarker.owner = threading.get_ident()
        calls.append(landmarker)
        return landmarker

    monkeypatch.setattr("app.pose_detector.vision.PoseLandmarker.create_from_options", create)
    monkeypatch.setattr("app.keyboard_controller.KeyboardController.emergency_stop", lambda self: None)
    monkeypatch.setattr("ui.main_window.QMessageBox.warning", lambda *args: errors.append(args[-1]))
    return SimpleNamespace(calls=calls, entered=entered, unblock=unblock, errors=errors,
                           inference_delay=inference_delay, timestamps=timestamps)


def test_camera_preview_and_ui_continue_while_model_loads(qt_app, model_factory, monkeypatch, tmp_path):
    opening = threading.Event()
    unblock_camera = threading.Event()
    caller = threading.get_ident()

    class SlowCamera:
        def __init__(self, *args):
            assert threading.get_ident() != caller
            opening.set()
            assert unblock_camera.wait(3)

        def isOpened(self):
            return True

        def set(self, *args):
            return True

        def get(self, *args):
            return 32

        def read(self):
            time.sleep(0.01)
            return True, np.zeros((32, 32, 3), dtype=np.uint8)

        def release(self):
            assert threading.get_ident() != caller

    monkeypatch.setattr("app.camera.cv2.VideoCapture", SlowCamera)
    model_factory.unblock.clear()
    window = MainWindow(config_path=str(tmp_path / "config.json"))
    try:
        assert not model_factory.calls  # Constructing the UI does not load a model.
        window._on_toggle_camera(True)
        pump_until(qt_app, lambda: opening.is_set() and model_factory.entered.is_set())
        assert window._starting
        unblock_camera.set()
        pump_until(qt_app, lambda: window.camera_widget.current_qimage is not None)
        assert window._starting  # Preview is visible before model initialization finishes.
        assert not model_factory.calls
        model_factory.unblock.set()
        pump_until(qt_app, lambda: not window._starting)
        assert not model_factory.errors
        assert "CPU" in window.control_panel.lbl_inference_device.text()
        assert "ms" in window.control_panel.lbl_startup_time.text()
        assert model_factory.calls[0].owner != caller

        window._on_toggle_camera(False)
        pump_until(qt_app, lambda: not window._stopping)
        window._on_toggle_camera(True)
        pump_until(qt_app, lambda: not window._starting)
        assert not model_factory.errors
        assert len(model_factory.calls) == 1  # Warm model survives camera stop/start.

        window._on_model_changed("full")
        pump_until(qt_app, lambda: len(model_factory.calls) == 2)
        pump_until(qt_app, lambda: window.control_panel.radio_full.isEnabled())
        assert "FULL" in window.control_panel.lbl_inference_device.text()
        assert model_factory.calls[1].owner != caller
    finally:
        unblock_camera.set()
        model_factory.unblock.set()
        window._on_toggle_camera(False)
        pump_until(qt_app, lambda: not window._stopping)
        window.close()


def test_close_during_model_load_waits_without_blocking_ui(qt_app, model_factory, tmp_path):
    model_factory.unblock.clear()
    window = MainWindow(config_path=str(tmp_path / "config.json"), force_mock_camera=True)
    window.show()
    try:
        window._on_toggle_camera(True)
        pump_until(qt_app, model_factory.entered.is_set)
        assert not window.close()
        assert window._closing and window.worker.isRunning()
        model_factory.unblock.set()
        pump_until(qt_app, lambda: not window.isVisible())
        assert not window.worker.isRunning()
        assert not window.camera.is_alive()
    finally:
        model_factory.unblock.set()
        if window.worker.isRunning() or window.camera.is_alive():
            window._on_toggle_camera(False)
            pump_until(qt_app, lambda: not window._stopping)
        window.close()


def test_missing_full_model_falls_back_once(qt_app, model_factory, monkeypatch, tmp_path):
    original_exists = os.path.exists
    monkeypatch.setattr("app.pose_detector.os.path.exists", lambda path: (
        False if str(path).endswith("pose_landmarker_full.task") else original_exists(path)
    ))
    window = MainWindow(config_path=str(tmp_path / "config.json"), force_mock_camera=True)
    try:
        window._on_model_changed("full")
        window._on_toggle_camera(True)
        pump_until(qt_app, lambda: not window._starting)
        for _ in range(10):
            qt_app.processEvents()
            time.sleep(0.01)
        assert len(model_factory.calls) == 1
        assert window.worker._requested_model == "lite"
        assert window.control_panel.radio_lite.isChecked()
    finally:
        window._on_toggle_camera(False)
        pump_until(qt_app, lambda: not window._stopping)
        window.close()


def test_device_change_waits_for_old_session_then_restarts(qt_app, model_factory, tmp_path):
    window = MainWindow(config_path=str(tmp_path / "config.json"), force_mock_camera=True)
    try:
        window._on_toggle_camera(True)
        pump_until(qt_app, lambda: not window._starting)
        window._on_camera_device_changed(1, True)
        pump_until(qt_app, lambda: not window._stopping and not window._starting
                   and window.camera.camera_index == 1)
        assert window.camera.running and window.worker.isRunning()
        assert len(model_factory.calls) == 1
        assert not model_factory.errors
    finally:
        window._on_toggle_camera(False)
        pump_until(qt_app, lambda: not window._stopping)
        window.close()


def test_rapid_start_stop_can_start_again(qt_app, model_factory, tmp_path):
    window = MainWindow(config_path=str(tmp_path / "config.json"), force_mock_camera=True)
    try:
        for _ in range(5):
            window._on_toggle_camera(True)
            window._on_toggle_camera(False)
            pump_until(qt_app, lambda: not window._stopping)
        window._on_toggle_camera(True)
        pump_until(qt_app, lambda: not window._starting)
        assert window.worker.isRunning() and window.camera.running
        assert not model_factory.errors
    finally:
        window._on_toggle_camera(False)
        pump_until(qt_app, lambda: not window._stopping)
        window.close()


def test_camera_failure_restores_start_button(qt_app, model_factory, monkeypatch, tmp_path):
    monkeypatch.setattr("app.camera.cv2.VideoCapture", lambda *args: SimpleNamespace(
        isOpened=lambda: False, release=lambda: None,
    ))
    window = MainWindow(config_path=str(tmp_path / "config.json"))
    try:
        window._on_toggle_camera(True)
        pump_until(qt_app, lambda: bool(model_factory.errors) and not window._stopping)
        assert not window.camera.is_mock
        assert window.control_panel.btn_camera.isEnabled()
        assert "Start" in window.control_panel.btn_camera.text()
        assert not window.worker.isRunning()
    finally:
        if window.worker.isRunning() or window.camera.is_alive():
            window._on_toggle_camera(False)
            pump_until(qt_app, lambda: not window._stopping)
        window.close()


def test_preview_keeps_receiving_fresh_frames_when_ai_runs_at_five_fps(qt_app, model_factory, tmp_path):
    model_factory.inference_delay[0] = 0.2
    window = MainWindow(config_path=str(tmp_path / "config.json"), force_mock_camera=True)
    window.camera.width = window.camera.height = 64
    try:
        window._on_toggle_camera(True)
        pump_until(qt_app, lambda: not window._starting)
        displayed = set()
        started = time.perf_counter()
        first_count = len(model_factory.timestamps)
        while time.perf_counter() - started < 1.1:
            qt_app.processEvents()
            displayed.add(window._preview_timestamp)
            time.sleep(0.002)
        ai_results = len(model_factory.timestamps) - first_count
        assert ai_results <= 7
        assert len(displayed) >= 25  # Many unique camera frames per AI result.
        assert window.camera.measured_fps() > 40
        assert "CAM" in window.camera_widget.fps_text
        assert window.worker.latest_result().stats.inference_fps < 8
        assert len(model_factory.timestamps) == len(set(model_factory.timestamps))
        # The next inference consumes a current frame instead of draining a backlog.
        assert time.perf_counter() - model_factory.timestamps[-1] / 1000 < 0.3
        assert not model_factory.errors
    finally:
        window._on_toggle_camera(False)
        pump_until(qt_app, lambda: not window._stopping)
        window.close()


def test_worker_follows_three_zones_and_vertical_lines_end_to_end(qt_app, model_factory, monkeypatch, tmp_path):
    window = MainWindow(config_path=str(tmp_path / "config.json"), force_mock_camera=True)
    body = {"x": 0.5, "dy": 0.0}
    sent = []
    window.calibration.baseline = BaselineData(0.5, 0.35, 0.65, 0.3, 0.2, is_calibrated=True)
    window.processor.set_ema_alpha(1)
    window.keyboard_ctrl.set_test_mode(True)
    window.keyboard_ctrl.on_key_sent = sent.append
    window.worker.control_active = True
    window.camera.width = window.camera.height = 64
    monkeypatch.setattr(window.detector, "detect", lambda *args, **kwargs: (
        create_synthetic_landmarks(center_x=body["x"], shoulder_y=0.35 + body["dy"],
                                   hip_y=0.65 + body["dy"]), 0.5,
    ))
    try:
        window._on_toggle_camera(True)
        pump_until(qt_app, lambda: not window._starting)
        body["x"] = 0.25
        pump_until(qt_app, lambda: sent == ["LEFT"])
        body["x"] = 0.75  # No intermediate center samples.
        pump_until(qt_app, lambda: sent == ["LEFT", "RIGHT", "RIGHT"])
        body["x"] = 0.5
        pump_until(qt_app, lambda: sent == ["LEFT", "RIGHT", "RIGHT", "LEFT"])
        body["dy"] = -0.07
        pump_until(qt_app, lambda: sent[-1:] == ["UP"])
        body["dy"] = 0.08
        pump_until(qt_app, lambda: sent[-1:] == ["DOWN"])
        assert sent == ["LEFT", "RIGHT", "RIGHT", "LEFT", "UP", "DOWN"]
        assert window.state_machine.current_lane == 1
        window._on_sensitivity_changed(2)
        pump_until(qt_app, lambda: window.camera_widget.control_zones ==
                   window.gesture_engine.get_zones(window.calibration.baseline))
        assert not model_factory.errors
    finally:
        window._on_toggle_camera(False)
        pump_until(qt_app, lambda: not window._stopping)
        window.close()


def test_overlay_draws_two_vertical_and_two_horizontal_lines_in_video_coordinates(qt_app):
    from ui.camera_widget import CameraWidget
    from app.gesture_engine import GestureEngine
    widget = CameraWidget()
    baseline = BaselineData(0.5, 0.35, 0.65, 0.3, 0.2, is_calibrated=True)
    widget.control_zones = GestureEngine(sensitivity=2).get_zones(baseline)
    lines = []
    painter = SimpleNamespace(setPen=lambda *args: None, setFont=lambda *args: None,
                              drawText=lambda *args: None, drawLine=lambda *args: lines.append(args))
    widget._draw_zones(painter, 20, 10, 600, 450)
    assert lines == [(272, 10, 272, 460), (368, 10, 368, 460),
                     (20, 226, 620, 226), (20, 244, 620, 244)]
    widget.close()


@pytest.mark.parametrize("stage,expected", [
    ("test", "CHỈ MÔ PHỎNG, KHÔNG GỬI PHÍM"),
    ("camera", "CHƯA BẬT CAMERA"),
    ("calibration", "CẦN HOÀN TẤT CALIBRATE"),
    ("paused", "NHẤN BẮT ĐẦU ĐIỀU KHIỂN"),
    ("focus", "CLICK VÀO VÙNG CHƠI GAME"),
    ("ready", "ĐIỀU KHIỂN THẬT: ĐANG BẬT"),
])
def test_input_status_explains_why_game_keys_are_suppressed(
    qt_app, model_factory, monkeypatch, tmp_path, stage, expected
):
    window = MainWindow(config_path=str(tmp_path / "config.json"), force_mock_camera=True)
    try:
        window.camera.running = stage != "camera"
        if stage != "calibration":
            window.calibration.baseline = BaselineData(0.5, 0.35, 0.65, 0.3, 0.2, is_calibrated=True)
        window.worker.control_active = stage != "paused"
        window.keyboard_ctrl.set_test_mode(stage == "test")
        monkeypatch.setattr(window.window_mgr, "is_game_focused", lambda: stage != "focus")
        window._update_input_status()
        assert expected in window.control_panel.lbl_input_status.text()
    finally:
        window.camera.running = False
        window.close()


def test_calibration_updates_visible_lanes_for_each_player(qt_app, model_factory, monkeypatch, tmp_path):
    window = MainWindow(config_path=str(tmp_path / "config.json"), force_mock_camera=True)
    player = {"x": 0.43, "width": 0.16}
    window.processor.set_ema_alpha(1)
    window.calibration.countdown_duration = 0.02
    window.calibration.sample_count = 5
    window.camera.width = window.camera.height = 64
    monkeypatch.setattr(window.detector, "detect", lambda *args, **kwargs: (
        create_synthetic_landmarks(center_x=player["x"], shoulder_width=player["width"]), 0.5,
    ))
    try:
        window._on_toggle_camera(True)
        pump_until(qt_app, lambda: not window._starting)
        for x, width in ((0.43, 0.16), (0.57, 0.24)):
            player.update(x=x, width=width)
            window._on_start_calibration()
            pump_until(qt_app, window.calibration.is_calibrated)
            # A previous baseline remains usable while recalibrating; wait for completion.
            pump_until(qt_app, lambda: window.calibration.baseline.body_center_x == pytest.approx(x))
            pump_until(qt_app, lambda: window.camera_widget.control_zones.left_boundary == pytest.approx(x - width * 0.4))
            assert window.camera_widget.control_zones.right_boundary == pytest.approx(x + width * 0.4)
        assert not model_factory.errors
    finally:
        window._on_toggle_camera(False)
        pump_until(qt_app, lambda: not window._stopping)
        window.close()

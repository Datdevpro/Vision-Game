"""
Main Application Window for Subway Surfers AI Body Controller.
Coordinates Camera Worker thread, AI Pose Detection, Calibration,
Gesture State Machine, and PySide6 UI components.
"""
import time
import threading
from dataclasses import dataclass, replace
from typing import Optional
import numpy as np

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer
from PySide6.QtGui import QFont, QCloseEvent

from app.config_manager import ConfigManager
from app.camera import CameraCapture
from app.pose_detector import PoseDetector
from app.landmarks import LandmarkProcessor, BodyMetrics
from app.calibration import CalibrationManager, CalibrationState, BaselineData
from app.gesture_engine import GestureEngine, GestureType, ControlMode
from app.gesture_state_machine import GestureStateMachine, MachineState
from app.keyboard_controller import KeyboardController
from app.window_manager import WindowManager
from app.performance_monitor import PerformanceMonitor, PerformanceStats

from ui.camera_widget import CameraWidget
from ui.control_panel import ControlPanel
from ui.gesture_indicators import GestureIndicatorsWidget
from ui.metrics_panel import MetricsPanel
from ui.calibration_dialog import CalibrationDialog
from ui.styles import DARK_THEME_QSS


@dataclass(frozen=True)
class ProcessingResult:
    capture_time: float
    completed_at: float
    metrics: BodyMetrics
    baseline: Optional[BaselineData]
    active_gesture: GestureType
    is_calibrating: bool
    calib_message: str
    current_gesture: str
    last_key: str
    is_focused: bool
    stats: PerformanceStats
    game_lane: int


class ProcessingWorker(QThread):
    """
    Dedicated background worker thread for Computer Vision & AI Inference.
    Decoupled from Qt GUI event loop to ensure zero UI freezing.
    """
    gesture_accepted = Signal(object)
    calibration_updated = Signal(object, str, float)
    model_ready = Signal(str, str, float)
    pipeline_ready = Signal()
    failed = Signal(str)

    def __init__(
        self,
        config: ConfigManager,
        camera: CameraCapture,
        detector: PoseDetector,
        processor: LandmarkProcessor,
        calibration: CalibrationManager,
        gesture_engine: GestureEngine,
        state_machine: GestureStateMachine,
        keyboard_ctrl: KeyboardController,
        window_mgr: WindowManager,
        perf_monitor: PerformanceMonitor,
    ):
        super().__init__()
        self.config = config
        self.camera = camera
        self.detector = detector
        self.processor = processor
        self.calibration = calibration
        self.gesture_engine = gesture_engine
        self.state_machine = state_machine
        self.keyboard_ctrl = keyboard_ctrl
        self.window_mgr = window_mgr
        self.perf_monitor = perf_monitor

        self.running = False
        self.control_active = False
        self._requested_model = detector.model_type
        self._result_lock = threading.Lock()
        self._latest_result = None
        self._reset_lane_requested = threading.Event()

    def request_lane_reset(self):
        self._reset_lane_requested.set()

    def latest_result(self) -> Optional[ProcessingResult]:
        with self._result_lock:
            return self._latest_result

    def clear_result(self):
        with self._result_lock:
            self._latest_result = None

    def request_model(self, model_type: str):
        # The inference thread alone creates, replaces and uses the landmarker.
        self._requested_model = model_type

    def _prepare_detector(self):
        requested_model = self._requested_model
        self.detector.change_model(requested_model)
        self.detector.initialize()
        if self._requested_model == requested_model:
            self._requested_model = self.detector.model_type
        self.model_ready.emit(
            self.detector.model_type, self.detector.inference_device,
            self.detector.initialization_time_ms,
        )

    def run(self):
        self.running = True
        self.state_machine.clear_candidates()
        self.perf_monitor = PerformanceMonitor(window_size=60)
        try:
            self._prepare_detector()
            self._process_frames()
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))
        finally:
            self.running = False

    def _process_frames(self):
        last_loop_time = time.perf_counter()
        last_capture_time = 0.0
        first_inference = True

        while not self.isInterruptionRequested():
            if self._requested_model != self.detector.model_type:
                self._prepare_detector()
            if self.isInterruptionRequested():
                break
            now = time.perf_counter()

            # 1. Grab latest camera frame
            success, frame, capture_time = self.camera.read(copy=False, after_timestamp=last_capture_time)
            if not success or frame is None:
                if self.camera.startup_error:
                    raise RuntimeError(self.camera.startup_error)
                time.sleep(0.01)
                continue
            last_capture_time = capture_time
            dt = max(0.001, now - last_loop_time)
            last_loop_time = now

            # 2. AI Pose Detection
            raw_landmarks, inf_time_ms = self.detector.detect(frame, timestamp_ms=int(capture_time * 1000))
            self.perf_monitor.record_inference(inf_time_ms, capture_time)

            # 3. Geometric Metrics Processing & Smoothing
            metrics = self.processor.process(raw_landmarks, timestamp_s=now)
            self.perf_monitor.set_confidence(metrics.confidence if metrics.is_valid else 0.0)

            # 4. Calibration Update if active
            calib_state = self.calibration.state
            calib_msg = self.calibration.status_message
            is_calibrating = calib_state in [CalibrationState.COUNTDOWN, CalibrationState.COLLECTING]
            if is_calibrating:
                state, msg, progress = self.calibration.update(metrics, dt)
                self.calibration_updated.emit(state, msg, progress)

            # 5. Follow the target lane; dispatch admission controls lane accounting.
            active_gesture = GestureType.NONE
            if self._reset_lane_requested.is_set():
                self._reset_lane_requested.clear()
                self.state_machine.reset()
            is_focused = self.window_mgr.is_game_focused()
            baseline = self.calibration.get_baseline()
            raw_gesture, debug_signals = self.gesture_engine.evaluate(metrics, baseline)
            accepted = self.state_machine.update(
                raw_gesture=raw_gesture, debug_signals=debug_signals,
                is_player_tracked=metrics.is_valid,
                is_calibrated=self.calibration.is_calibrated(), dt=dt,
                can_dispatch=self.control_active and not is_calibrating
                and (self.keyboard_ctrl.test_mode or is_focused),
                dispatch=self.keyboard_ctrl.dispatch,
            )
            if accepted:
                active_gesture = accepted
                self.gesture_accepted.emit(accepted)

            # Update performance stats
            self.perf_monitor.set_action_counts(
                self.state_machine.accepted_actions_count,
                self.state_machine.debounced_actions_count,
            )
            stats = self.perf_monitor.get_stats(camera_fps=self.camera.measured_fps())

            # Replace one metadata snapshot. Slow UI/inference never queues old video frames.
            baseline = self.calibration.get_baseline()
            result = ProcessingResult(
                capture_time=capture_time, completed_at=time.perf_counter(),
                metrics=metrics, baseline=baseline, active_gesture=active_gesture,
                is_calibrating=is_calibrating, calib_message=calib_msg,
                current_gesture=self.state_machine.current_state.value,
                last_key=self.keyboard_ctrl.last_key_sent, is_focused=is_focused, stats=stats,
                game_lane=self.state_machine.current_lane,
            )
            with self._result_lock:
                self._latest_result = result
            if first_inference:
                first_inference = False
                self.pipeline_ready.emit()

            # Yield execution briefly without capping FPS
            time.sleep(0.001)

    def stop(self, wait: bool = True):
        self.requestInterruption()
        self.running = False
        if wait:
            self.wait(1000)

class MainWindow(QMainWindow):
    """Subway Surfers AI Body Controller Desktop Application."""
    def __init__(self, config_path: str = None, force_mock_camera: bool = False):
        super().__init__()
        self.setWindowTitle("Subway Surfers AI Body Controller — Vision Lab")
        self.resize(1180, 780)
        self.setMinimumSize(960, 680)

        # 1. Initialize Core Models & Managers
        self.config = ConfigManager(config_path)
        
        cam_cfg = self.config.camera
        ctrl_cfg = self.config.control
        time_cfg = self.config.timing
        mp_cfg = self.config.mediapipe
        ui_cfg = self.config.ui

        self.camera = CameraCapture(
            camera_index=cam_cfg.get("index", 0),
            width=cam_cfg.get("width", 640),
            height=cam_cfg.get("height", 480),
            fps=cam_cfg.get("fps", 60),
            mirrored=cam_cfg.get("mirrored", True),
            is_mock=force_mock_camera,
        )

        self.detector = PoseDetector(
            model_type=mp_cfg.get("model_type", "lite"),
            min_detection_confidence=mp_cfg.get("min_pose_detection_confidence", 0.5),
            min_presence_confidence=mp_cfg.get("min_pose_presence_confidence", 0.5),
            min_tracking_confidence=mp_cfg.get("min_tracking_confidence", 0.5),
            max_num_poses=mp_cfg.get("max_num_poses", 1),
            lazy_init=True,
        )

        self.processor = LandmarkProcessor(
            ema_alpha=time_cfg.get("smoothing_ema_alpha", 0.40)
        )

        self.calibration = CalibrationManager(
            countdown_s=3.0, sample_count=30,
            jump_threshold=ctrl_cfg.get("jump_threshold", 0.12),
            crouch_threshold=ctrl_cfg.get("crouch_threshold", 0.14),
            lean_threshold=ctrl_cfg.get("lean_threshold", 10.0),
        )

        mode_enum = ControlMode.LEAN if ctrl_cfg.get("mode") == "lean" else ControlMode.ZONES
        self.gesture_engine = GestureEngine(
            mode=mode_enum,
            sensitivity=ctrl_cfg.get("sensitivity", 1.0),
            mirrored=cam_cfg.get("mirrored", True),
            hysteresis_factor=ctrl_cfg.get("hysteresis_factor", 0.55),
            lane_center_half_width=ctrl_cfg.get("lane_center_half_width", 0.10),
            auto_calibrate_lanes=ctrl_cfg.get("auto_calibrate_lanes", True),
            lane_shoulder_width_factor=ctrl_cfg.get("lane_shoulder_width_factor", 0.8),
        )

        self.state_machine = GestureStateMachine(
            confirmation_time_ms=time_cfg.get("confirmation_time_ms", 70.0),
            horizontal_cooldown_ms=time_cfg.get("horizontal_cooldown_ms", 120.0),
            jump_cooldown_ms=time_cfg.get("jump_cooldown_ms", 400.0),
            crouch_cooldown_ms=time_cfg.get("crouch_cooldown_ms", 350.0),
        )

        self.window_mgr = WindowManager(
            patterns=self.config.game.get("window_patterns", []),
            require_focus=self.config.game.get("require_focus", True),
        )

        self.keyboard_ctrl = KeyboardController(
            window_manager=self.window_mgr,
            pulse_duration_ms=time_cfg.get("key_press_duration_ms", 65.0),
            test_mode=ui_cfg.get("test_mode", False),
            use_send_input=self.config.keyboard.get("use_send_input", True),
        )

        self.perf_monitor = PerformanceMonitor(window_size=30)

        # 2. Setup Worker Thread
        self.worker = ProcessingWorker(
            config=self.config,
            camera=self.camera,
            detector=self.detector,
            processor=self.processor,
            calibration=self.calibration,
            gesture_engine=self.gesture_engine,
            state_machine=self.state_machine,
            keyboard_ctrl=self.keyboard_ctrl,
            window_mgr=self.window_mgr,
            perf_monitor=self.perf_monitor,
        )

        # 3. Build UI
        self.calib_dialog = CalibrationDialog(self)
        self.calib_dialog.start_requested.connect(self._on_start_calibration)
        self._build_ui()
        self._starting = False
        self._stopping = False
        self._closing = False
        self._session_started_at = 0.0
        self._preview_timestamp = 0.0
        self._last_metrics_update = 0.0
        self._last_input_status_update = 0.0
        self._pending_camera_device = None
        self.control_panel.radio_full.setChecked(self.detector.model_type == "full")
        self.control_panel.radio_lite.setChecked(self.detector.model_type != "full")
        selected_camera = -1 if force_mock_camera else self.camera.camera_index
        if self.control_panel.combo_cam.findData(selected_camera) < 0:
            self.control_panel.combo_cam.addItem(f"Webcam {selected_camera}", selected_camera)
        self.control_panel.combo_cam.setCurrentIndex(self.control_panel.combo_cam.findData(selected_camera))
        self.control_panel.set_camera_state(False)
        self.control_panel.radio_lean.setChecked(mode_enum == ControlMode.LEAN)
        self.control_panel.radio_step.setChecked(mode_enum != ControlMode.LEAN)
        self.control_panel.slider_sens.setValue(round(self.gesture_engine.sensitivity * 10))
        self.control_panel.chk_mirror.setChecked(self.camera.mirrored)
        self.control_panel.chk_test.setChecked(self.keyboard_ctrl.test_mode)
        self._wire_signals()
        self._update_input_status()
        self._lifecycle_timer = QTimer(self)
        self._lifecycle_timer.setTimerType(Qt.PreciseTimer)
        self._lifecycle_timer.setInterval(16)
        self._lifecycle_timer.timeout.connect(self._poll_lifecycle)
        self._lifecycle_timer.start()

    def _build_ui(self):
        self.setStyleSheet(DARK_THEME_QSS)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(16, 12, 16, 12)
        root_layout.setSpacing(10)

        # -------------------------------------------------------------
        # Header Bar
        # -------------------------------------------------------------
        header_bar = QHBoxLayout()
        header_bar.setContentsMargins(4, 0, 4, 4)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        lbl_app_title = QLabel("SUBWAY SURFERS AI BODY CONTROLLER")
        lbl_app_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        lbl_app_title.setStyleSheet("color: #38BDF8; letter-spacing: 1px;")

        lbl_app_sub = QLabel("THPT Interactive AI Vision Experience • Powered by MediaPipe Pose")
        lbl_app_sub.setStyleSheet("color: #64748B; font-size: 11px;")
        title_layout.addWidget(lbl_app_title)
        title_layout.addWidget(lbl_app_sub)

        self.lbl_system_status = QLabel("SYSTEM STANDBY")
        self.lbl_system_status.setFixedHeight(28)
        self.lbl_system_status.setStyleSheet("""
            background-color: #1E293B;
            color: #38BDF8;
            font-weight: bold;
            font-size: 11px;
            padding: 4px 12px;
            border-radius: 14px;
            border: 1px solid #334155;
        """)

        header_bar.addLayout(title_layout)
        header_bar.addStretch()
        header_bar.addWidget(self.lbl_system_status)
        root_layout.addLayout(header_bar)

        # -------------------------------------------------------------
        # Main Workspace (Camera Preview & Indicators + Control Panel)
        # -------------------------------------------------------------
        workspace_layout = QHBoxLayout()
        workspace_layout.setSpacing(14)

        # Left Column: Camera + Gesture Indicators
        left_column = QVBoxLayout()
        left_column.setSpacing(10)

        self.camera_widget = CameraWidget(self)
        self.indicators_widget = GestureIndicatorsWidget(self)

        left_column.addWidget(self.camera_widget, stretch=1)
        left_column.addWidget(self.indicators_widget)
        workspace_layout.addLayout(left_column, stretch=1)

        # Right Column: Control Panel
        self.control_panel = ControlPanel(self)
        panel_scroll = QScrollArea(self)
        panel_scroll.setWidgetResizable(True)
        panel_scroll.setFrameShape(QFrame.NoFrame)
        panel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        panel_scroll.setMinimumWidth(340)
        panel_scroll.setMaximumWidth(400)
        panel_scroll.setWidget(self.control_panel)
        workspace_layout.addWidget(panel_scroll)
        root_layout.addLayout(workspace_layout, stretch=1)

        # -------------------------------------------------------------
        # Bottom Metrics Bar
        # -------------------------------------------------------------
        self.metrics_panel = MetricsPanel(self)
        root_layout.addWidget(self.metrics_panel)

    def _wire_signals(self):
        # Worker -> UI
        self.worker.gesture_accepted.connect(self.indicators_widget.on_gesture_detected)
        self.worker.calibration_updated.connect(self.calib_dialog.update_calibration_state)
        self.worker.calibration_updated.connect(self._on_calibration_updated)
        self.worker.model_ready.connect(self._on_model_ready)
        self.worker.pipeline_ready.connect(self._on_pipeline_ready)
        self.worker.failed.connect(self._on_pipeline_failed)

        # Control Panel -> Worker / Logic
        self.control_panel.camera_toggled.connect(self._on_toggle_camera)
        self.control_panel.calibration_clicked.connect(self._on_open_calibration_dialog)
        self.control_panel.control_toggled.connect(self._on_toggle_control)
        self.control_panel.emergency_stop_clicked.connect(self._on_emergency_stop)
        self.control_panel.open_game_clicked.connect(self._on_open_game)
        self.control_panel.mode_changed.connect(self._on_mode_changed)
        self.control_panel.sensitivity_changed.connect(self._on_sensitivity_changed)
        self.control_panel.camera_device_changed.connect(self._on_camera_device_changed)
        self.control_panel.model_changed.connect(self._on_model_changed)
        self.control_panel.setting_toggled.connect(self._on_setting_toggled)
        self.control_panel.reset_defaults_clicked.connect(self._on_reset_defaults)
        self.control_panel.lane_reset_clicked.connect(self.worker.request_lane_reset)

    def _on_toggle_camera(self, start: bool):
        if start:
            if self._stopping or self._closing:
                return
            self._starting = True
            self._session_started_at = time.perf_counter()
            self._preview_timestamp = 0.0
            self._last_metrics_update = 0.0
            self.worker.clear_result()
            self.control_panel.set_camera_state(True, starting=True)
            self.lbl_system_status.setText("ĐANG MỞ CAMERA / NẠP AI...")
            self.camera_widget.current_qimage = None
            self.camera_widget.standby_message = "Đang mở camera..."
            self.camera_widget.update()
            if not self.camera.start():
                self._on_pipeline_failed("Camera đang dừng. Vui lòng thử lại.")
                return
            if not self.worker.isRunning():
                self.worker.start()
        else:
            self._starting = False
            self._stopping = True
            self.worker.control_active = False
            self.worker.stop(wait=False)
            self.camera.stop(wait=False)
            self.keyboard_ctrl.emergency_stop()
            self.control_panel.set_camera_state(False, stopping=True)
            self.control_panel.btn_control.setText("🎮 Bắt đầu Điều khiển (Start Control)")
            self.control_panel.btn_control.setEnabled(False)
            self.lbl_system_status.setText("ĐANG DỪNG CAMERA...")
            self.lbl_system_status.setStyleSheet("background-color: #1E293B; color: #38BDF8; font-weight: bold; border-radius: 14px; padding: 4px 12px;")

    def _poll_lifecycle(self):
        now = time.perf_counter()
        if now - self._last_input_status_update >= 0.1:
            self._last_input_status_update = now
            self._update_input_status()
        if self._stopping:
            if not self.worker.isRunning() and not self.camera.is_alive():
                self._stopping = False
                self.control_panel.set_camera_state(False)
                self.camera_widget.current_qimage = None
                self.camera_widget.standby_message = "CAMERA STANDBY\nNhấn 'Start Camera' để bắt đầu"
                self.camera_widget.update()
                self.lbl_system_status.setText("CAMERA STANDBY")
                if self._closing:
                    self.close()
                elif self._pending_camera_device is not None:
                    idx, is_mock = self._pending_camera_device
                    self._pending_camera_device = None
                    self.camera.camera_index = idx
                    self.camera.is_mock = is_mock
                    self._on_toggle_camera(True)
            return
        if self.camera.startup_error and (self._starting or self.worker.isRunning()):
            self._on_pipeline_failed(self.camera.startup_error)
            return
        if self.camera.running:
            self._refresh_preview()

    def _update_input_status(self):
        if self.keyboard_ctrl.test_mode:
            text, color = "TEST ONLY: CHỈ MÔ PHỎNG, KHÔNG GỬI PHÍM", "#FBBF24"
        elif not self.camera.running or self._stopping:
            text, color = "ĐIỀU KHIỂN: CHƯA BẬT CAMERA", "#94A3B8"
        elif not self.calibration.is_calibrated() or self.calibration.state in (
            CalibrationState.COUNTDOWN, CalibrationState.COLLECTING
        ):
            text, color = "CHƯA GỬI PHÍM: CẦN HOÀN TẤT CALIBRATE", "#FBBF24"
        elif not self.worker.control_active:
            text, color = "CHƯA GỬI PHÍM: NHẤN BẮT ĐẦU ĐIỀU KHIỂN", "#FBBF24"
        elif not self.window_mgr.is_game_focused():
            text, color = "CHƯA GỬI PHÍM: CLICK VÀO VÙNG CHƠI GAME", "#FBBF24"
        else:
            text, color = "ĐIỀU KHIỂN THẬT: ĐANG BẬT", "#34D399"
        label = self.control_panel.lbl_input_status
        if label.text() != text:
            label.setText(text)
            label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")

    def _refresh_preview(self):
        # Camera rendering runs at ~60 Hz, independently of inference throughput.
        now = time.perf_counter()
        result = self.worker.latest_result()
        self.camera_widget.control_zones = self.gesture_engine.get_zones(self.calibration.get_baseline())
        success, frame, timestamp = self.camera.read(copy=False, after_timestamp=self._preview_timestamp)
        camera_fps = self.camera.measured_fps()
        refresh_metrics = now - self._last_metrics_update >= 0.1
        if success:
            self._preview_timestamp = timestamp
        if success or refresh_metrics:
            overlay_max_age = max(0.25, min(0.5, result.stats.latency_ms * 0.002)) if result else 0.25
            fresh_result = result is not None and now - result.capture_time < overlay_max_age
            self.camera_widget.update_frame(
                frame, result.metrics if fresh_result else None,
                result.baseline if result else None,
                result.active_gesture if fresh_result else GestureType.NONE,
                f"CAM {camera_fps:.0f} FPS",
                result.is_calibrating if result else False,
                result.calib_message if result else "",
            )
            if self._starting and success:
                self.lbl_system_status.setText("CAMERA SẴN SÀNG • ĐANG NẠP AI...")
        if refresh_metrics:
            self._last_metrics_update = now
            if result:
                stats = replace(result.stats, camera_fps=camera_fps)
                if now - result.completed_at > 1.0:
                    stats.inference_fps = 0.0
                self.metrics_panel.update_metrics(
                    result.current_gesture, result.last_key, result.is_focused, stats
                )
                names = ("TRÁI", "GIỮA", "PHẢI")
                self.control_panel.lbl_lane_status.setText(f"Làn điều khiển: {names[result.game_lane]}")
            else:
                self.metrics_panel.card_fps.set_value(f"{camera_fps:.0f} / 0 FPS")
            driver_rate = f"{self.camera.reported_fps:.0f}" if self.camera.reported_fps else "?"
            self.control_panel.lbl_camera_rate.setText(
                f"Yêu cầu {self.camera.fps} • Thiết bị {driver_rate} • Đo {camera_fps:.0f} FPS"
            )

    @Slot(str, str, float)
    def _on_model_ready(self, model_type: str, device: str, init_ms: float):
        self.control_panel.lbl_inference_device.setText(f"AI: {device} • {model_type.upper()}")
        self.control_panel.lbl_inference_device.setToolTip(
            f"Nạp model: {init_ms:.0f} ms. MediaPipe Python trên Windows hiện chạy model bằng CPU."
        )
        if not self._stopping:
            self.control_panel.radio_lite.setEnabled(True)
            self.control_panel.radio_full.setEnabled(True)
        for radio, checked in ((self.control_panel.radio_lite, model_type == "lite"),
                               (self.control_panel.radio_full, model_type == "full")):
            radio.blockSignals(True)
            radio.setChecked(checked)
            radio.blockSignals(False)
        self.config.set("mediapipe", "model_type", model_type, auto_save=True)

    @Slot()
    def _on_pipeline_ready(self):
        if not self._starting or self._stopping:
            return
        self._starting = False
        total_ms = (time.perf_counter() - self._session_started_at) * 1000.0
        self.control_panel.set_camera_state(True)
        self.control_panel.set_control_enabled(self.calibration.is_calibrated())
        mode = "MOCK CAMERA" if self.camera.is_mock else "CAMERA ACTIVE"
        self.lbl_system_status.setText(f"{mode} • AI: CPU")
        self.lbl_system_status.setStyleSheet("background-color: #065F46; color: #34D399; font-weight: bold; border-radius: 14px; padding: 4px 12px;")
        self.control_panel.lbl_startup_time.setText(
            f"Camera: {self.camera.first_frame_ms or 0:.0f} ms • Sẵn sàng: {total_ms:.0f} ms"
        )
        print(f"[Startup] Camera + first AI result: {total_ms:.0f} ms")

    @Slot(str)
    def _on_pipeline_failed(self, message: str):
        if self._stopping or self._closing:
            return
        self._on_toggle_camera(False)
        QMessageBox.warning(self, "Không khởi động được Camera / AI", message)

    def _on_open_calibration_dialog(self):
        if not self.camera.running:
            QMessageBox.warning(self, "Camera chưa bật", "Vui lòng bật Camera trước khi thực hiện hiệu chỉnh tư thế!")
            return
        self.calib_dialog.show()

    def _on_start_calibration(self):
        self.worker.control_active = False
        self.keyboard_ctrl.emergency_stop()
        self.control_panel.btn_control.setText("🎮 Bắt đầu Điều khiển (Start Control)")
        self.lbl_system_status.setText("CALIBRATING...")
        self.lbl_system_status.setStyleSheet("background-color: #5B21B6; color: #C084FC; font-weight: bold; border-radius: 14px; padding: 4px 12px;")
        self.calibration.start_calibration()
        self.control_panel.set_control_enabled(False)

    @Slot(object, str, float)
    def _on_calibration_updated(self, state, message, progress):
        if state == CalibrationState.COMPLETED and not self._stopping:
            self.control_panel.set_control_enabled(True)
            self.lbl_system_status.setText("SẴN SÀNG • 3 VÙNG ĐIỀU KHIỂN")

    def _on_toggle_control(self, start: bool):
        if start:
            if not self.calibration.is_calibrated():
                QMessageBox.information(
                    self, "Chưa hiệu chỉnh",
                    "Vui lòng hoàn tất 'Hiệu chỉnh Baseline' trước khi bật điều khiển.\n"
                    "Đứng thẳng ở vùng giữa và giữ yên đến khi hiệu chỉnh hoàn tất."
                )
                self.control_panel.btn_control.setText("🎮 Bắt đầu Điều khiển (Start Control)")
                return
            self.keyboard_ctrl.resume()
            self.worker.control_active = True
            self.lbl_system_status.setText("ACTIVE CONTROL 🎮")
            self.lbl_system_status.setStyleSheet("background-color: #047857; color: #A7F3D0; font-weight: bold; border-radius: 14px; padding: 4px 12px;")
        else:
            self.worker.control_active = False
            self.keyboard_ctrl.emergency_stop()
            self.lbl_system_status.setText("CONTROL PAUSED ⏸")
            self.lbl_system_status.setStyleSheet("background-color: #92400E; color: #FDE68A; font-weight: bold; border-radius: 14px; padding: 4px 12px;")
        self._update_input_status()

    def _on_emergency_stop(self):
        self.worker.control_active = False
        self.keyboard_ctrl.emergency_stop()
        self.control_panel.btn_control.setText("🎮 Tiếp tục Điều khiển (Resume)")
        self.control_panel.btn_control.setStyleSheet("")
        self.lbl_system_status.setText("EMERGENCY STOP 🛑")
        self.lbl_system_status.setStyleSheet("background-color: #991B1B; color: #FECACA; font-weight: bold; border-radius: 14px; padding: 4px 12px;")

    def _on_open_game(self):
        url = self.config.game.get("url", "https://poki.com/en/g/subway-surfers")
        self.window_mgr.open_game_url(url)

    def _on_mode_changed(self, mode: ControlMode):
        self.gesture_engine.set_mode(mode)
        self.config.set("control", "mode", mode.value, auto_save=True)

    def _on_sensitivity_changed(self, sens: float):
        self.gesture_engine.set_sensitivity(sens)
        self.config.set("control", "sensitivity", sens, auto_save=True)

    def _on_camera_device_changed(self, idx: int, is_mock: bool):
        if self.camera.is_alive() or self.worker.isRunning():
            self._pending_camera_device = (idx, is_mock)
            self._on_toggle_camera(False)
            return
        self.camera.camera_index = idx
        self.camera.is_mock = is_mock

    def _on_model_changed(self, model_type: str):
        self.worker.request_model(model_type)
        if self.worker.isRunning():
            self.control_panel.radio_lite.setEnabled(False)
            self.control_panel.radio_full.setEnabled(False)
            self.control_panel.lbl_inference_device.setText(f"AI: CPU • Đang nạp {model_type.upper()}...")
        else:
            self.control_panel.lbl_inference_device.setText(f"AI: CPU • {model_type.upper()} (chờ bật camera)")
        self.config.set("mediapipe", "model_type", model_type, auto_save=True)

    def _on_setting_toggled(self, key: str, value: bool):
        if key == "mirrored":
            self.camera.mirrored = value
            self.gesture_engine.set_mirrored(value)
            self.config.set("camera", "mirrored", value, auto_save=True)
        elif key == "show_skeleton":
            self.camera_widget.show_skeleton = value
            self.config.set("ui", "show_skeleton", value, auto_save=True)
        elif key == "show_zones":
            self.camera_widget.show_zones = value
            self.config.set("ui", "show_zones", value, auto_save=True)
        elif key == "test_mode":
            self.worker.control_active = False
            self.keyboard_ctrl.emergency_stop()
            self.keyboard_ctrl.set_test_mode(value)
            self.worker.request_lane_reset()
            self.control_panel.btn_control.setText("🎮 Bắt đầu Điều khiển (Start Control)")
            self.control_panel.btn_control.setStyleSheet("")
            self.lbl_system_status.setText("ĐÃ TẠM DỪNG • ĐỒNG BỘ LÀN TRƯỚC KHI CHƠI")
            self.config.set("ui", "test_mode", value, auto_save=True)
        elif key == "require_focus":
            self.window_mgr.set_require_focus(value)
            self.config.set("game", "require_focus", value, auto_save=True)

    def _on_reset_defaults(self):
        reply = QMessageBox.question(
            self, "Khôi phục mặc định",
            "Bạn có chắc muốn đặt lại toàn bộ cài đặt về mặc định?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.config.reset_defaults()
            QMessageBox.information(self, "Đã khôi phục", "Cài đặt đã được đặt về mặc định!")

    def closeEvent(self, event: QCloseEvent):
        # Graceful shutdown
        self.keyboard_ctrl.emergency_stop()
        if self.worker.isRunning() or self.camera.is_alive():
            self._closing = True
            self._on_toggle_camera(False)
            event.ignore()
            return
        self._lifecycle_timer.stop()
        self.detector.close()
        event.accept()

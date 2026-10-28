"""
Control Panel for Subway Surfers AI Body Controller.
Houses device selection, model options, action buttons, sensitivity tuning,
mode toggles, and game launcher.
"""
from typing import List, Callable, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QSlider, QCheckBox, QGroupBox, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, Signal
from app.gesture_engine import ControlMode

class ControlPanel(QWidget):
    """Right-side control dashboard."""
    # Signals for main window to react to
    camera_toggled = Signal(bool)          # True=start, False=stop
    calibration_clicked = Signal()
    control_toggled = Signal(bool)         # True=running, False=paused
    emergency_stop_clicked = Signal()
    open_game_clicked = Signal()
    mode_changed = Signal(ControlMode)
    sensitivity_changed = Signal(float)
    camera_device_changed = Signal(int, bool) # (index, is_mock)
    model_changed = Signal(str)            # "lite" or "full"
    setting_toggled = Signal(str, bool)    # (setting_key, value)
    reset_defaults_clicked = Signal()
    lane_reset_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(320)
        self.setMaximumWidth(380)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(14)

        # -------------------------------------------------------------
        # 1. Device & Model Group
        # -------------------------------------------------------------
        grp_device = QGroupBox("CẤU HÌNH CAMERA & AI MODEL")
        dev_layout = QVBoxLayout(grp_device)
        dev_layout.setSpacing(8)

        # Camera dropdown row
        cam_row = QHBoxLayout()
        lbl_cam = QLabel("Camera:")
        lbl_cam.setFixedWidth(60)
        self.combo_cam = QComboBox()
        self.combo_cam.addItem("Webcam 0", 0)
        self.combo_cam.addItem("Webcam 1", 1)
        self.combo_cam.addItem("Mock Camera (Test AI)", -1)
        self.btn_refresh_cam = QPushButton("🔄")
        self.btn_refresh_cam.setFixedWidth(36)
        cam_row.addWidget(lbl_cam)
        cam_row.addWidget(self.combo_cam)
        cam_row.addWidget(self.btn_refresh_cam)
        dev_layout.addLayout(cam_row)

        # Model Lite vs Full row
        model_row = QHBoxLayout()
        lbl_model = QLabel("AI Model:")
        lbl_model.setFixedWidth(60)
        self.radio_lite = QRadioButton("Lite (Nhanh)")
        self.radio_full = QRadioButton("Full (Chính xác)")
        self.radio_lite.setChecked(True)
        self.btn_group_model = QButtonGroup(self)
        self.btn_group_model.addButton(self.radio_lite)
        self.btn_group_model.addButton(self.radio_full)
        model_row.addWidget(lbl_model)
        model_row.addWidget(self.radio_lite)
        model_row.addWidget(self.radio_full)
        dev_layout.addLayout(model_row)
        self.lbl_inference_device = QLabel("AI: CPU • Chờ bật camera")
        self.lbl_inference_device.setStyleSheet("color: #38BDF8; font-size: 11px;")
        self.lbl_inference_device.setToolTip("MediaPipe Tasks Python trên Windows chạy model bằng CPU.")
        dev_layout.addWidget(self.lbl_inference_device)
        self.lbl_startup_time = QLabel("Thời gian khởi động: —")
        self.lbl_startup_time.setStyleSheet("color: #94A3B8; font-size: 10px;")
        dev_layout.addWidget(self.lbl_startup_time)
        self.lbl_camera_rate = QLabel("Camera: chờ đo FPS thực tế")
        self.lbl_camera_rate.setStyleSheet("color: #94A3B8; font-size: 10px;")
        self.lbl_camera_rate.setToolTip(
            "Yêu cầu: FPS cấu hình. Thiết bị: FPS driver báo. Đo: số khung hình thực tế nhận mỗi giây. "
            "Webcam có thể không hỗ trợ 60 FPS ở độ phân giải đang chọn."
        )
        dev_layout.addWidget(self.lbl_camera_rate)
        self.lbl_lane_status = QLabel("Làn điều khiển: GIỮA")
        self.lbl_lane_status.setStyleSheet("color: #38BDF8; font-size: 11px;")
        dev_layout.addWidget(self.lbl_lane_status)
        self.btn_reset_lane = QPushButton("Đồng bộ làn giữa (Lượt mới)")
        self.btn_reset_lane.setToolTip("Nhấn khi bắt đầu lượt mới và nhân vật trong game đang ở làn giữa.")
        dev_layout.addWidget(self.btn_reset_lane)

        main_layout.addWidget(grp_device)

        # -------------------------------------------------------------
        # 2. Main Actions Group
        # -------------------------------------------------------------
        grp_actions = QGroupBox("ĐIỀU KHIỂN CHÍNH")
        act_layout = QVBoxLayout(grp_actions)
        act_layout.setSpacing(10)
        self.lbl_input_status = QLabel("ĐIỀU KHIỂN: CHƯA BẬT CAMERA")
        self.lbl_input_status.setWordWrap(True)
        self.lbl_input_status.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: bold;")
        act_layout.addWidget(self.lbl_input_status)

        self.btn_camera = QPushButton("▶ Bật Camera (Start Camera)")
        self.btn_camera.setObjectName("btnStartCamera")
        self.btn_camera.setFixedHeight(38)

        self.btn_calibrate = QPushButton("🎯 Hiệu chỉnh Baseline (Calibrate)")
        self.btn_calibrate.setObjectName("btnCalibrate")
        self.btn_calibrate.setFixedHeight(38)

        self.btn_control = QPushButton("🎮 Bắt đầu Điều khiển (Start Control)")
        self.btn_control.setObjectName("btnStartControl")
        self.btn_control.setFixedHeight(40)
        self.btn_control.setEnabled(False)

        self.btn_open_game = QPushButton("🌐 Mở Game Subway Surfers (Poki)")
        self.btn_open_game.setObjectName("btnOpenGame")
        self.btn_open_game.setFixedHeight(36)

        self.btn_stop = QPushButton("🛑 DỪNG KHẨN CẤP (EMERGENCY STOP)")
        self.btn_stop.setObjectName("btnEmergencyStop")
        self.btn_stop.setFixedHeight(36)

        act_layout.addWidget(self.btn_camera)
        act_layout.addWidget(self.btn_calibrate)
        act_layout.addWidget(self.btn_control)
        act_layout.addWidget(self.btn_open_game)
        act_layout.addWidget(self.btn_stop)

        main_layout.addWidget(grp_actions)

        # -------------------------------------------------------------
        # 3. Gesture Mode & Sensitivity Tuning
        # -------------------------------------------------------------
        grp_tuning = QGroupBox("CHẾ ĐỘ & ĐỘ NHẠY (TUNING)")
        tune_layout = QVBoxLayout(grp_tuning)
        tune_layout.setSpacing(8)

        # Control Mode Toggle: absolute image zones vs lean.
        mode_row = QHBoxLayout()
        lbl_mode = QLabel("Chế độ:")
        lbl_mode.setFixedWidth(60)
        self.radio_step = QRadioButton("3 vùng (Làn)")
        self.radio_lean = QRadioButton("Lean (Nghiêng)")
        self.radio_step.setChecked(True)
        self.btn_group_mode = QButtonGroup(self)
        self.btn_group_mode.addButton(self.radio_step)
        self.btn_group_mode.addButton(self.radio_lean)
        mode_row.addWidget(lbl_mode)
        mode_row.addWidget(self.radio_step)
        mode_row.addWidget(self.radio_lean)
        tune_layout.addLayout(mode_row)

        # Sensitivity Slider
        sens_header = QHBoxLayout()
        lbl_sens = QLabel("Độ nhạy cử chỉ:")
        self.lbl_sens_val = QLabel("1.0x")
        self.lbl_sens_val.setStyleSheet("color: #22D3EE; font-weight: bold;")
        sens_header.addWidget(lbl_sens)
        sens_header.addStretch()
        sens_header.addWidget(self.lbl_sens_val)
        tune_layout.addLayout(sens_header)

        self.slider_sens = QSlider(Qt.Horizontal)
        self.slider_sens.setRange(5, 25)  # 0.5x to 2.5x
        self.slider_sens.setValue(10)
        self.slider_sens.setToolTip("Chỉnh độ nhạy nhảy/cúi. Sau Calibrate, hai vạch dọc tự căn theo vị trí đứng và độ rộng vai.")
        tune_layout.addWidget(self.slider_sens)

        # Options Checkboxes
        self.chk_mirror = QCheckBox("Lật gương Camera (Mirrored)")
        self.chk_mirror.setChecked(True)
        self.chk_skeleton = QCheckBox("Hiện khung xương (Skeleton)")
        self.chk_skeleton.setChecked(True)
        self.chk_zones = QCheckBox("Hiện vùng cử chỉ (Left/Center/Right)")
        self.chk_zones.setChecked(True)
        self.chk_test = QCheckBox("Chế độ Test Only (Không gửi phím)")
        self.chk_test.setChecked(False)
        self.chk_focus = QCheckBox("Chỉ gửi phím khi Game có Focus")
        self.chk_focus.setChecked(True)

        tune_layout.addWidget(self.chk_mirror)
        tune_layout.addWidget(self.chk_skeleton)
        tune_layout.addWidget(self.chk_zones)
        tune_layout.addWidget(self.chk_test)
        tune_layout.addWidget(self.chk_focus)

        # Reset button
        self.btn_reset = QPushButton("Khôi phục mặc định (Reset Defaults)")
        tune_layout.addWidget(self.btn_reset)

        main_layout.addWidget(grp_tuning)
        main_layout.addStretch()

        # Wire internal signals
        self._wire_events()

    def _wire_events(self):
        self.btn_camera.clicked.connect(self._toggle_camera)
        self.btn_calibrate.clicked.connect(self.calibration_clicked.emit)
        self.btn_control.clicked.connect(self._toggle_control)
        self.btn_stop.clicked.connect(self.emergency_stop_clicked.emit)
        self.btn_open_game.clicked.connect(self.open_game_clicked.emit)
        self.btn_reset.clicked.connect(self.reset_defaults_clicked.emit)
        self.btn_reset_lane.clicked.connect(self.lane_reset_clicked.emit)

        self.radio_step.toggled.connect(lambda c: self.mode_changed.emit(ControlMode.ZONES) if c else None)
        self.radio_lean.toggled.connect(lambda c: self.mode_changed.emit(ControlMode.LEAN) if c else None)

        self.radio_lite.toggled.connect(lambda c: self.model_changed.emit("lite") if c else None)
        self.radio_full.toggled.connect(lambda c: self.model_changed.emit("full") if c else None)

        self.slider_sens.valueChanged.connect(self._on_sens_changed)
        self.combo_cam.currentIndexChanged.connect(self._on_camera_changed)

        self.chk_mirror.toggled.connect(lambda v: self.setting_toggled.emit("mirrored", v))
        self.chk_skeleton.toggled.connect(lambda v: self.setting_toggled.emit("show_skeleton", v))
        self.chk_zones.toggled.connect(lambda v: self.setting_toggled.emit("show_zones", v))
        self.chk_test.toggled.connect(lambda v: self.setting_toggled.emit("test_mode", v))
        self.chk_focus.toggled.connect(lambda v: self.setting_toggled.emit("require_focus", v))

    def _toggle_camera(self):
        is_starting = "Start" in self.btn_camera.text() or "Bật" in self.btn_camera.text()
        if is_starting:
            self.btn_camera.setText("⏹ Tắt Camera (Stop Camera)")
            self.btn_camera.setStyleSheet("background: #EF4444; color: white;")
            self.camera_toggled.emit(True)
        else:
            self.btn_camera.setText("▶ Bật Camera (Start Camera)")
            self.btn_camera.setStyleSheet("")
            self.camera_toggled.emit(False)

    def _toggle_control(self):
        is_starting = any(text in self.btn_control.text() for text in ("Bắt đầu", "Start", "Resume"))
        if is_starting:
            self.btn_control.setText("⏸ Tạm dừng Điều khiển (Pause)")
            self.btn_control.setStyleSheet("background: #F59E0B; color: white; font-weight: bold;")
            self.control_toggled.emit(True)
        else:
            self.btn_control.setText("🎮 Tiếp tục Điều khiển (Resume)")
            self.btn_control.setStyleSheet("")
            self.control_toggled.emit(False)

    def _on_sens_changed(self, val: int):
        factor = val / 10.0
        self.lbl_sens_val.setText(f"{factor:.1f}x")
        self.sensitivity_changed.emit(factor)

    def _on_camera_changed(self, idx: int):
        data = self.combo_cam.currentData()
        if data == -1:
            self.camera_device_changed.emit(0, True)  # Mock camera
        else:
            self.camera_device_changed.emit(int(data), False)

    def set_control_enabled(self, enabled: bool):
        self.btn_control.setEnabled(enabled)

    def set_camera_state(self, active: bool, starting: bool = False, stopping: bool = False):
        self.btn_camera.setText("Đang dừng..." if stopping else (
            "⏹ Tắt Camera (Stop Camera)" if active else "▶ Bật Camera (Start Camera)"
        ))
        self.btn_camera.setStyleSheet("background: #EF4444; color: white;" if active else "")
        self.btn_camera.setEnabled(not stopping)
        self.combo_cam.setEnabled(not starting and not stopping)
        self.btn_refresh_cam.setEnabled(not active and not stopping)
        self.radio_lite.setEnabled(not starting and not stopping)
        self.radio_full.setEnabled(not starting and not stopping)
        self.btn_calibrate.setEnabled(active and not starting and not stopping)
        if starting or stopping or not active:
            self.btn_control.setEnabled(False)
        if starting:
            self.lbl_startup_time.setText("Đang đo thời gian khởi động...")

    def update_camera_list(self, devices: List[int]):
        self.combo_cam.blockSignals(True)
        self.combo_cam.clear()
        for d in devices:
            self.combo_cam.addItem(f"Webcam {d}", d)
        self.combo_cam.addItem("Mock Camera (Synthetic)", -1)
        self.combo_cam.blockSignals(False)

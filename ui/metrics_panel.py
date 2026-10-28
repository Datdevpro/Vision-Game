"""
Real-time Metrics Panel for Subway Surfers AI Body Controller.
Displays Current Gesture, Last Keyboard Action, Game Focus,
Latency, FPS, Confidence, and Action Counters.
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from app.performance_monitor import PerformanceStats

class MetricCard(QFrame):
    """Small glass card showing a title and prominent value."""
    def __init__(self, title: str, initial_value: str = "-", accent_color: str = "#22D3EE"):
        super().__init__()
        self.setProperty("class", "glassCard")
        self.setFixedHeight(65)
        self.setMinimumWidth(110)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self.lbl_title = QLabel(title)
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #94A3B8; text-transform: uppercase;")

        self.lbl_value = QLabel(initial_value)
        self.lbl_value.setAlignment(Qt.AlignCenter)
        self.lbl_value.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.lbl_value.setStyleSheet(f"color: {accent_color};")

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)

    def set_value(self, text: str, color: str = None):
        self.lbl_value.setText(text)
        if color:
            self.lbl_value.setStyleSheet(f"color: {color};")

class MetricsPanel(QWidget):
    """Realtime bottom dashboard metrics row."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)

        self.card_gesture = MetricCard("Current Gesture", "NEUTRAL", "#38BDF8")
        self.card_key = MetricCard("Last Key", "NONE", "#A78BFA")
        self.card_focus = MetricCard("Game Focus", "CHECKING...", "#10B981")
        self.card_fps = MetricCard("Cam / AI FPS", "0 / 0", "#34D399")
        self.card_latency = MetricCard("Est. Latency", "0 ms", "#FBBF24")
        self.card_confidence = MetricCard("Confidence", "0%", "#60A5FA")
        self.card_actions = MetricCard("Accepted / Filtered", "0 / 0", "#E2E8F0")

        layout.addWidget(self.card_gesture)
        layout.addWidget(self.card_key)
        layout.addWidget(self.card_focus)
        layout.addWidget(self.card_fps)
        layout.addWidget(self.card_latency)
        layout.addWidget(self.card_confidence)
        layout.addWidget(self.card_actions)

    def update_metrics(self, current_gesture: str, last_key: str, is_focused: bool, stats: PerformanceStats):
        self.card_gesture.set_value(current_gesture)
        self.card_key.set_value(last_key)

        if is_focused:
            self.card_focus.set_value("FOCUSED", "#10B981")
        else:
            self.card_focus.set_value("NOT FOCUSED", "#EF4444")

        self.card_fps.set_value(f"{stats.camera_fps:.0f} / {stats.inference_fps:.0f} FPS")
        self.card_latency.set_value(f"{stats.latency_ms:.0f} ms")
        self.card_confidence.set_value(f"{stats.confidence_pct:.0f}%")
        self.card_actions.set_value(f"{stats.accepted_actions} / {stats.debounced_actions}")

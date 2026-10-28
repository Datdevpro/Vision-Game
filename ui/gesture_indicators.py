"""
Gesture Indicator cards for Subway Surfers AI Body Controller.
Displays 4 large interactive badges (LEFT, RIGHT, JUMP, CROUCH)
with pulsing neon visual feedback when gestures are detected.
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame, QVBoxLayout
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from app.gesture_engine import GestureType

class IndicatorCard(QFrame):
    """Individual action badge with glowing feedback."""
    def __init__(self, key_text: str, name_text: str, icon_symbol: str, accent_color: str = "#06B6D4"):
        super().__init__()
        self.key_text = key_text
        self.name_text = name_text
        self.icon_symbol = icon_symbol
        self.accent_color = accent_color
        self.is_active = False

        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedHeight(85)
        self.setMinimumWidth(110)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)

        self.lbl_icon = QLabel(self.icon_symbol)
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        self.lbl_icon.setFont(QFont("Segoe UI Emoji", 20, QFont.Bold))

        self.lbl_name = QLabel(self.name_text)
        self.lbl_name.setAlignment(Qt.AlignCenter)
        self.lbl_name.setFont(QFont("Segoe UI", 11, QFont.Bold))

        self.lbl_key = QLabel(self.key_text)
        self.lbl_key.setAlignment(Qt.AlignCenter)
        self.lbl_key.setFont(QFont("Segoe UI", 9))
        self.lbl_key.setStyleSheet("color: #64748B;")

        layout.addWidget(self.lbl_icon)
        layout.addWidget(self.lbl_name)
        layout.addWidget(self.lbl_key)

        self.timer_off = QTimer(self)
        self.timer_off.setSingleShot(True)
        self.timer_off.timeout.connect(self.set_inactive)

        self.set_inactive()

    def trigger(self, duration_ms: int = 240):
        self.is_active = True
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {self.accent_color}55, stop:1 #0F172A);
                border: 2px solid {self.accent_color};
                border-radius: 12px;
            }}
            QLabel {{
                color: #FFFFFF;
            }}
        """)
        self.lbl_icon.setStyleSheet(f"color: {self.accent_color}; font-size: 22px;")
        self.lbl_name.setStyleSheet("color: #FFFFFF; font-weight: bold;")
        self.lbl_key.setStyleSheet(f"color: {self.accent_color}; font-weight: bold;")
        self.timer_off.start(duration_ms)

    def set_inactive(self):
        self.is_active = False
        self.setStyleSheet("""
            QFrame {{
                background-color: #0F172A;
                border: 1px solid #1E293B;
                border-radius: 12px;
            }}
            QLabel {{
                color: #94A3B8;
            }}
        """)
        self.lbl_icon.setStyleSheet("color: #64748B; font-size: 20px;")
        self.lbl_name.setStyleSheet("color: #94A3B8; font-weight: 600;")
        self.lbl_key.setStyleSheet("color: #475569;")

class GestureIndicatorsWidget(QWidget):
    """Container widget housing all 4 gesture indicators."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)

        # 4 Indicators: Left, Right, Jump, Crouch
        self.card_left = IndicatorCard("LEFT ARROW", "MOVE LEFT", "⬅️", "#06B6D4")
        self.card_right = IndicatorCard("RIGHT ARROW", "MOVE RIGHT", "➡️", "#06B6D4")
        self.card_jump = IndicatorCard("UP ARROW", "JUMP", "⬆️", "#10B981")
        self.card_crouch = IndicatorCard("DOWN ARROW", "CROUCH / ROLL", "⬇️", "#F59E0B")

        layout.addWidget(self.card_left)
        layout.addWidget(self.card_right)
        layout.addWidget(self.card_jump)
        layout.addWidget(self.card_crouch)

    def on_gesture_detected(self, gesture: GestureType):
        if gesture == GestureType.MOVE_LEFT:
            self.card_left.trigger()
        elif gesture == GestureType.MOVE_RIGHT:
            self.card_right.trigger()
        elif gesture == GestureType.JUMP:
            self.card_jump.trigger()
        elif gesture == GestureType.CROUCH:
            self.card_crouch.trigger()

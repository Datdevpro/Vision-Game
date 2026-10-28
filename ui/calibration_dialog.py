"""
Calibration Dialog / Guidance modal for Subway Surfers AI Body Controller.
Provides Vietnamese instructions, 3-second visual countdown, and live progress.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from app.calibration import CalibrationState

class CalibrationDialog(QDialog):
    """Guided modal for camera body calibration."""
    start_requested = Signal()
    recalibrate_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hiệu chỉnh Tư thế Cơ thể (Body Calibration)")
        self.setFixedSize(520, 430)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.setStyleSheet("""
            QDialog {
                background-color: #0F172A;
                border: 2px solid #334155;
                border-radius: 12px;
            }
            QLabel {
                color: #F8FAFC;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Title
        lbl_header = QLabel("HIỆU CHỈNH CƠ THỂ CHO GAME")
        lbl_header.setAlignment(Qt.AlignCenter)
        lbl_header.setFont(QFont("Segoe UI", 16, QFont.Bold))
        lbl_header.setStyleSheet("color: #38BDF8;")
        layout.addWidget(lbl_header)

        # Subtitle instructions
        self.lbl_instruction = QLabel(
            "Đứng thẳng gần giữa ảnh, để camera thấy rõ hai vai và hai hông. "
            "Giữ yên để hệ thống đo vai và tự đặt các vạch điều khiển."
        )
        self.lbl_instruction.setAlignment(Qt.AlignCenter)
        self.lbl_instruction.setWordWrap(True)
        self.lbl_instruction.setStyleSheet("color: #94A3B8; font-size: 13px;")
        layout.addWidget(self.lbl_instruction)

        # Big Countdown / Status Card
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 10px;
                padding: 12px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)

        self.lbl_status = QLabel("Nhấn 'Bắt đầu' để đếm ngược 3 giây")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.lbl_status.setStyleSheet("color: #22D3EE;")
        card_layout.addWidget(self.lbl_status)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #0F172A;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C3AED, stop:1 #06B6D4);
                border-radius: 6px;
            }
        """)
        card_layout.addWidget(self.progress_bar)
        layout.addWidget(card)

        # Guidance checklist tips in Vietnamese
        tips = QLabel(
            "💡 Hướng dẫn:\n"
            "• Giữ rõ hai vai trong ảnh; không cần căn vào vạch có sẵn.\n"
            "• Nên thấy từ đầu tới đầu gối; không cúi hoặc nghiêng người.\n"
            "• Hai vạch dọc tự đặt theo vai sau 3 giây và 30 mẫu.\n"
            "• Đổi vị trí hoặc khoảng cách thì hiệu chỉnh lại."
        )
        tips.setStyleSheet("color: #64748B; font-size: 11px;")
        layout.addWidget(tips)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_start = QPushButton("Bắt đầu (Start)")
        self.btn_start.setObjectName("btnCalibrate")
        self.btn_start.setFixedHeight(38)
        self.btn_start.clicked.connect(self._on_start)

        self.btn_close = QPushButton("Xong / Đóng")
        self.btn_close.setFixedHeight(38)
        self.btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

    def _on_start(self):
        self.lbl_instruction.setText(
            "Đứng thẳng và giữ yên, để camera thấy rõ hai vai và hai hông. "
            "Các vạch sẽ tự đặt lại theo tư thế và độ rộng vai của bạn."
        )
        self.start_requested.emit()

    def update_calibration_state(self, state: CalibrationState, message: str, progress: float):
        self.lbl_status.setText(message)
        self.progress_bar.setValue(int(progress * 100))

        if state == CalibrationState.COUNTDOWN:
            self.lbl_status.setStyleSheet("color: #F59E0B;")
        elif state == CalibrationState.COLLECTING:
            self.lbl_status.setStyleSheet("color: #38BDF8;")
        elif state == CalibrationState.COMPLETED:
            self.lbl_status.setStyleSheet("color: #10B981;")
            self.lbl_instruction.setText(
                "✅ Đã hiệu chỉnh tư thế và các vạch! Đóng hộp thoại, tắt Test Only, "
                "nhấn Bắt đầu Điều khiển rồi click vào vùng chơi game."
            )
        elif state == CalibrationState.FAILED:
            self.lbl_status.setStyleSheet("color: #EF4444;")

"""
Live Camera Widget for Subway Surfers AI Body Controller.
Renders webcam stream, skeleton overlay, landmark points,
LEFT/CENTER/RIGHT interactive zone boundaries, baseline levels, and HUD overlays.
"""
from typing import Optional, List, Dict
import numpy as np

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRect, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QImage, QColor, QPen, QBrush, QFont, QLinearGradient
)

from app.landmarks import BodyMetrics, SKELETON_CONNECTIONS, PoseLandmark
from app.calibration import BaselineData
from app.control_zones import ControlZones
from app.gesture_engine import GestureType

class CameraWidget(QWidget):
    """
    High-performance QPainter-based live video renderer with
    AI vision laboratory HUD and skeleton visualization.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(480, 360)
        self.setStyleSheet("background-color: #070B14; border-radius: 12px;")

        self.current_qimage: Optional[QImage] = None
        self.current_metrics: Optional[BodyMetrics] = None
        self.baseline: Optional[BaselineData] = None
        self.control_zones = ControlZones.from_baseline(None)
        
        self.show_skeleton: bool = True
        self.show_zones: bool = True
        self.mirrored: bool = True
        
        self.tracking_status: str = "NO CAMERA"
        self.fps_text: str = "0 FPS"
        self.active_gesture: GestureType = GestureType.NONE
        self.is_calibrating: bool = False
        self.calib_message: str = ""
        self.standby_message: str = "CAMERA STANDBY\nNhấn 'Start Camera' để bắt đầu"

    def update_frame(
        self,
        bgr_frame: Optional[np.ndarray],
        metrics: Optional[BodyMetrics],
        baseline: Optional[BaselineData],
        active_gesture: GestureType = GestureType.NONE,
        fps_text: str = "",
        is_calibrating: bool = False,
        calib_message: str = "",
    ):
        """Update live frame and tracking metadata for next repaint."""
        if bgr_frame is not None:
            h, w, ch = bgr_frame.shape
            bytes_per_line = ch * w
            # OpenCV BGR -> QImage RGB888
            # Note: bgr_frame is BGR, so Format_BGR888 is supported by Qt and ultra-fast (no copy/convert)!
            self.current_qimage = QImage(
                bgr_frame.data, w, h, bytes_per_line, QImage.Format_BGR888
            ).copy()

        self.current_metrics = metrics
        self.baseline = baseline
        self.active_gesture = active_gesture
        self.fps_text = fps_text
        self.is_calibrating = is_calibrating
        self.calib_message = calib_message

        if metrics and metrics.is_valid:
            self.tracking_status = "LOCKED: PLAYER 1"
        elif metrics and not metrics.is_valid:
            self.tracking_status = "PLAYER NOT DETECTED"
        else:
            self.tracking_status = "SEARCHING FOR BODY..."

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        widget_w = self.width()
        widget_h = self.height()

        # 1. Background
        if self.current_qimage is None or self.current_qimage.isNull():
            painter.fillRect(self.rect(), QColor("#0B1120"))
            painter.setPen(QColor("#475569"))
            painter.setFont(QFont("Segoe UI", 14, QFont.Bold))
            painter.drawText(self.rect(), Qt.AlignCenter, self.standby_message)
            return

        # 2. Draw Video Frame directly with KeepAspectRatio (Zero CPU memory reallocation!)
        img_w = self.current_qimage.width()
        img_h = self.current_qimage.height()
        aspect = img_w / max(1, img_h)
        if (widget_w / max(1, widget_h)) > aspect:
            draw_h = widget_h
            draw_w = int(draw_h * aspect)
        else:
            draw_w = widget_w
            draw_h = int(draw_w / aspect)
        draw_x = (widget_w - draw_w) // 2
        draw_y = (widget_h - draw_h) // 2

        # Draw frame centered directly
        painter.drawImage(QRect(draw_x, draw_y, draw_w, draw_h), self.current_qimage)

        # Subtle dark vignette over video area
        vignette = QLinearGradient(0, draw_y, 0, draw_y + draw_h)
        vignette.setColorAt(0.0, QColor(11, 17, 32, 60))
        vignette.setColorAt(0.5, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(11, 17, 32, 100))
        painter.fillRect(QRectF(draw_x, draw_y, draw_w, draw_h), vignette)

        # 3. Draw Zone Boundaries if baseline exists (aligned with video)
        if self.show_zones:
            self._draw_zones(painter, draw_x, draw_y, draw_w, draw_h)

        # 4. Draw Skeleton Overlay (aligned with video)
        if self.show_skeleton and self.current_metrics and self.current_metrics.is_valid:
            self._draw_skeleton(painter, draw_x, draw_y, draw_w, draw_h, self.current_metrics)
        if self.current_metrics and self.current_metrics.is_valid:
            self._draw_body_center(painter, draw_x, draw_y, draw_w, draw_h, self.current_metrics)

        # 5. Draw HUD Overlays (Top Bar, Badges, Toast)
        self._draw_hud(painter, widget_w, widget_h)

    def _draw_zones(self, painter: QPainter, ox: int, oy: int, w: int, h: int):
        """Draw the exact normalized geometry consumed by GestureEngine."""
        zones = self.control_zones
        painter.setPen(QPen(QColor(6, 182, 212, 200), 2, Qt.DashLine))
        for boundary in (zones.left_boundary, zones.right_boundary):
            x = int(ox + boundary * w)
            painter.drawLine(x, oy, x, oy + h)

        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        for boundary, color, label in (
            (zones.jump_y, QColor(16, 185, 129, 220), "JUMP"),
            (zones.crouch_y, QColor(245, 158, 11, 220), "CROUCH"),
        ):
            y = int(oy + boundary * h)
            painter.setPen(QPen(color, 2, Qt.DashLine))
            painter.drawLine(ox, y, ox + w, y)
            painter.drawText(ox + w - 85, y - 5, label)

        painter.setPen(QColor(6, 182, 212, 230))
        for left, right, label in (
            (0.0, zones.left_boundary, "LEFT"),
            (zones.left_boundary, zones.right_boundary, "CENTER"),
            (zones.right_boundary, 1.0, "RIGHT"),
        ):
            painter.drawText(QRectF(ox + left * w, oy + h - 35, (right - left) * w, 25),
                             Qt.AlignCenter, label)

    def _draw_skeleton(self, painter: QPainter, ox: int, oy: int, w: int, h: int, metrics: BodyMetrics):
        """Draw bone connections and joint circles mapped to video rectangle."""
        raw = metrics.raw_landmarks
        if not raw:
            return

        # Bones
        pen_bone = QPen(QColor(6, 182, 212, 220), 3)
        painter.setPen(pen_bone)

        for p1_idx, p2_idx in SKELETON_CONNECTIONS:
            if p1_idx < len(raw) and p2_idx < len(raw):
                lm1 = raw[p1_idx]
                lm2 = raw[p2_idx]
                if lm1.visibility > 0.4 and lm2.visibility > 0.4:
                    x1 = int(ox + lm1.x * w)
                    y1 = int(oy + lm1.y * h)
                    x2 = int(ox + lm2.x * w)
                    y2 = int(oy + lm2.y * h)
                    painter.drawLine(x1, y1, x2, y2)

        # Joints
        brush_joint = QBrush(QColor(255, 255, 255))
        pen_joint = QPen(QColor(14, 165, 233), 2)
        painter.setPen(pen_joint)
        painter.setBrush(brush_joint)

        key_indices = [11, 12, 23, 24, 25, 26, 27, 28]  # Shoulders, hips, knees, ankles
        for idx in key_indices:
            if idx < len(raw) and raw[idx].visibility > 0.4:
                cx = int(ox + raw[idx].x * w)
                cy = int(oy + raw[idx].y * h)
                painter.drawEllipse(QPointF(cx, cy), 5, 5)

    def _draw_body_center(self, painter, ox, oy, w, h, metrics):
        # The same point determines horizontal zones and vertical crossings.
        bc_x = int(ox + metrics.body_center.x * w)
        bc_y = int(oy + metrics.body_center.y * h)
        painter.setPen(QPen(QColor(244, 63, 94), 2))
        painter.setBrush(QBrush(QColor(244, 63, 94, 200)))
        painter.drawEllipse(QPointF(bc_x, bc_y), 6, 6)

    def _draw_hud(self, painter: QPainter, w: int, h: int):
        """Draw modern status cards, FPS, and gesture toast."""
        # Top Left: Tracking status badge
        is_locked = "LOCKED" in self.tracking_status
        badge_bg = QColor(16, 185, 129, 210) if is_locked else QColor(239, 68, 68, 210)
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(badge_bg))
        painter.drawRoundedRect(16, 16, 180, 30, 6, 6)

        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        icon = "● " if is_locked else "▲ "
        painter.drawText(QRectF(16, 16, 180, 30), Qt.AlignCenter, icon + self.tracking_status)

        # Top Right: FPS Badge
        painter.setBrush(QBrush(QColor(15, 23, 42, 210)))
        painter.setPen(QPen(QColor(51, 65, 85), 1))
        painter.drawRoundedRect(w - 110, 16, 94, 30, 6, 6)
        
        painter.setPen(QColor(34, 211, 238))
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        painter.drawText(QRectF(w - 110, 16, 94, 30), Qt.AlignCenter, self.fps_text)

        # Active Gesture Banner Toast (Center Bottom)
        if self.active_gesture and self.active_gesture != GestureType.NONE:
            toast_text = f"ACTION: {self.active_gesture.value}"
            color_map = {
                GestureType.MOVE_LEFT: QColor(6, 182, 212, 230),
                GestureType.MOVE_RIGHT: QColor(6, 182, 212, 230),
                GestureType.JUMP: QColor(16, 185, 129, 230),
                GestureType.CROUCH: QColor(245, 158, 11, 230),
            }
            bg = color_map.get(self.active_gesture, QColor(59, 130, 246, 230))
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(bg))
            toast_rect = QRectF((w - 240) / 2, h - 80, 240, 42)
            painter.drawRoundedRect(toast_rect, 10, 10)
            
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(QFont("Segoe UI", 12, QFont.Bold))
            painter.drawText(toast_rect, Qt.AlignCenter, toast_text)

        # Calibration message banner if calibrating
        if self.is_calibrating and self.calib_message:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(124, 58, 237, 230)))
            calib_rect = QRectF((w - 380) / 2, 60, 380, 36)
            painter.drawRoundedRect(calib_rect, 8, 8)
            
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
            painter.drawText(calib_rect, Qt.AlignCenter, self.calib_message)

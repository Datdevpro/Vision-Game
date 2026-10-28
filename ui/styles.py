"""
AI Vision Lab Dark Theme Stylesheet for Subway Surfers AI Body Controller.
Palette: Dark Navy (#0B1120, #0F172A), Slate (#1E293B), Cyan (#06B6D4, #22D3EE),
Electric Blue (#3B82F6), Vibrant Purple (#8B5CF6), Emerald (#10B981).
"""

DARK_THEME_QSS = """
/* Global Styling */
QWidget {
    background-color: #0B1120;
    color: #F8FAFC;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #070B14;
}

/* ScrollBars */
QScrollBar:vertical {
    background: #0F172A;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #06B6D4;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* GroupBox / Panels */
QGroupBox {
    background-color: #0F172A;
    border: 1px solid #1E293B;
    border-radius: 12px;
    margin-top: 24px;
    font-weight: bold;
    font-size: 13px;
    color: #38BDF8;
    padding-top: 14px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 0 8px;
    background-color: #0B1120;
    border-radius: 4px;
}

/* Card / Frame */
QFrame.glassCard {
    background-color: #0F172A;
    border: 1px solid #1E293B;
    border-radius: 12px;
}
QFrame.glassCard:hover {
    border: 1px solid #0284C7;
}

/* Push Buttons */
QPushButton {
    background-color: #1E293B;
    color: #F8FAFC;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 13px;
    min-height: 22px;
}
QPushButton:hover {
    background-color: #334155;
    border: 1px solid #38BDF8;
    color: #FFFFFF;
}
QPushButton:pressed {
    background-color: #0F172A;
}
QPushButton:disabled {
    background-color: #0F172A;
    color: #475569;
    border: 1px solid #1E293B;
}

/* Special Action Buttons */
QPushButton#btnStartCamera {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #06B6D4);
    border: none;
    color: #FFFFFF;
    font-weight: bold;
}
QPushButton#btnStartCamera:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369A1, stop:1 #0891B2);
}

QPushButton#btnCalibrate {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C3AED, stop:1 #9333EA);
    border: none;
    color: #FFFFFF;
    font-weight: bold;
}
QPushButton#btnCalibrate:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6D28D9, stop:1 #7E22CE);
}

QPushButton#btnStartControl {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10B981);
    border: none;
    color: #FFFFFF;
    font-weight: bold;
}
QPushButton#btnStartControl:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
}

QPushButton#btnOpenGame {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #3B82F6);
    border: none;
    color: #FFFFFF;
    font-weight: bold;
}
QPushButton#btnOpenGame:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:1 #2563EB);
}

QPushButton#btnEmergencyStop {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #DC2626, stop:1 #EF4444);
    border: none;
    color: #FFFFFF;
    font-weight: bold;
}
QPushButton#btnEmergencyStop:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #B91C1C, stop:1 #DC2626);
}

/* Combo Box */
QComboBox {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 6px 12px;
    color: #F8FAFC;
    font-weight: 500;
}
QComboBox:hover {
    border: 1px solid #06B6D4;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #0F172A;
    border: 1px solid #1E293B;
    selection-background-color: #0284C7;
    selection-color: #FFFFFF;
    color: #F8FAFC;
    border-radius: 4px;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #1E293B;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #06B6D4);
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #22D3EE;
    border: 2px solid #FFFFFF;
    width: 16px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover {
    background: #FFFFFF;
}

/* Checkbox */
QCheckBox {
    color: #CBD5E1;
    font-weight: 500;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #475569;
    border-radius: 5px;
    background-color: #1E293B;
}
QCheckBox::indicator:hover {
    border: 1px solid #06B6D4;
}
QCheckBox::indicator:checked {
    background-color: #06B6D4;
    border: 1px solid #22D3EE;
}

/* Labels */
QLabel {
    color: #E2E8F0;
}
QLabel.sectionHeader {
    font-size: 15px;
    font-weight: bold;
    color: #38BDF8;
}
QLabel.metricValue {
    font-size: 20px;
    font-weight: bold;
    color: #22D3EE;
}
QLabel.metricTitle {
    font-size: 11px;
    font-weight: 600;
    color: #94A3B8;
    text-transform: uppercase;
}
"""

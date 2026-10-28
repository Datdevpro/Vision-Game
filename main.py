"""
Subway Surfers AI Body Controller - Main Entry Point.
Launches the PySide6 desktop GUI with MediaPipe Pose Landmarker
and real-time body motion gesture control.
"""
import sys
import os
import argparse
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Ensure local modules are found
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from download_models import ensure_models
from ui.main_window import MainWindow

def main():
    parser = argparse.ArgumentParser(description="Subway Surfers AI Body Controller")
    parser.add_argument("--config", type=str, default=None, help="Path to custom config.json")
    parser.add_argument("--mock-camera", action="store_true", help="Force synthetic mock camera feed (for testing without webcam)")
    parser.add_argument("--model", type=str, choices=["lite", "full"], default="lite", help="MediaPipe model type (lite or full)")
    parser.add_argument("--test-mode", action="store_true", help="Start with keyboard dispatch suppressed")
    args = parser.parse_args()

    print("==========================================================")
    print("       SUBWAY SURFERS AI BODY CONTROLLER (VISION LAB)     ")
    print("==========================================================")
    print("Checking AI model assets...")
    
    # Auto-verify / download model if missing
    models_dir = os.path.join(base_dir, "models")
    if not ensure_models(models_dir, download_all=False):
        print("[ERROR] Required model files could not be initialized.")
        sys.exit(1)

    # Enable High DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Subway Surfers AI Body Controller")
    app.setOrganizationName("AIVisionLab")

    window = MainWindow(
        config_path=args.config,
        force_mock_camera=args.mock_camera,
    )

    if args.test_mode:
        window.keyboard_ctrl.set_test_mode(True)
        window.control_panel.chk_test.setChecked(True)

    if args.model != "lite":
        window.control_panel.radio_full.setChecked(True)

    window.show()
    print("[INFO] Application running. Press Ctrl+C in terminal or close window to exit.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

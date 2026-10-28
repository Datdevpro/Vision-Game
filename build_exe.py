"""
PyInstaller packaging helper for Subway Surfers AI Body Controller.
Builds a standalone Windows executable.
"""
import os
import sys
import subprocess

def build():
    print("========================================================")
    print("   BUILDING WINDOWS EXECUTABLE WITH PYINSTALLER         ")
    print("========================================================")

    # Verify PyInstaller is installed in the current environment
    try:
        import PyInstaller
    except ImportError:
        print("[INFO] PyInstaller not detected. Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    base_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(base_dir, "models")
    config_file = os.path.join(base_dir, "config.json")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=SubwaySurfersAIController",
        "--onedir",
        "--windowed",
        "--clean",
        "--noconfirm",
        f"--add-data={models_dir};models",
        f"--add-data={config_file};.",
        "--collect-all=mediapipe",
        "--collect-all=PySide6",
        "main.py"
    ]

    print(f"Running command: {' '.join(cmd)}")
    subprocess.check_call(cmd)
    print("\n[SUCCESS] Build complete! Executable is located in dist/SubwaySurfersAIController/")

if __name__ == "__main__":
    build()

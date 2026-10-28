# 🎮 Subway Surfers Control Using Body Gestures (Pose Detection)

This project demonstrates a **real-time Human–Computer Interaction (HCI)** system where the game **Subway Surfers** is controlled using **body gestures** captured through a webcam.

Using **MediaPipe Pose**, **OpenCV**, and **PyAutoGUI**, the system detects human pose landmarks, interprets body movements, and converts them into **keyboard inputs** to control the game character.

---

## 📌 Features
- Real-time pose detection using webcam
- Gesture-based game start using hand-joining
- Left / Right lane control using body position
- Jump and Crouch using upper-body posture
- Keyboard control using PyAutoGUI
- FPS counter and visual feedback

---

## 🛠️ Technologies Used
- Python
- OpenCV
- MediaPipe
- PyAutoGUI

---

## 📁 Project Structure
Subway Surfers/
│
├── pose_utils.py # Pose detection logic
├── gesture_utils.py # Gesture detection functions
├── main.py # Final application (game controller)
├── requirements.txt
└── README.md


---

## 🚀 Setup Instructions

### 1. Run with the project's Python environment

From `D:\datworkspace\Subway-AI`, use PowerShell:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe download_models.py
.\venv\Scripts\python.exe .\Subway-Surfers-Pose-Control\main.py
```

Pose detection uses MediaPipe Tasks Vision (`PoseLandmarker`) and does not
require the removed `mp.solutions` API. The Lite model is loaded from this
folder's `models` directory or the parent `Subway-AI\models` directory.

### 2. Play

Open Subway Surfers in the browser and focus the game. Join your hands to
start, then move left/right, jump, or crouch to control the character.
Press Escape in the camera window to exit.



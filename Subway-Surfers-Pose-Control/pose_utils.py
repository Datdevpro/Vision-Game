import atexit
from pathlib import Path
import time
from types import SimpleNamespace

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions, vision


_pose = None
_last_timestamp_ms = -1


def closePose():
    """Release the model when the program exits."""
    global _pose, _last_timestamp_ms
    if _pose is not None:
        _pose.close()
        _pose = None
    _last_timestamp_ms = -1


atexit.register(closePose)


def _get_pose():
    global _pose
    if _pose is None:
        project_dir = Path(__file__).resolve().parent
        model_paths = [
            project_dir / "models" / "pose_landmarker_lite.task",
            project_dir.parent / "models" / "pose_landmarker_lite.task",
        ]
        model_path = next((path for path in model_paths if path.is_file()), None)
        if model_path is None:
            raise FileNotFoundError(
                "Missing pose_landmarker_lite.task. Run download_models.py "
                "in the Subway-AI folder, or put the model in the models "
                "folder beside pose_utils.py."
            )
        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        _pose = vision.PoseLandmarker.create_from_options(options)
    return _pose


def _draw_pose(image, landmarks):
    height, width = image.shape[:2]
    points = {}
    for index, landmark in enumerate(landmarks):
        if any(value is not None and value < 0.5
               for value in (landmark.visibility, landmark.presence)):
            continue
        if 0 <= landmark.x <= 1 and 0 <= landmark.y <= 1:
            points[index] = (
                min(int(landmark.x * width), width - 1),
                min(int(landmark.y * height), height - 1),
            )
    for connection in vision.PoseLandmarksConnections.POSE_LANDMARKS:
        if connection.start in points and connection.end in points:
            cv2.line(image, points[connection.start], points[connection.end],
                     (224, 224, 224), 2)
    for point in points.values():
        cv2.circle(image, point, 3, (0, 0, 255), -1)

def detectPose(image, draw=True):
    """Detect a pose with Tasks Vision, preserving the gesture helpers' result format."""
    global _last_timestamp_ms
    output_image = image.copy()
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pose = _get_pose()
    timestamp_ms = max(time.monotonic_ns() // 1_000_000, _last_timestamp_ms + 1)
    result = pose.detect_for_video(
        mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb), timestamp_ms
    )
    _last_timestamp_ms = timestamp_ms

    # Existing game code reads results.pose_landmarks.landmark[index].
    landmarks = result.pose_landmarks[0] if result.pose_landmarks else None
    results = SimpleNamespace(
        pose_landmarks=SimpleNamespace(landmark=landmarks) if landmarks else None
    )

    if landmarks and draw:
        _draw_pose(output_image, landmarks)

    return output_image, results

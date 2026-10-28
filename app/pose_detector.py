"""
MediaPipe Tasks Vision PoseLandmarker wrapper.
Uses official Google Tasks Vision API in VIDEO mode with monotonic timestamps,
single-player tracking lock, and Lite/Full model selection.
"""
import os
import time
from typing import List, Optional, Tuple
import numpy as np

import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core.base_options import BaseOptions
from app.landmarks import PoseLandmark

class PoseDetector:
    """
    Wrapper around mediapipe.tasks.python.vision.PoseLandmarker.
    Operates in VIDEO mode with monotonically increasing timestamps.
    Locks onto a single primary player to avoid switching to passers-by.
    """
    def __init__(
        self,
        model_type: str = "lite",
        models_dir: str = None,
        min_detection_confidence: float = 0.5,
        min_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        max_num_poses: int = 1,
        lazy_init: bool = False,
    ):
        self.model_type = model_type.lower()
        if models_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            models_dir = os.path.join(base_dir, "models")
        self.models_dir = models_dir

        self.min_detection_confidence = min_detection_confidence
        self.min_presence_confidence = min_presence_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.max_num_poses = max_num_poses

        self.landmarker: Optional[vision.PoseLandmarker] = None
        self.last_timestamp_ms: int = 0
        self.inference_device = "CPU"
        self.initialization_time_ms = 0.0
        
        # Player lock persistence
        self.locked_player_center: Optional[Tuple[float, float]] = None
        self.consecutive_missed_frames: int = 0
        self.max_missed_frames: int = 15

        if not lazy_init:
            self.initialize()

    def initialize(self):
        if self.landmarker is None:
            self._initialize_landmarker()

    def _get_model_path(self) -> str:
        filename = f"pose_landmarker_{self.model_type}.task"
        path = os.path.join(self.models_dir, filename)
        if not os.path.exists(path):
            # Fallback to lite if full is missing
            alt_path = os.path.join(self.models_dir, "pose_landmarker_lite.task")
            if os.path.exists(alt_path):
                self.model_type = "lite"
                return alt_path
            raise FileNotFoundError(f"Model file not found at {path} or {alt_path}")
        return path

    def _initialize_landmarker(self):
        started_at = time.perf_counter()
        model_path = self._get_model_path()
        base_options = BaseOptions(model_asset_path=model_path, delegate=BaseOptions.Delegate.CPU)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_poses=self.max_num_poses,
            min_pose_detection_confidence=self.min_detection_confidence,
            min_pose_presence_confidence=self.min_presence_confidence,
            min_tracking_confidence=self.min_tracking_confidence,
            output_segmentation_masks=False,
        )
        self.landmarker = vision.PoseLandmarker.create_from_options(options)
        self.initialization_time_ms = (time.perf_counter() - started_at) * 1000.0
        self.last_timestamp_ms = 0
        self.reset_lock()
        print(f"[AI] {self.model_type.upper()} | {self.inference_device} | Model init: {self.initialization_time_ms:.0f} ms")

    def change_model(self, model_type: str):
        if model_type.lower() != self.model_type:
            self.model_type = model_type.lower()
            if self.landmarker:
                self.landmarker.close()
                self.landmarker = None
            self.initialize()

    def detect(self, bgr_frame: np.ndarray, timestamp_ms: int = None) -> Tuple[Optional[List[PoseLandmark]], float]:
        """
        Run inference on a single BGR video frame.
        Guarantees monotonically increasing timestamp_ms.
        Returns: (primary_player_landmarks, inference_time_ms).
        """
        if self.landmarker is None or bgr_frame is None:
            return None, 0.0

        if timestamp_ms is None or timestamp_ms <= self.last_timestamp_ms:
            # Enforce strictly monotonic timestamp
            curr_ms = int(time.time() * 1000)
            if curr_ms <= self.last_timestamp_ms:
                curr_ms = self.last_timestamp_ms + 1
            timestamp_ms = curr_ms
        self.last_timestamp_ms = timestamp_ms

        # Convert BGR to RGB MediaPipe Image
        # Limit preprocessing cost for high-resolution camera inputs. This is a
        # speed/detail tradeoff; normalized landmark coordinates stay unchanged.
        import cv2
        h, w = bgr_frame.shape[:2]
        if w > 640:
            scale = 640.0 / w
            inf_w = 640
            inf_h = int(h * scale)
            small_bgr = cv2.resize(bgr_frame, (inf_w, inf_h), interpolation=cv2.INTER_LINEAR)
            rgb_frame = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2RGB)
        else:
            rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        t_start = time.perf_counter()
        result = self.landmarker.detect_for_video(mp_image, timestamp_ms)
        inference_time_ms = (time.perf_counter() - t_start) * 1000.0

        if not result or not result.pose_landmarks:
            self.consecutive_missed_frames += 1
            if self.consecutive_missed_frames > self.max_missed_frames:
                self.locked_player_center = None
            return None, inference_time_ms

        self.consecutive_missed_frames = 0
        all_poses = result.pose_landmarks

        # Select primary player
        selected_pose = self._select_primary_pose(all_poses)
        if not selected_pose:
            return None, inference_time_ms

        # Convert to list of PoseLandmark
        landmarks = [
            PoseLandmark(
                x=p.x,
                y=p.y,
                z=p.z,
                visibility=getattr(p, "visibility", 1.0) or 1.0,
                presence=getattr(p, "presence", 1.0) or 1.0,
            )
            for p in selected_pose
        ]

        # Update locked position
        ls_x, ls_y = landmarks[11].x, landmarks[11].y
        rs_x, rs_y = landmarks[12].x, landmarks[12].y
        self.locked_player_center = ((ls_x + rs_x) / 2.0, (ls_y + rs_y) / 2.0)

        return landmarks, inference_time_ms

    def _select_primary_pose(self, all_poses) -> Optional[list]:
        """Lock onto existing player or pick largest/most centered pose."""
        if len(all_poses) == 1:
            return all_poses[0]

        best_pose = None
        best_score = float("inf") if self.locked_player_center else -1.0

        for pose in all_poses:
            # Approximate center using shoulders (11, 12)
            ls = pose[11]
            rs = pose[12]
            cx = (ls.x + rs.x) / 2.0
            cy = (ls.y + rs.y) / 2.0

            if self.locked_player_center:
                # Distance to locked center
                dist = (cx - self.locked_player_center[0]) ** 2 + (cy - self.locked_player_center[1]) ** 2
                if dist < best_score:
                    best_score = dist
                    best_pose = pose
            else:
                # Pick the pose closest to frame center with largest shoulder span
                dist_to_center = (cx - 0.5) ** 2 + (cy - 0.5) ** 2
                shoulder_span = abs(ls.x - rs.x)
                score = shoulder_span - (dist_to_center * 0.5)
                if score > best_score:
                    best_score = score
                    best_pose = pose

        return best_pose or all_poses[0]

    def reset_lock(self):
        self.locked_player_center = None
        self.consecutive_missed_frames = 0

    def close(self):
        if self.landmarker:
            try:
                self.landmarker.close()
            except Exception:
                pass
            self.landmarker = None

"""
Performance metrics collector for Subway Surfers AI Body Controller.
Monitors Camera FPS, AI Inference FPS, End-to-End Latency, and Action Counters.
"""
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque

@dataclass
class PerformanceStats:
    camera_fps: float = 0.0
    inference_fps: float = 0.0
    inference_time_ms: float = 0.0
    latency_ms: float = 0.0
    confidence_pct: float = 0.0
    accepted_actions: int = 0
    debounced_actions: int = 0

class PerformanceMonitor:
    """
    Maintains rolling windows of timestamps to compute accurate realtime
    FPS, latency, and throughput statistics.
    """
    def __init__(self, window_size: int = 30):
        self.window_size = window_size
        self.inference_timestamps: Deque[float] = deque(maxlen=window_size)
        self.inference_times: Deque[float] = deque(maxlen=window_size)
        self.latencies: Deque[float] = deque(maxlen=window_size)
        
        self.confidence_pct: float = 0.0
        self.accepted_actions: int = 0
        self.debounced_actions: int = 0

    def record_inference(self, inference_ms: float, frame_capture_time: float = None):
        """Record inference completion and latency."""
        now = time.perf_counter()
        self.inference_timestamps.append(now)
        self.inference_times.append(inference_ms)
        
        if frame_capture_time is not None:
            latency = (now - frame_capture_time) * 1000.0
            self.latencies.append(latency)

    def set_confidence(self, confidence: float):
        self.confidence_pct = max(0.0, min(100.0, confidence * 100.0))

    def set_action_counts(self, accepted: int, debounced: int):
        self.accepted_actions = accepted
        self.debounced_actions = debounced

    def get_stats(self, camera_fps: float = 0.0) -> PerformanceStats:
        # Camera rate must come from the capture thread, never from inference polling.
        inference_fps = self._calculate_fps(self.inference_timestamps)
        avg_inf_ms = float(sum(self.inference_times) / len(self.inference_times)) if self.inference_times else 0.0
        avg_latency = float(sum(self.latencies) / len(self.latencies)) if self.latencies else avg_inf_ms

        return PerformanceStats(
            camera_fps=camera_fps,
            inference_fps=inference_fps,
            inference_time_ms=avg_inf_ms,
            latency_ms=avg_latency,
            confidence_pct=self.confidence_pct,
            accepted_actions=self.accepted_actions,
            debounced_actions=self.debounced_actions,
        )

    def _calculate_fps(self, timestamps: Deque[float]) -> float:
        if len(timestamps) < 2:
            return 0.0
        duration = timestamps[-1] - timestamps[0]
        if duration <= 0:
            return 0.0
        return float((len(timestamps) - 1) / duration)

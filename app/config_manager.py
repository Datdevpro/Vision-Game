"""
Configuration manager for Subway Surfers AI Body Controller.
Handles loading, updating, saving, and resetting config.json.
"""
import os
import json
import copy
from typing import Any, Dict

DEFAULT_CONFIG: Dict[str, Any] = {
    "camera": {
        "index": 0,
        "width": 640,
        "height": 480,
        "fps": 60,
        "mirrored": True,
    },
    "mediapipe": {
        "model_type": "lite",
        "min_pose_detection_confidence": 0.5,
        "min_pose_presence_confidence": 0.5,
        "min_tracking_confidence": 0.5,
        "max_num_poses": 1,
    },
    "control": {
        "mode": "zones",  # "zones" or "lean"
        "sensitivity": 1.0,
        "lane_center_half_width": 0.10,
        "auto_calibrate_lanes": True,
        "lane_shoulder_width_factor": 0.8,
        "lean_threshold": 10.0,
        "jump_threshold": 0.12,
        "crouch_threshold": 0.14,
        "hysteresis_factor": 0.55,
    },
    "timing": {
        "confirmation_time_ms": 70,
        "horizontal_cooldown_ms": 120,
        "jump_cooldown_ms": 400,
        "crouch_cooldown_ms": 350,
        "smoothing_ema_alpha": 0.40,
        "key_press_duration_ms": 65,
    },
    "keyboard": {
        "key_left": "left",
        "key_right": "right",
        "key_jump": "up",
        "key_crouch": "down",
        "use_send_input": True,
    },
    "game": {
        "url": "https://poki.com/en/g/subway-surfers",
        "window_patterns": [
            "subway surfers",
            "poki",
            "google chrome",
            "microsoft edge",
            "mozilla firefox",
            "brave",
            "opera",
        ],
        "require_focus": True,
    },
    "ui": {
        "theme": "dark_ai_lab",
        "show_skeleton": True,
        "show_zones": True,
        "show_metrics": True,
        "test_mode": False,
    },
}

class ConfigManager:
    def __init__(self, config_path: str = None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config.json")
        self.config_path = config_path
        self._config: Dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
        self.load()

    def load(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    user_cfg = json.load(f)
                    self._merge(self._config, user_cfg)
            except Exception as e:
                print(f"[ConfigManager] Error reading {self.config_path}: {e}. Using defaults.")
        else:
            self.save()
        return self._config

    def _merge(self, base: dict, override: dict):
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                self._merge(base[k], v)
            else:
                base[k] = v

    def save(self) -> bool:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[ConfigManager] Failed to save config: {e}")
            return False

    def reset_defaults(self) -> Dict[str, Any]:
        self._config = copy.deepcopy(DEFAULT_CONFIG)
        self.save()
        return self._config

    def get(self, section: str, key: str = None, default: Any = None) -> Any:
        if section not in self._config:
            return default
        if key is None:
            return self._config[section]
        return self._config[section].get(key, default)

    def set(self, section: str, key: str, value: Any, auto_save: bool = False):
        if section not in self._config:
            self._config[section] = {}
        self._config[section][key] = value
        if auto_save:
            self.save()

    @property
    def camera(self) -> dict:
        return self._config.get("camera", {})

    @property
    def mediapipe(self) -> dict:
        return self._config.get("mediapipe", {})

    @property
    def control(self) -> dict:
        return self._config.get("control", {})

    @property
    def timing(self) -> dict:
        return self._config.get("timing", {})

    @property
    def keyboard(self) -> dict:
        return self._config.get("keyboard", {})

    @property
    def game(self) -> dict:
        return self._config.get("game", {})

    @property
    def ui(self) -> dict:
        return self._config.get("ui", {})

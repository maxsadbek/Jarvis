"""
Vision configuration - loads ``config/vision.yaml``.

These settings are consumed by ``vision/vision_control.py`` (via
``VisionController.from_config()``) to build the hand-tracking pipeline:
camera, gesture recognition and screen control parameters.

Any key missing from the YAML file falls back to the defaults defined in
:class:`VisionSettings`, so the file only needs to contain what you want to
override.

Example
-------
.. code-block:: python

    from config.vision import load_vision_config

    cfg = load_vision_config()
    print(cfg.pinch_threshold, cfg.smooth_factor)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# config/vision.yaml - next to this module.
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "vision.yaml"


@dataclass
class VisionSettings:
    """Runtime settings for the hand-controlled vision pipeline."""

    # Whether hand control starts automatically with the backend.
    enabled_on_startup: bool = False

    # --- Camera / hand tracking ---
    camera_index: int = 0  # webcam device index
    frame_width: int = 640  # capture resolution (width)
    frame_height: int = 480  # capture resolution (height)
    max_num_hands: int = 1  # track a single hand

    # --- Gesture recognition ---
    pinch_threshold: float = 0.045  # thumb-index distance for PINCH (normalized)
    gesture_history_size: int = 5  # frames used for gesture smoothing
    gesture_confidence: float = 0.6  # min share of history a gesture needs to win

    # --- Screen control ---
    active_zone: float | list[float] = 0.7  # central % OR [left,right,top,bottom]
    cursor_filter: str = "kalman"  # kalman | exponential | none
    kalman_q: float = 4.0  # process noise (higher = snappier)
    kalman_r: float = 60.0  # measurement noise (higher = smoother)
    smooth_factor: float = 0.4  # cursor smoothing for the exponential filter
    pinch_button: str = "left"  # mouse button pressed by PINCH
    pinch_debounce_frames: int = 3  # PINCH must be stable N frames before click
    window_drag_enabled: bool = True  # FIST window dragging (Windows)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VisionSettings":
        """Build settings from a dict, ignoring unknown keys."""
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})


def load_vision_config(path: str | os.PathLike | None = None) -> VisionSettings:
    """
    Load vision settings from a YAML file.

    :param path: Optional explicit path; defaults to ``config/vision.yaml``.
        A missing file yields the built-in defaults (no error).
    :return: A populated :class:`VisionSettings`.
    """
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return VisionSettings()

    with open(config_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return VisionSettings.from_dict(data)

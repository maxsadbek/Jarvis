"""
Vision Control module - combines hand tracking, gesture recognition and
screen control into one background thread.

This is the main vision pipeline for Jarvis. It wires together:

* :class:`vision.hand_tracker.HandTracker` - camera capture + 21 landmarks
* :class:`vision.gesture_recognizer.GestureRecognizer` - gesture names
* :class:`vision.screen_controller.ScreenController` - real mouse / window
  actions

The chain (hand detection -> gesture recognition -> screen control) runs in a
dedicated daemon thread, so it never blocks - and is never blocked by - the
main Jarvis loop (e.g. voice commands). The current pipeline state can be read
from any thread at any time via :attr:`VisionController.state` (thread-safe).

Example
-------
.. code-block:: python

    from vision.vision_control import VisionController

    vision = VisionController()
    vision.start()            # opens the camera, starts the background thread

    # ... the main Jarvis loop (voice, etc.) keeps running here ...

    if vision.state["gesture"] == "POINT":
        # the voice loop can also react to the current gesture

    vision.stop()             # clean shutdown on exit

Note: ``ScreenController`` disables pyautogui's corner FAILSAFE (camera
control intentionally reaches screen edges), so provide an emergency stop in
your main loop (e.g. a keyboard quit that calls ``stop()``).
"""

from __future__ import annotations

import logging
import threading
import time

from vision.gesture_recognizer import GESTURE_NONE, GestureRecognizer
from vision.hand_tracker import HandTracker
from vision.screen_controller import ScreenController

logger = logging.getLogger(__name__)

_THREAD_NAME = "jarvis-vision"


class VisionController:
    """
    Runs the hand -> gesture -> screen pipeline in a background thread.

    :param tracker: A :class:`HandTracker` instance. ``None`` = create one
        (and open the camera) when :meth:`start` is called.
    :param recognizer: A :class:`GestureRecognizer` instance. ``None`` =
        create a default one.
    :param controller: A :class:`ScreenController` instance. ``None`` =
        create a default one.
    :param daemon: Mark the thread as a daemon so it never prevents the
        process from exiting.
    :param tracker_kwargs: Extra keyword arguments passed to :class:`HandTracker`
        when it is created internally (e.g. ``camera_index``, frame size).
        Ignored when a custom ``tracker`` is injected.
    """

    def __init__(
        self,
        *,
        tracker: HandTracker | None = None,
        recognizer: GestureRecognizer | None = None,
        controller: ScreenController | None = None,
        daemon: bool = True,
        tracker_kwargs: dict | None = None,
    ) -> None:
        self._tracker = tracker
        self._recognizer = recognizer if recognizer is not None else GestureRecognizer()
        self._controller = controller if controller is not None else ScreenController()
        self._daemon = daemon
        self._tracker_kwargs = tracker_kwargs or {}
        # Only a tracker we created ourselves may be dropped on stop() so a
        # restart can open a fresh camera.
        self._tracker_owned = tracker is None

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_state: dict = {
            "hand_found": False,
            "gesture": GESTURE_NONE,
            "action": None,
            "cursor": None,
            "fps": 0.0,
            "frame": 0,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """
        Open the camera and start the vision loop in a background thread.

        :return: ``True`` when the loop was started, ``False`` when it was
            already running.
        :raises RuntimeError: When the camera cannot be opened (only when a
            tracker was not injected and the default one fails to start).
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            if self._tracker is None:
                self._tracker = HandTracker(**self._tracker_kwargs)
                self._tracker_owned = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name=_THREAD_NAME,
                daemon=self._daemon,
            )
            self._thread.start()
            return True

    def stop(self, timeout: float = 2.0) -> None:
        """
        Stop the vision loop and release all resources.

        Safe to call more than once and from any thread. Releases the camera,
        the mouse buttons and any ongoing window drag.

        Note: when a *custom* tracker was injected via the constructor, it is
        released here but kept (its lifecycle belongs to the caller) - pass a
        fresh instance to :meth:`start` again for a restart. Internally owned
        trackers are recreated automatically.

        :param timeout: Seconds to wait for the thread to finish.
        """
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)
            if thread.is_alive():
                logger.warning(
                    "Vision thread did not stop within %.1f s - continuing.",
                    timeout,
                )
        with self._lock:
            self._thread = None

        self._controller.release_all()
        if self._tracker is not None:
            self._tracker.release()
        if self._tracker_owned:
            self._tracker = None  # a later start() opens a fresh camera

    @property
    def is_running(self) -> bool:
        """Whether the vision thread is currently alive."""
        thread = self._thread  # single read - stop() may clear it concurrently
        return thread is not None and thread.is_alive()

    @property
    def state(self) -> dict:
        """
        Snapshot of the latest processed frame (thread-safe).

        Keys: ``hand_found``, ``gesture``, ``action``, ``cursor``, ``fps``,
        ``frame`` (monotonic counter).
        """
        with self._lock:
            return dict(self._last_state)

    def _set_state(
        self,
        hand_found: bool,
        gesture: str,
        action=None,
        cursor=None,
        fps: float | None = None,
    ) -> None:
        """Thread-safe snapshot of the latest frame (``fps=None`` keeps the
        previous value, e.g. on camera-failure frames)."""
        with self._lock:
            self._last_state = {
                "hand_found": bool(hand_found),
                "gesture": gesture,
                "action": action,
                "cursor": cursor,
                "fps": self._last_state["fps"] if fps is None else fps,
                "frame": self._last_state["frame"] + 1,
            }

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Per-frame pipeline: detect hand -> recognize gesture -> act."""
        logger.info("Vision control thread started.")
        prev_time = time.perf_counter()
        try:
            while not self._stop_event.is_set():
                try:
                    hand_found, landmarks, frame = self._tracker.update()
                except Exception:
                    logger.exception("Vision frame failed - skipping.")
                    self._set_state(False, GESTURE_NONE)
                    time.sleep(0.05)
                    continue

                if frame is None:
                    # Camera hiccup: release everything, avoid a busy loop.
                    self._controller.update(GESTURE_NONE, None)
                    self._set_state(False, GESTURE_NONE)
                    time.sleep(0.1)
                    continue

                gesture = (
                    self._recognizer.recognize(landmarks)
                    if hand_found
                    else GESTURE_NONE
                )
                info = self._controller.update(gesture, landmarks)

                now = time.perf_counter()
                fps = 1.0 / max(now - prev_time, 1e-6)
                prev_time = now
                self._set_state(
                    bool(hand_found),
                    gesture,
                    action=info.get("action"),
                    cursor=info.get("cursor"),
                    fps=round(fps, 1),
                )
        finally:
            # Never leave a mouse button down or a window drag open.
            self._controller.release_all()
            logger.info("Vision control thread stopped.")

    @classmethod
    def from_config(cls, config_path=None) -> "VisionController":
        """
        Build a VisionController from ``config/vision.yaml``.

        Wires the camera, gesture and screen-control settings from the YAML
        file (see :func:`config.vision.load_vision_config`) into fresh
        :class:`HandTracker` / :class:`GestureRecognizer` /
        :class:`ScreenController` instances. The camera is only opened when
        :meth:`start` is called.

        :param config_path: Optional explicit path to the YAML config.
        """
        from config.vision import load_vision_config  # lazy - keeps import light

        cfg = load_vision_config(config_path)
        return cls(
            recognizer=GestureRecognizer(
                pinch_threshold=cfg.pinch_threshold,
                history_size=cfg.gesture_history_size,
                confidence_threshold=cfg.gesture_confidence,
            ),
            controller=ScreenController(
                active_zone=cfg.active_zone,
                smooth_factor=cfg.smooth_factor,
                cursor_filter=cfg.cursor_filter,
                kalman_q=cfg.kalman_q,
                kalman_r=cfg.kalman_r,
                pinch_button=cfg.pinch_button,
                pinch_debounce_frames=cfg.pinch_debounce_frames,
                window_drag_enabled=cfg.window_drag_enabled,
            ),
            tracker_kwargs={
                "camera_index": cfg.camera_index,
                "frame_width": cfg.frame_width,
                "frame_height": cfg.frame_height,
                "max_num_hands": cfg.max_num_hands,
            },
        )

    # ------------------------------------------------------------------
    # Context manager support:  with VisionController() as vision: ...
    # ------------------------------------------------------------------

    def __enter__(self) -> "VisionController":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

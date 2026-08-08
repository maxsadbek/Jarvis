"""
Hand Tracker module - real-time hand landmark detection.

This module provides the :class:`HandTracker` class, which combines
OpenCV (camera capture) and MediaPipe Hands (21-point hand landmark
detection) to track a hand in real time. It is written as a standalone,
importable module so that other Jarvis components (gesture control,
virtual mouse, sign-language detection, etc.) can reuse it.

Example
-------
.. code-block:: python

    import cv2
    from vision.hand_tracker import HAND_LANDMARKS, HandTracker

    tracker = HandTracker()
    try:
        while True:
            hand_found, landmarks, frame = tracker.update()
            if hand_found:
                index_tip = landmarks[HAND_LANDMARKS["index_tip"]]
                print(f"Index fingertip at: ({index_tip['px']}, {index_tip['py']})")
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        tracker.release()
        cv2.destroyAllWindows()

Dependencies: opencv-python, mediapipe (see requirements.txt).
"""

from __future__ import annotations

import cv2
import mediapipe as mp

# MediaPipe Hand solutions - initialised once at module level so that every
# HandTracker instance shares the same drawing helpers.
_mp_hands = mp.solutions.hands
_mp_drawing = mp.solutions.drawing_utils
_mp_styles = mp.solutions.drawing_styles

# Named indices of the 21 hand landmarks (MediaPipe Hands convention).
# Useful for reading specific points (e.g. fingertips) in other modules.
HAND_LANDMARKS: dict[str, int] = {
    "wrist": 0,
    "thumb_cmc": 1,
    "thumb_mcp": 2,
    "thumb_ip": 3,
    "thumb_tip": 4,
    "index_mcp": 5,
    "index_pip": 6,
    "index_dip": 7,
    "index_tip": 8,
    "middle_mcp": 9,
    "middle_pip": 10,
    "middle_dip": 11,
    "middle_tip": 12,
    "ring_mcp": 13,
    "ring_pip": 14,
    "ring_dip": 15,
    "ring_tip": 16,
    "pinky_mcp": 17,
    "pinky_pip": 18,
    "pinky_dip": 19,
    "pinky_tip": 20,
}

# Landmark names in index order - the reverse of HAND_LANDMARKS.
_LANDMARK_NAMES: list[str] = [""] * 21
for _name, _idx in HAND_LANDMARKS.items():
    _LANDMARK_NAMES[_idx] = _name


def draw_landmarks(frame, hand_landmarks) -> None:
    """
    Draw the connections and landmark dots of one detected hand on a frame.

    The frame is modified in place (standard OpenCV behaviour).

    :param frame: BGR frame (numpy array) to draw on.
    :param hand_landmarks: MediaPipe ``NormalizedLandmarkList`` object from
        ``result.multi_hand_landmarks``.
    """
    _mp_drawing.draw_landmarks(
        frame,
        hand_landmarks,
        _mp_hands.HAND_CONNECTIONS,
        _mp_styles.get_default_hand_landmarks_style(),
        _mp_styles.get_default_hand_connections_style(),
    )


class HandTracker:
    """
    Real-time single-hand landmark tracker built on OpenCV + MediaPipe.

    Typical flow::

        tracker = HandTracker()
        hand_found, landmarks, frame = tracker.update()
        tracker.release()

    The tracker can also be used as a context manager::

        with HandTracker() as tracker:
            hand_found, landmarks, frame = tracker.update()
    """

    def __init__(
        self,
        *,
        camera_index: int = 0,
        frame_width: int = 640,
        frame_height: int = 480,
        max_num_hands: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        mirror: bool = True,
    ) -> None:
        """
        Initialise the camera and the MediaPipe Hands model.

        :param camera_index: Index of the webcam to open (0 is the default
            camera). Pass ``None`` to create a tracker without a camera,
            e.g. when frames will be supplied manually via ``process_frame``.
        :param frame_width: Desired capture width in pixels.
        :param frame_height: Desired capture height in pixels.
        :param max_num_hands: Maximum number of hands to detect (keep 1 for
            single-hand tracking).
        :param min_detection_confidence: Minimum confidence for hand
            detection (0.0 - 1.0).
        :param min_tracking_confidence: Minimum confidence for landmark
            tracking (0.0 - 1.0).
        :param mirror: Horizontally flip the image so it behaves like a
            mirror (recommended for webcam use).

        :raises RuntimeError: If a camera index was given but the camera
            could not be opened.
        """
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.mirror = mirror
        self.camera_index = camera_index

        # MediaPipe Hands model.
        self._hands = _mp_hands.Hands(
            static_image_mode=False,  # False = continuous video tracking (faster)
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

        # OpenCV video capture (only if a camera was requested).
        self._cap = None
        if camera_index is not None:
            self._cap = cv2.VideoCapture(camera_index)
            if not self._cap.isOpened():
                self._cap = None
                self._hands.close()  # avoid leaking the model on failure
                raise RuntimeError(
                    f"Could not open camera with index {camera_index}. "
                    "Check that the webcam is connected and not in use."
                )
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, frame_width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_height)

        # Results of the most recent processed frame.
        self._hand_landmarks = None  # MediaPipe NormalizedLandmarkList or None
        self._hand_label = None  # "Left" / "Right" as reported by MediaPipe
        self._last_frame_shape = (0, 0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def capture_frame(self):
        """
        Read the next frame from the camera.

        :return: The captured BGR frame, or ``None`` if the camera failed
            or no camera was opened.
        """
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        if not ok or frame is None:
            return None
        if self.mirror:
            frame = cv2.flip(frame, 1)
        return frame

    def process_frame(self, frame):
        """
        Run hand detection on a given frame (from the camera or any source).

        The frame is drawn on with the detected landmarks, so pass a copy
        if you need the raw image afterwards.

        :param frame: BGR frame (numpy array).
        :return: The annotated BGR frame.
        """
        if frame is None:
            return None

        self._last_frame_shape = frame.shape
        height, width = frame.shape[:2]

        # MediaPipe expects RGB; OpenCV works with BGR.
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._hands.process(frame_rgb)

        # Store the first detected hand for get_landmarks().
        self._hand_landmarks = (
            results.multi_hand_landmarks[0] if results.multi_hand_landmarks else None
        )
        # Handedness label ("Left" / "Right") - used e.g. for thumb detection.
        self._hand_label = None
        if results.multi_handedness:
            self._hand_label = results.multi_handedness[0].classification[0].label

        # Visualise the detected hand on the original BGR frame.
        if self._hand_landmarks is not None:
            draw_landmarks(frame, self._hand_landmarks)

        return frame

    def get_landmarks(self) -> tuple[bool, list[dict[str, float | int | str]]]:
        """
        Return whether a hand was found and its 21 landmark coordinates.

        Reflects the most recently processed frame (via ``update`` or
        ``process_frame``). Before any frame is processed, this returns
        ``(False, [])``.

        :return: A tuple ``(hand_found, landmarks)`` where ``hand_found`` is
            ``True`` when a hand is currently detected, and ``landmarks`` is
            a list of 21 dicts (one per landmark point), each containing:

            * ``"id"``    - landmark index (0-20)
            * ``"name"``  - human-readable name (e.g. ``"index_tip"``)
            * ``"hand"``  - "Left" or "Right" handedness, or ``None``
            * ``"x"``     - normalized X coordinate (0.0 - 1.0)
            * ``"y"``     - normalized Y coordinate (0.0 - 1.0)
            * ``"z"``     - relative depth (MediaPipe z value)
            * ``"px"``    - X in pixels, relative to the frame
            * ``"py"``    - Y in pixels, relative to the frame
        """
        if self._hand_landmarks is None:
            return False, []

        height, width = self._last_frame_shape[:2]
        landmarks: list[dict[str, float | int | str]] = []
        for idx, lm in enumerate(self._hand_landmarks.landmark):
            landmarks.append(
                {
                    "id": idx,
                    "name": _LANDMARK_NAMES[idx],
                    "hand": self._hand_label,
                    "x": lm.x,  # normalized [0..1]
                    "y": lm.y,  # normalized [0..1]
                    "z": lm.z,  # relative depth
                    "px": int(lm.x * width),  # pixel coordinates
                    "py": int(lm.y * height),
                }
            )
        return True, landmarks

    def update(self) -> tuple[bool, list[dict[str, float | int | str]], object | None]:
        """
        Capture, process and annotate a single frame in one call.

        Convenience wrapper around :meth:`capture_frame` +
        :meth:`process_frame` + :meth:`get_landmarks`.

        :return: Tuple ``(hand_found, landmarks, frame)`` - same as
            ``get_landmarks()`` plus the annotated BGR frame (``None`` if
            the camera read failed).
        """
        frame = self.capture_frame()
        if frame is None:
            return False, [], None
        frame = self.process_frame(frame)
        hand_found, landmarks = self.get_landmarks()
        return hand_found, landmarks, frame

    def release(self) -> None:
        """Release the camera and free MediaPipe resources."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._hands.close()

    # ------------------------------------------------------------------
    # Context manager support:  with HandTracker() as tracker: ...
    # ------------------------------------------------------------------

    def __enter__(self) -> "HandTracker":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()

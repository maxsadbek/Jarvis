"""
Gesture Recognizer module - classifies hand landmarks into gestures.

This module consumes the 21-landmark dicts produced by
:meth:`vision.hand_tracker.HandTracker.get_landmarks` and classifies them
into one of the following gestures:

=================  ========================================================
Gesture            Meaning / typical use
=================  ========================================================
``POINT``          Only the index finger is extended - cursor movement
``PINCH``          Thumb tip and index tip closer than a threshold - click
``FIST``           All fingers folded - window drag
``OPEN_PALM``      All fingers extended - release / stop
``NO_GESTURE``     Hand absent, or the pose matches none of the above
=================  ========================================================

Temporal smoothing
------------------
Discrete gestures cannot be numerically averaged, so :meth:`recognize`
applies a *rolling majority vote* over the last ``history_size`` frames
(default 5). This removes flicker when a pose sits on the edge between two
gestures. The winner must also hold at least ``confidence_threshold`` of the
window (default 0.6 = 3 of 5 frames) - below that, ``NO_GESTURE`` is
returned so weak / flickering poses never trigger actions. Use
:meth:`recognize_raw` to get the immediate (unsmoothed) result.

The module intentionally does not import OpenCV / MediaPipe, so it can be
imported (and unit tested) independently of the hand tracker. Landmark
names used here match ``HAND_LANDMARKS`` in ``vision/hand_tracker.py``.

Example
-------
.. code-block:: python

    from vision.gesture_recognizer import GESTURE_POINT, GestureRecognizer

    recognizer = GestureRecognizer()
    hand_found, landmarks, frame = tracker.update()
    if hand_found:
        gesture = recognizer.recognize(landmarks)
        if gesture == GESTURE_POINT:
            print("Move the cursor!")
"""

from __future__ import annotations

from collections import Counter, deque
from collections.abc import Sequence
from typing import NotRequired, TypedDict, TypeAlias

# --- Public gesture names -------------------------------------------------
GESTURE_NONE = "NO_GESTURE"
GESTURE_POINT = "POINT"
GESTURE_PINCH = "PINCH"
GESTURE_FIST = "FIST"
GESTURE_OPEN_PALM = "OPEN_PALM"

# --- Landmark names (must match HAND_LANDMARKS in vision/hand_tracker.py) --
_THUMB_IP = "thumb_ip"
_THUMB_TIP = "thumb_tip"
_INDEX_MCP = "index_mcp"
_INDEX_PIP = "index_pip"
_INDEX_TIP = "index_tip"
_MIDDLE_PIP = "middle_pip"
_MIDDLE_TIP = "middle_tip"
_RING_PIP = "ring_pip"
_RING_TIP = "ring_tip"
_PINKY_MCP = "pinky_mcp"
_PINKY_PIP = "pinky_pip"
_PINKY_TIP = "pinky_tip"


class Landmark(TypedDict):
    """One landmark point, as returned by HandTracker.get_landmarks()."""

    id: NotRequired[int]
    name: NotRequired[str]
    hand: NotRequired[str | None]
    x: float
    y: float
    z: NotRequired[float]
    px: NotRequired[int]
    py: NotRequired[int]


# Accepted input: a list of landmarks, or a dict keyed by landmark name.
Landmarks: TypeAlias = Sequence[Landmark] | dict[str, Landmark] | None


def _distance(a: Landmark, b: Landmark) -> float:
    """Euclidean distance between two landmarks in normalized coordinates."""
    return ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5


def _midpoint(a: Landmark, b: Landmark) -> Landmark:
    """Midpoint of two landmarks (approximation of the palm centre)."""
    return {"x": (a["x"] + b["x"]) / 2, "y": (a["y"] + b["y"]) / 2}


def _to_named(landmarks: Landmarks) -> dict[str, Landmark]:
    """
    Normalize the landmark input to a name-keyed dict.

    Accepts either the list of landmark dicts produced by
    ``HandTracker.get_landmarks()`` or an already name-keyed dict.
    Returns an empty dict when no hand is present.

    :param landmarks: Landmarks from the hand tracker, or ``None`` / ``[]``
        when the hand was not detected.
    """
    if not landmarks:
        return {}
    if isinstance(landmarks, dict):
        return landmarks
    return {lm["name"]: lm for lm in landmarks}


def _is_extended(tip: Landmark, pip: Landmark) -> bool:
    """
    A finger is extended when its tip sits above (smaller ``y``) its PIP joint.

    Valid while the hand points upward, which covers all four target
    gestures (y grows downwards in both normalized and pixel coordinates).
    """
    return tip["y"] < pip["y"]


def _is_thumb_open(named: dict[str, Landmark]) -> bool:
    """
    Detect whether the thumb is extended.

    Uses the handedness label reported by MediaPipe (the classic x-axis
    comparison). When handedness is unknown (e.g. landmarks from another
    source), falls back to a distance heuristic: the thumb counts as open
    when its tip is farther from the palm centre than its IP joint.

    :param named: Name-keyed landmark dict (see ``_to_named``).
    """
    tip = named[_THUMB_TIP]
    ip = named[_THUMB_IP]
    hand = tip.get("hand")

    if hand == "Right":  # extended thumb points toward -x in the image
        return tip["x"] < ip["x"]
    if hand == "Left":  # extended thumb points toward +x in the image
        return tip["x"] > ip["x"]

    # Fallback heuristic (no handedness available).
    palm_centre = _midpoint(named[_INDEX_MCP], named[_PINKY_MCP])
    return _distance(tip, palm_centre) > _distance(ip, palm_centre)


class GestureRecognizer:
    """
    Classifies hand landmarks into gestures, with temporal smoothing.

    :param pinch_threshold: Normalized distance (0.0 - 1.0) below which the
        thumb and index tips count as PINCH. Smaller = a tighter pinch.
    :param history_size: Number of recent frames kept for the smoothing
        majority vote. ``1`` disables smoothing entirely.
    :param confidence_threshold: Minimum share (0.5 - 1.0) of the history
        window the winning gesture must hold. Below it, :meth:`recognize`
        returns ``NO_GESTURE`` - filters out flicker / accidental poses.
    """

    def __init__(
        self,
        *,
        pinch_threshold: float = 0.045,
        history_size: int = 5,
        confidence_threshold: float = 0.6,
    ) -> None:
        if not 0.5 <= confidence_threshold <= 1.0:
            raise ValueError(
                "confidence_threshold must be in [0.5, 1.0], "
                f"got {confidence_threshold}"
            )
        self.pinch_threshold = pinch_threshold
        self.history_size = max(1, history_size)
        self.confidence_threshold = confidence_threshold
        self._history: deque[str] = deque(maxlen=self.history_size)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recognize(self, landmarks: Landmarks) -> str:
        """
        Classify the current frame and return the *smoothed* gesture name.

        Smoothing = majority vote over the last ``history_size`` frames
        (see the module docstring). Ties favor the gesture that has been
        stable for longer.

        :param landmarks: Landmarks from ``HandTracker.get_landmarks()``
            (or ``None`` / ``[]`` when no hand is detected).
        :return: One of the ``GESTURE_*`` constants.
        """
        raw = self.recognize_raw(landmarks)
        self._history.append(raw)
        return _majority_gesture(self._history, self.confidence_threshold)

    def recognize_raw(self, landmarks: Landmarks) -> str:
        """
        Classify a single frame without smoothing.

        :param landmarks: Same input as :meth:`recognize`.
        :return: One of the ``GESTURE_*`` constants.
        """
        named = _to_named(landmarks)
        if not named:
            return GESTURE_NONE

        # PINCH is distance-based and the most specific gesture - check it
        # first so a pinching hand is never misread as FIST or POINT.
        if _distance(named[_THUMB_TIP], named[_INDEX_TIP]) < self.pinch_threshold:
            return GESTURE_PINCH

        states = self.finger_states(named)
        if states is None:  # unreachable here, but keeps the type checker happy
            return GESTURE_NONE
        open_set = {name for name, is_open in states.items() if is_open}

        if not open_set:
            return GESTURE_FIST
        if open_set == set(states):
            return GESTURE_OPEN_PALM
        if open_set == {"index"}:
            return GESTURE_POINT
        return GESTURE_NONE

    def finger_states(self, landmarks: Landmarks) -> dict[str, bool] | None:
        """
        Return the open/closed state of each finger (independent of gestures).

        Useful for debugging or for consumers that need raw finger data.

        :param landmarks: Same input as :meth:`recognize`.
        :return: A dict like ``{"thumb": True, "index": True, ...}``, or
            ``None`` when no hand is present.
        """
        named = _to_named(landmarks)
        if not named:
            return None
        return {
            "thumb": _is_thumb_open(named),
            "index": _is_extended(named[_INDEX_TIP], named[_INDEX_PIP]),
            "middle": _is_extended(named[_MIDDLE_TIP], named[_MIDDLE_PIP]),
            "ring": _is_extended(named[_RING_TIP], named[_RING_PIP]),
            "pinky": _is_extended(named[_PINKY_TIP], named[_PINKY_PIP]),
        }

    def pinch_distance(self, landmarks: Landmarks) -> float | None:
        """
        Distance between the thumb tip and the index tip (normalized 0..1).

        Lets consumers implement click/drag with hysteresis (e.g. a lower
        threshold to press and a higher one to release).

        :param landmarks: Same input as :meth:`recognize`.
        :return: The distance, or ``None`` when no hand is present.
        """
        named = _to_named(landmarks)
        if not named:
            return None
        return _distance(named[_THUMB_TIP], named[_INDEX_TIP])

    def reset(self) -> None:
        """Clear the smoothing history (e.g. when the hand was lost)."""
        self._history.clear()


def _majority_gesture(history: deque[str], confidence: float) -> str:
    """
    Return the most frequent gesture in the history window.

    ``Counter.most_common`` preserves insertion order for ties, so the
    gesture that has been present longer wins - this prevents flicker
    during a transition. When even the winner holds less than ``confidence``
    of the window, ``NO_GESTURE`` is returned instead (the pose is too
    unstable to act on).
    """
    counts = Counter(history)
    top_gesture, top_count = counts.most_common(1)[0]
    if top_count / len(history) >= confidence:
        return top_gesture
    return GESTURE_NONE

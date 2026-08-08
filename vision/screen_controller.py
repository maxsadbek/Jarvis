"""
Screen Controller module - turns gestures into real mouse / window actions.

Consumes the gesture name produced by :class:`vision.gesture_recognizer.GestureRecognizer`
(together with the landmark list from the hand tracker) and drives the real
mouse through pyautogui:

=================  =========================================================
Gesture            Screen action
=================  =========================================================
``POINT``          Move the cursor (index fingertip -> screen coordinates)
``PINCH``          Press (``mouseDown``) on start, release (``mouseUp``)
                   on end - content click / drag
``FIST``           Grab the title bar of the window under the cursor and
                   drag it (Windows)
``OPEN_PALM``      Release everything (stop drag, release buttons)
``NO_GESTURE``     Release everything (hand was lost)
=================  =========================================================

Active zone
-----------
Only the central part of the camera frame (``active_zone``, default 70%) is
mapped to the full screen, so the screen edges are reachable without extreme
hand movements. ``active_zone`` may be a single fraction (symmetric zone) or
four margins ``[left, right, top, bottom]`` for an asymmetric zone - a
smaller margin makes that screen edge easier to reach.

Cursor smoothing
----------------
Cursor movement is smoothed by a selectable filter (``cursor_filter``):
``"kalman"`` (default - a 1D constant-velocity Kalman filter per axis, the
smoothest), ``"exponential"`` (moving average) or ``"none"``. Smoothed
*gestures* are already handled by the recognizer - this module adds
cursor-position smoothing on top.

Accidental-click protection
---------------------------
``pinch_debounce_frames`` requires PINCH to stay stable for N consecutive
frames before the mouse button goes down, so a brief hand flicker never
produces an accidental click or drag. Releasing stays immediate so a drag
never gets stuck.

Note: together with the recognizer's ``gesture_confidence`` vote, a click
fires after roughly ``gesture_history_size`` + ``pinch_debounce_frames``
frames (~160 ms at 30 fps). This is intentional - tune either setting in
the config if you want clicks to fire faster (or be even stricter).

Platform notes
--------------
* Cursor + pinch work on any OS supported by pyautogui.
* Window dragging (``FIST``) uses ``pygetwindow`` and is implemented for
  **Windows**; on other platforms it is skipped with a logged warning.
* On Windows with display scaling > 100%, pyautogui coordinates may be
  offset unless the process is DPI aware - see pyautogui docs. If cursor or
  window positions look off, enable DPI awareness for the process.

Example
-------
.. code-block:: python

    from vision.gesture_recognizer import GESTURE_NONE, GestureRecognizer
    from vision.screen_controller import ScreenController

    recognizer = GestureRecognizer()
    controller = ScreenController()

    hand_found, landmarks, frame = tracker.update()
    gesture = recognizer.recognize(landmarks) if hand_found else GESTURE_NONE
    controller.update(gesture, landmarks)
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

import pyautogui

from vision.gesture_recognizer import (
    GESTURE_FIST,
    GESTURE_NONE,
    GESTURE_OPEN_PALM,
    GESTURE_PINCH,
    GESTURE_POINT,
    Landmarks,
)

if TYPE_CHECKING:  # pygetwindow is imported lazily (Windows-only drag)
    import pygetwindow as gw

logger = logging.getLogger(__name__)

# Windows shell windows that must never be grabbed for dragging.
_SHELL_TITLES = {
    "program manager",
    "shell_traywnd",
    "windows input experience",
    "task switching",
    "system tray overflow window",
}


class _Kalman1D:
    """Minimal 1D constant-velocity Kalman filter (pure Python, no numpy).

    State is ``[position, velocity]``; every frame runs a predict step
    (constant velocity, ``dt = 1``) followed by a correct step against the
    measured position. ``q`` (process noise) and ``r`` (measurement noise)
    trade responsiveness against smoothing: a larger ``r / q`` ratio
    filters more aggressively. Two independent instances (one per screen
    axis) are used by :class:`ScreenController`.
    """

    def __init__(self, q: float, r: float) -> None:
        self._q = max(float(q), 0.0)
        self._r = max(float(r), 1e-6)
        self._pos = 0.0
        self._vel = 0.0
        self._p00 = 1.0
        self._p01 = 0.0
        self._p11 = 1.0
        self._initialized = False

    def reset(self, value: float) -> None:
        """Re-seed the filter with a known position (e.g. after a jump)."""
        self._pos = float(value)
        self._vel = 0.0
        self._p00 = 1.0
        self._p01 = 0.0
        self._p11 = 1.0
        self._initialized = True

    def update(self, measurement: float) -> float:
        """Feed one measured position; returns the filtered position."""
        z = float(measurement)
        if not self._initialized:
            self.reset(z)
            return z

        # --- predict: constant velocity over one frame ---
        pos = self._pos + self._vel
        vel = self._vel
        p00 = self._p00 + 2.0 * self._p01 + self._p11 + self._q
        p01 = self._p01 + self._p11
        p11 = self._p11 + self._q

        # --- correct: 1D measurement of the position ---
        innovation_var = p00 + self._r
        k0 = p00 / innovation_var  # position gain
        k1 = p01 / innovation_var  # velocity gain
        innovation = z - pos

        self._pos = pos + k0 * innovation
        self._vel = vel + k1 * innovation
        self._p00 = p00 * (1.0 - k0)
        self._p01 = p01 * (1.0 - k0)
        self._p11 = p11 - k1 * p01
        return self._pos


class ScreenController:
    """
    Maps recognized gestures to real mouse / window actions via pyautogui.

    :param screen_width: Screen width in pixels. ``None`` = detect via
        ``pyautogui.size()`` (primary monitor).
    :param screen_height: Screen height in pixels. ``None`` = detect.
    :param active_zone: Central frame fraction (0.0 - 1.0) that maps to the
        full screen (``0.7`` = central 70%), *or* four margins
        ``(left, right, top, bottom)`` for an asymmetric zone - a smaller
        margin makes that screen edge easier to reach.
    :param smooth_factor: Cursor smoothing for the ``exponential`` filter,
        0.0 - 1.0. Higher = snappier, lower = smoother but laggier.
    :param cursor_filter: Cursor filter - ``"kalman"`` (default, smoothest),
        ``"exponential"`` or ``"none"``.
    :param kalman_q: Kalman process noise. Higher = trusts the hand motion
        more (snappier); lower = more smoothing.
    :param kalman_r: Kalman measurement noise. Higher = trusts the measured
        position less (smoother); lower = more responsive.
    :param pinch_button: Mouse button used by PINCH ("left", "middle", "right").
    :param pinch_debounce_frames: Consecutive PINCH frames required before
        the mouse button goes down - filters out accidental 1-2 frame flicks.
    :param window_drag_enabled: Allow FIST window dragging (Windows).
    :param title_bar_offset: Pixels below the window top where the cursor
        grabs the title bar.
    :param failsafe: Enable pyautogui's FAILSAFE (cursor to a corner raises).
        Defaults to ``False`` because camera control intentionally sends the
        cursor to screen edges. Keep it off and provide an emergency stop in
        your main loop (e.g. a keyboard quit) instead.
    """

    def __init__(
        self,
        *,
        screen_width: int | None = None,
        screen_height: int | None = None,
        active_zone: float | Sequence[float] = 0.7,
        smooth_factor: float = 0.4,
        cursor_filter: str = "kalman",
        kalman_q: float = 4.0,
        kalman_r: float = 60.0,
        pinch_button: str = "left",
        pinch_debounce_frames: int = 3,
        window_drag_enabled: bool = True,
        title_bar_offset: int = 20,
        failsafe: bool = False,
    ) -> None:
        if not 0.0 < smooth_factor <= 1.0:
            raise ValueError(f"smooth_factor must be in (0, 1], got {smooth_factor}")
        if cursor_filter not in ("kalman", "exponential", "none"):
            raise ValueError(
                "cursor_filter must be 'kalman', 'exponential' or 'none', "
                f"got {cursor_filter!r}"
            )
        if kalman_q < 0.0 or kalman_r <= 0.0:
            raise ValueError("kalman_q must be >= 0 and kalman_r must be > 0")

        # Camera control moves the cursor to screen edges on purpose, so
        # pyautogui's corner FAILSAFE would fire constantly - disable it.
        pyautogui.FAILSAFE = failsafe
        # pyautogui inserts a 0.1 s pause between actions by default, which
        # makes cursor tracking feel sluggish - remove it.
        pyautogui.PAUSE = 0.0

        self.active_zone = active_zone  # original value (fraction or margins)
        self._margins = self._parse_active_zone(active_zone)
        self.smooth_factor = smooth_factor
        self.cursor_filter = cursor_filter
        self.pinch_button = pinch_button
        self.pinch_debounce_frames = max(1, int(pinch_debounce_frames))
        self.window_drag_enabled = window_drag_enabled
        self.title_bar_offset = title_bar_offset

        detected = pyautogui.size()
        self.set_screen_size(
            screen_width if screen_width is not None else detected.width,
            screen_height if screen_height is not None else detected.height,
        )

        # Internal state.
        self._cursor: tuple[int, int] | None = None
        self._pinching = False
        self._pinch_press_frames = 0  # consecutive PINCH frames (press debounce)
        self._dragging_window: "gw.Window" | None = None
        self._kalman_x = _Kalman1D(kalman_q, kalman_r)
        self._kalman_y = _Kalman1D(kalman_q, kalman_r)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, gesture: str, landmarks: Landmarks) -> dict:
        """
        Process one frame: act on the recognized gesture.

        Call once per video frame, right after ``GestureRecognizer.recognize``.

        :param gesture: One of the ``GESTURE_*`` constants.
        :param landmarks: Landmarks from ``HandTracker.get_landmarks()``
            (may be ``None``/``[]`` when the hand was lost).
        :return: An info dict ``{"gesture", "action", "cursor"}`` useful for
            debugging or an on-screen overlay. ``cursor`` is the last cursor
            position or ``None``.
        """
        info: dict = {"gesture": gesture, "action": None, "cursor": self._cursor}

        if gesture == GESTURE_POINT:
            self._stop_window_drag()
            self._set_pinching(False)
            self._move_cursor(landmarks)
            info["action"] = "move_cursor"

        elif gesture == GESTURE_PINCH:
            self._stop_window_drag()
            info["action"] = self._set_pinching(True)
            self._move_cursor(landmarks)  # drag the content around

        elif gesture == GESTURE_FIST:
            self._set_pinching(False)
            info["action"] = self._start_window_drag()
            self._move_cursor(landmarks)  # the window follows the hand

        elif gesture in (GESTURE_OPEN_PALM, GESTURE_NONE):
            # Release everything and freeze the cursor.
            self._set_pinching(False)
            self._stop_window_drag()

        info["cursor"] = self._cursor
        return info

    def release_all(self) -> None:
        """Release any pressed mouse button / ongoing window drag.

        Safe to call on shutdown so the mouse is never left stuck down.
        """
        self._set_pinching(False)
        self._stop_window_drag()

    def set_screen_size(self, width: int, height: int) -> None:
        """Update the target screen size (e.g. after a resolution change)."""
        if width <= 0 or height <= 0:
            raise ValueError(f"screen size must be positive, got {width}x{height}")
        self.screen_width = width
        self.screen_height = height

    # ------------------------------------------------------------------
    # Cursor control
    # ------------------------------------------------------------------

    def _move_cursor(self, landmarks: Landmarks) -> bool:
        """Move the cursor to the index fingertip (smoothed). Returns False
        when no index tip is available."""
        tip = self._find_landmark(landmarks, "index_tip")
        if tip is None:
            return False
        target = self._map_to_screen(tip["x"], tip["y"])
        self._move_to(*target, smooth=True)
        return True

    def _move_to(self, x: int, y: int, *, smooth: bool) -> None:
        """Move the mouse, optionally through the selected cursor filter."""
        if smooth:
            x, y = self._filter_position(x, y)
        else:
            # A forced jump (e.g. grabbing a title bar) resets the Kalman
            # filters so the next smooth move starts from the real position.
            if self.cursor_filter == "kalman":
                self._kalman_x.reset(x)
                self._kalman_y.reset(y)
        pyautogui.moveTo(x, y)
        self._cursor = (x, y)

    def _filter_position(self, target_x: int, target_y: int) -> tuple[int, int]:
        """Apply the configured cursor filter to one target position."""
        if self.cursor_filter == "none":
            return target_x, target_y
        if self.cursor_filter == "exponential":
            return self._smooth(target_x, target_y)
        return (
            int(round(self._kalman_x.update(target_x))),
            int(round(self._kalman_y.update(target_y))),
        )

    def _smooth(self, target_x: int, target_y: int) -> tuple[int, int]:
        """Exponential moving average toward the target position."""
        if self._cursor is None:
            return target_x, target_y
        k = self.smooth_factor
        x = self._cursor[0] + k * (target_x - self._cursor[0])
        y = self._cursor[1] + k * (target_y - self._cursor[1])
        return int(round(x)), int(round(y))

    def _map_to_screen(self, nx: float, ny: float) -> tuple[int, int]:
        """
        Map a normalized camera coordinate to a screen coordinate.

        Only the central ``active_zone`` of the frame is used, so the whole
        screen maps into a smaller hand travel area and screen edges are
        reachable easily. Out-of-zone positions are clamped to the screen.
        """
        left, right, top, bottom = self._margins
        sx = (nx - left) / (1.0 - left - right) * self.screen_width
        sy = (ny - top) / (1.0 - top - bottom) * self.screen_height

        sx = min(max(sx, 0.0), self.screen_width - 1)
        sy = min(max(sy, 0.0), self.screen_height - 1)
        return int(round(sx)), int(round(sy))

    @staticmethod
    def _parse_active_zone(
        active_zone: float | Sequence[float],
    ) -> tuple[float, float, float, float]:
        """Normalize ``active_zone`` into ``(left, right, top, bottom)``
        margins. A single number yields a symmetric zone (the same margin on
        every side); a 4-sequence is used as margins directly."""
        if isinstance(active_zone, (int, float)):
            zone = float(active_zone)
            if not 0.0 < zone <= 1.0:
                raise ValueError(f"active_zone must be in (0, 1], got {zone}")
            margin = (1.0 - zone) / 2.0
            return (margin, margin, margin, margin)

        if isinstance(active_zone, str) or not isinstance(active_zone, Sequence):
            raise ValueError(
                "active_zone must be a fraction (0, 1] or 4 margins "
                "[left, right, top, bottom]"
            )

        values = [float(m) for m in active_zone]
        if len(values) != 4:
            raise ValueError(
                "active_zone must be a fraction (0, 1] or 4 margins "
                "[left, right, top, bottom]"
            )
        left, right, top, bottom = values
        if (
            left < 0.0
            or right < 0.0
            or top < 0.0
            or bottom < 0.0
            or left + right >= 1.0
            or top + bottom >= 1.0
        ):
            raise ValueError(f"invalid active_zone margins {values!r}")
        return (left, right, top, bottom)

    @staticmethod
    def _find_landmark(landmarks: Landmarks, name: str) -> dict | None:
        """Locate one landmark by name in either supported input format."""
        if not landmarks:
            return None
        if isinstance(landmarks, dict):
            return landmarks.get(name)
        for lm in landmarks:
            if lm.get("name") == name:
                return lm
        return None

    # ------------------------------------------------------------------
    # Pinch (mouse down / up)
    # ------------------------------------------------------------------

    def _set_pinching(self, pinching: bool) -> str | None:
        """Toggle the pinch button on gesture transitions only.

        Pressing is debounced: the button goes down only after PINCH has
        been stable for ``pinch_debounce_frames`` consecutive frames, so a
        brief flicker never causes an accidental click or drag. Releasing is
        immediate so a drag never gets stuck.
        """
        if pinching:
            if self._pinching:
                return None
            self._pinch_press_frames += 1
            if self._pinch_press_frames < self.pinch_debounce_frames:
                return None
            pyautogui.mouseDown(button=self.pinch_button)
            self._pinching = True
            self._pinch_press_frames = 0
            return "mouse_down"

        self._pinch_press_frames = 0
        if self._pinching:
            pyautogui.mouseUp(button=self.pinch_button)
            self._pinching = False
            return "mouse_up"
        return None

    # ------------------------------------------------------------------
    # Window drag (FIST, Windows)
    # ------------------------------------------------------------------

    def _start_window_drag(self) -> str | None:
        """Grab a window by its title bar (Windows).

        The active window (or the first draggable window under the cursor) is
        grabbed: the cursor moves to the centre of its title bar and the left
        button is pressed. While FIST stays active, the window follows the
        cursor. Returns the action name, or ``None`` if nothing was grabbed.
        """
        if self._dragging_window is not None or not self.window_drag_enabled:
            return None

        try:
            import pygetwindow as gw  # lazy import - only needed on Windows
        except ImportError:
            logger.warning(
                "pygetwindow is not installed - FIST window dragging is "
                "disabled. Install it with: pip install pygetwindow"
            )
            return None

        cursor_x, cursor_y = pyautogui.position()
        window = self._pick_window(gw, cursor_x, cursor_y)
        if window is None:
            logger.info("FIST: no draggable window under the cursor.")
            return None
        if getattr(window, "isMaximized", False):
            logger.info("FIST: window is maximized - cannot drag it.")
            return None

        title_x = window.left + window.width // 2
        title_y = window.top + self.title_bar_offset
        self._move_to(title_x, title_y, smooth=False)
        pyautogui.mouseDown()
        self._dragging_window = window
        logger.info("FIST: grabbing window '%s'", window.title)
        return "window_drag_start"

    def _stop_window_drag(self) -> str | None:
        """Release the grabbed window title bar."""
        if self._dragging_window is None:
            return None
        pyautogui.mouseUp()
        self._dragging_window = None
        logger.info("FIST: released window drag.")
        return "window_drag_end"

    @staticmethod
    def _pick_window(gw: "gw", x: int, y: int):
        """Choose a window to drag: prefer the active window (the one the
        user was just using), then the first draggable window under the
        cursor. ``getWindowsAt`` lists overlapping windows in enumeration
        order, so preferring the active window avoids grabbing a window that
        sits visually behind another one."""
        active = gw.getActiveWindow()
        if active is not None and ScreenController._is_draggable(active):
            return active
        if hasattr(gw, "getWindowsAt"):
            for window in gw.getWindowsAt(x, y):
                if ScreenController._is_draggable(window):
                    return window
        return None

    @staticmethod
    def _is_draggable(window) -> bool:
        """Reject shell / empty-title / maximized windows."""
        title = str(getattr(window, "title", "") or "").strip()
        if not title or title.lower() in _SHELL_TITLES:
            return False
        if getattr(window, "isMaximized", False):
            return False
        return True

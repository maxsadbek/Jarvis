"""
Test / demo script for the HandTracker module.

Opens the webcam and shows a live window with the detected hand landmarks
drawn on top of the video stream, plus a status line and an FPS counter.

Usage
-----
Run from the project root::

    python vision/test_hand_tracker.py            # default camera (0)
    python vision/test_hand_tracker.py 1          # camera index 1

Controls
--------
    Q or ESC  - close the window and exit
"""

from __future__ import annotations

import sys
import time

import cv2

# Import the tracker. When run as a script the ``vision`` package is not
# importable (unless run via ``python -m``), so fall back to the local import.
if __package__:
    from vision.hand_tracker import HAND_LANDMARKS, HandTracker
else:  # running directly:  python vision/test_hand_tracker.py
    from hand_tracker import HAND_LANDMARKS, HandTracker


def main() -> None:
    """Run the live hand-tracking demo."""
    # Optional camera index as a command-line argument.
    camera_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    tracker = HandTracker(camera_index=camera_index)
    print("JARVIS Hand Tracker demo - press Q or ESC to quit.")

    # FPS counter helpers.
    prev_time = time.perf_counter()
    fps = 0.0

    # Track state changes so we only print when a hand appears/disappears.
    hand_was_detected = False

    try:
        while True:
            hand_found, landmarks, frame = tracker.update()
            if frame is None:
                print("Failed to read frame from camera.")
                break

            # Status line: hand detected or not.
            status = "HAND DETECTED" if hand_found else "NO HAND"
            color = (0, 255, 0) if hand_found else (0, 0, 255)
            cv2.putText(
                frame,
                status,
                (15, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                color,
                2,
                cv2.LINE_AA,
            )

            # FPS counter.
            now = time.perf_counter()
            fps = 0.9 * fps + 0.1 * (1.0 / max(now - prev_time, 1e-6))
            prev_time = now
            cv2.putText(
                frame,
                f"FPS: {fps:.1f}",
                (15, 65),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            # Print once when the hand appears / disappears.
            if hand_found and not hand_was_detected:
                index_tip = landmarks[HAND_LANDMARKS["index_tip"]]
                print(
                    f"Hand detected | index tip: "
                    f"({index_tip['px']}, {index_tip['py']}) | FPS: {fps:.1f}"
                )
            elif not hand_found and hand_was_detected:
                print("Hand lost.")
            hand_was_detected = hand_found

            cv2.imshow("JARVIS - Hand Tracker", frame)

            # Quit on Q or ESC.
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
    finally:
        tracker.release()
        cv2.destroyAllWindows()
        print("Hand tracker closed.")


if __name__ == "__main__":
    main()

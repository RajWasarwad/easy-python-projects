import cv2
import time
from camera.camera import Camera
from camera.tracking import Tracker

# Constants
HFOV, VFOV = 60.0, 45.0
CROSSHAIR_OFFSET_X, CROSSHAIR_OFFSET_Y = 0, 0

# Use a dict for global settings to ensure real-time access in callbacks
settings = {"size": 100, "last_center": None}  # Stores (x, y) of the target

camera = Camera(src=0)
tracker = Tracker(tracker_type="CSRT")
camera.start()
time.sleep(2)


def click_event(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        current_frame = param["frame"]
        # Define ROI centered on click
        s = settings["size"]
        roi = (int(x - s // 2), int(y - s // 2), s, s)
        tracker.init(current_frame, roi)


cv2.namedWindow("Camera Frame")

while True:
    frame = camera.read()
    if frame is None:
        continue

    h, w = frame.shape[:2]
    marker_x, marker_y = (w // 2) + CROSSHAIR_OFFSET_X, (h // 2) - CROSSHAIR_OFFSET_Y

    # Update mouse callback with latest frame
    cv2.setMouseCallback("Camera Frame", click_event, param={"frame": frame})

    if tracker.initialized:
        success, bbox = tracker.track(frame)
        if success:
            tx, ty, tw, th = [int(v) for v in bbox]
            settings["last_center"] = (tx + tw // 2, ty + th // 2)

            # Display target info
            azimuth = ((settings["last_center"][0] - marker_x) / w) * HFOV
            elevation = ((settings["last_center"][1] - marker_y) / h) * VFOV

            cv2.rectangle(frame, (tx, ty), (tx + tw, ty + th), (255, 0, 0), 2)

            cv2.line(
                frame,
                (marker_x, marker_y),
                (settings["last_center"][0], settings["last_center"][1]),
                (0, 255, 0),
                1,
            )

            cv2.putText(
                frame,
                f"Az: {azimuth:.1f} El: {elevation:.1f}",
                (10, 60),
                0,
                0.6,
                (255, 255, 255),
                2,
            )

    # UI Elements
    cv2.drawMarker(frame, (marker_x, marker_y), (0, 255, 255), cv2.MARKER_CROSS, 20, 2)
    cv2.putText(
        frame, f"Tracker Size: {settings['size']}px", (10, 30), 0, 0.6, (0, 255, 255), 2
    )

    cv2.imshow("Camera Frame", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break

    # Handle Resize (Up: 82, Down: 84 on many systems, or use 'w'/'s')
    if key in [82, ord("w"), 84, ord("s")]:
        if key in [82, ord("w")]:
            settings["size"] += 10
        else:
            settings["size"] = max(20, settings["size"] - 10)

        # REAL-TIME UPDATE: If currently tracking, re-init with new size immediately
        if tracker.initialized and settings["last_center"]:
            cx, cy = settings["last_center"]
            s = settings["size"]
            new_roi = (int(cx - s // 2), int(cy - s // 2), s, s)
            tracker.init(frame, new_roi)

camera.stop()
cv2.destroyAllWindows()

import cv2


class Tracker:
    def __init__(self, tracker_type="KCF"):
        self.tracker_type = tracker_type
        self.tracker = None
        self.initialized = False

    def _create_tracker(self):
        # Re-create the tracker instance to allow re-initialization
        if self.tracker_type == "KCF":
            return cv2.TrackerKCF_create()
        elif self.tracker_type == "CSRT":
            return cv2.TrackerCSRT_create()  # Better accuracy than KCF
        elif self.tracker_type == "MIL":
            return cv2.TrackerMIL_create()
        raise ValueError("Unsupported tracker type")

    def init(self, frame, bbox):
        self.tracker = self._create_tracker()  # Always create fresh
        self.tracker.init(frame, bbox)
        self.initialized = True

    def track(self, frame):
        if not self.initialized:
            # Use a consistent window name
            roi = cv2.selectROI("Camera Frame", frame, fromCenter=False)

            if roi == (0, 0, 0, 0):  # Handle user canceling (pressing 'c')
                return False, None
            self.init(frame, roi)

        success, bbox = self.tracker.update(frame)
        if not success:
            self.initialized = False  # Trigger re-init on next loop
        return success, bbox

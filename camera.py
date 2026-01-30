import cv2
import threading
import time


class Camera:
    def __init__(self, src=0, width=640, height=480):
        self.src = src
        self.width = width
        self.height = height
        self.fps = 8
        self.cap = cv2.VideoCapture(self.src)
        # self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        # self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        self.captured = False

    def start(self):
        if self.running:
            return

        self.running = True
        threading.Thread(target=self.update, daemon=True).start()

    def update(self):
        start_time = time.time()
        while self.running:
            ret, frame = self.cap.read()
            current_time = time.time()
            fps = 1 / (current_time - start_time)
            start_time = current_time
            if not ret:
                continue

            with self.lock:
                # print(f"Frame captured @ FPS: {fps:.2f}")
                self.frame = frame
                self.captured = True

            time.sleep(0.01)  # avoid tight loop

    def read(self):
        with self.lock:
            # Return a copy of the current frame if it exists
            return self.frame.copy() if self.frame is not None else None

    def stop(self):
        self.running = False
        self.cap.release()

    def is_running(self):
        return "main cam running" if self.running else "main cam stopped"

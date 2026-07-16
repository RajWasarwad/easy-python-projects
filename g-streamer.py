Migrating from an HTTP-based Flask MJPEG stream to a hardware-optimized **GStreamer** pipeline is the best way to achieve ultra-low latency (sub-100ms) on an On-Board Computer (OBC). Flask introduces immense TCP overhead and lacks hardware-accelerated encoding, whereas GStreamer handles raw byte streams closer to the kernel level.

The cleanest, most integrated way to swap Flask for GStreamer inside your existing Python thread architecture is using OpenCV's `cv2.VideoWriter` configured with an **`appsrc`** GStreamer pipeline string. This injects your processed NumPy frames directly into a UDP network stream.

Here is the complete replacement for `app.py` using GStreamer.

---

### New `app.py` (GStreamer UDP Transmitter Node)

This script replaces Flask entirely. It sets up an independent thread that captures your shared system state, renders the tracker bounding box overlay if active, and pushes the raw frames into a zero-latency H.264 UDP pipeline.

```python
import cv2
import time
import threading

class Streamer:
    def __init__(self, state):
        self.state = state
        self.lock = threading.Lock()
        
        # Stream configuration
        self.host = "127.0.0.1"  # Change this to the IP of your ground station/receiving device
        self.port = 5000
        self.width = 640
        self.height = 480
        self.fps = 30
        
        self.writer = None
        self.running = False

    def _build_gstreamer_pipeline(self):
        """
        Constructs a zero-latency H.264 encoding UDP sink pipeline.
        Choose the pipeline string below based on your target hardware.
        """
        
        # OPTION A: Standard CPU-based encoding (Works everywhere)
        pipeline = (
            f"appsrc ! videoconvert ! "
            f"x264enc tune=zerolatency bitrate=2000 speed-preset=ultrafast ! "
            f"rtph264pay config-interval=1 pt=96 ! "
            f"udpsink host={self.host} port={self.port} sync=false"
        )
        
        # OPTION B: NVIDIA Jetson Hardware Accelerated Encoding (Highly Recommended for Jetson)
        # Uncomment the lines below if running on an embedded NVIDIA Jetson platform:
        # pipeline = (
        #     f"appsrc ! videoconvert ! video/x-raw, format=BGRx ! "
        #     f"nvvidconv ! video/x-raw(memory:NVMM), format=NV12 ! "
        #     f"nvv4l2h264enc maxperf-enable=1 bitrate=2000000 insert-sps-pps=true ! "
        #     f"rtph264pay config-interval=1 pt=96 ! "
        #     f"udpsink host={self.host} port={self.port} sync=false"
        # )
        
        return pipeline

    def generate_frames(self):
        frame_interval = 1.0 / self.fps
        
        while self.running and self.state.program.running:
            start_time = time.time()
            
            with self.lock:
                if self.state.camera.frame is None or isinstance(self.state.camera.frame, str):
                    time.sleep(0.005)
                    continue
                
                # Fetch fresh frame and current tracker status
                frame = self.state.camera.frame.copy()
                bbox = self.state.tracker.bbox
                tracker_active = self.state.tracker.initialized

            # Paint the tracker overlay onto the frame if tracking is running
            if tracker_active and bbox != (0, 0, 0, 0):
                p1 = (int(bbox[0]), int(bbox[1]))
                p2 = (int(bbox[0] + bbox[2]), int(bbox[1] + bbox[3]))
                cv2.rectangle(frame, p1, p2, (0, 255, 0), 2, 1)

            # Ensure the frame matches the exact dimensions the pipeline expects
            if frame.shape[1] != self.width or frame.shape[0] != self.height:
                frame = cv2.resize(frame, (self.width, self.height))

            # Push the raw frame into the GStreamer pipeline engine
            if self.writer and self.writer.isOpened():
                self.writer.write(frame)
                
            # Maintain stable target frame pacing
            elapsed = time.time() - start_time
            sleep_time = max(0.001, frame_interval - elapsed)
            time.sleep(sleep_time)

    def run(self):
        """Initializes the GStreamer VideoWriter and spins up the processing thread."""
        pipeline_string = self._build_gstreamer_pipeline()
        
        # Initialize OpenCV VideoWriter with GStreamer backend preference
        self.writer = cv2.VideoWriter(
            pipeline_string, 
            cv2.CAP_GSTREAMER, 
            0, 
            self.fps, 
            (self.width, self.height), 
            True
        )
        
        if not self.writer.isOpened():
            print("❌ Critical Error: Could not initialize OpenCV GStreamer Writer. Check if OpenCV is compiled with GStreamer support.")
            return

        print(f"🚀 GStreamer Pipeline Active! Streaming UDP H.264 payloads to {self.host}:{self.port}")
        self.running = True
        threading.Thread(target=self.generate_frames, daemon=True).start()

    def stop(self):
        self.running = False
        if self.writer:
            self.writer.release()

```

---

## 📺 How to Receive and View the Stream

Because UDP streams do not contain a container file format (like `.mp4`), standard media players cannot just open the URL. You have to tell the receiving device how to interpret the incoming H.264 packets.

### Method 1: Using the command line (Lowest Latency)

Run this command on your destination machine (the computer running at `self.host` IP address) to open an instant, zero-buffer preview window:

```bash
gst-launch-1.0 -v udpsrc port=5000 caps = "application/x-rtp, media=(string)video, clock-rate=(integer)90000, encoding-name=(string)H264, payload=(integer)96" ! rtph264depay ! decodebin ! videoconvert ! autovideosink sync=false

```

### Method 2: Using VLC Media Player

1. Create a text file on your receiving machine named `stream.sdp`.
2. Paste the following network configuration details inside it:
```text
v=0
o=- 0 0 IN IP4 127.0.0.1
s=GStreamer Video Stream
c=IN IP4 127.0.0.1
t=0 0
m=video 5000 RTP/AVP 96
a=rtpmap:96 H264/90000

```


3. Open `stream.sdp` directly using VLC. *(Note: Modify `127.0.0.1` inside the file to your actual receiving IP address if testing across separate computers).*

### ⚠️ Dependency Requirement

For this code to run, your target environment needs `opencv-python` built with GStreamer support enabled. You can verify if your system is ready by running this quick test command in your terminal:

```bash
python3 -c "import cv2; print(cv2.getBuildInformation())" | grep -i gstreamer

```

If you see `GStreamer: YES`, your system is fully optimized and ready to execute this zero-latency pipeline.



------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

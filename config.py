import os

# Camera Settings
RTSP_MAIN = "rtsp://admin:Abu2912112@10.10.2.75:554/Streaming/Channels/101"
RTSP_SUB = "rtsp://admin:Abu2912112@10.10.2.75:554/Streaming/Channels/102"

# ROI (x, y, width, height)
# Set to None to scan the full frame with YOLO
ROI = None

# Processing
FRAME_SKIP = 5
OCR_CONFIDENCE = 20
PLATE_REGEX = r"(?:\b|^)([A-Z0-9]{1,4})[ \-]*([A-Z0-9]{3,4})(?:\b|$)"

# Auto-exit detection window
AUTO_EXIT_HOURS = 8

# Directory and Database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "anpr.db")
IMAGE_SAVE_DIR = os.path.join(BASE_DIR, "captured_plates")

if not os.path.exists(IMAGE_SAVE_DIR):
    os.makedirs(IMAGE_SAVE_DIR)

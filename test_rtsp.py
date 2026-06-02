import cv2
import os

url = "rtsp://admin:Abu2912112@10.10.2.75:554/Streaming/Channels/101"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

print("Trying to open main stream...")
cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
if not cap.isOpened():
    print("Failed to open stream.")
else:
    print("Stream opened successfully.")
    ret, frame = cap.read()
    if ret:
        print("Read first frame successfully, shape:", frame.shape)
    else:
        print("Failed to read first frame.")
    cap.release()

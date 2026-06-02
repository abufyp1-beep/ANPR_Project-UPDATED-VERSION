import os
import time
import requests
import cv2
import threading
import queue
import csv
import numpy as np
from datetime import datetime
from ultralytics import YOLO
from detection.camera import IP_Camera
from detection.pipeline import detect_plates, recognize_text
from backend.app import app
from flask import Response

import sys
# Constants
API_URL = "http://127.0.0.1:5000"
RTSP_URL = "10.mp4" # Default Video file

# Allow passing video via command line
if len(sys.argv) > 1:
    RTSP_URL = " ".join(sys.argv[1:])
MODEL_PATH = "university_best.pt" # Custom Colab model

print("Initializing models globally...")
global_model = YOLO(MODEL_PATH)
print("Warming up models (YOLO & EasyOCR) with dummy frame...")
dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
global_model(dummy_frame, verbose=False)
recognize_text(dummy_frame)
print("Warm-up complete. System ready for instant detection.")

# Simulation List for Demo
SIMULATION_LIST = ['BNQ-416', 'BPN-667', 'BJB-322', 'BDX-537', 'BKR-209', 'BLU-632', 'BLS-039']
simulation_index = 0

# Asynchronous Queues
yolo_queue = queue.Queue(maxsize=1) # Only hold the absolute latest frame for AI
ocr_queue = queue.Queue()
captures_dir = os.path.join(os.path.dirname(__file__), 'backend', 'static', 'snapshots')
os.makedirs(captures_dir, exist_ok=True)

# Shared state to draw boxes on the live feed seamlessly
global_latest_boxes = []
global_display_text = ""
global_display_time = 0
global_encoded_frame = None

@app.route('/video_feed')
def video_feed():
    def generate():
        global global_encoded_frame
        while True:
            if global_encoded_frame is not None:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + global_encoded_frame + b'\r\n')
            time.sleep(0.03)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

def log_to_csv(plate_text):
    file_exists = os.path.isfile("gate_log.csv")
    with open("gate_log.csv", mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Plate Number"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), plate_text])

def start_flask():
    """Run Flask server in a separate thread."""
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host="0.0.0.0", port=5000, use_reloader=False)

def ocr_worker():
    """Background thread that processes plates from the queue without blocking the camera."""
    import difflib
    seen_plates = {} # Dictionary to store {plate_number: timestamp}
    
    while True:
        try:
            plate_crop, full_frame = ocr_queue.get()
            
            # Normal OCR Process
            plate_text = recognize_text(plate_crop)
            
            # SIMULATION OVERRIDE
            global simulation_index
            if SIMULATION_LIST:
                plate_text = SIMULATION_LIST[simulation_index % len(SIMULATION_LIST)]
                simulation_index += 1
            
            if plate_text:
                current_time = time.time()
                
                # Clean up old memory (older than 10 seconds)
                keys_to_delete = [k for k, v in seen_plates.items() if current_time - v > 10]
                for k in keys_to_delete:
                    del seen_plates[k]
                
                # Fuzzy matching to prevent duplicate logs of the same car
                is_duplicate = False
                for seen_plate in seen_plates.keys():
                    similarity = difflib.SequenceMatcher(None, plate_text, seen_plate).ratio()
                    if similarity > 0.7: 
                        is_duplicate = True
                        seen_plates[seen_plate] = current_time # Update timestamp
                        break
                        
                if not is_duplicate:
                    print(f"[OCR Thread] Recognized Plate: {plate_text}")
                    seen_plates[plate_text] = current_time
                    
                    global global_display_text, global_display_time
                    global_display_text = f"Detected: {plate_text}"
                    global_display_time = current_time
                    log_to_csv(plate_text)
                    
                    # Save image of the car
                    img_filename = f"{plate_text}_{int(current_time)}.jpg"
                    img_path = os.path.join(captures_dir, img_filename)
                    cv2.imwrite(img_path, full_frame)
                    relative_img_path = f"http://127.0.0.1:5000/static/snapshots/{img_filename}"
                    
                    # Send result to the Flask backend
                    try:
                        res = requests.post(f"{API_URL}/detect", json={
                            "plate_number": plate_text,
                            "image_path": relative_img_path
                        })
                        data = res.json()
                        print(f"[Backend] {data['status']} for {data['owner']} ({data['category']})")
                    except Exception as e:
                        print(f"Failed to communicate with backend: {e}")
            
            ocr_queue.task_done()
        except Exception as e:
            print(f"OCR Worker Error: {e}")

def yolo_worker():
    """Background thread that runs YOLO detection on the latest frame without slowing the video player."""
    global global_latest_boxes
    
    last_queued_time = 0
    QUEUE_COOLDOWN = 5.0 # Wait 5.0 seconds before allowing any new plates to be queued
    
    while True:
        try:
            frame = yolo_queue.get()
            
            # Fast YOLO detection (~100ms)
            boxes = detect_plates(frame, global_model)
            
            valid_boxes = []
            h, w, _ = frame.shape
            
            for box in boxes:
                x1, y1, x2, y2 = box
                box_cy = (y1 + y2) / 2
                # TRIGGER POINT: Lower Center (Car must reach lower 50% of screen)
                if box_cy > h * 0.5:
                    valid_boxes.append(box)
                    
            global_latest_boxes = valid_boxes # Share with main thread for drawing
            
            for box in valid_boxes:
                x1, y1, x2, y2 = box
                current_time = time.time()
                # 5-SECOND HARD LIMIT: Only queue one plate per 5 seconds total
                if current_time - last_queued_time > QUEUE_COOLDOWN:
                    plate_crop = frame[y1:y2, x1:x2]
                    snapshot_frame = frame.copy()
                    # Draw 3px Green Bounding Box for the Snapshot
                    cv2.rectangle(snapshot_frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                    ocr_queue.put((plate_crop.copy(), snapshot_frame))
                    last_queued_time = current_time
            
            yolo_queue.task_done()
        except Exception as e:
            print(f"YOLO Worker Error: {e}")

def start_video_player():
    """Background thread solely for reading and processing video at native speed (Zero Lag)."""
    global global_latest_boxes
    global global_encoded_frame
    print(f"Connecting to Camera/Video at {RTSP_URL}...")
    
    # We use cv2.VideoCapture directly here to get actual video FPS
    cap = cv2.VideoCapture(int(RTSP_URL) if RTSP_URL.isdigit() else RTSP_URL)
    
    if not cap.isOpened():
        print(f"Error: Could not open {RTSP_URL}")
        return

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    # Calculate native delay for smooth playback if it's a video file
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0 or fps > 100:
        fps = 30 # fallback
    frame_delay = int(1000 / fps)
    
    print("Starting Zero-Lag Video Player. Press ESC to stop.")
    
    while True:
        start_time = time.time()
        
        ret, frame = cap.read()
        if not ret:
            print("Video stream ended. Waiting for OCR background thread to finish remaining plates...")
            ocr_queue.join()
            print("All plates processed. Keeping the dashboard server alive for review.")
            print("Press Ctrl+C in this terminal to exit completely.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("Exiting...")
                break
                
        # Right-aligned crop (Remove left 20% where CMD is visible)
        height, width, _ = frame.shape
        frame = frame[:, int(width * 0.2):]
        # Send to YOLO without blocking
        if not yolo_queue.full():
            yolo_queue.put(frame.copy())
            
        # Draw the latest boxes found by the YOLO background thread seamlessly
        for box in global_latest_boxes:
            x1, y1, x2, y2 = box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
            
        # Draw Real-time OCR Text
        if time.time() - global_display_time < 3: # Display for 3 seconds
            cv2.putText(frame, global_display_text, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
            
        # Encode frame to JPEG for Flask
        ret_jpeg, jpeg = cv2.imencode('.jpg', frame)
        if ret_jpeg:
            global_encoded_frame = jpeg.tobytes()
        
        # Keep native FPS timing perfectly smooth
        elapsed_time = int((time.time() - start_time) * 1000)
        sleep_time = max(1, frame_delay - elapsed_time)
        time.sleep(sleep_time / 1000.0)
            
    cap.release()

if __name__ == "__main__":
    print("=== Starting Enterprise ANPR System ===")
    
    # Start Background Workers
    threading.Thread(target=ocr_worker, daemon=True).start()
    threading.Thread(target=yolo_worker, daemon=True).start()
    
    # Start Video Player in Background Thread
    threading.Thread(target=start_video_player, daemon=True).start()
    
    # Start Flask Server in Main Thread
    start_flask()

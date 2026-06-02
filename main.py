import os

# Limit CPU threads for heavy ML libraries to prevent starving RTSP camera threads
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["VECLIB_MAXIMUM_THREADS"] = "2"
os.environ["NUMEXPR_NUM_THREADS"] = "2"

import time
import threading
from database.db import init_db
from camera.capture import VideoCaptureThread
from camera.motion import MotionDetector
from ocr.recognizer import OCRProcessor
from web.app import run_server
import config

def main():
    print("=== University Gate ANPR System ===")
    print("[1] Initializing Database...")
    init_db()

    print("[2] Connecting to Cameras...")
    # Thread A: Video Capture (Sub-stream for monitoring, Main for OCR)
    sub_stream_thread = VideoCaptureThread(config.RTSP_SUB, name="SubStream", is_main=False)
    main_stream_thread = VideoCaptureThread(config.RTSP_MAIN, name="MainStream", is_main=True)
    
    sub_stream_thread.start()
    main_stream_thread.start()

    print("[3] Starting OCR Processor...")
    # Thread B: OCR Processing
    ocr_thread = OCRProcessor(main_stream_thread)
    ocr_thread.start()

    print("[4] Starting Web UI...")
    # Thread C: Web Server (Flask)
    web_thread = threading.Thread(target=run_server, daemon=True)
    web_thread.start()

    # Main Loop: Motion Detection processing
    motion_detector = MotionDetector()
    frame_count = 0
    last_frame_id = -1

    print("System fully active. Monitoring for motion...")
    try:
        while True:
            # We process motion on the sub stream to save CPU
            frame, current_frame_id = sub_stream_thread.get_latest_frame_with_id()
            if frame is not None and current_frame_id != last_frame_id:
                last_frame_id = current_frame_id
                frame_count += 1
                
                # Apply frame skip for optimization
                if frame_count % config.FRAME_SKIP == 0:
                    if frame_count % (config.FRAME_SKIP * 100) == 0:
                        print(f"[System Heartbeat] Camera is live and streaming successfully... (Frame {frame_count})")
                    
                    if motion_detector.detect(frame):
                        print("[Motion] Movement detected in ROI! Triggering OCR...")
                        ocr_thread.trigger()
            
            # Sleep slightly to prevent 100% CPU lock
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("\n[Shutdown] Stopping threads...")
    finally:
        sub_stream_thread.stop()
        main_stream_thread.stop()
        ocr_thread.stop()
        sub_stream_thread.join()
        main_stream_thread.join()
        ocr_thread.join()
        print("Shutdown complete.")

if __name__ == "__main__":
    main()

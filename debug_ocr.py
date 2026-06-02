import cv2
import sys
import easyocr
import pytesseract
from ocr.preprocessor import preprocess_for_ocr, basic_preprocessing
import config

print("Connecting to camera stream...")
cap = cv2.VideoCapture(config.RTSP_MAIN)
ret, frame = cap.read()
if ret:
    print("Frame grabbed successfully.")
    cv2.imwrite("debug_raw.jpg", frame)
    print("Saved raw frame to debug_raw.jpg")

    # Run YOLO to detect vehicles
    from ultralytics import YOLO
    print("Loading YOLOv8 model...")
    yolo_model = YOLO("yolov8n.pt")

    print("Running YOLO inference...")
    results = yolo_model(frame, classes=[2, 3, 5, 7], verbose=False)

    annotated = frame.copy()
    vehicle_count = len(results[0].boxes)
    print(f"Detected {vehicle_count} vehicles.")

    for i, box in enumerate(results[0].boxes):
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        conf = float(box.conf[0])
        label = f"Vehicle {i} ({conf:.0%})"
        print(f"  -> {label} at ({x1},{y1}) to ({x2},{y2})")

        # Draw bounding box on annotated frame
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 3)
        cv2.putText(annotated, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        # Save vehicle crop (debug_roi_0.jpg, debug_roi_1.jpg, ...)
        vehicle_crop = frame[y1:y2, x1:x2]
        crop_path = f"debug_roi_{i}.jpg"
        cv2.imwrite(crop_path, vehicle_crop)
        print(f"    Saved vehicle crop to {crop_path}")

        # Preprocessing and OCR test
        location, processed = preprocess_for_ocr(vehicle_crop)
        if location is None:
            processed = basic_preprocessing(vehicle_crop)

        proc_path = f"debug_processed_{i}.jpg"
        cv2.imwrite(proc_path, processed)
        print(f"    Saved processed frame to {proc_path}")

        custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-'
        tess_text = pytesseract.image_to_string(processed, config=custom_config).strip()
        print(f"    [Tesseract] Raw: '{tess_text}'")

        ocr_results = easyocr.Reader(['en'], gpu=False).readtext(processed)
        for (bbox, text, prob) in ocr_results:
            if prob * 100 >= config.OCR_CONFIDENCE:
                print(f"    [EasyOCR] Text: '{text}' (confidence: {prob:.0%})")

    # Save fully annotated frame showing what YOLO sees
    cv2.imwrite("debug_annotated.jpg", annotated)
    print("Saved annotated frame (with bounding boxes) to debug_annotated.jpg")

    # Also update legacy debug_roi.jpg and debug_processed.jpg from the first vehicle found
    if vehicle_count > 0:
        first_box = results[0].boxes[0]
        x1, y1, x2, y2 = map(int, first_box.xyxy[0])
        first_crop = frame[y1:y2, x1:x2]
        cv2.imwrite("debug_roi.jpg", first_crop)
        print("Updated debug_roi.jpg with first detected vehicle crop")

        loc, first_processed = preprocess_for_ocr(first_crop)
        if loc is None:
            first_processed = basic_preprocessing(first_crop)
        cv2.imwrite("debug_processed.jpg", first_processed)
        print("Updated debug_processed.jpg with preprocessed version of first vehicle")

    if vehicle_count == 0:
        print("No vehicles detected. Camera may not be pointed at a vehicle right now.")
else:
    print("Failed to grab frame from camera stream.")

cap.release()

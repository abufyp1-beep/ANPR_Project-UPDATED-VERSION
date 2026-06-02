import cv2
import sys
import easyocr
import pytesseract
from ocr.preprocessor import basic_preprocessing
from ocr.validator import validate_plate
import config

def test_image(image_path):
    print(f"Testing image: {image_path}")
    frame = cv2.imread(image_path)
    if frame is None:
        print("Error: Could not read image.")
        return

    # Skip contour detection for a pre-cropped license plate, use basic preprocessing
    processed_image = basic_preprocessing(frame)

    print("\n--- Try 1: PyTesseract ---")
    custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-'
    tess_text = pytesseract.image_to_string(processed_image, config=custom_config).strip()
    print(f"Raw Output: '{tess_text}'")
    val = validate_plate(tess_text)
    print(f"Validation Result: {val}")

    print("\n--- Try 2: EasyOCR ---")
    reader = easyocr.Reader(['en'], gpu=False)
    plate_chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ- '
    ocr_results = reader.readtext(processed_image, allowlist=plate_chars)
    # Sort bounding boxes horizontally (left-to-right) to ensure correct concatenation order
    ocr_results.sort(key=lambda x: x[0][0][0])
    print(f"Raw Output: {ocr_results}")

    valid_texts = [text for (bbox, text, prob) in ocr_results if prob * 100 >= config.OCR_CONFIDENCE]
    print(f"Texts with >{config.OCR_CONFIDENCE}% confidence: {valid_texts}")

    validated_plate = None
    if valid_texts:
        combined_text = " ".join(valid_texts)
        val = validate_plate(combined_text)
        print(f"Combined validation for '{combined_text}': {val}")
        if val:
             validated_plate = val

    if not validated_plate:
        for text in valid_texts:
            val = validate_plate(text)
            print(f"Individual validation for '{text}': {val}")
            if val and not validated_plate:
                validated_plate = val

    print(f"\nFinal Chosen Plate: {validated_plate}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_ocr.py <image_path>")
    else:
        test_image(sys.argv[1])

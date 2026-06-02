import sys
import os

# Ensure we can import from ocr
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ocr.validator import validate_plate

print("--- Image 1: White Honda City (Plate: BQE 780, SINDH) ---")
print("1. PyTesseract Output (Concatenated): 'BQE780SINDH'")
print(f"   Validation Result: {validate_plate('BQE780SINDH')}")
print("2. EasyOCR Output (Separated): 'BQE 780' and 'SINDH'")
print(f"   Validation Result ('BQE 780'): {validate_plate('BQE 780')}")
print(f"   Validation Result ('SINDH'): {validate_plate('SINDH')}")

print("\n--- Image 2: Black Toyota Pixis (Plate: BWQ 016, SINDH) ---")
print("1. PyTesseract Output (Concatenated): 'BWQ016SINDH'")
print(f"   Validation Result: {validate_plate('BWQ016SINDH')}")
print("2. EasyOCR Output (Separated): 'BWQ 016' and 'SINDH'")
print(f"   Validation Result ('BWQ 016'): {validate_plate('BWQ 016')}")
print(f"   Validation Result ('SINDH'): {validate_plate('SINDH')}")

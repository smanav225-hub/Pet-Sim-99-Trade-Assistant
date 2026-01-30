import cv2
import numpy as np
import os
import sys
from PIL import Image, ImageEnhance

# Constants
EXCLUSIVE_HEXES = ["#331f4c", "#392652", "#382550"]

def hex_to_bgr(hex_code):
    hex_code = hex_code.lstrip('#')
    r, g, b = int(hex_code[0:2], 16), int(hex_code[2:4], 16), int(hex_code[4:6], 16)
    return [b, g, r]

def process_name_detection(input_path, output_path):
    if not os.path.exists(input_path):
        print(f"Error: Input file {input_path} not found.")
        sys.exit(1)

    # Load capture1
    capture1 = cv2.imread(input_path)
    if capture1 is None:
        print("Error: Could not decode image.")
        sys.exit(1)

    height, width = capture1.shape[:2]
    top_limit = int(height * 0.25)
    roi = capture1[0:top_limit, 0:width]
    
    # Detect "Exclusive" tag using multiple colors
    e_mask = np.zeros(roi.shape[:2], dtype=np.uint8)
    for h in EXCLUSIVE_HEXES:
        bgr = hex_to_bgr(h)
        # Use slightly wider range (+/- 4) for better detection
        lower = np.array([max(0, bgr[0]-4), max(0, bgr[1]-4), max(0, bgr[2]-4)])
        upper = np.array([min(255, bgr[0]+4), min(255, bgr[1]+4), min(255, bgr[2]+4)])
        e_mask = cv2.bitwise_or(e_mask, cv2.inRange(roi, lower, upper))

    coords = cv2.findNonZero(e_mask)
    if coords is not None:
        pts = coords.reshape(-1, 2)
        
        # Find the LOWEST Y coordinate value (the TOP-most point of the detected pixels)
        # We want to crop everything ABOVE the "Exclusive" tag.
        min_y = np.min(pts[:, 1])
        
        # Crop from the TOP (0) to that top-most point (min_y)
        # Subtracting a buffer (-2 px) to ensure the tag is completely removed
        final_y = max(0, min_y - 2)
        name_crop = capture1[0:final_y, 0:width]
        print(f"[INFO] Name anchor found. Cropping above tag at Y={min_y}")
    else:
        # Fallback: Capture top 25% if no tag anchor found
        fallback_limit = int(height * 0.25)
        name_crop = capture1[0:fallback_limit, 0:width]
        print("[INFO] Name anchor NOT found. Using fallback 25% crop.")

    # Safety check: If crop is empty (e.g., tag detected at very top or fallback failed)
    if name_crop is None or name_crop.size == 0:
        print("[WARN] Name crop is empty. Converting original capture1 instead.")
        name_crop = capture1

    # Enhancement for OCR
    # Convert BGR to RGB for PIL
    try:
        pil_img = Image.fromarray(cv2.cvtColor(name_crop, cv2.COLOR_BGR2RGB)).convert('L')
    except cv2.error:
        print("[ERROR] OpenCV Conversion Failed. Skipping enhancement.")
        return
    pil_img = ImageEnhance.Contrast(pil_img).enhance(3.0)
    pil_img = ImageEnhance.Sharpness(pil_img).enhance(2.5)
    
    # Save result
    # Convert back to numpy if needed or just save via PIL (PIL is easier)
    pil_img.save(output_path)
    print(f"[FILES] Saved {output_path} (Name Snip)")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python name_detection.py <input_path> <output_path>")
        sys.exit(1)
        
    input_p = sys.argv[1]
    output_p = sys.argv[2]
    
    process_name_detection(input_p, output_p)

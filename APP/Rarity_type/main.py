import os
import sys
import cv2
import numpy as np

# Add current directory to path so steps can be imported
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

# Import modular logic
import step1 as s1
import step2 as s2
import step3 as s3
import step4 as s4
import step5 as s5
import step6 as s6

def detect_variant(input_image, output_crop_path):
    """
    Detects the variant of a pet (Golden, Rainbow, Shiny) from a capture image.
    Saves the analysis crop to output_crop_path.
    Returns: string (e.g., 'GOLDEN SHINY', 'RAINBOW', 'NORMAL')
    """
    if not os.path.exists(input_image):
        print(f"[VAR-DET] Error: {input_image} not found.")
        return "NORMAL"

    img = cv2.imread(input_image)
    if img is None:
        return "NORMAL"

    golden_hexes = ["#feed4f", "#ffdf33", "#fee844"]
    golden_bgrs = [s1.hex_to_bgr(h) for h in golden_hexes]

    # --- 1. INITIAL CHECK: GOLDEN ---
    is_golden = False
    for bgr in golden_bgrs:
        # Apply +/- 2 tolerance
        lower = np.array([max(0, c-2) for c in bgr], dtype=np.uint8)
        upper = np.array([min(255, c+2) for c in bgr], dtype=np.uint8)
        mask = cv2.inRange(img, lower, upper)
        if cv2.countNonZero(mask) > 0:
            is_golden = True
            break
    
    if is_golden:
        print("[VAR-DET] GOLDEN detected.")
        is_shiny, _ = s4.detect_shiny(img)
        # For Golden, we just save the full-ish card as the debug image
        cv2.imwrite(output_crop_path, img) 
        
        status = ["GOLDEN"]
        if is_shiny: status.append("SHINY")
        return " ".join(status)

    # --- 2. FALLBACK: RAINBOW PIPELINE ---
    # Step 1: Exclusive Bottom
    excl_bottom = s1.get_exclusive_bottom(input_image)
    if excl_bottom is None:
        return "NORMAL"

    # Step 2: Gray Description Top
    # ADDED internal cropping: only search BELOW exclusive tag
    gray_top = s2.get_gray_top(input_image, excl_bottom)
    if gray_top is None:
        # Fallback buffer if gray text is missing
        gray_top = excl_bottom + 40 

    # Step 3: Crop ROI & Detect Shiny
    variant_roi, is_shiny = s3.crop_middle(input_image, excl_bottom, gray_top)
    if variant_roi is None:
        return "NORMAL"

    # Step 6: Entropy Analysis (Rainbow)
    is_rainbow_entropy, variety = s6.detect_rainbow_entropy(variant_roi)

    # Step 5: Save Crop & Verification
    final_text_from_s5 = s5.analyze_and_save(variant_roi, is_shiny, output_crop_path)
    
    # Compose final verdict using Entropy result
    result_parts = []
    if is_shiny: result_parts.append("SHINY")
    if is_rainbow_entropy: result_parts.append("RAINBOW")
    
    final_verdict = " ".join(result_parts) if result_parts else "NORMAL"
    print(f"[VAR-DET] Final Result: {final_verdict}")
    
    return final_verdict

if __name__ == "__main__":
    # Standalone Test Logic
    if len(sys.argv) > 1:
        test_img = sys.argv[1]
        output_img = sys.argv[2] if len(sys.argv) > 2 else "capture3.png"
        res = detect_variant(test_img, output_img)
        print(f"RESULT: {res}")
    else:
        print("Usage: python main.py <input_image_path> [output_image_path]")

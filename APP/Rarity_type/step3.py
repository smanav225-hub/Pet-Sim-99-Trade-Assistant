import cv2
import os
import sys

import cv2
import numpy as np
import os

def hex_to_bgr(hex_code):
    hex_code = hex_code.lstrip('#')
    r, g, b = int(hex_code[0:2], 16), int(hex_code[2:4], 16), int(hex_code[4:6], 16)
    return (b, g, r)

def crop_middle(image_path, exclusive_bottom, gray_top):
    img = cv2.imread(image_path)
    if img is None:
        return None, False
    
    # 1. Define the full span search area (Exclusive to Gray)
    # We use min/max to be safe on ordering
    y_min = min(exclusive_bottom, gray_top)
    y_max = max(exclusive_bottom, gray_top)
    
    search_roi = img[y_min : y_max, :]
    
    # 2. Check for Shiny pixels in this span
    shiny_hexes = ["#f9d5f0", "#ffd9d6", "#ffdacf"]
    shiny_bgrs = [hex_to_bgr(h) for h in shiny_hexes]
    
    shiny_mask = np.zeros(search_roi.shape[:2], dtype=np.uint8)
    for bgr in shiny_bgrs:
        # Using +/- 2 tolerance for robustness
        lower = np.array([max(0, c-2) for c in bgr], dtype=np.uint8)
        upper = np.array([min(255, c+2) for c in bgr], dtype=np.uint8)
        shiny_mask = cv2.bitwise_or(shiny_mask, cv2.inRange(search_roi, lower, upper))
        
    shiny_pixels = cv2.countNonZero(shiny_mask)
    is_shiny = shiny_pixels >= 4 # Sensitivity boost
    
    # 3. Determine the final crop's bottom boundary
    final_end_y = y_max
    
    if is_shiny:
        # Find the TOP (Min Y) of the shiny text relative to search_roi
        coords = cv2.findNonZero(shiny_mask)
        if coords is not None:
            local_min_y = np.min(coords.reshape(-1, 2)[:, 1])
            # The crop should end right before Shiny starts to isolate Rainbow
            final_end_y = y_min + local_min_y
            print(f"[STEP 3] Shiny detected! Truncating crop at local Y={local_min_y} (Global Y={final_end_y})")
    
    # 4. Perform the final crop
    # Ensure some minimum height for analysis
    if final_end_y <= y_min + 5:
        print("[STEP 3] ROI too small after truncation. Using default span.")
        final_end_y = y_max
        
    cropped = img[y_min : final_end_y, :]
    print(f"[STEP 3] Final Crop Height: {cropped.shape[0]}px (Y: {y_min}-{final_end_y})")
    
    return cropped, is_shiny

if __name__ == "__main__":
    # Test only if needed
    pass

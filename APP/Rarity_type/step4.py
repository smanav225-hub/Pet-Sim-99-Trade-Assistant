import cv2
import numpy as np

def hex_to_bgr(hex_code):
    hex_code = hex_code.lstrip('#')
    r, g, b = int(hex_code[0:2], 16), int(hex_code[2:4], 16), int(hex_code[4:6], 16)
    return (b, g, r)

def detect_shiny(roi):
    if roi is None or roi.size == 0:
        return False, 0
    
    shiny_hexes = ["#f9d5f0", "#ffd9d6", "#ffdacf"]
    shiny_bgrs = [hex_to_bgr(h) for h in shiny_hexes]
    
    mask = np.zeros(roi.shape[:2], dtype=np.uint8)
    for bgr in shiny_bgrs:
        # Apply +/- 2 tolerance
        lower = np.array([max(0, c-2) for c in bgr], dtype=np.uint8)
        upper = np.array([min(255, c+2) for c in bgr], dtype=np.uint8)
        mask = cv2.bitwise_or(mask, cv2.inRange(roi, lower, upper))
        
    pixel_count = cv2.countNonZero(mask)
    is_shiny = pixel_count >= 4
    
    if is_shiny:
        print(f"[STEP 4] Shiny DETECTED (Pixels: {pixel_count})")
    else:
        print(f"[STEP 4] No Shiny pixels found ({pixel_count})")
        
    return is_shiny, pixel_count
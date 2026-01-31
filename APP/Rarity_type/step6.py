import cv2
import numpy as np

def detect_rainbow_entropy(roi):
    """
    Analyzes an ROI to find 'Rainbow Entropy'.
    Rainbow text is identified by a high density of UNIQUE colors in a small area.
    """
    if roi is None or roi.size == 0 or roi.shape[0] < 10:
        return False, 0

    h, w = roi.shape[:2]
    
    # --- STEP 1: Area Filtering (20-80% height focus) ---
    # We focus on the middle to ignore any edge noise from the anchors
    y_start = int(h * 0.15)
    y_end = int(h * 0.85)
    core_roi = roi[y_start:y_end, :]
    
    if core_roi.size == 0:
        return False, 0

    # --- STEP 2: Color Variety Check (Entropy) ---
    # We flatten the pixels to a list of (R,G,B)
    pixels = core_roi.reshape(-1, 3)
    
    # We filter for 'Colorful' pixels only (to ignore the dark background)
    # Saturated pixels only
    hsv = cv2.cvtColor(core_roi, cv2.COLOR_BGR2HSV)
    sat_mask = cv2.inRange(hsv, np.array([0, 50, 50]), np.array([179, 255, 255]))
    colorful_pixels = core_roi[sat_mask > 0]
    
    if len(colorful_pixels) < 50:
        print("[STEP 6] Density Check: Too few colorful pixels found.")
        return False, 0

    # Convert to a tuple list so we can find unique ones
    unique_colors = np.unique(colorful_pixels, axis=0)
    unique_count = len(unique_colors)
    
    # Calculate Density (Unique colors per area)
    # If a tiny 50x50 area has > 150 unique colors, it's a gradient (Rainbow)
    print(f"[STEP 6] Rainbow Density Analysis:")
    print(f"         > Unique Colors: {unique_count}")
    print(f"         > Total Colorful Pixels: {len(colorful_pixels)}")
    
    # --- STEP 3: Classification Rule ---
    # Rainbow pets usually have massive unique color counts (>100 shades)
    # Shiny/Golden/Normal pets are much lower (<30 shades of one color)
    is_rainbow = unique_count > 80
    
    if is_rainbow:
        print(f"         > Result: RAINBOW (High entropy detected)")
    else:
        print(f"         > Result: NOT RAINBOW (Low entropy: {unique_count})")
        
    return is_rainbow, unique_count

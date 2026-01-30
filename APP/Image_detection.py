import cv2
import numpy as np
import os
import time

IMAGE_PATH = "Images/test_image_6.PNG"
OUTPUT_PATH = "capture1.png"

def hex_to_hsv(hex_code):
    hex_code = hex_code.lstrip('#')
    r, g, b = int(hex_code[0:2], 16), int(hex_code[2:4], 16), int(hex_code[4:6], 16)
    return cv2.cvtColor(np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2HSV)[0][0]

def detect_and_save_adaptive(image_path=None, output_path=None):
    """
    Robust detection that works for ALL card sizes (large, small, exclusive).
    Key: Use CONTINUOUS DENSITY instead of fixed thresholds.
    Returns: (left, top, right, bottom) or None if failed
    """
    path_to_read = image_path if image_path else IMAGE_PATH
    path_to_save = output_path if output_path else OUTPUT_PATH
    
    purple_hexes = ["#784da9", "#6f439d", "#693a9f", "#987abb"]
    
    if not os.path.exists(path_to_read):
        print(f"Error: File {path_to_read} not found.")
        return None

    # 1. Load Image
    img = cv2.imread(path_to_read)
    if img is None:
        print("Error: Could not decode image.")
        return None
        
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h_img, w_img = img.shape[:2]
    
    # 2. Precise Color Masking (Wide S/V range catches faint borders)
    p_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for h in purple_hexes:
        c = hex_to_hsv(h)
        lower = np.array([max(0, c[0]-2), 50, 50])
        upper = np.array([min(180, c[0]+2), 255, 255])
        p_mask = cv2.bitwise_or(p_mask, cv2.inRange(hsv, lower, upper))

    # 3. Morphological Closing (Fills gaps in borders)
    kernel = np.ones((5, 5), np.uint8)
    closed_mask = cv2.morphologyEx(p_mask, cv2.MORPH_CLOSE, kernel)
    
    # 4. Get all purple pixel coordinates
    ys, xs = np.where(closed_mask > 0)
    
    if len(xs) == 0:
        print("No purple pixels detected.")
        return None

    # 5. FIND BORDERS USING CONTINUOUS DENSITY (not fixed thresholds)
    col_counts = np.bincount(xs, minlength=w_img)
    row_counts = np.bincount(ys, minlength=h_img)
    
    # For VERTICAL borders: Find columns with SUSTAINED high density
    col_density = col_counts / h_img  # Normalize: 0.0 to 1.0
    
    # Find peaks in column density (left and right edges have high density)
    # DYNAMIC THRESHOLD:
    # 1. Start with a low absolute floor (2%) to capture small cards where border is short relative to screen height
    # 2. Use a relative threshold (e.g., 30% of max peak) to distinguish borders from background noise
    max_col_density = np.max(col_density) if len(col_density) > 0 else 0
    min_col_density = max(0.02, max_col_density * 0.3)  
    
    dense_cols = np.where(col_density > min_col_density)[0]
    
    if len(dense_cols) < 2:
        print(f"Could not find left/right borders. Max density: {max_col_density:.3f}")
        return None
    
    # Group consecutive dense columns 
    # Gap > 10 allows for slightly broken lines or thickness variations
    col_groups = np.split(dense_cols, np.where(np.diff(dense_cols) > 10)[0] + 1)
    
    if len(col_groups) < 2:
        print("Strict Mode: Only found one vertical border group. Detection failed.")
        return None
    
    # Use center of first and last groups (Outermost borders)
    left = int(np.mean(col_groups[0]))
    right = int(np.mean(col_groups[-1]))
    
    # For HORIZONTAL borders: Only look between left and right
    inner_p_mask = closed_mask[:, left:right+1]
    inner_row_counts = np.sum(inner_p_mask > 0, axis=1)
    
    card_width = right - left
    inner_row_density = inner_row_counts / card_width  # Normalize
    
    # Find TOP: First row with sustained high horizontal density
    min_row_density = 0.15  # 15% - catches card top
    dense_rows = np.where(inner_row_density > min_row_density)[0]
    
    if len(dense_rows) == 0:
        print("Could not find top border.")
        return None
    
    # Group consecutive dense rows and pick the first group's center
    row_groups = np.split(dense_rows, np.where(np.diff(dense_rows) > 5)[0] + 1)
    top = int(np.mean(row_groups[0]))
    
    # BOTTOM: Lowest purple pixel (already works perfectly)
    bottom = int(ys.max())
    
    # 6. Sanity check - ensure reasonable bounds
    if (right - left) < 50 or (bottom - top) < 50:
        print(f"Detected bounds too small: {right-left}x{bottom-top}")
        return None
    
    if (right - left) > w_img * 0.95 or (bottom - top) > h_img * 0.95:
        print(f"Detected bounds too large: {right-left}x{bottom-top}")
        return None

    # 7. Create perfect rectangular crop
    final_mask = np.zeros_like(img)
    cv2.rectangle(final_mask, (left, top), (right, bottom), (255, 255, 255), -1)
    result = cv2.bitwise_and(img, final_mask)
    detected_region = result[top:bottom+1, left:right+1]
    
    # 8. Save result
    cv2.imwrite(path_to_save, detected_region)
    
    # --- PIPELINE STEP: Find Inner Crop via image_detection2.py ---
    # Call the secondary script to refine the crop (top/bottom) based on pixel logic
    # It will overwrite path_to_save (capture1.png)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    second_script_path = os.path.join(script_dir, "image_detection2.py")
    
    print(f"Triggering secondary detection: {second_script_path} on {path_to_save}")
    try:
        import subprocess
        import sys
        
        # We run it as a subprocess to keep it isolated as requested ("send a request")
        # PASS THE PATH as an argument
        result = subprocess.run([sys.executable, second_script_path, path_to_save], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Secondary detection successful.")
            print(result.stdout)
        else:
            print("Secondary detection FAILED.")
            print(result.stderr)
            
    except Exception as e:
        print(f"Failed to run secondary detection: {e}")
    # ---------------------------------------------------------------
    
    # Save debug visualization
    debug_dir = os.path.dirname(path_to_save) if os.path.dirname(path_to_save) else "."
    debug_img = img.copy()
    cv2.rectangle(debug_img, (left, top), (right, bottom), (0, 255, 0), 3)
    debug_path = os.path.join(debug_dir, "debug_result.png")
    cv2.imwrite(debug_path, debug_img)
    
    print(f"✓ SUCCESS: Card detected and cropped")
    print(f"  Bounds: L={left}, R={right}, T={top}, B={bottom}")
    print(f"  Size: {right-left}x{bottom-top} pixels")
    print(f"  Purple Pixels: {len(xs)}")
    
    return (left, top, right, bottom)


if __name__ == "__main__":
    print(f"Analyzing {IMAGE_PATH}...")
    start_time = time.time()
    detect_and_save_adaptive(IMAGE_PATH, OUTPUT_PATH)
    print(f"Process finished in {time.time() - start_time:.4f}s")
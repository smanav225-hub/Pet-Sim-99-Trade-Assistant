import cv2
import numpy as np
import os
import sys

def hex_to_bgr(hex_code):
    hex_code = hex_code.lstrip('#')
    r, g, b = int(hex_code[0:2], 16), int(hex_code[2:4], 16), int(hex_code[4:6], 16)
    return (b, g, r)

def get_gray_top(input_path, search_from_y=0):
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return None

    img = cv2.imread(input_path)
    if img is None:
        return None

    # Implement Internal Cropping: Only look below the specified Y
    # This prevents catching gray text in nametags ABOVE the tag
    if search_from_y > 0:
        search_roi = img[search_from_y:, :]
    else:
        search_roi = img

    target_hexes = ["#878788", "#eeebf4", "#a4a3a6"]
    target_bgrs = [hex_to_bgr(h) for h in target_hexes]
    combined_mask = np.zeros(search_roi.shape[:2], dtype=np.uint8)
    
    for bgr in target_bgrs:
        lower = np.array(bgr, dtype=np.uint8)
        upper = np.array(bgr, dtype=np.uint8)
        mask = cv2.inRange(search_roi, lower, upper)
        combined_mask = cv2.bitwise_or(combined_mask, mask)

    ys, xs = np.where(combined_mask > 0)
    if len(ys) == 0:
        print("Gray description text not found in search area.")
        return None

    # We want the TOP of the gray text relative to the ROI
    local_gray_top = np.min(ys)
    
    # Convert to Global Coordinate
    global_gray_top = search_from_y + local_gray_top
    print(f"[STEP 2] Gray Text Top found at Global Y={global_gray_top} (Local: {local_gray_top})")
    return global_gray_top

if __name__ == "__main__":
    if len(sys.argv) > 1:
        start_y = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        get_gray_top(sys.argv[1], start_y)
    else:
        print("No image path provided.")

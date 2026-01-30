import cv2
import numpy as np
import os
import sys

def hex_to_bgr(hex_code):
    hex_code = hex_code.lstrip('#')
    r, g, b = int(hex_code[0:2], 16), int(hex_code[2:4], 16), int(hex_code[4:6], 16)
    return (b, g, r)

def get_exclusive_bottom(input_path):
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return None

    img = cv2.imread(input_path)
    if img is None:
        return None

    # Restrict search to top 35% of the image to avoid XP charms/noise
    h, w = img.shape[:2]
    search_limit = int(h * 0.35)
    img_roi = img[:search_limit, :]

    # Actual Purple/Pink Exclusive Tag colors
   #  target_hexes = ["#331f4c", "#392652", "#382550", "#342550", "#392452"]
    target_hexes = ["#a973ff" , "#a876ff", "#a275f6", "#a275f6", "#a378f9"]    
    target_bgrs = [hex_to_bgr(h) for h in target_hexes]
    combined_mask = np.zeros(img_roi.shape[:2], dtype=np.uint8)
    
    for bgr in target_bgrs:
        lower = np.array([max(0, c-15) for c in bgr], dtype=np.uint8)
        upper = np.array([min(255, c+15) for c in bgr], dtype=np.uint8)
        mask = cv2.inRange(img_roi, lower, upper)
        combined_mask = cv2.bitwise_or(combined_mask, mask)

    ys, xs = np.where(combined_mask > 0)
    if len(ys) == 0:
        print("Exclusive tag not found.")
        return None

    # We want the BOTTOM of the tag, which is the MAX Y
    exclusive_bottom = np.max(ys)
    print(f"[STEP 1] Exclusive Bottom found at Y={exclusive_bottom}")
    return exclusive_bottom

if __name__ == "__main__":
    if len(sys.argv) > 1:
        get_exclusive_bottom(sys.argv[1])
    else:
        print("No image path provided.")


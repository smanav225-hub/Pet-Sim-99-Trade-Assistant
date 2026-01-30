import cv2
import numpy as np
import os

def hex_to_bgr(hex_code):
    """Converts hex string (e.g. '#F8F5FF') to BGR tuple (255, 245, 248)."""
    hex_code = hex_code.lstrip('#')
    r, g, b = int(hex_code[0:2], 16), int(hex_code[2:4], 16), int(hex_code[4:6], 16)
    return (b, g, r)

import sys

def crop_top_bottom_by_color():
    # Helper to check for command line args
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        output_path = sys.argv[1] # Overwrite same file as per previous logic
    else:
        print("Error: No file path provided.")
        return

    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return

    # Load image
    img = cv2.imread(input_path)
    if img is None:
        print(f"Error: Could not read {input_path}.")
        return

    # Target colors
    target_hexes = [
        "#F8F5FF", "#F7F4FE", "#F4F2FC", 
        "#F3F1FB", "#F0EEF8", "#F6F4FE"
    ]
    
    target_bgrs = [hex_to_bgr(h) for h in target_hexes]

    # Create a mask for matches
    # We essentially want pixels that match ANY of the target colors exactly.
    # Since we have a specific list, we can check for equality.
    
    dataset = np.array(target_bgrs, dtype=np.uint8) # Shape (N, 3)
    
    # Efficient way: create a mask
    # For exact matching, we can iterate or use broadcasting if the image isn't too huge.
    # Given typical screenshot sizes, broadcasting might be heavy on RAM depending on N.
    # Standard cv2.inRange is for ranges. For exact discrete colors, we can loop.
    
    combined_mask = np.zeros(img.shape[:2], dtype=np.uint8)
    
    for bgr in target_bgrs:
        # Create lower and upper bound same for exact match
        # (Or slightly loose if compression noise is expected, but user asked for exact)
        # Using a very small tolerance (variance of 1) to be safe against minor encoding shifts
        # But user said "exact pixels", so I will stick to exact first.
        # Actually, let's allow a TINY tolerance (0) just to be purely exact as requested.
        
        lower = np.array(bgr, dtype=np.uint8)
        upper = np.array(bgr, dtype=np.uint8)
        
        mask = cv2.inRange(img, lower, upper)
        combined_mask = cv2.bitwise_or(combined_mask, mask)

    # Find where pixels matched
    ys, xs = np.where(combined_mask > 0)

    if len(ys) == 0:
        print("No matching pixels found.")
        return

    min_y = np.min(ys)
    max_y = np.max(ys)

    print(f"Found matching pixels.")
    print(f"Highest point (Min Y): {min_y}")
    print(f"Lowest point (Max Y): {max_y}")

    # Crop
    # We want to keep the full width, just crop the height?
    # "now crop that area. so only middle remain." 
    # Usually means trim top and bottom outside the region of interest? 
    # Or keep ONLY the region from min_y to max_y? "so only middle remain" suggests keeping [min_y : max_y]
    
    cropped_img = img[min_y : max_y + 1, :]

    cv2.imwrite(output_path, cropped_img)
    print(f"Saved cropped image to {output_path}")

if __name__ == "__main__":
    crop_top_bottom_by_color()

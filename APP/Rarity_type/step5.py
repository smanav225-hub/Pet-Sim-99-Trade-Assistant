import cv2
import numpy as np

def analyze_and_save(roi, is_shiny, output_path="final.png"):
    if roi is None or roi.size == 0:
        print(f"[STEP 5] ROI empty. Cannot analyze rainbow for {output_path}.")
        return "NORMAL"

    # Save the crop
    cv2.imwrite(output_path, roi)
    print(f"[STEP 5] Saved {output_path}")

    # Rainbow Spectrum Check
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    
    # 1. High Saturation (Colorfulness)
    sat_mask = cv2.inRange(hsv, np.array([0, 80, 50]), np.array([179, 255, 255]))
    total_sat = cv2.countNonZero(sat_mask)
    
    # 2. Yellow Check (Exclusion)
    yellow_mask = cv2.inRange(hsv, np.array([20, 80, 50]), np.array([35, 255, 255]))
    yellow_pixels = cv2.countNonZero(yellow_mask)
    
    is_rainbow = False
    if total_sat > 20:
        # If colorful but NOT mostly yellow
        ratio = yellow_pixels / total_sat
        if ratio < 0.7:
            is_rainbow = True
            print(f"         > Rainbow Check: SAT={total_sat}, Yellow%={ratio:.1%}. Result: RAINBOW")
        else:
            print(f"         > Rainbow Check: SAT={total_sat}, Yellow%={ratio:.1%}. Result: GOLDEN")
    else:
        print(f"         > Rainbow Check: SAT={total_sat} (Too low color). Result: NONE")

    # Final Summary
    status = []
    if is_shiny: status.append("SHINY")
    if is_rainbow: status.append("RAINBOW")
    
    final_text = " ".join(status) if status else "NORMAL"
    print(f"\n>> FINAL VERDICT: {final_text}")
    return final_text
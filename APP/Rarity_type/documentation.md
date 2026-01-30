# Pet Simulator 99 Variant Detection Pipeline Documentation

This document outlines the architecture and logic of the image processing pipeline located in `APP ps99/color detection/rainbow_testing/`. The system is designed to identify the specific variant of a pet (Normal, Golden, Rainbow, Shiny) from a raw screenshot capture.

## 1. Pipeline Overview

The core orchestrator is **`main.py`**. It processes a batch of images (e.g., `capture1.png` through `capture8.png`) and determines the pet's status using a modular step-by-step approach.

The pipeline splits into **two distinct paths** early in the process based on the presence of "Golden" text/pixels.

### The Two Logic Paths

1.  **Path A: The "Golden" Shortcut**
    *   **Trigger:** If specific Golden Hex colors (`#feed4f`, `#ffdf33`, `#ffe136`) are detected anywhere in the image during the initial scan.
    *   **Logic:**
        *   The pet is immediately classified as **GOLDEN**.
        *   The system then performs a global check for **SHINY** particles (using logic from `step4`).
        *   **Outcome:** Returns `GOLDEN` or `GOLDEN SHINY`.
        *   **Note:** This path skips the complex cropping and entropy analysis because Golden pets are easily identifiable by color alone.

2.  **Path B: The "Rainbow/Normal" Deep Scan**
    *   **Trigger:** If NO gold pixels are found.
    *   **Logic:**
        *   **Anchoring:** Finds the text "Exclusive" (Purple tag) and the Gray description text to define a vertical Region of Interest (ROI).
        *   **Cropping:** Extracts the strip of image *between* these two text anchors. This strip contains the "Rainbow" or "Shiny" text indicator if present.
        *   **Entropy Analysis:** Since "Rainbow" text is a gradient of many colors, the system counts the number of *unique* colors (entropy) in the crop.
        *   **Outcome:**
            *   **High Unique Color Count (>80):** Classified as **RAINBOW**.
            *   **Low Unique Color Count:** Classified as **NORMAL**.
            *   **Shiny Check:** Checks for specific pink/shiny pixels within the crop to add the **SHINY** modifier.

---

## 2. Detailed Script Analysis

### `main.py` (The Orchestrator)
*   **Purpose:** Runs the loop for all capture images and decides which path (Golden vs. Rainbow) to take.
*   **Key Functions:**
    *   Imports modules `1` through `6`.
    *   Performs the initial `cv2.inRange` check for Golden colors.
    *   If Gold is found: Sets status to GOLDEN, checks Shiny, saves result.
    *   If Gold is NOT found: Calls Steps 1, 2, 3, 6, and 5 sequentially to determine if it is Rainbow or Normal.
    *   Aggregates the final report.

### `1.py` (Exclusive Anchor Detection)
*   **Purpose:** Finds the **bottom** y-coordinate of the "Exclusive" tag.
*   **Logic:**
    *   Searches for specific purple hex codes (`#331f4c`, `#392652`, etc.).
    *   Creates a combined mask of these colors.
    *   Returns the `max(y)` (lowest point) of these pixels.
*   **Role:** Acts as the **Top Boundary** for our crop (we want the area *below* this tag).

### `2.py` (Gray Text Anchor Detection)
*   **Purpose:** Finds the **top** y-coordinate of the gray description text.
*   **Logic:**
    *   Searches for specific gray hex codes (`#878788`, `#eeebf4`, etc.).
    *   Returns the `min(y)` (highest point) of these pixels.
*   **Role:** Acts as the **Bottom Boundary** for our crop (we want the area *above* this text).

### `3.py` (Smart Cropping)
*   **Purpose:** Extracts the "Variant Strip" (the ROI) based on coordinates from Step 1 and Step 2.
*   **Logic:**
    *   **Initial Span:** Defines the area between `exclusive_bottom` and `gray_top`.
    *   **Shiny Interference Check:** Checks if "Shiny" text is present within this span. Shiny text usually appears *below* the Rainbow text.
    *   **Truncation:** If Shiny is detected, it calculates the top of the Shiny text and **cuts the crop short** right before it. This ensures the ROI only contains the "Rainbow" text (or empty space) and isn't polluted by Shiny colors.
    *   **Returns:** The final cropped image (`variant_roi`) and a boolean `is_shiny`.

### `4.py` (Shiny Detection Logic)
*   **Purpose:** A reusable module to detect "Shiny" text/particles.
*   **Logic:**
    *   Looks for specific pink/peach hex codes (`#f9d5f0`, `#ffd9d6`, etc.).
    *   Applies a +/- 2 color tolerance.
    *   Returns `True` if pixel count > 4.

### `5.py` (Output & Legacy Check)
*   **Purpose:** Saves the debug image (`final_X.png`) and runs a secondary color saturation check.
*   **Logic:**
    *   Saves `roi` to disk.
    *   **Saturation Check:** Calculates the ratio of high-saturation pixels vs. yellow pixels. (Legacy logic, largely superseded by Step 6's entropy check but useful for verification).
    *   Formats the final string (e.g., "SHINY RAINBOW").

### `6.py` (Rainbow Entropy Analysis)
*   **Purpose:** The definitive check for "Rainbow" status using Color Entropy.
*   **Logic:**
    *   **Concept:** "Rainbow" text is a gradient. Even a small letter contains dozens of distinct color values. "Normal" or flat text contains very few unique colors.
    *   **Process:**
        1.  Takes the center 70% of the ROI (height-wise) to ignore edges.
        2.  Filters for colorful pixels (High Saturation).
        3.  **Counts Unique Colors:** Uses `np.unique()` to count how many distinct RGB tuples exist.
    *   **Threshold:**
        *   **> 80 Unique Colors:** Result is **RAINBOW**.
        *   **< 80 Unique Colors:** Result is **NOT RAINBOW**.

---

## 3. Summary of Flow

```mermaid
graph TD
    A[Start: capture.png] --> B{Contains GOLD Pixels?}
    
    B -- YES --> C[Set Status: GOLDEN]
    C --> D[Run Step 4: Detect Shiny Global]
    D --> E[Final Result: GOLDEN + (SHINY?)]
    
    B -- NO --> F[Run Step 1: Find Exclusive Tag Bottom]
    F --> G[Run Step 2: Find Gray Text Top]
    G --> H[Run Step 3: Crop Middle Area]
    H --> I{Is Shiny Detected in Crop?}
    I --> J[Run Step 6: Entropy Analysis on Crop]
    
    J -- High Entropy --> K[Add RAINBOW]
    J -- Low Entropy --> L[Add NORMAL]
    
    K --> M[Final Result: (SHINY?) + RAINBOW]
    L --> N[Final Result: (SHINY?) + NORMAL]
```

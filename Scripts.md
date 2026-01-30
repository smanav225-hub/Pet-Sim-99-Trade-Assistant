# 📜 Detailed Script Documentation

This file provides a deep dive into every script within the Pet Simulator 99 Trading Assistant, explaining their purpose, features, and technical inner workings.

---

## 🛠 Main Application & Logic

### 1. App.py
*   **Purpose**: The central "brain" and main user interface of the application. It manages the background OCR engine, handles keyboard hotkeys, and coordinates all other windows (Trade, Settings, Calculator).
*   **Features**:
    *   **Multi-threaded OCR Engine**: Runs heavy image processing in a background thread to prevent game lag.
    *   **Live Overlay**: Transparent GUI that stays on top of Roblox.
    *   **Hotkey Management**: Listens for `Z` and `X` globally via `win32api`.
    *   **Stealth Mode Logic**: Temporarily hides all UI elements during a capture to ensure a clean screenshot.
    *   **Integrated Search**: A mini-database browser with filters for Category, Sort, and Variant.
    *   **App Monitor**: Automatically hides/shows the GUI based on whether Roblox is the active window.
    *   **Batch Processing**: Capability to queue and process multiple captures simultaneously.
*   **Working (Technical Terms)**: 
    *   Employs a **Producer-Consumer pattern** using a `queue.Queue`. Hotkey triggers add tasks, while the `processing_loop` consumes them.
    *   Uses **PySide6 Signals** with `BlockingQueuedConnection` to ensure the GUI is fully hidden before the `mss` library takes a screenshot.
    *   **Connections**: Primary orchestrator for `Image_detection.py`, `Setting.py`, `calculator.py`, `Trade.py`, `Values.py`, and `Rarity_type`.

### 2. Cosmic_webscrapper.py
*   **Purpose**: An automated data harvester that pulls the latest pet values from the Cosmic Values website to keep the local database up to date.
*   **Features**:
    *   **Asynchronous Scraping**: Uses `Playwright` to open multiple browser pages simultaneously for extreme speed.
    *   **Smart Database Sync**: Compares web data with the local `master` table; it only updates rows that have changed.
    *   **Excel Exporting**: Generates beautifully formatted `.xlsx` files (Master, Titanics, Huges, etc.) with auto-adjusted column widths.
    *   **Regex Parsing**: Uses complex regular expressions to extract Value, Demand, RAP, and Existence from raw web text.
    *   **Category Filtering**: Supports individual category scraping or a full site "All" scan.
*   **Working (Technical Terms)**: 
    *   Uses `asyncio.Semaphore` to manage concurrency and `playwright.async_api` for headless browser control.
    *   Data is structured using `Pandas` before being committed to an `SQLite3` database.
    *   **Connections**: Triggered by `Values.py`. Feeds data into `cosmic_values.db`.

### 3. Image_detection.py
*   **Purpose**: The primary "Eye" of the app. It analyzes a full-screen screenshot to find the exact location of a pet's info card.
*   **Features**:
    *   **Adaptive Detection**: Works on any screen resolution (720p to 4K) without hardcoded coordinates.
    *   **Continuous Density Mapping**: Calculates the "density" of purple pixels across the screen to find borders.
    *   **Morphological Filtering**: Uses `cv2.morphologyEx` to bridge gaps in broken or faint lines.
    *   **Dynamic Thresholding**: Adjusts sensitivity based on the maximum color peak detected.
*   **Working (Technical Terms)**: 
    *   Converts images to **HSV Color Space** to isolate the purple UI borders (`#784da9`).
    *   Uses `np.bincount` to find the X and Y coordinates with the highest frequency of target pixels.
    *   **Connections**: Called by `App.py`. Triggers `image_detection2.py` as a subprocess to refine the crop.

### 4. image_detection2.py
*   **Purpose**: A precision refinement script that performs a "micro-crop" on the output of the primary detection.
*   **Features**:
    *   **Exact Pixel Matching**: Searches for the specific white/off-white background colors of the nameplate.
    *   **Vertical Trimming**: Removes extra space at the top and bottom to isolate the text area.
*   **Working (Technical Terms)**: 
    *   Scans for a list of BGR tuples corresponding to the game's UI colors.
    *   Identifies the `min_y` and `max_y` of these pixels to perform the final `numpy` slice on the image.
    *   **Connections**: Sub-step of the `Image_detection.py` pipeline.

### 5. name_detection.py
*   **Purpose**: Isolates the pet name text from the cropped card image to make it readable for the OCR engine.
*   **Features**:
    *   **Anchor Detection**: Searches for the "Exclusive" tag (Purple) to use as a landmark.
    *   **Dynamic Cropping**: Automatically cuts everything below the tag, leaving only the area where the name is written.
    *   **Image Enhancement**: Boosts contrast (3.0x) and sharpness (2.5x) using `PIL` to help OCR read difficult fonts.
    *   **Grayscale Conversion**: Converts the snip to L-mode (grayscale) to remove background noise.
*   **Working (Technical Terms)**: 
    *   Finds purple pixels using `cv2.inRange` and identifies the `min_y` coordinate of the tag.
    *   **Connections**: Triggered by `OCRWorker` in `App.py`. Feeds its output into the `EasyOCR` reader.

### 6. Search.py
*   **Purpose**: A standalone database browser that allows users to look up any pet or item without needing to see it on screen.
*   **Features**:
    *   **Detailed View Toggle**: Can expand from a slim view to a wide view showing RAP, Value Change, and Update times.
    *   **Multi-Filter System**: Filter by Category (Huges, Titanics, etc.), Variant (Golden, Shiny), and Sort method.
    *   **Live Search**: Results update instantly as you type.
    *   **Fuzzy-Ready Table**: Uses a custom `NameDelegate` to render bold text in the results table.
*   **Working (Technical Terms)**: 
    *   Executes `SQL` queries with `LOWER()` and `LIKE` parameters for case-insensitive searching.
    *   Uses `QPropertyAnimation` to smoothly resize the window based on result count.
    *   **Connections**: Independent database browser using `cosmic_values.db`.

### 7. Setting.py
*   **Purpose**: The configuration hub that lets users customize how the app behaves and looks.
*   **Features**:
    *   **Hotkey Rebinding**: Rebind "Find" or "Trade" keys to any keyboard or mouse button.
    *   **Stealth Mode Toggle**: Enables/disables the synchronized UI hiding feature.
    *   **Batch Processing Control**: Set how many images are processed at once (1-16).
    *   **Config Persistence**: All changes are instantly saved to `settings_config.json`.
*   **Working (Technical Terms)**: 
    *   Captures input using `event.nativeVirtualKey()` to support hardware-level keys.
    *   Uses `QIntValidator` and `QDoubleValidator` to ensure user inputs are valid.
    *   **Connections**: Loaded by `App.py` to determine hotkey bindings and capture settings.

### 8. Trade.py
*   **Purpose**: A professional-grade calculator specifically designed for PS99 trades to determine value differences.
*   **Features**:
    *   **Dual-Window Management**: Syncs "Your Offer" and "Their Offer" windows.
    *   **Real-time Difference**: Shows "Win/Loss" gems with dynamic color indicators (Green/Red).
    *   **Gem Support**: Accepts shorthand units like `k`, `m`, and `b` for diamond offers.
    *   **Quantity Controls**: Includes in-table `+` and `-` buttons for quick adjustments.
    *   **Demand Averaging**: Automatically calculates the average demand of the entire offer.
*   **Working (Technical Terms)**: 
    *   `TradeBackend` routes data to sides based on screen coordinates (Left vs Right).
    *   Uses `QGraphicsDropShadowEffect` for a modern, floating UI look.
    *   **Connections**: Receives data from `App.py` via the `X` hotkey.

### 9. Values.py
*   **Purpose**: The graphical interface for the web scraper, allowing users to manage database updates.
*   **Features**:
    *   **Selective Scanning**: Use checkboxes to update only specific categories (e.g., Titanics or Eggs).
    *   **Performance Tuning**: Set "Max Pages" and "Concurrent Windows" to match your internet speed.
    *   **Live Status Bar**: Real-time progress updates from the background scraper.
    *   **Global Toggle**: Includes an "All" checkbox to quickly select every category.
*   **Working (Technical Terms)**: 
    *   Launches `ScraperWorker` (a `QThread`) to run the `asyncio` loop of the scraper without freezing the UI.
    *   **Connections**: The frontend for `Cosmic_webscrapper.py`.

### 10. calculator.py
*   **Purpose**: A floating, unit-aware calculator designed for high-value game trades.
*   **Features**:
    *   **Unit Support**: Native support for `K`, `M`, and `B` suffixes in calculations.
    *   **UI Scaling**: The entire window scales based on the `calc_size` setting in `settings_config.json`.
    *   **Smart Formatting**: Automatically converts raw numbers back to shorthand (e.g., `1,000,000` becomes `1.000M`).
    *   **History Label**: Shows the full expression used to reach the current result.
*   **Working (Technical Terms)**: 
    *   Uses `re.sub` to transform unit characters into math operations (e.g., `5M` -> `5 * 10^6`) before evaluation.
    *   **Connections**: Triggered from the main `App.py` window.

### 11. batch.py
*   **Purpose**: A performance benchmarking tool to optimize OCR speed on different computers.
*   **Features**:
    *   **GPU Detection**: Checks for NVIDIA CUDA support to enable lightning-fast OCR.
    *   **Throughput Benchmark**: Tests various batch sizes (1, 2, 4, 8, 16) to find the highest "Images Per Second" (FPS).
    *   **Optimal Recommendation**: Analyzes results to suggest the best batch size for your hardware.
*   **Working (Technical Terms)**: 
    *   Uses `torch.cuda` for hardware detection and `time.perf_counter` for high-precision timing.
    *   **Connections**: Independent utility used to calibrate the `batch_size` in settings.

### 12. Rarity_type/main.py
*   **Purpose**: The central orchestrator for the "Rarity Pipeline" that identifies pet variants.
*   **Features**:
    *   **Two-Path Logic**: Features a fast-path for Golden pets and a deep-scan path for Rainbow pets.
    *   **Modular Design**: Easily expandable by adding or removing "Step" scripts.
    *   **Error Handling**: Returns "NORMAL" status if any part of the image analysis is ambiguous.
*   **Working (Technical Terms)**: 
    *   Coordinates the execution of 6 separate vision modules. It passes the `input_image` and `output_crop_path` through the pipeline.
    *   **Connections**: Triggered by `App.py`. Imports `step1.py` through `step6.py`.

---

## 🌈 The Rarity Pipeline (Step-by-Step)

### 13. Rarity_type/step1.py (Exclusive Anchor)
*   **Purpose**: Identifies the top boundary of the variant info area.
*   **Features**:
    *   **Landmark Detection**: Specifically tuned to find the purple/pink "Exclusive" or "Huge" rarity tags.
    *   **Noise Reduction**: Limits its search to the top 35% of the card image.
*   **Working (Technical Terms)**: 
    *   Uses a BGR mask for hex `#a973ff`. Finds the `max(y)` (bottom-most) purple pixel to define where the variant text starts.
    *   **Connections**: Passes the "Exclusive Bottom" coordinate to `step2`.

### 14. Rarity_type/step2.py (Gray Anchor)
*   **Purpose**: Identifies the bottom boundary of the variant info area.
*   **Features**:
    *   **Description Pinpointing**: Finds the gray description text that always sits below the variant name.
*   **Working (Technical Terms)**: 
    *   Searches for gray hexes (`#878788`) only *below* the Step 1 coordinate. Returns the `min(y)` (top-most) gray pixel.
    *   **Connections**: Defines the end of the "Variant Strip" for `step3`.

### 15. Rarity_type/step3.py (Smart Crop & Shiny Detect)
*   **Purpose**: Extracts the final image strip and performs an early Shiny check.
*   **Features**:
    *   **Interference Prevention**: If "Shiny" text is found, it cuts the crop short to prevent shiny colors from being miscounted as a Rainbow gradient.
*   **Working (Technical Terms)**: 
    *   Slices the image between the two anchors. Scans for pink/peach pixels with a 4-pixel sensitivity threshold.
    *   **Connections**: Produces the final `variant_roi` used by `step6`.

### 16. Rarity_type/step4.py (Shiny Logic)
*   **Purpose**: A dedicated utility for detecting the specific "Shiny" particle effect and text.
*   **Features**:
    *   **Robust Tolerance**: Uses a +/- 2 BGR tolerance to account for slight color shifts in different game lighting.
*   **Working (Technical Terms)**: 
    *   Creates a boolean mask of all shiny-colored pixels. If the count is >= 4, `is_shiny` is set to True.
    *   **Connections**: A shared utility used by both the orchestrator and Step 3.

### 17. Rarity_type/step5.py (Verification & Saving)
*   **Purpose**: Saves the debug image and performs a backup saturation check.
*   **Features**:
    *   **Golden Exclusion**: Calculates the ratio of Yellow vs. Other colors to double-check that a Golden pet wasn't misread as Rainbow.
*   **Working (Technical Terms)**: 
    *   Uses `cv2.imwrite` to save the final crop for debugging. Compares total saturated pixels against a yellow-specific mask.
    *   **Connections**: The final verification step before the result is returned to the user.

### 18. Rarity_type/step6.py (Rainbow Entropy Analysis)
*   **Purpose**: The definitive check for Rainbow status using "Color Entropy."
*   **Features**:
    *   **Gradient Analysis**: Counts *unique* colors instead of pixel volume, which is the most accurate way to detect the Rainbow gradient.
    *   **Center-Focus**: Only analyzes the middle 70% of the crop to ignore any border noise.
*   **Working (Technical Terms)**: 
    *   Flattens the image pixels and uses `np.unique` to count distinct RGB combinations.
    *   **Threshold**: If the unique color count is **> 80**, it is confirmed as **RAINBOW**.
    *   **Connections**: Provides the final verdict for the Rainbow detection pipeline.

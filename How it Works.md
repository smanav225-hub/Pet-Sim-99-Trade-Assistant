# 🧠 How it Works: The Technical Pipeline

Ever wonder how the app "sees" your screen and knows the value of your pets? This document explains the step-by-step journey of an image through the system.

---

### 1. Capture (The Camera)
When you press the **`Z`** or **`X`** key, the app uses a library called `mss` to take a high-speed screenshot of your Roblox window. This happens in milliseconds!

### 2. Finding the Pet (Adaptive Detection)
Roblox screens can be different sizes, and pets can be in different places. Instead of looking at fixed spots, the app uses **Computer Vision (OpenCV)**:
*   **Color Masking:** It looks for the specific "Purple/Blue" colors of the Pet Simulator 99 item cards.
*   **Density Analysis:** The app counts the purple pixels horizontally and vertically. It looks for "peaks" of color.
*   **Auto-Cropping:** Once it finds the borders of the card you are hovering over, it crops that specific area so it can focus only on the pet's name.

### 3. Reading the Text (OCR)
Now that we have a clean image of just the pet card, the app uses **EasyOCR** (Optical Character Recognition). 
*   It "reads" the pixels and turns them into actual text (like "Huge Cat").
*   **Preprocessing:** Before reading, the app enhances the contrast of the image to make the text pop, ensuring it doesn't miss letters.

### 4. Smart Matching (Fuzzy Search)
Sometimes the OCR makes small mistakes (like reading a "0" instead of an "O"). 
*   The app uses **RapidFuzz** to compare the text it read against thousands of names in the database.
*   It finds the "Closest Match." So if the OCR reads "Hge Dragon," the app is smart enough to know you meant "Huge Dragon."

### 5. Database Lookup
Once the name is confirmed, the app queries its brain—the **`cosmic_values.db`** (an SQLite database). 
*   It instantly pulls the latest Gem value, Demand rating, and Price trends.
*   Because the database is stored on your computer, this lookup happens almost instantly without needing to wait for a website to load.

### 6. The Overlay (The Result)
Finally, the app uses **PySide6** to draw a beautiful, transparent window right on your screen.
*   It calculates the totals if you are in a trade.
*   It shows you the final "Win/Loss" result based on the math it just performed.

---

### 🛠 Summary of Technologies
*   **UI:** PySide6 (Python's version of the professional Qt framework).
*   **Vision:** OpenCV (The same tech used in self-driving cars).
*   **OCR:** EasyOCR (Deep learning model for text recognition).
*   **Database:** SQLite (Lightweight and fast local storage).
*   **Speed:** Multi-threading (The app does all this "math" in the background so your game doesn't lag).

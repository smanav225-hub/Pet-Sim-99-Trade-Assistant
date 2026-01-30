# 🛠 Requirements & Installation

### 💻 System Requirement
*   **Operating System:** You **MUST** have a Windows computer (Windows 10, 11, or any older version). This app will not work on Mac or Linux.

---

### 📥 Step 1: Download the App from GitHub
1.  On this GitHub page, look for the green **"<> Code"** button near the top right.
2.  Click it and then click **"Download ZIP"**.
3.  Once the download is finished, go to your **Downloads** folder.
4.  **Right-click** on the file (it will be named something like `Pet-simulator-99-main.zip`).
5.  Click **"Extract All..."** or **"Extract Here"**. 
6.  This will create a new folder. Open that folder to find the app files.

---

### 🐍 Step 2: Install Python
You need Python to run the scripts. Follow these exact steps:
1.  Go to [python.org/downloads](https://www.python.org/downloads/).
2.  Click the big yellow button that says **Download Python**.
3.  Open the file you just downloaded to start the installer.
4.  **CRITICAL:** Look at the bottom of the installer window and check the box that says **"Add Python to PATH"**. If you miss this, the app won't work!
5.  Click **Install Now** and wait for it to finish.

---

### ⌨️ Step 3: Install App Libraries
Now you need to tell your computer to download the tools the app needs to work.
1.  Click the **Start** button on your Windows taskbar (the bottom left corner).
2.  Type **"cmd"** into the search bar.
3.  You will see **Command Prompt** appear. Click it to open it.
4.  Copy the long command below and **right-click** inside the black Command Prompt window to paste it:

```bash
pip install PySide6 easyocr keyboard mss opencv-python pandas pillow playwright pywin32 rapidfuzz && playwright install chromium
```

5.  Press **Enter** on your keyboard. Wait for it to finish (it might take a minute or two).

---

### 🏃 Step 4: Run the App

#### Using the .EXE File
1.  **Double-click** the `.exe` file.
2.  If a window says **"Windows protected your PC"**, click **"More info"** and then click **"Run anyway."**
3.  If it closes, just open it again. It will work after the first attempt.

#### Using the Python Script
1.  Open the folder you extracted in Step 1.
2.  Open the **APP ps99** folder.
3.  Inside the Command Prompt (cmd), type `cd` followed by a space, then drag the **APP ps99** folder into the window and press Enter.
4.  Type this and press Enter:
    ```bash
    python App.py
    ```
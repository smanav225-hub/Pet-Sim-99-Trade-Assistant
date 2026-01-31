# Pet Simulator 99 App Documentation

## GUI Stealth Mode (Hiding GUI during screenshots)

To make the "Stealth Mode" work perfectly and ensure the GUI never appears in your pet detection screenshots, we implemented a **Synchronized Hiding** system:

1. **Unified Process**: We moved the `Setting.py` and `calculator.py` windows into the main `App.py` process. This allows the app to have one-click control over every window on your screen.
2. **Blocking Connection**: We use a "Blocking Signal" which forces the background OCR thread to stop and wait until the GUI thread confirms the windows are 100% hidden.
3. **DWM Buffer Clear**: We added a tiny delay (0.12s) after hiding the windows. This allows the Windows Desktop Manager to clear the "ghost" of the window from the display buffer before `mss` takes the picture.
4. **Immediate Refresh**: We call `QApplication.processEvents()` to force the computer to update the screen state immediately, rather than waiting for the next frame.

## Quick Start
- **Gear Icon (⚙️)**: Opens Settings.
- **Calculator Button**: Opens the built-in unit calculator.
- **Z Key**: Detects pet value (Auto-hides GUI if Stealth Mode is ON).
- **X Key**: Routes pet to Trade window (Auto-hides GUI if Stealth Mode is ON).
- **Roblox Only Mode**: Automatically hides all app windows when you click away from Roblox to keep your desktop clean.

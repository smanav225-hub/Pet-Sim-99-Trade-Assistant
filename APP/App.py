import sys
import os
import json
import shutil
import re
import time
import threading
import sqlite3
import logging
import cv2
import concurrent.futures
import numpy as np
import keyboard
import easyocr
import subprocess
import win32gui
import win32process
import win32api
import queue
from mss import mss
from PIL import Image, ImageEnhance
from rapidfuzz import process, fuzz

# Import the detection logic
from Image_detection import detect_and_save_adaptive
from Setting import SettingWindow
from calculator import ModernCalculator
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QFrame, QLayout, QComboBox, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QStyledItemDelegate, QStyle
)
from PySide6.QtGui import QCursor, QGuiApplication, QFont, QColor, QTextOption
from PySide6.QtCore import Qt, QPoint, QObject, Signal, QThread, QEvent, QTimer, QPropertyAnimation, QEasingCurve

# Suppress EasyOCR logging
logging.getLogger('easyocr').setLevel(logging.ERROR)

def parse_price(price_str):
    if not price_str or price_str == "-": return 0.0
    price_str = price_str.upper().replace(",", "").replace("$", "").replace(" ", "").strip()
    price_str = re.sub(r'[▲▼%]', '', price_str)
    multiplier = 1
    if "B" in price_str: multiplier = 1_000_000_000; price_str = price_str.replace("B", "")
    elif "M" in price_str: multiplier = 1_000_000; price_str = price_str.replace("M", "")
    elif "K" in price_str: multiplier = 1_000; price_str = price_str.replace("K", "")
    try: return float(price_str) * multiplier
    except ValueError: return 0.0

def parse_demand(dem_str):
    if not dem_str or dem_str == "-": return 0.0
    try: return float(dem_str.split("/")[0])
    except: return 0.0

class TableNameDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        if option.state & QStyle.State_Selected:
            bg_color = QColor("#0078d7")
        else:
            bg_color = QColor(0, 0, 0, 0)
        painter.fillRect(option.rect, bg_color)
        
        painter.setPen(QColor(255, 255, 255, 15))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        painter.drawLine(option.rect.topRight(), option.rect.bottomRight())
        
        text = index.data()
        rect = option.rect.adjusted(8, 0, -5, 0)
        font = painter.font()
        font.setFamily("Segoe UI"); font.setPointSize(10); font.setBold(True); painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        opt = QTextOption(); opt.setWrapMode(QTextOption.WordWrap); opt.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        painter.drawText(rect, text, opt); painter.restore()
    def sizeHint(self, option, index): return QSize(150, 45)

# -----------------------------
# OCR Worker Class (Background Thread)
# -----------------------------
class OCRWorker(QObject):
    # Signal to emit updated data to the GUI
    data_found = Signal(dict)
    status_update = Signal(str)
    opacity_signal = Signal(float)

    def __init__(self):
        super().__init__()
        self.running = True
        if getattr(sys, 'frozen', False):
            self.script_dir = os.path.dirname(sys.executable)
        else:
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.live_dir = os.path.join(self.script_dir, "live")
        self.db_path = os.path.join(self.script_dir, "cosmic_values.db")
        
        self.purple_hexes = ["#784da9", "#6f439d", "#693a9f", "#987abb"]
        self.exclusive_hexes = ["#331f4c", "#392652", "#382550"]
        self.capture_count = 0
        self.config_path = os.path.join(self.script_dir, "settings_config.json")
        self.reader = None
        self.cached_names = []
        self.trade_active = False
        self.task_queue = queue.Queue()
        self.ocr_lock = threading.Lock()

    def run(self):
        """Initializes EasyOCR and starts the listening loop with custom binds."""
        print(f"[SYSTEM] Background thread started. DB Path: {self.db_path}")
        self.status_update.emit("Loading OCR Engine...")
        
        try:
            if os.path.exists(self.live_dir):
                shutil.rmtree(self.live_dir, ignore_errors=True)
            os.makedirs(self.live_dir, exist_ok=True)
        except Exception as e:
            print(f"[ERROR] Folder setup failed: {e}")

        try:
            self.reader = easyocr.Reader(['en'], gpu=True)
            print("[READY] EasyOCR Loaded (GPU).")
            self.load_cached_names()
            self.status_update.emit("Ready. Press 'Z' or 'X'")
        except Exception as e:
            print(f"[WARN] GPU OCR failed, trying CPU: {e}")
            try:
                self.reader = easyocr.Reader(['en'], gpu=False)
                print("[READY] EasyOCR Loaded (CPU).")
                self.load_cached_names()
                self.status_update.emit("Ready. Press 'Z' or 'X'")
            except Exception as e2:
                print(f"[ERROR] OCR Initialization failed: {e2}")
                self.status_update.emit("OCR Load Error")
                return

        # Start the processing loop in a separate thread
        threading.Thread(target=self.processing_loop, daemon=True).start()

        while self.running:
            try:
                # 1. Load binds from config
                bind_find = {"vk": 90, "name": "z"} # Default Z
                bind_trade = {"vk": 88, "name": "x"} # Default X
                
                if os.path.exists(self.config_path):
                    try:
                        with open(self.config_path, 'r') as f:
                            cfg = json.load(f)
                            bind_find = cfg.get("bind_find", bind_find)
                            bind_trade = cfg.get("bind_trade", bind_trade)
                            bind_inventory = cfg.get("bind_inventory", {"vk": 16}) # Default Shift
                    except: pass

                # Helper to get VK from bind data
                def get_vk(data):
                    vk = data.get("vk")
                    if vk: return vk
                    char = data.get("char")
                    if char and isinstance(char, str) and len(char) == 1:
                        # Convert ASCII char to VK code
                        res = win32api.VkKeyScan(char)
                        if res != -1: return res & 0xFF
                    return None

                vk_find = get_vk(bind_find)
                vk_trade = get_vk(bind_trade)
                vk_inventory = get_vk(bind_inventory)
                
                pressed_key = None
                if vk_find and win32api.GetAsyncKeyState(vk_find) & 0x8000:
                    pressed_key = 'z'
                elif vk_trade and win32api.GetAsyncKeyState(vk_trade) & 0x8000:
                    if self.trade_active:
                        pressed_key = 'x'
                elif vk_inventory and win32api.GetAsyncKeyState(vk_inventory) & 0x8000:
                    pressed_key = 'inventory'

                if pressed_key:
                    # 1. Capture Mouse and Screen immediately
                    mouse_x = QCursor.pos().x()
                    
                    # Read stealth mode from config
                    stealth_mode = False
                    if os.path.exists(self.config_path):
                        try:
                            with open(self.config_path, 'r') as f:
                                stealth_mode = json.load(f).get("stealth_mode", False)
                        except: pass

                    if stealth_mode:
                        self.opacity_signal.emit(0.0)
                        time.sleep(0.12) # Small delay for OS buffer to clear

                    self.capture_count += 1
                    current_live_dir = os.path.join(self.live_dir, f"live_{self.capture_count}")
                    os.makedirs(current_live_dir, exist_ok=True)
                    shot_path = os.path.join(current_live_dir, "original_screen.png")

                    with mss() as sct:
                        frame = np.array(sct.grab(sct.monitors[1]))
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                        cv2.imwrite(shot_path, frame)
                    
                    if stealth_mode:
                        self.opacity_signal.emit(1.0)

                    # 2. Queue the Task
                    self.task_queue.put({
                        "trigger_key": pressed_key,
                        "mouse_x": mouse_x,
                        "shot_path": shot_path,
                        "dir": current_live_dir
                    })
                    
                    # Wait for release to prevent multiple triggers
                    while (vk_find and win32api.GetAsyncKeyState(vk_find) & 0x8000) or \
                          (vk_trade and win32api.GetAsyncKeyState(vk_trade) & 0x8000) or \
                          (vk_inventory and win32api.GetAsyncKeyState(vk_inventory) & 0x8000):
                        time.sleep(0.05)
            except Exception as e:
                print(f"[LOOP ERROR] {e}")
            time.sleep(0.01)

    def processing_loop(self):
        """Processes queued captures in batches (Consumer)."""
        while self.running:
            task = self.task_queue.get() # Wait for first task
            
            # 1. Load batch size from settings
            batch_limit = 1
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, 'r') as f:
                        batch_limit = json.load(f).get("batch_size", 1)
                except: pass
            
            # 2. Gather additional tasks if available
            tasks = [task]
            while len(tasks) < batch_limit:
                try:
                    tasks.append(self.task_queue.get_nowait())
                except queue.Empty:
                    break
            
            # 3. Update status
            q_rem = self.task_queue.qsize()
            if len(tasks) > 1:
                self.status_update.emit(f"Processing Batch of {len(tasks)} ({q_rem} left)...")
            else:
                msg = "Processing..." if q_rem == 0 else f"Processing ({q_rem} left)...";
                self.status_update.emit(msg)

            # 4. Process Batch in Parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as executor:
                # Use list() to ensure all tasks start and we wait for them properly
                list(executor.map(self.process_task, tasks))
            
            # 5. Mark tasks as done
            for _ in range(len(tasks)):
                self.task_queue.task_done()

    def process_task(self, task):
        """Heavy lifting: Detection + OCR + DB."""
        capture1_path = os.path.join(task['dir'], "capture1.png")
        capture2_path = os.path.join(task['dir'], "capture2.png")
        capture3_path = os.path.join(task['dir'], "capture3.png")
        
        # UI Detection
        detect_and_save_adaptive(task['shot_path'], capture1_path)

        if not os.path.exists(capture1_path):
            self.status_update.emit("No UI Detected")
            return

        # Parallel OCR and Variant Detection
        from Rarity_type import detect_variant
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_ocr = executor.submit(self._ocr_task, capture1_path, capture2_path)
            future_variant = executor.submit(detect_variant, capture1_path, capture3_path)
            pet_name = future_ocr.result()
            pet_variant = future_variant.result()

        # Database Lookup
        v_upper = str(pet_variant).upper()
        is_gold = any(x in v_upper for x in ["GOLD", "GOLDEN"])
        is_rainbow = "RAINBOW" in v_upper
        is_shiny = "SHINY" in v_upper
        
        db_match = self.lookup_value(pet_name, gold=is_gold, rainbow=is_rainbow, shiny=is_shiny)
        
        # Prepare payload
        payload = {
            "found": False,
            "detected_name": pet_name,
            "detected_variant": pet_variant,
            "trigger_key": task['trigger_key'],
            "mouse_x": task['mouse_x']
        }

        if db_match:
            payload.update(db_match)
            payload["found"] = True
            self.status_update.emit("Data Updated")
        else:
            self.status_update.emit("No Match in DB")

        self.data_found.emit(payload)

    def load_cached_names(self):
        if not os.path.exists(self.db_path): return
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT Name FROM master")
            self.cached_names = [row[0] for row in cursor.fetchall() if row[0]]
            conn.close()
        except Exception as e:
            print(f"[CACHE ERROR] {e}")

    def lookup_value(self, pet_name, gold=False, rainbow=False, shiny=False):
        if not os.path.exists(self.db_path): return None
        if not self.cached_names: self.load_cached_names()
        match = process.extractOne(pet_name.upper(), self.cached_names, scorer=fuzz.WRatio)
        if not match or match[1] < 60: return None
        best_name = match[0]
        if best_name.upper().endswith("EGG"):
            gold = rainbow = shiny = False
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT [Pet Name] as full_name, Name as base_name, Variant, Value, [Value Change] as value_change, [Last Updated] as last_updated, Demand, Exist, RAP FROM master WHERE Name = ? AND GOLD = ? AND RAINBOW = ? AND SHINY = ? ORDER BY Date_Scraped DESC LIMIT 1"
            cursor.execute(query, (best_name, int(gold), int(rainbow), int(shiny)))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            print(f"[DB ERROR] {e}"); return None

    def _ocr_task(self, capture1_path, capture2_path):
        try:
            name_script_path = os.path.join(self.script_dir, "name_detection.py")
            subprocess.run([sys.executable, name_script_path, capture1_path, capture2_path], check=True, capture_output=True, text=True)
            if not os.path.exists(capture2_path): return "Unknown"
            capture2 = cv2.imread(capture2_path)
            if capture2 is None: return "Unknown"
            
            with self.ocr_lock:
                raw_results = self.reader.readtext(capture2, detail=1)
            
            if not raw_results: return "Unknown"
            heights = [abs(res[0][0][1] - res[0][2][1]) for res in raw_results]
            max_h = max(heights) if heights else 0
            filtered_text = [res[1] for i, res in enumerate(raw_results) if heights[i] >= (max_h - 6.5)]
            return " ".join(filtered_text) if filtered_text else " ".join([r[1] for r in raw_results])
        except Exception as e:
            print(f"[ERROR] OCR Task failed: {e}"); return "Unknown"

    def process_capture(self, trigger_key='z', mouse_x=0):
        # Read stealth mode from config
        stealth_mode = False
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    stealth_mode = json.load(f).get("stealth_mode", False)
            except: pass

        if stealth_mode:
            self.opacity_signal.emit(0.0)
            time.sleep(0.12) # Small delay for OS buffer to clear

        self.status_update.emit("Processing...")
        t_start = time.time()
        with mss() as sct:
            frame = np.array(sct.grab(sct.monitors[1]))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        
        if stealth_mode:
            self.opacity_signal.emit(1.0)
        self.capture_count += 1
        current_live_dir = os.path.join(self.live_dir, f"live_{self.capture_count}")
        os.makedirs(current_live_dir, exist_ok=True)
        full_shot_path = os.path.join(current_live_dir, "original_screen.png")
        capture1_path = os.path.join(current_live_dir, "capture1.png")
        capture2_path = os.path.join(current_live_dir, "capture2.png")
        capture3_path = os.path.join(current_live_dir, "capture3.png")
        cv2.imwrite(full_shot_path, frame)
        detect_and_save_adaptive(full_shot_path, capture1_path)
        if not os.path.exists(capture1_path):
            self.status_update.emit("No UI Detected"); return
        from Rarity_type import detect_variant
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_ocr = executor.submit(self._ocr_task, capture1_path, capture2_path)
            future_variant = executor.submit(detect_variant, capture1_path, capture3_path)
            pet_name = future_ocr.result()
            pet_variant = future_variant.result()
        v_upper = str(pet_variant).upper()
        is_gold = any(x in v_upper for x in ["GOLD", "GOLDEN"])
        is_rainbow = "RAINBOW" in v_upper
        is_shiny = "SHINY" in v_upper
        db_match = self.lookup_value(pet_name, gold=is_gold, rainbow=is_rainbow, shiny=is_shiny)
        payload = {"found": False, "detected_name": pet_name, "detected_variant": pet_variant, "trigger_key": trigger_key, "mouse_x": mouse_x}
        if db_match:
            payload.update(db_match); payload["found"] = True
            self.status_update.emit("Data Updated")
        else: self.status_update.emit("No Match in DB")
        self.data_found.emit(payload)

# -----------------------------
# Main GUI Window
# -----------------------------
class FloatingPetCard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        if getattr(sys, 'frozen', False):
            self.script_dir = os.path.dirname(sys.executable)
        else:
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
            
        self.config_path = os.path.join(self.script_dir, "settings_config.json")

        # Initialize all state attributes first to avoid AttributeError
        self.dragging = False
        self.drag_offset = QPoint()
        self.trade_active = False
        self.trade_manager = None
        self.setting_window = None
        self.calc_window = None
        self.values_window = None
        self.inventory_window = None
        self.is_capturing = False
        self.current_pet_data = None
        
        self.search_section = None
        
        self.build_ui()
        self.init_ocr_worker()

        # Start App Monitor
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.check_active_app)
        self.monitor_timer.start(1000)

    def init_ocr_worker(self):
        self.ocr_thread = QThread()
        self.worker = OCRWorker()
        self.worker.moveToThread(self.ocr_thread)
        self.ocr_thread.started.connect(self.worker.run)
        self.worker.data_found.connect(self.update_card)
        self.worker.status_update.connect(self.update_status)
        # Use BlockingQueuedConnection to force worker to wait until UI hides
        self.worker.opacity_signal.connect(self.set_gui_opacity, Qt.BlockingQueuedConnection)
        self.ocr_thread.start()

    def set_gui_opacity(self, opacity):
        """Changes transparency of all active app windows with state checking."""
        if opacity < 0.5:
            self.is_capturing = True
            self.apply_visibility(0.0)
        else:
            self.is_capturing = False
            # Check if we SHOULD show
            if self.should_show_gui():
                self.apply_visibility(1.0)

    def should_show_gui(self):
        """Logic to determine if GUI is allowed to be visible."""
        # Don't show if middle of capture
        if self.is_capturing: return False
        
        # Check Roblox Only Mode
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    settings = json.load(f)
                    if settings.get("roblox_only", False):
                        hwnd = win32gui.GetForegroundWindow()
                        if not hwnd: return False
                        
                        title = win32gui.GetWindowText(hwnd).upper()
                        # Whitelist: Roblox, Terminal windows, or the app windows
                        whitelist = ["ROBLOX", "PET SIM", "PYTHON", "POWERSHELL", "CMD", "TERMINAL"]
                        if any(x in title for x in whitelist):
                            return True
                            
                        # Double check if it's our own process (for the frameless windows)
                        try:
                            _, pid = win32process.GetWindowThreadProcessId(hwnd)
                            if pid == os.getpid():
                                return True
                        except: pass
                        
                        return False
            except: pass
        return True

    def check_active_app(self):
        """Periodic check for Roblox Focus."""
        if self.is_capturing: return
        
        if self.should_show_gui():
            if self.windowOpacity() < 0.5:
                self.apply_visibility(1.0)
        else:
            if self.windowOpacity() > 0.5:
                self.apply_visibility(0.0)

    def apply_visibility(self, opacity):
        """Physical application of transparency."""
        self.setWindowOpacity(opacity)
        if self.setting_window and self.setting_window.isVisible():
            self.setting_window.setWindowOpacity(opacity)
        if self.calc_window and self.calc_window.isVisible():
            self.calc_window.setWindowOpacity(opacity)
        if self.values_window and self.values_window.isVisible():
            self.values_window.setWindowOpacity(opacity)
        if self.inventory_window:
            self.inventory_window.setWindowOpacity(opacity)
        if self.trade_active and self.trade_manager:
            try:
                self.trade_manager.your_offer.setWindowOpacity(opacity)
                self.trade_manager.their_offer.setWindowOpacity(opacity)
            except: pass
        QApplication.processEvents()

    def divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet("background: rgba(255,255,255,0.08);")
        return line

    def build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSizeConstraint(QLayout.SetFixedSize)
        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(330) # Increased from 300
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        header_row = QHBoxLayout()
        
        # Gear Button (Setting)
        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setObjectName("info_btn")
        self.btn_settings.setFixedSize(22, 22)
        self.btn_settings.clicked.connect(self.open_settings)
        header_row.addWidget(self.btn_settings)

        # Values Button
        self.btn_values = QPushButton("📋")
        self.btn_values.setObjectName("info_btn")
        self.btn_values.setFixedSize(22, 22)
        self.btn_values.clicked.connect(self.run_values_script)
        header_row.addWidget(self.btn_values)

        # Inventory Button
        self.btn_inventory = QPushButton("🎒")
        self.btn_inventory.setObjectName("info_btn")
        self.btn_inventory.setFixedSize(22, 22)
        self.btn_inventory.clicked.connect(self.run_inventory_script)
        header_row.addWidget(self.btn_inventory)
        
        header_row.addStretch()
        self.btn_info = QPushButton("i")
        self.btn_info.setObjectName("info_btn")
        self.btn_info.setFixedSize(22, 22)
        self.btn_info.installEventFilter(self) 
        btn_close = QPushButton("✕")
        btn_close.setObjectName("close_btn")
        btn_close.setFixedSize(22, 22)
        btn_close.clicked.connect(self.close_app)
        header_row.addWidget(self.btn_info); header_row.addWidget(btn_close)
        card_layout.addLayout(header_row)
        nav_row = QHBoxLayout()
        nav_row.setSpacing(8)
        self.btn_trade = QPushButton("Trade")
        self.btn_trade.setObjectName("nav_btn")
        self.btn_trade.setFixedHeight(30)
        self.btn_trade.clicked.connect(self.open_trade)
        self.btn_calc = QPushButton("Calculator")
        self.btn_calc.setObjectName("nav_btn")
        self.btn_calc.setFixedHeight(30)
        self.btn_calc.clicked.connect(self.open_calculator)
        nav_row.addWidget(self.btn_trade); nav_row.addWidget(self.btn_calc)
        card_layout.addLayout(nav_row)
        self.values_frame = QFrame()
        self.values_frame.setObjectName("values_box")
        v_box = QVBoxLayout(self.values_frame)
        v_box.setSpacing(10); v_box.setContentsMargins(12, 12, 12, 12)
        stats_row = QHBoxLayout()
        self.lbl_exist = QLabel("EXIST: ---"); self.lbl_exist.setObjectName("pill_pink")
        self.lbl_rap = QLabel("RAP: ---"); self.lbl_rap.setObjectName("pill_purple")
        stats_row.addWidget(self.lbl_exist); stats_row.addStretch(); stats_row.addWidget(self.lbl_rap)
        v_box.addLayout(stats_row)
        self.lbl_updated = QLabel("Waiting for input (Press Z or X)...")
        self.lbl_updated.setObjectName("muted"); self.lbl_updated.setAlignment(Qt.AlignCenter)
        v_box.addWidget(self.lbl_updated)
        card_layout.addWidget(self.values_frame)
        self.lbl_name = QLabel("PET SIM 99"); self.lbl_name.setObjectName("title")
        self.lbl_name.setWordWrap(True); self.lbl_name.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.lbl_name)
        row1 = QHBoxLayout(); row1.addWidget(QLabel("Variant")); row1.addStretch()
        self.lbl_variant = QLabel("-"); row1.addWidget(self.lbl_variant)
        card_layout.addLayout(row1); card_layout.addWidget(self.divider())
        row2 = QHBoxLayout(); row2.addWidget(QLabel("Value")); row2.addStretch()
        self.lbl_value_change = QLabel("-"); self.lbl_value_change.setObjectName("value_up")
        self.lbl_value = QLabel("-"); row2.addWidget(self.lbl_value_change); row2.addWidget(QLabel("|")); row2.addWidget(self.lbl_value)
        card_layout.addLayout(row2); card_layout.addWidget(self.divider())
        row3 = QHBoxLayout(); row3.addWidget(QLabel("Demand")); row3.addStretch()
        self.lbl_demand = QLabel("-"); self.lbl_demand.setObjectName("demand"); row3.addWidget(self.lbl_demand)
        card_layout.addLayout(row3); card_layout.addWidget(self.divider())

        # Add to Inventory Button (Full Width)
        self.btn_add_inv_manual = QPushButton("Add to Inventory")
        self.btn_add_inv_manual.setObjectName("add_inv_btn")
        self.btn_add_inv_manual.setFixedHeight(28)
        self.btn_add_inv_manual.clicked.connect(self.add_to_inventory_manual)
        card_layout.addWidget(self.btn_add_inv_manual)

        # Manual Trade Row
        self.manual_trade_widget = QFrame()
        mt_layout = QHBoxLayout(self.manual_trade_widget); mt_layout.setContentsMargins(0,0,0,0); mt_layout.setSpacing(5)
        self.btn_m_your = QPushButton("Your Offer"); self.btn_m_their = QPushButton("Their Offer")
        self.ent_qty = QLineEdit(); self.ent_qty.setPlaceholderText("Qty"); self.ent_qty.setFixedWidth(45)
        self.ent_qty.setAlignment(Qt.AlignCenter)
        self.ent_qty.setStyleSheet("QLineEdit { background: #0a0b12; color: #fff; border: 1px solid #3a3d66; border-radius: 8px; font-size: 11px; } QLineEdit:focus { border: 1px solid #784da9; }")
        for b in [self.btn_m_your, self.btn_m_their]: b.setObjectName("nav_btn"); b.setFixedHeight(24); b.clicked.connect(self.add_manual_to_trade)
        mt_layout.addWidget(self.btn_m_your); mt_layout.addWidget(self.btn_m_their); mt_layout.addWidget(self.ent_qty)
        self.manual_trade_widget.hide(); card_layout.addWidget(self.manual_trade_widget)

        # Search Section
        self.search_section = SearchSection(self)
        self.search_section.pet_selected.connect(self.update_card)
        card_layout.addWidget(self.search_section)

        outer.addWidget(card)
        self.setStyleSheet("""
        QLabel { color: #eaeaf0; font-size: 14px; }
        #card { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1b1c2b, stop:1 #11121c); border-radius: 18px; padding: 10px; }
        #values_box { background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; }
        #nav_btn { background: #2a2c45; color: #cfd3ff; border-radius: 8px; font-size: 12px; font-weight: bold; }
        #nav_btn:hover { background: #3a3d66; }
        #pill_pink { background: #5b1b3b; color: #ff9acb; padding: 4px 10px; border-radius: 10px; font-size: 11px; font-weight: bold; }
        #pill_purple { background: #3b2b5b; color: #b8a4ff; padding: 4px 10px; border-radius: 10px; font-size: 11px; font-weight: bold; }
        #muted { color: #8a8fa8; font-size: 11px; }
        #title { font-size: 19px; font-weight: bold; color: #ffffff; margin-top: 5px; }
        #value_up { color: #3dff84; font-weight: bold; }
        #demand { color: #6dff9c; }
        QPushButton { border: none; background: transparent; color: #cfd3ff; font-weight: bold; }
        #close_btn:hover { color: #ff5f5f; }
        #info_btn { border-radius: 11px; background: #2a2c45; }
        #info_btn:hover { background: #3a3d66; }
        #add_inv_btn { background: #3b2b5b; color: #b8a4ff; border-radius: 10px; font-size: 13px; font-weight: bold; border: 1px solid #784da9; }
        #add_inv_btn:hover { background: #784da9; color: #ffffff; }
        """)

    def add_to_inventory_manual(self):
        """Manually adds the current pet to the inventory."""
        if not self.current_pet_data: return
        
        # Ensure inventory window is loaded
        if not self.inventory_window:
            from Inventory import InventoryWindow
            self.inventory_window = InventoryWindow()
            if not self.should_show_gui():
                self.inventory_window.setWindowOpacity(0.0)
        
        # Add the pet to inventory
        self.inventory_window.add_pet(self.current_pet_data)

    def open_calculator(self):
        """Toggles the Calculator window."""
        if not self.calc_window:
            self.calc_window = ModernCalculator()
            self.calc_window.show()
            self.calc_window.activateWindow()
        else:
            if self.calc_window.isVisible():
                self.calc_window.hide()
            else:
                self.calc_window.show()
                self.calc_window.activateWindow()

    def open_settings(self):
        """Toggles the Settings window."""
        if not self.setting_window:
            from Setting import SettingWindow
            self.setting_window = SettingWindow()
            self.setting_window.show()
            self.setting_window.activateWindow()
        else:
            if self.setting_window.isVisible():
                self.setting_window.hide()
            else:
                self.setting_window.show()
                self.setting_window.activateWindow()

    def run_values_script(self):
        """Toggles the Values window."""
        if not self.values_window:
            from Values import ValuesWindow
            self.values_window = ValuesWindow()
            self.values_window.show()
            self.values_window.activateWindow()
        else:
            if self.values_window.isVisible():
                self.values_window.hide()
            else:
                self.values_window.show()
                self.values_window.activateWindow()

    def run_inventory_script(self):
        """Toggles the Inventory window."""
        if not self.inventory_window:
            from Inventory import InventoryWindow
            self.inventory_window = InventoryWindow()
            
            # Apply current focus opacity immediately
            if not self.should_show_gui():
                self.inventory_window.setWindowOpacity(0.0)
                
            self.inventory_window.show()
            self.inventory_window.activateWindow()
        else:
            if self.inventory_window.isVisible():
                self.inventory_window.hide()
            else:
                self.inventory_window.show()
                self.inventory_window.activateWindow()

    def open_trade(self):
        if not self.trade_active:
            try:
                from Trade import TradeBackend
                self.trade_manager = TradeBackend()
                self.trade_manager.your_offer.btn_close.clicked.connect(self.stop_trade)
                self.trade_manager.their_offer.btn_close.clicked.connect(self.stop_trade)
                self.trade_active = True
                if self.worker: self.worker.trade_active = True
                self.btn_trade.setStyleSheet("background: #3dff84; color: #11121c;")
                self.btn_trade.setText("Trade (ON)")
                self.manual_trade_widget.show()
            except Exception as e: print(f"[ERROR] Failed to open trade: {e}")
        else: self.stop_trade()

    def stop_trade(self):
        if self.trade_manager:
            self.trade_active = False
            if self.worker: self.worker.trade_active = False
            try: self.trade_manager.close()
            except: pass
            self.trade_manager = None
        self.btn_trade.setStyleSheet(""); self.btn_trade.setText("Trade"); self.manual_trade_widget.hide()

    def add_manual_to_trade(self):
        if not self.current_pet_data or not self.trade_manager: return
        side = "left" if self.sender() == self.btn_m_your else "right"
        qty = self.ent_qty.text()
        qty = int(qty) if qty.isdigit() else 1
        self.trade_manager.route_pet(side, self.current_pet_data, qty)

    def update_status(self, msg): self.lbl_updated.setText(msg)

    def update_card(self, data):
        self.current_pet_data = data
        trigger = data.get("trigger_key")
        if trigger == 'x' and not self.trade_active: return
        
        # Always update main card for Find or Inventory
        if data["found"]:
            self.lbl_name.setText(data.get("full_name", data.get("base_name", data.get("detected_name"))))
            self.lbl_exist.setText(f"EXIST: {data.get('Exist', '?')}")
            self.lbl_rap.setText(f"RAP: {data.get('RAP', '?')}")
            self.lbl_updated.setText(f"Updated: {data.get('last_updated', '?')}")
            self.lbl_variant.setText(data.get("detected_variant", data.get("Variant", "Normal")))
            self.lbl_value.setText(data.get("Value", "?"))
            
            change_text = data.get("value_change", "-")
            self.lbl_value_change.setText(change_text)
            
            # Color coding for value change
            if "▲" in change_text or "up" in change_text.lower():
                self.lbl_value_change.setStyleSheet("color: #3dff84; font-weight: bold;")
            elif "▼" in change_text or "down" in change_text.lower():
                self.lbl_value_change.setStyleSheet("color: #ff5f5f; font-weight: bold;")
            else:
                self.lbl_value_change.setStyleSheet("color: #eaeaf0; font-weight: bold;")

            self.lbl_demand.setText(data.get("Demand", "?"))
        else:
            self.lbl_name.setText(data.get("detected_name", "Unknown"))
            self.lbl_exist.setText("EXIST: ?"); self.lbl_rap.setText("RAP: ?")
            self.lbl_updated.setText("Not found in DB")
            self.lbl_variant.setText(data.get("detected_variant", "-"))
            self.lbl_value.setText("-"); self.lbl_value_change.setText("-"); self.lbl_demand.setText("-")
        
        # Route to Trade
        if trigger == 'x' and self.trade_active and data.get("found"):
            screen_width = QGuiApplication.primaryScreen().geometry().width()
            side = "left" if data.get("mouse_x", 0) < (screen_width / 2) else "right"
            if self.trade_manager: self.trade_manager.route_pet(side, data)
            
        # Route to Inventory
        if trigger == 'inventory' and data.get("found"):
            if not self.inventory_window:
                from Inventory import InventoryWindow
                self.inventory_window = InventoryWindow()
                # Apply focus opacity but keep it hidden if it wasn't already open
                if not self.should_show_gui():
                    self.inventory_window.setWindowOpacity(0.0)
            
            self.inventory_window.add_pet(data)

    def eventFilter(self, source, event):
        if source == self.btn_info:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self.dragging, self.drag_offset = True, event.globalPosition().toPoint() - self.pos()
                return True
            elif event.type() == QEvent.MouseMove and self.dragging:
                self.move(event.globalPosition().toPoint() - self.drag_offset); return True
            elif event.type() == QEvent.MouseButtonRelease: self.dragging = False; return True
        return super().eventFilter(source, event)

    def close_app(self):
        self.worker.running = False
        if self.inventory_window:
            self.inventory_window.close()
        self.ocr_thread.quit(); self.ocr_thread.wait()
        self.close(); QApplication.quit(); sys.exit()

# -----------------------------
# Embedded Search Component
# -----------------------------
class SearchSection(QWidget):
    pet_selected = Signal(dict)

    def __init__(self, parent_card):
        super().__init__()
        self.parent_card = parent_card
        if getattr(sys, 'frozen', False):
            self.script_dir = os.path.dirname(sys.executable)
        else:
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
            
        self.db_path = os.path.join(self.script_dir, "cosmic_values.db")
        self.MAX_DISPLAY = 5
        self.ROW_HEIGHT = 52 # Increased for 2-line room
        
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)
        
        self.setup_ui()
        self.apply_styles()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 0)
        layout.setSpacing(8)

        # Dropdowns Row
        drop_row = QHBoxLayout()
        drop_row.setSpacing(5)
        
        self.combo_category = QComboBox()
        self.combo_category.addItems(["All", "Huges", "Titanics", "Gargantuans", "Misc"])
        self.combo_category.currentIndexChanged.connect(self.perform_search)
        
        self.combo_sort = QComboBox()
        self.combo_sort.addItems(["Default Sort", "Highest Value", "Lowest Value", "Highest Exist", "Lowest Exist", "Alphabetical"])
        self.combo_sort.currentIndexChanged.connect(self.perform_search)
        
        self.combo_variant = QComboBox()
        self.combo_variant.addItems(["All Variants", "Normal", "Golden", "Rainbow", "Shiny"])
        self.combo_variant.currentIndexChanged.connect(self.perform_search)
        
        for c in [self.combo_category, self.combo_sort, self.combo_variant]:
            c.setFixedHeight(26)
        
        drop_row.addWidget(self.combo_category)
        drop_row.addWidget(self.combo_sort)
        drop_row.addWidget(self.combo_variant)
        layout.addLayout(drop_row)

        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Quick search...")
        self.search_input.setFixedHeight(30)
        self.search_input.setObjectName("search_input")
        self.search_input.textChanged.connect(lambda: self.search_timer.start(300))
        layout.addWidget(self.search_input)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["PET", "VALUE", "EXIST", "DEMAND"])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setWordWrap(True)
        self.table.setItemDelegateForColumn(0, TableNameDelegate(self.table))
        self.table.setFixedHeight(0) # Hidden by default
        self.table.itemDoubleClicked.connect(self.on_select)
        self.table.installEventFilter(self)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 65) # Value
        self.table.setColumnWidth(2, 45) # Exist
        self.table.setColumnWidth(3, 55) # Demand (increased to fit label)
        
        layout.addWidget(self.table)

    def apply_styles(self):
        self.setStyleSheet("""
            QComboBox { background: #1a1c2b; color: #ffffff; border: 1px solid #3a3d66; border-radius: 4px; font-size: 10px; padding: 2px 4px; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #1a1c2b; color: #ffffff; selection-background-color: #784da9; outline: none; border: 1px solid #3a3d66; }
            QComboBox QAbstractItemView::item { color: #ffffff; padding: 4px; }
            QComboBox QAbstractItemView QScrollBar:vertical { width: 0px; }
            
            #search_input { background: #0a0b12; color: #fff; border: 1px solid #3a3d66; border-radius: 6px; padding: 4px 8px; font-size: 11px; }
            #search_input:focus { border: 1px solid #784da9; }
            
                    QTableWidget { background: transparent; border: none; outline: none; color: #fff; font-size: 11px; }
                    QHeaderView::section { background: rgba(45, 27, 77, 0.5); color: #4B0082; padding: 4px; border: none; font-size: 11px; font-weight: bold; text-transform: uppercase; }
                    QTableWidget::item { border-bottom: 1px solid rgba(255,255,255,0.05); border-right: 1px solid rgba(255,255,255,0.05); }            QTableWidget::item:selected { background: #0078d7; }
        """)

    def perform_search(self):
        text = self.search_input.text().strip().lower()
        cat = self.combo_category.currentText().lower()
        sort_mode = self.combo_sort.currentText()
        var_mode = self.combo_variant.currentText().lower()
        
        # Determine if we should show results
        is_default = (not text and cat == "all" and sort_mode == "Default Sort" and "all" in var_mode)
        
        if is_default:
            self.table.setRowCount(0)
            self.table.setFixedHeight(0)
            self.parent_card.adjustSize()
            return

        # Query logic
        query = "SELECT [Pet Name], Value, Exist, Demand, [Value Change], RAP, [Last Updated], GOLD, RAINBOW, SHINY, Name FROM master WHERE 1=1"
        if cat == "huges": 
            query += " AND LOWER([Pet Name]) LIKE '%huge%'"
        elif cat == "titanics": 
            query += " AND LOWER([Pet Name]) LIKE '%titanic%'"
        elif cat == "gargantuans": 
            query += " AND LOWER([Pet Name]) LIKE '%gargantuan%'"
        elif cat == "misc":
            query += " AND LOWER([Pet Name]) NOT LIKE '%huge%' AND LOWER([Pet Name]) NOT LIKE '%titanic%' AND LOWER([Pet Name]) NOT LIKE '%gargantuan%'"

        params = []
        if text:
            query += " AND (LOWER([Pet Name]) LIKE ? OR LOWER(Name) LIKE ?)"
            params.extend([f"%{text}%", f"%{text}%"])

        if "normal" in var_mode: query += " AND GOLD=0 AND RAINBOW=0 AND SHINY=0"
        elif "golden" in var_mode: query += " AND GOLD=1 AND RAINBOW=0"
        elif "rainbow" in var_mode: query += " AND RAINBOW=1"
        elif "shiny" in var_mode: query += " AND SHINY=1"

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(query, params)
            raw = cursor.fetchall()
            conn.close()
            
            processed = []
            for r in raw:
                processed.append({
                    'display': r[0], 'value_s': r[1], 'value_f': parse_price(r[1]),
                    'exist_s': r[2], 'exist_f': float(re.sub(r'[^\d.]', '', str(r[2]).replace(',', '')) or 0) if r[2] != "?" else 0,
                    'demand_s': r[3], 'demand_f': parse_demand(r[3]),
                    'change': r[4], 'rap': r[5], 'updated': r[6], 'variant': 'Normal' # simplified
                })

            if sort_mode == "Highest Value": processed.sort(key=lambda x: x['value_f'], reverse=True)
            elif sort_mode == "Lowest Value": processed.sort(key=lambda x: x['value_f'])
            elif sort_mode == "Highest Exist": processed.sort(key=lambda x: x['exist_f'], reverse=True)
            elif sort_mode == "Lowest Exist": processed.sort(key=lambda x: x['exist_f'])
            elif sort_mode == "Alphabetical": processed.sort(key=lambda x: x['display'])

            display = processed[:self.MAX_DISPLAY]
            self.table.setRowCount(0)
            if display:
                for d in display:
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    self.table.setItem(row, 0, QTableWidgetItem(d['display']))
                    
                    val_item = QTableWidgetItem(d['value_s'])
                    val_item.setTextAlignment(Qt.AlignCenter)
                    val_item.setFont(QFont("Segoe UI", 11, QFont.Bold))
                    self.table.setItem(row, 1, val_item)
                    
                    ex_item = QTableWidgetItem(d['exist_s'])
                    ex_item.setTextAlignment(Qt.AlignCenter)
                    ex_item.setFont(QFont("Segoe UI", 11))
                    self.table.setItem(row, 2, ex_item)
                    
                    dem = QTableWidgetItem(d['demand_s'])
                    dem.setTextAlignment(Qt.AlignCenter)
                    dem.setFont(QFont("Segoe UI", 11))
                    dem_c = "#4ade80" if d['demand_f'] >= 7 else ("#facc15" if d['demand_f'] >= 4 else "#ef4444")
                    dem.setForeground(QColor(dem_c))
                    self.table.setItem(row, 3, dem)
                    
                    self.table.setRowHeight(row, self.ROW_HEIGHT)
                    self.table.item(row, 0).setData(Qt.UserRole, d)

                h_height = self.table.horizontalHeader().height() or 25
                self.table.setFixedHeight(h_height + (len(display) * self.ROW_HEIGHT) + 2)
            else:
                self.table.setFixedHeight(0)
            
            self.parent_card.adjustSize()
        except: pass

    def on_select(self, item):
        row = item.row()
        data = self.table.item(row, 0).data(Qt.UserRole)
        if data:
            payload = {
                "found": True,
                "full_name": data['display'],
                "Value": data['value_s'],
                "value_change": data['change'],
                "Exist": data['exist_s'],
                "RAP": data['rap'],
                "Demand": data['demand_s'],
                "last_updated": data['updated'],
                "Variant": data['variant'],
                "trigger_key": 'search'
            }
            self.pet_selected.emit(payload)
            # Clear to hide
            self.search_input.clear()
            self.combo_category.setCurrentIndex(0)
            self.combo_variant.setCurrentIndex(0)
            self.perform_search()

    def eventFilter(self, source, event):
        if source == self.table and event.type() == QEvent.KeyPress:
            if event.key() in [Qt.Key_Return, Qt.Key_Enter]:
                curr = self.table.currentItem()
                if curr: self.on_select(curr); return True
            if event.key() == Qt.Key_Tab:
                curr = self.table.currentRow()
                next_row = (curr + 1) if curr < self.table.rowCount() - 1 else 0
                self.table.setCurrentCell(next_row, 0)
                return True
        return super().eventFilter(source, event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = FloatingPetCard()
    w.show()
    sys.exit(app.exec())

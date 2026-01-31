import sys
import os
import json
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QFrame, QLayout, QToolTip, QLineEdit
)
from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtGui import QFont, QColor, QDoubleValidator, QIntValidator, QKeyEvent, QCursor, QKeySequence, QMouseEvent

class InfoLabel(QLabel):
    """Custom label for (i) that shows tooltips instantly and has hover effects."""
    def __init__(self, tooltip_text):
        super().__init__("ⓘ")
        self.setFixedSize(18, 18)
        self.setAlignment(Qt.AlignCenter)
        self.setToolTip(tooltip_text)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QLabel {
                color: #8a8fa8; 
                font-size: 14px; 
                border: 1px solid #3a3d66; 
                border-radius: 9px;
                background: #2a2c45;
            }
            QLabel:hover {
                color: #ffffff;
                background: #3a3d66;
                border-color: #cfd3ff;
            }
        """)

    def enterEvent(self, event):
        QToolTip.showText(QCursor.pos(), self.toolTip(), self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        QToolTip.hideText()
        super().leaveEvent(event)

class KeyBindButton(QPushButton):
    def __init__(self, setting_key, default_data, parent_window):
        super().__init__()
        self.setting_key = setting_key
        self.default_data = default_data
        self.parent_window = parent_window
        self.is_recording = False
        
        # This is critical for capturing TAB and other system keys
        self.setFocusPolicy(Qt.StrongFocus)
        
        self.update_display()
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self.start_recording)

    def update_display(self):
        key_data = self.parent_window.settings.get(self.setting_key, self.default_data)
        text = key_data.get("name", "NONE").upper()
        self.setText(text)
        self.setStyleSheet(self.get_style(False))

    def get_style(self, recording):
        bg = "#3a3d66" if not recording else "#784da9"
        border = "#3a3d66" if not recording else "#bb86fc"
        return f"""
            QPushButton {{
                background-color: {bg};
                color: #ffffff;
                border: 1px solid {border};
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                min-width: 80px;
                padding: 5px;
                outline: none;
            }}
            QPushButton:focus {{ border: 1px solid {border}; }}
            QPushButton:hover {{ background-color: #4a4d76; }}
        """

    def start_recording(self):
        if self.is_recording: return
        self.is_recording = True
        current_text = self.text()
        self.setText(f"> {current_text} <")
        self.setStyleSheet(self.get_style(True))
        self.grabKeyboard()
        self.grabMouse()

    def keyPressEvent(self, event: QKeyEvent):
        if self.is_recording:
            key_code = event.key()
            if key_code == Qt.Key_Escape:
                self.stop_recording()
                return

            vk = event.nativeVirtualKey()
            text = event.text()
            
            # Special case for Minecraft style names
            key_name = QKeySequence(key_code).toString().lower()
            if not key_name or len(key_name) > 15:
                key_name = text.lower() if text else "unknown"
            
            # Standardizing names
            mapping = {"backspace": "backspace", "tab": "tab", "return": "enter", "enter": "enter", "space": "space"}
            if key_name in mapping: key_name = mapping[key_name]

            self.save_bind({"name": key_name, "char": text if text else None, "vk": vk, "type": "keyboard"})
            self.stop_recording()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if self.is_recording:
            # If click is outside the button boundaries while recording, cancel recording
            if not self.rect().contains(event.position().toPoint()):
                self.stop_recording()
                return

            btn = event.button()
            key_data = None
            
            # Map mouse buttons if click is INSIDE the button
            if btn == Qt.LeftButton: key_data = {"name": "left click", "vk": 1, "type": "mouse"}
            elif btn == Qt.RightButton: key_data = {"name": "right click", "vk": 2, "type": "mouse"}
            elif btn == Qt.MiddleButton: key_data = {"name": "middle click", "vk": 4, "type": "mouse"}
            elif btn == Qt.XButton1: key_data = {"name": "mouse x1", "vk": 5, "type": "mouse"}
            elif btn == Qt.XButton2: key_data = {"name": "mouse x2", "vk": 6, "type": "mouse"}
            
            if key_data:
                self.save_bind(key_data)
                self.stop_recording()
        else:
            super().mousePressEvent(event)

    def save_bind(self, data):
        self.parent_window.settings[self.setting_key] = data
        self.parent_window.save_settings()

    def stop_recording(self):
        self.is_recording = False
        self.releaseKeyboard()
        self.releaseMouse()
        self.update_display()

    def focusOutEvent(self, event):
        if self.is_recording:
            self.stop_recording()
        super().focusOutEvent(event)

class SettingWindow(QWidget):
    def __init__(self):
        super().__init__()
        if getattr(sys, 'frozen', False):
            self.script_dir = os.path.dirname(sys.executable)
        else:
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
            
        self.config_path = os.path.join(self.script_dir, "settings_config.json")
        self.settings = self.load_settings()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.dragging = False
        self.drag_offset = QPoint()
        self.build_ui()

    def load_settings(self):
        defaults = {
            "stealth_mode": False, 
            "roblox_only": False, 
            "calc_size": 0.95,
            "batch_size": 1,
            "bind_find": {"name": "z", "char": "z", "vk": 90, "type": "keyboard"},
            "bind_trade": {"name": "x", "char": "x", "vk": 88, "type": "keyboard"},
            "bind_inventory": {"name": "shift", "char": None, "vk": 16, "type": "keyboard"}
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    for k, v in defaults.items():
                        if k not in data: data[k] = v
                    return data
            except: pass
        return defaults

    def save_settings(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.settings, f)
        except Exception as e: print(f"Save error: {e}")

    def build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSizeConstraint(QLayout.SetFixedSize)

        self.card = QFrame()
        self.card.setObjectName("card")
        self.card.setFixedSize(340, 360)
        
        card_layout = QVBoxLayout(self.card)
        card_layout.setSpacing(15)
        card_layout.setContentsMargins(15, 10, 15, 15)

        header_row = QHBoxLayout()
        self.title_lbl = QLabel("SETTING")
        self.title_lbl.setObjectName("title")
        header_row.addWidget(self.title_lbl)
        header_row.addStretch()
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("close_btn")
        self.btn_close.setFixedSize(22, 22)
        self.btn_close.clicked.connect(self.hide)
        header_row.addWidget(self.btn_close)
        card_layout.addLayout(header_row)

        self.add_toggle_setting(card_layout, "GUI Stealth Mode", "stealth_mode", "Hides all GUI windows for a moment during screenshot capture\nto prevent UI overlap.")
        self.add_toggle_setting(card_layout, "Show GUI Only in Roblox", "roblox_only", "Automatically hides all windows when you switch away from Roblox.")
        
        self.add_bind_setting(card_layout, "Find Value", "bind_find", "z", "When this key is pressed it will analyze your screen and tell the details about the pet you are hovering on.")
        self.add_bind_setting(card_layout, "Update Trade", "bind_trade", "x", "Add pet value in trade. When this key is pressed it will analyze your screen and tell the details about the pet you are hovering on.")
        self.add_bind_setting_special(card_layout, "Inventory", "bind_inventory", {"name": "shift", "char": None, "vk": 16, "type": "keyboard"}, "the pet will be added to your inventory.")

        # Batch Size
        self.add_batch_setting(card_layout, "Batch Size", "batch_size", "Number of images analyzed at once. Range: 1-16.")

        # Calculator Size
        self.add_input_setting(card_layout, "Calculator Size", "calc_size")

        self.update_toggle_style()
        card_layout.addStretch()
        outer.addWidget(self.card)

        self.setStyleSheet("""
        QLabel { color: #eaeaf0; font-family: 'Segoe UI', sans-serif; }
        #card { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1b1c2b, stop:1 #11121c); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 18px; padding: 10px; }
        #title { font-size: 19px; font-weight: bold; color: #ffffff; margin-top: 2px; }
        QPushButton#close_btn { border: none; background: transparent; color: #cfd3ff; font-weight: bold; outline: none; }
        QPushButton#close_btn:hover { color: #ffffff; background-color: #ef4444; border-radius: 4px; }
        QToolTip { 
            background-color: #000000; 
            color: #ffffff; 
            border: 1px solid #3a3d66; 
            padding: 8px; 
            font-size: 13px;
            border-radius: 5px;
        }
        """
)

    def add_toggle_setting(self, layout, title, key, tooltip):
        row = QHBoxLayout()
        lbl = QLabel(title); lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #cfd3ff;")
        info = InfoLabel(tooltip)
        row.addWidget(lbl); row.addWidget(info); row.addStretch()
        toggle = QPushButton(); toggle.setFixedSize(44, 22); toggle.setCursor(Qt.PointingHandCursor)
        toggle.clicked.connect(lambda: self.toggle_bool(key))
        if key == "stealth_mode": self.toggle_btn = toggle
        else: self.roblox_toggle = toggle
        row.addWidget(toggle); layout.addLayout(row)

    def add_bind_setting(self, layout, title, key, default_char, tooltip):
        row = QHBoxLayout()
        lbl = QLabel(title); lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #cfd3ff;")
        info = InfoLabel(tooltip)
        row.addWidget(lbl); row.addWidget(info); row.addStretch()
        
        reset_btn = QPushButton("Reset")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.setStyleSheet("background: transparent; color: #8a8fa8; font-size: 12px; border: 1px solid #3a3d66; border-radius: 4px; padding: 3px 8px; outline: none;")
        
        default_data = {"name": default_char, "char": default_char, "vk": ord(default_char.upper()), "type": "keyboard"}
        bind_btn = KeyBindButton(key, default_data, self)
        reset_btn.clicked.connect(lambda: self.reset_bind(key, default_data, bind_btn))
        
        row.addWidget(reset_btn); row.addWidget(bind_btn); layout.addLayout(row)

    def add_bind_setting_special(self, layout, title, key, default_data, tooltip):
        row = QHBoxLayout()
        lbl = QLabel(title); lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #cfd3ff;")
        info = InfoLabel(tooltip)
        row.addWidget(lbl); row.addWidget(info); row.addStretch()
        
        reset_btn = QPushButton("Reset")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.setStyleSheet("background: transparent; color: #8a8fa8; font-size: 12px; border: 1px solid #3a3d66; border-radius: 4px; padding: 3px 8px; outline: none;")
        
        bind_btn = KeyBindButton(key, default_data, self)
        reset_btn.clicked.connect(lambda: self.reset_bind(key, default_data, bind_btn))
        
        row.addWidget(reset_btn); row.addWidget(bind_btn); layout.addLayout(row)

    def add_input_setting(self, layout, title, key):
        row = QHBoxLayout()
        lbl = QLabel(title); lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #cfd3ff;")
        row.addWidget(lbl); row.addStretch()
        inp = QLineEdit(); inp.setFixedWidth(60); inp.setText(str(self.settings.get(key))); inp.setAlignment(Qt.AlignCenter)
        inp.setStyleSheet("background: #1a1c2b; color: #ffffff; border: 1px solid #3a3d66; border-radius: 4px; font-size: 12px; outline: none;")
        inp.editingFinished.connect(lambda: self.save_val(key, inp))
        row.addWidget(inp); layout.addLayout(row)

    def add_batch_setting(self, layout, title, key, tooltip):
        row = QHBoxLayout()
        lbl = QLabel(title); lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #cfd3ff;")
        info = InfoLabel(tooltip)
        row.addWidget(lbl); row.addWidget(info); row.addStretch()
        
        inp = QLineEdit()
        inp.setFixedWidth(60)
        inp.setText(str(self.settings.get(key, 1)))
        inp.setAlignment(Qt.AlignCenter)
        validator = QIntValidator(1, 16)
        inp.setValidator(validator)
        inp.setStyleSheet("background: #1a1c2b; color: #ffffff; border: 1px solid #3a3d66; border-radius: 4px; font-size: 12px; outline: none;")
        inp.editingFinished.connect(lambda: self.save_batch_val(key, inp))
        
        row.addWidget(inp)
        layout.addLayout(row)

    def toggle_bool(self, key):
        self.settings[key] = not self.settings[key]
        self.save_settings(); self.update_toggle_style()

    def reset_bind(self, key, default_data, btn):
        self.settings[key] = default_data
        self.save_settings(); btn.update_display()

    def save_val(self, key, inp):
        try: self.settings[key] = float(inp.text())
        except: self.settings[key] = 0.95; inp.setText("0.95")
        self.save_settings()

    def save_batch_val(self, key, inp):
        try:
            val = int(inp.text())
            if not (1 <= val <= 16):
                val = 1
                inp.setText("1")
            self.settings[key] = val
        except:
            self.settings[key] = 1
            inp.setText("1")
        self.save_settings()

    def update_toggle_style(self):
        for toggle, key in [(self.toggle_btn, "stealth_mode"), (self.roblox_toggle, "roblox_only")]:
            is_on = self.settings.get(key)
            toggle.setText("ON" if is_on else "OFF")
            toggle.setStyleSheet(f"background-color: {'#3dff84' if is_on else '#3a3d66'}; color: {'#11121c' if is_on else '#cfd3ff'}; border-radius: 11px; font-weight: bold; font-size: 10px; outline: none;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging, self.drag_offset = True, event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self.dragging: self.move(event.globalPosition().toPoint() - self.drag_offset)

    def mouseReleaseEvent(self, event): self.dragging = False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SettingWindow(); window.show()
    sys.exit(app.exec())
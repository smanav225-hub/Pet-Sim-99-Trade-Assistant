import sys
import re
import os
import json
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QFrame, QGridLayout, QLineEdit
)
from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtGui import QKeyEvent

# --- CONFIGURATION ---
# Load scale factor from settings
def load_scale_factor():
    if getattr(sys, 'frozen', False):
        script_dir = os.path.dirname(sys.executable)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
    config_path = os.path.join(script_dir, "settings_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                return json.load(f).get("calc_size", 0.95)
        except: pass
    return 0.95

SCALE_FACTOR = load_scale_factor()
# ---------------------

class ModernCalculator(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.dragging = False
        self.drag_offset = QPoint()
        
        self.expression = ""
        
        self.build_ui()

    def s(self, value):
        """Scale a pixel value by the SCALE_FACTOR."""
        return int(value * SCALE_FACTOR)

    def build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(self.s(10), self.s(10), self.s(10), self.s(10))
        outer.setSizeConstraint(QVBoxLayout.SetFixedSize)

        self.card = QFrame()
        self.card.setObjectName("card")
        self.card.setFixedWidth(self.s(320))

        card_layout = QVBoxLayout(self.card)
        card_layout.setSpacing(self.s(15))

        # --- Top Bar ---
        top_bar = QHBoxLayout()
        
        title = QLabel("CALCULATOR")
        title.setObjectName("title_small")
        
        self.btn_info = QPushButton("i")
        self.btn_info.setObjectName("info_btn")
        self.btn_info.setFixedSize(self.s(22), self.s(22))
        self.btn_info.installEventFilter(self)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("close_btn")
        btn_close.setFixedSize(self.s(22), self.s(22))
        btn_close.clicked.connect(self.close_app)

        top_bar.addWidget(title)
        top_bar.addStretch()
        top_bar.addWidget(self.btn_info)
        top_bar.addWidget(btn_close)
        card_layout.addLayout(top_bar)

        # --- Display Area ---
        display_frame = QFrame()
        display_frame.setObjectName("display_frame")
        display_layout = QVBoxLayout(display_frame)
        display_layout.setContentsMargins(self.s(10), self.s(5), self.s(10), self.s(5))
        display_layout.setSpacing(self.s(2))

        self.lbl_history = QLabel("")
        self.lbl_history.setObjectName("lbl_history")
        self.lbl_history.setAlignment(Qt.AlignRight)
        
        self.entry = QLineEdit()
        self.entry.setObjectName("entry")
        self.entry.setAlignment(Qt.AlignRight)
        self.entry.setPlaceholderText("0")
        self.entry.textChanged.connect(self.on_text_changed)

        display_layout.addWidget(self.lbl_history)
        display_layout.addWidget(self.entry)
        card_layout.addWidget(display_frame)

        # --- Buttons ---
        grid = QGridLayout()
        grid.setSpacing(self.s(8))

        buttons = [
            ('C', 0, 0), ('K', 0, 1), ('M', 0, 2), ('B', 0, 3),
            ('7', 1, 0), ('8', 1, 1), ('9', 1, 2), ('/', 1, 3),
            ('4', 2, 0), ('5', 2, 1), ('6', 2, 2), ('*', 2, 3),
            ('1', 3, 0), ('2', 3, 1), ('3', 3, 2), ('-', 3, 3),
            ('0', 4, 0), ('.', 4, 1), ('⌫', 4, 2), ('+', 4, 3),
            ('=', 5, 0, 1, 4)
        ]

        for b_info in buttons:
            if len(b_info) == 3:
                text, r, c = b_info
                row_span, col_span = 1, 1
            else:
                text, r, c, row_span, col_span = b_info

            btn = QPushButton(text)
            if col_span > 1:
                btn.setFixedHeight(self.s(50))
                btn.setMinimumWidth(self.s(280))
            else:
                btn.setFixedSize(self.s(65), self.s(50))

            if text.isdigit() or text == '.':
                btn.setObjectName("num_btn")
            elif text == '=':
                btn.setObjectName("equal_btn")
            elif text in ['K', 'M', 'B']:
                btn.setObjectName("unit_btn")
            elif text == '⌫':
                btn.setObjectName("back_btn")
            else:
                btn.setObjectName("op_btn")
            
            btn.clicked.connect(lambda _, ch=text: self.on_button_click(ch))
            grid.addWidget(btn, r, c, row_span, col_span)

        card_layout.addLayout(grid)
        outer.addWidget(self.card)

        # Dynamic Stylesheet with Scaled Values
        self.setStyleSheet(f"""
        #card {{
            background: #000000;
            border-radius: {self.s(18)}px;
            padding: {self.s(12)}px;
            border: 1px solid #1a1a1a;
        }}

        #title_small {{
            color: #444444;
            font-size: {self.s(11)}px;
            font-weight: bold;
            letter-spacing: 1px;
        }}

        #display_frame {{
            background: #080808;
            border-radius: {self.s(12)}px;
            border: 1px solid #111111;
        }}

        #lbl_history {{
            color: #555555;
            font-size: {self.s(12)}px;
        }}

        #entry {{
            background: transparent;
            border: none;
            color: #ffffff;
            font-size: {self.s(24)}px;
            font-weight: bold;
        }}

        QPushButton {{
            border: none;
            border-radius: {self.s(10)}px;
            font-size: {self.s(16)}px;
            font-weight: bold;
            color: #eaeaf0;
            background: #111111;
        }}

        QPushButton:hover {{
            background: #1a1a1a;
        }}

        #num_btn {{
            background: #0a0a0a;
            color: #dddddd;
        }}

        #op_btn {{
            background: #151515;
            color: #b8a4ff;
        }}

        #unit_btn {{
            background: #1a1425;
            color: #ff9acb;
        }}
                           
        #back_btn {{
            background: #1a1425;
            color: #ff9acb;
        }}

        #equal_btn {{
            background: #784da9;
            color: white;
        }}

        #equal_btn:hover {{
            background: #8a5bc2;
        }}

        #close_btn {{
            background: transparent;
            color: #444444;
        }}

        #close_btn:hover {{
            color: #ff5f5f;
        }}

        #info_btn {{
            border-radius: {self.s(11)}px;
            background: #111111;
            color: #444444;
        }}

        #info_btn:hover {{
            background: #1a1a1a;
            color: #cfd3ff;
        }}
        """)

    def on_text_changed(self, text):
        self.expression = text

    def on_button_click(self, char):
        if char == 'C':
            self.entry.clear()
            self.lbl_history.clear()
        elif char == '⌫':
            current = self.entry.text()
            self.entry.setText(current[:-1])
        elif char == '=':
            self.calculate()
        else:
            current = self.entry.text()
            self.entry.setText(str(current) + str(char))

    def calculate(self):
        try:
            raw_expr = self.entry.text()
            if not raw_expr:
                return
            
            # Prepare for eval
            processed_expr = raw_expr.upper().replace('X', '*')
            # Improved regex to handle cases like .5K or 1.5K
            processed_expr = re.sub(r'(\d*\.?\d+)K', r'(\1*1000)', processed_expr)
            processed_expr = re.sub(r'(\d*\.?\d+)M', r'(\1*1000000)', processed_expr)
            processed_expr = re.sub(r'(\d*\.?\d+)B', r'(\1*1000000000)', processed_expr)
            
            # Basic validation
            if not re.match(r'^[0-9\+\-\*\/\.\(\)\s\*e\+]+$', processed_expr):
                 pass

            result = eval(processed_expr)
            formatted_result = self.format_number(result)
            
            self.lbl_history.setText(raw_expr)
            self.entry.setText(formatted_result)
        except Exception as e:
            self.lbl_history.setText("Error")
            print(f"Calc error: {e}")

    def format_number(self, num):
        try:
            num = float(num)
            abs_num = abs(num)
            if abs_num >= 1_000_000_000:
                val = num / 1_000_000_000
                return f"{val:.3f}" + "B"
            elif abs_num >= 1_000_000:
                val = num / 1_000_000
                return f"{val:.3f}" + "M"
            elif abs_num >= 1_000:
                val = num / 1_000
                return f"{val:.3f}" + "K"
            else:
                return f"{num:.3f}"
        except:
            return str(num)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.calculate()
        elif event.key() == Qt.Key_Escape:
            self.entry.clear()
        elif event.key() == Qt.Key_Backspace:
            current = self.entry.text()
            self.entry.setText(current[:-1])
        else:
            super().keyPressEvent(event)

    def eventFilter(self, source, event):
        if source == self.btn_info:
            if event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    self.dragging = True
                    self.drag_offset = event.globalPosition().toPoint() - self.pos()
                    return True
            elif event.type() == QEvent.MouseMove:
                if self.dragging:
                    self.move(event.globalPosition().toPoint() - self.drag_offset)
                    return True
            elif event.type() == QEvent.MouseButtonRelease:
                self.dragging = False
                return True
        return super().eventFilter(source, event)

    def close_app(self):
        self.hide()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    calc = ModernCalculator()
    calc.show()
    sys.exit(app.exec())
import sys
import os
import sqlite3
import re
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QFrame, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QStyledItemDelegate, QStyle,
    QLineEdit, QComboBox, QLayout
)
from PySide6.QtCore import Qt, QPoint, QSize, QTimer, QPropertyAnimation, QEasingCurve, QEvent
from PySide6.QtGui import QFont, QColor, QTextOption, QCursor

# --- CONFIGURATION ---
MAX_DISPLAY = 5  # Max results per view

# Helper to parse K/M/B strings into floats for sorting
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

class NameDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        
        # Selection highlight logic
        if option.state & QStyle.State_Selected:
            bg_color = QColor("#0078d7") # Bright Blue for selection
        else:
            bg_color = QColor(0, 0, 0, 0) # Transparent normally
            
        painter.fillRect(option.rect, bg_color)
        
        # Grid lines / Separators
        painter.setPen(QColor(255, 255, 255, 15))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        painter.drawLine(option.rect.topRight(), option.rect.bottomRight())
        
        text = index.data()
        rect = option.rect.adjusted(10, 0, -5, 0)
        font = painter.font()
        font.setFamily("Segoe UI"); font.setPointSize(10); font.setBold(True); painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        opt = QTextOption(); opt.setWrapMode(QTextOption.WordWrap); opt.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        painter.drawText(rect, text, opt); painter.restore()
    def sizeHint(self, option, index): return QSize(180, 47)

class SearchWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        if getattr(sys, 'frozen', False):
            self.script_dir = os.path.dirname(sys.executable)
        else:
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
            
        self.db_path = os.path.join(self.script_dir, "cosmic_values.db")
        
        self.dragging = False
        self.drag_offset = QPoint()
        self.details_visible = False
        self.MAX_RESULTS = 10
        self.ROW_HEIGHT = 47
        self.HEADER_HEIGHT = 50
        self.CONTROL_HEIGHT = 160 # Approx height of header + dropdowns + search bar
        
        # Debounce timer for search
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)
        
        self.setup_ui()
        self.apply_styles()
        self.perform_search()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        
        self.card = QFrame()
        self.card.setObjectName("card")
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(0)
        
        # Header (App.py style)
        self.header_frame = QFrame()
        self.header_frame.setFixedHeight(50)
        self.header_frame.setObjectName("header")
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(15, 0, 15, 0)
        
        self.title_lbl = QLabel("DATABASE SEARCH")
        self.title_lbl.setObjectName("title")
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("close_btn")
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.clicked.connect(self.hide)
        
        header_layout.addWidget(self.title_lbl)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_close)
        self.card_layout.addWidget(self.header_frame)
        
        # Content Area
        self.content_frame = QFrame()
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(15, 10, 15, 15)
        self.content_layout.setSpacing(12)
        
        # Dropdowns Row (3 Dropdowns)
        drop_row = QHBoxLayout()
        drop_row.setSpacing(8)
        
        # Dropdown 3: Category (First)
        self.combo_category = QComboBox()
        self.combo_category.addItems(["All", "Huges", "Titanics", "Gargantuans", "Misc"])
        self.combo_category.currentIndexChanged.connect(self.perform_search)
        
        # Dropdown 1: Sort (Second)
        self.combo_sort = QComboBox()
        self.combo_sort.addItems([
            "Default Sort", "Recently Updated", "Lowest Exist", "Highest Exist",
            "Lowest Value", "Highest Value", "Lowest RAP", "Highest RAP",
            "Lowest Demand", "Highest Demand", "Alphabetical"
        ])
        self.combo_sort.currentIndexChanged.connect(self.perform_search)
        
        # Dropdown 2: Variant (Third)
        self.combo_variant = QComboBox()
        self.combo_variant.addItems([
            "All Variants", "Normal", "Golden", "Rainbow", "Shiny",
            "Shiny Rainbow", "Shiny Golden"
        ])
        self.combo_variant.currentIndexChanged.connect(self.perform_search)
        
        drop_row.addWidget(self.combo_category)
        drop_row.addWidget(self.combo_sort)
        drop_row.addWidget(self.combo_variant)
        self.content_layout.addLayout(drop_row)
        
        # Search Entry
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search pets or items...")
        self.search_input.setObjectName("search_input")
        self.search_input.textChanged.connect(lambda: self.search_timer.start(300))
        self.content_layout.addWidget(self.search_input)
        
        # Table (Trade.py style)
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["PET NAME", "VALUE", "EXIST", "DEMAND", "CHANGE", "RAP", "UPDATED"])
        self.table.setObjectName("pet_table")
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        # Force scrollbars off via policy
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Override keyPress to handle Tab -> Down
        self.table.installEventFilter(self)
        
        self.table.setItemDelegateForColumn(0, NameDelegate(self.table))
        
        t_header = self.table.horizontalHeader()
        t_header.setSectionResizeMode(0, QHeaderView.Stretch)
        t_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        t_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        t_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        for i in range(4, 7): self.table.setColumnHidden(i, True)
        
        self.content_layout.addWidget(self.table)
        
        # Footer
        self.footer_layout = QHBoxLayout()
        self.btn_details = QPushButton("Show Details")
        self.btn_details.setObjectName("details_btn")
        self.btn_details.setFixedSize(110, 28)
        self.btn_details.clicked.connect(self.toggle_details)
        self.footer_layout.addStretch()
        self.footer_layout.addWidget(self.btn_details)
        self.content_layout.addLayout(self.footer_layout)
        
        self.card_layout.addWidget(self.content_frame)
        self.main_layout.addWidget(self.card)
        self.setFixedWidth(480) # Increased from 450 to ensure all elements fit
        self.update_window_height(animate=False)

    def apply_styles(self):
        self.setStyleSheet("""
            #card { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1b1c2b, stop:1 #11121c); border-radius: 15px; border: 1px solid rgba(255, 255, 255, 0.12); }
            #header { background: rgba(0,0,0,0.2); border-top-left-radius: 15px; border-top-right-radius: 15px; border-bottom: 1px solid rgba(255,255,255,0.05); }
            #title { font-size: 15px; font-weight: 800; color: #D1C4E9; letter-spacing: 1px; }
            #close_btn { border: none; background: transparent; color: #555; font-size: 14px; }
            #close_btn:hover { color: #fff; background: #ef4444; border-radius: 5px; }
            
            #search_input { background: #0a0b12; color: #fff; border: 1px solid #3a3d66; border-radius: 8px; padding: 10px; font-size: 13px; selection-background-color: #784da9; }
            #search_input:focus { border: 1px solid #784da9; }
            
            QComboBox { background: #0a0b12; color: #cfd3ff; border: 1px solid #3a3d66; border-radius: 6px; padding: 6px 8px; font-weight: bold; font-size: 11px; }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow { image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 4px solid #784da9; margin-right: 8px; }
            QComboBox QAbstractItemView { background: #0a0b12; color: #cfd3ff; border: 1px solid #3a3d66; selection-background-color: #784da9; outline: none; }
            
            /* Remove scrollbar from dropdown list */
            QComboBox QAbstractItemView QScrollBar:vertical { width: 0px; background: transparent; }
            
            #pet_table { background: #000; border: none; color: #fff; font-size: 12px; outline: none; }
            QHeaderView::section { background: #2D1B4D; color: #D1C4E9; padding: 8px; border: none; font-size: 10px; font-weight: bold; text-transform: uppercase; border-right: 1px solid rgba(255,255,255,0.05); border-bottom: 1px solid rgba(255,255,255,0.05); }
            
            /* Table Item Selection Styling (Blue Highlight) */
            QTableWidget::item:selected { background-color: #0078d7; color: #ffffff; }
            QTableWidget::item { border-bottom: 1px solid rgba(255,255,255,0.05); border-right: 1px solid rgba(255,255,255,0.05); outline: none; }
            
            #details_btn { background: #2a1a4a; color: #bb86fc; border: 1px solid #bb86fc; border-radius: 6px; font-weight: bold; font-size: 11px; }
            #details_btn:hover { background: #3a2a5a; color: #fff; }
            
            # QScrollBar:vertical { border: none; background: #0a0a0a; width: 6px; }
            # QScrollBar::handle:vertical { background: #784da9; border-radius: 3px; min-height: 20px; }
            
            /* Remove vertical and horizontal scrollbars from table */
            #pet_table QScrollBar:vertical { width: 0px; background: transparent; }
            #pet_table QScrollBar:horizontal { height: 0px; background: transparent; }
            
            /* Ensure the table itself doesn't show scrollbars */
            #pet_table { border: none; outline: none; }
        """)

    def update_window_height(self, animate=True):
        num_rows = self.table.rowCount()
        header_height = self.table.horizontalHeader().height() or 30
        table_height = (num_rows * self.ROW_HEIGHT) + header_height + 5 # Small padding
        
        # Calculate target height: Header + Dropdowns + Search + Table + Footer
        # Adding more buffer to ensure everything is in frame
        target_content_h = 50 + 40 + 45 + table_height + 45 + 35 # Increased buffer
        target_h = max(220, target_content_h)
        
        if animate:
            self.anim = QPropertyAnimation(self, b"minimumHeight")
            self.anim.setDuration(300)
            self.anim.setEndValue(target_h)
            self.anim.setEasingCurve(QEasingCurve.OutCubic)
            
            self.anim_max = QPropertyAnimation(self, b"maximumHeight")
            self.anim_max.setDuration(300)
            self.anim_max.setEndValue(target_h)
            self.anim_max.setEasingCurve(QEasingCurve.OutCubic)
            
            self.anim.start()
            self.anim_max.start()
        else:
            self.setMinimumHeight(target_h)
            self.setMaximumHeight(target_h)

    def toggle_details(self):
        self.details_visible = not self.details_visible
        for i in range(4, 7): self.table.setColumnHidden(i, not self.details_visible)
        if self.details_visible:
            self.setFixedWidth(820) # Increased from 780
            self.btn_details.setText("Hide Details")
            self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        else:
            self.setFixedWidth(450)
            self.btn_details.setText("Show Details")
        self.update_window_height(animate=False)

    def perform_search(self):
        text = self.search_input.text().strip().lower()
        category = self.combo_category.currentText().lower()
        sort_mode = self.combo_sort.currentText()
        variant_mode = self.combo_variant.currentText()
        
        if category == "huges": 
            query = "SELECT [Pet Name], Value, Exist, Demand, [Value Change], RAP, [Last Updated], GOLD, RAINBOW, SHINY, Name FROM huges WHERE 1=1"
        elif category == "titanics": 
            query = "SELECT [Pet Name], Value, Exist, Demand, [Value Change], RAP, [Last Updated], GOLD, RAINBOW, SHINY, Name FROM titanics WHERE 1=1"
        elif category == "gargantuans": 
            query = "SELECT [Pet Name], Value, Exist, Demand, [Value Change], RAP, [Last Updated], GOLD, RAINBOW, SHINY, Name FROM gargantuans WHERE 1=1"
        elif category == "misc": 
            # Show everything other than Huges, Titanics, and Gargantuans
            query = "SELECT [Pet Name], Value, Exist, Demand, [Value Change], RAP, [Last Updated], GOLD, RAINBOW, SHINY, Name FROM master WHERE 1=1"
            query += " AND LOWER([Pet Name]) NOT LIKE '%huge%'"
            query += " AND LOWER([Pet Name]) NOT LIKE '%titanic%'"
            query += " AND LOWER([Pet Name]) NOT LIKE '%gargantuan%'"
        else: # All
            query = "SELECT [Pet Name], Value, Exist, Demand, [Value Change], RAP, [Last Updated], GOLD, RAINBOW, SHINY, Name FROM master WHERE 1=1"
        
        # Build Query
        params = []
        
        if text:
            query += " AND (LOWER([Pet Name]) LIKE ? OR LOWER(Name) LIKE ?)"
            params.extend([f"%{text}%", f"%{text}%"])
            
        if variant_mode != "All Variants":
            if variant_mode == "Normal": query += " AND GOLD=0 AND RAINBOW=0 AND SHINY=0"
            elif variant_mode == "Golden": query += " AND GOLD=1 AND RAINBOW=0"
            elif variant_mode == "Rainbow": query += " AND GOLD=0 AND RAINBOW=1"
            elif variant_mode == "Shiny": query += " AND SHINY=1"
            elif variant_mode == "Shiny Rainbow": query += " AND RAINBOW=1 AND SHINY=1"
            elif variant_mode == "Shiny Golden": query += " AND GOLD=1 AND SHINY=1"

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(query, params)
            raw_data = cursor.fetchall()
            conn.close()
            
            # Post-process for complex sorting
            processed = []
            for r in raw_data:
                processed.append({
                    'display': r[0],
                    'value_s': r[1],
                    'value_f': parse_price(r[1]),
                    'exist_s': r[2],
                    'exist_f': float(re.sub(r'[^\d.]', '', str(r[2]).replace(',', '')) or 0) if r[2] != "?" else 0,
                    'demand_s': r[3],
                    'demand_f': parse_demand(r[3]),
                    'change_s': r[4],
                    'rap_s': r[5],
                    'rap_f': parse_price(r[5]),
                    'updated_s': r[6]
                })

            # Sort
            if sort_mode == "Highest Value": processed.sort(key=lambda x: x['value_f'], reverse=True)
            elif sort_mode == "Lowest Value": processed.sort(key=lambda x: x['value_f'])
            elif sort_mode == "Highest Exist": processed.sort(key=lambda x: x['exist_f'], reverse=True)
            elif sort_mode == "Lowest Exist": processed.sort(key=lambda x: x['exist_f'])
            elif sort_mode == "Highest RAP": processed.sort(key=lambda x: x['rap_f'], reverse=True)
            elif sort_mode == "Lowest RAP": processed.sort(key=lambda x: x['rap_f'])
            elif sort_mode == "Highest Demand": processed.sort(key=lambda x: x['demand_f'], reverse=True)
            elif sort_mode == "Lowest Demand": processed.sort(key=lambda x: x['demand_f'])
            elif sort_mode == "Alphabetical": processed.sort(key=lambda x: x['display'])
            # Recently Updated / Default (no change to order)

            # Limit to top X as requested
            display_list = processed[:MAX_DISPLAY]
            
            self.table.setRowCount(0)
            for d in display_list:
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                # Cells
                self.table.setItem(row, 0, QTableWidgetItem(d['display']))
                
                val_item = QTableWidgetItem(d['value_s'])
                val_item.setTextAlignment(Qt.AlignCenter); val_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                self.table.setItem(row, 1, val_item)
                
                ex_item = QTableWidgetItem(d['exist_s'])
                ex_item.setTextAlignment(Qt.AlignCenter); self.table.setItem(row, 2, ex_item)
                
                dem_item = QTableWidgetItem(d['demand_s'])
                dem_item.setTextAlignment(Qt.AlignCenter)
                d_val = d['demand_f']
                dem_color = "#4ade80" if d_val >= 7 else ("#facc15" if d_val >= 4 else "#ef4444")
                dem_item.setForeground(QColor(dem_color)); self.table.setItem(row, 3, dem_item)
                
                chg_item = QTableWidgetItem(d['change_s'])
                chg_item.setTextAlignment(Qt.AlignCenter)
                if "▲" in d['change_s']: chg_item.setForeground(QColor("#4ade80"))
                elif "▼" in d['change_s']: chg_item.setForeground(QColor("#ef4444"))
                self.table.setItem(row, 4, chg_item)
                
                self.table.setItem(row, 5, QTableWidgetItem(d['rap_s']))
                
                upd_item = QTableWidgetItem(d['updated_s'])
                upd_item.setForeground(QColor("#a0a0a0")); self.table.setItem(row, 6, upd_item)
                
                self.table.setRowHeight(row, self.ROW_HEIGHT)
            
            self.update_window_height(animate=True)
                
        except Exception as e:
            print(f"Search Error: {e}")

    def eventFilter(self, source, event):
        if source == self.table and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Tab:
                # Move to next row
                curr = self.table.currentRow()
                if curr < self.table.rowCount() - 1:
                    self.table.setCurrentCell(curr + 1, 0)
                else:
                    self.table.setCurrentCell(0, 0) # Wrap around
                return True # Consume event
        return super().eventFilter(source, event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging, self.drag_offset = True, event.globalPosition().toPoint() - self.pos()
    def mouseMoveEvent(self, event):
        if self.dragging: self.move(event.globalPosition().toPoint() - self.drag_offset)
    def mouseReleaseEvent(self, event): self.dragging = False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = SearchWindow()
    w.show()
    sys.exit(app.exec())

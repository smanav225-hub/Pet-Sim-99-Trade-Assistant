import sys
import os
import sqlite3
import json
import re
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QFrame, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QStyledItemDelegate, QStyle,
    QLineEdit, QGraphicsDropShadowEffect, QLayout
)
from PySide6.QtCore import Qt, QPoint, QSize, QTimer, QPropertyAnimation, QEasingCurve, QEvent
from PySide6.QtGui import QFont, QColor, QTextOption, QIntValidator

# --- CONFIGURATION ---
DEFAULT_LIMIT = 100 

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

def format_price(value):
    if value >= 1_000_000_000: return f"{value/1_000_000_000:.2f}B"
    if value >= 1_000_000: return f"{value/1_000_000:.2f}M"
    if value >= 1_000: return f"{value/1_000:.2f}K"
    return str(int(value))

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
    def __init__(self, parent=None, scale=1.0):
        super().__init__(parent)
        self.scale_f = scale

    def s(self, value):
        return int(value * self.scale_f)

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
        rect = option.rect.adjusted(self.s(10), 0, -self.s(5), 0)
        font = painter.font()
        font.setFamily("Segoe UI"); font.setPointSize(self.s(11)); font.setBold(True); painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        opt = QTextOption(); opt.setWrapMode(QTextOption.WordWrap); opt.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        painter.drawText(rect, text, opt); painter.restore()
    
    def sizeHint(self, option, index):
        # Allow dynamic height by returning a reasonable minimum but letting the table expand
        base_size = super().sizeHint(option, index)
        return QSize(base_size.width(), self.s(47))

class InventoryWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        if getattr(sys, 'frozen', False):
            self.script_dir = os.path.dirname(sys.executable)
        else:
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
            
        self.db_path = os.path.join(self.script_dir, "cosmic_values.db")
        self.config_path = os.path.join(self.script_dir, "settings_config.json")
        
        self.dragging = False
        self.drag_offset = QPoint()
        self.details_visible = False
        self.is_expanded = True 
        self.items_data = [] 
        
        self.scale_factor = load_scale_factor()
        self.MAX_TABLE_HEIGHT = self.s(350)
        
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)
        
        self.setup_ui()
        self.apply_styles()
        self.load_inventory_from_config()

    def s(self, value):
        return int(value * self.scale_factor)

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(self.s(10), self.s(10), self.s(10), self.s(10))
        
        self.card = QFrame()
        self.card.setObjectName("card")
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(0)
        
        # Header
        self.header_frame = QFrame()
        self.header_frame.setFixedHeight(self.s(50))
        self.header_frame.setObjectName("header")
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(self.s(15), 0, self.s(15), 0)
        
        self.title_lbl = QLabel("YOUR INVENTORY")
        self.title_lbl.setObjectName("title")
        
        self.btn_minimize = QPushButton("⌵")
        self.btn_minimize.setObjectName("minimize_btn")
        self.btn_minimize.setFixedSize(self.s(24), self.s(24))
        self.btn_minimize.clicked.connect(self.toggle_expansion)

        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("close_btn")
        self.btn_close.setFixedSize(self.s(24), self.s(24))
        self.btn_close.clicked.connect(self.close_app)
        
        header_layout.addWidget(self.title_lbl)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_minimize)
        header_layout.addWidget(self.btn_close)
        self.card_layout.addWidget(self.header_frame)
        
        # Content Area
        self.content_frame = QFrame()
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(self.s(15), self.s(10), self.s(15), self.s(15))
        self.content_layout.setSpacing(self.s(12))
        
        # Info Row
        self.info_row_widget = QWidget()
        info_row = QHBoxLayout(self.info_row_widget)
        info_row.setContentsMargins(0,0,0,0)
        
        self.lbl_total_title = QLabel("Total Value:")
        self.lbl_total_title.setStyleSheet(f"font-size: {self.s(14)}px; font-weight: bold; color: #D1C4E9;")
        
        self.total_lbl = QLabel("0")
        self.total_lbl.setObjectName("total_lbl")
        total_shadow = QGraphicsDropShadowEffect(); total_shadow.setBlurRadius(self.s(2)); total_shadow.setColor(QColor("#00008B")); total_shadow.setOffset(self.s(1), self.s(1))
        self.total_lbl.setGraphicsEffect(total_shadow)
        
        self.lbl_qty_title = QLabel("Quantity:")
        self.lbl_qty_title.setStyleSheet(f"font-size: {self.s(14)}px; font-weight: bold; color: #D1C4E9;")
        self.lbl_qty_val = QLabel("0")
        self.lbl_qty_val.setStyleSheet(f"font-size: {self.s(16)}px; font-weight: bold; color: #ffffff;")
        
        info_row.addWidget(self.lbl_total_title); info_row.addWidget(self.total_lbl); info_row.addStretch(); info_row.addWidget(self.lbl_qty_title); info_row.addWidget(self.lbl_qty_val)
        self.content_layout.addWidget(self.info_row_widget)
        
        # Search Entry
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter inventory...")
        self.search_input.setObjectName("search_input")
        self.search_input.textChanged.connect(lambda: self.search_timer.start(300))
        self.content_layout.addWidget(self.search_input)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["PET NAME", "VALUE", "QUANTITY", "EXIST", "DEMAND", "CHANGE", "RAP", "UPDATED"])
        self.table.setObjectName("pet_table")
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setItemDelegateForColumn(0, NameDelegate(self.table, self.scale_factor))
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, self.s(125)) 
        
        for i in range(3, 8): self.table.setColumnHidden(i, True)
        
        self.content_layout.addWidget(self.table)
        
        # Footer
        self.footer_widget = QWidget()
        footer_layout = QHBoxLayout(self.footer_widget)
        footer_layout.setContentsMargins(0, self.s(25), 0, self.s(5)) 
        
        self.btn_clear = QPushButton("Clear Inventory")
        self.btn_clear.setObjectName("clear_btn")
        self.btn_clear.setFixedSize(self.s(110), self.s(28))
        self.btn_clear.clicked.connect(self.clear_inventory)
        
        self.btn_details = QPushButton("Show Details")
        self.btn_details.setObjectName("details_btn")
        self.btn_details.setFixedSize(self.s(110), self.s(28))
        self.btn_details.clicked.connect(self.toggle_details)
        
        footer_layout.addWidget(self.btn_clear)
        footer_layout.addStretch()
        footer_layout.addWidget(self.btn_details)
        self.content_layout.addWidget(self.footer_widget)
        
        self.card_layout.addWidget(self.content_frame)
        self.main_layout.addWidget(self.card)
        self.setFixedWidth(self.s(420))
        self.update_window_height(animate=False)

    def apply_styles(self):
        self.setStyleSheet(f"""
            #card {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1b1c2b, stop:1 #11121c); border-radius: {self.s(15)}px; border: 1px solid rgba(255, 255, 255, 0.12); }}
            #header {{ background: rgba(0,0,0,0.2); border-top-left-radius: {self.s(15)}px; border-top-right-radius: {self.s(15)}px; border-bottom: 1px solid rgba(255,255,255,0.05); }}
            #title {{ font-size: {self.s(15)}px; font-weight: 800; color: #D1C4E9; letter-spacing: 1px; }}
            #minimize_btn {{ border: none; background: transparent; color: #cfd3ff; font-size: {self.s(18)}px; font-weight: bold; }}
            #minimize_btn:hover {{ color: #ffffff; background: rgba(255,255,255,0.1); border-radius: {self.s(5)}px; }}
            #close_btn {{ border: none; background: transparent; color: #cfd3ff; font-weight: bold; font-size: {self.s(14)}px; }}
            #close_btn:hover {{ color: #ff5f5f; background: transparent; }}
            #total_lbl {{ color: #00BFFF; font-size: {self.s(16)}px; font-weight: bold; }}
            #search_input {{ background: #0a0b12; color: #fff; border: 1px solid #3a3d66; border-radius: {self.s(8)}px; padding: {self.s(10)}px; font-size: {self.s(13)}px; }}
            #pet_table {{ background: #000; border: none; color: #fff; font-size: {self.s(12)}px; outline: none; }}
            QHeaderView::section {{ background: #2D1B4D; color: #D1C4E9; padding: {self.s(8)}px; border: none; font-size: {self.s(12)}px; font-weight: bold; text-transform: uppercase; border-right: 1px solid rgba(255,255,255,0.05); border-bottom: 1px solid rgba(255,255,255,0.05); }}
            QTableWidget::item:selected {{ background-color: #0078d7; color: #ffffff; }}
            QTableWidget::item {{ border-bottom: 1px solid rgba(255,255,255,0.05); border-right: 1px solid rgba(255,255,255,0.05); }}
            #qty_btn {{ background-color: #2a1a4a; color: #ffffff; border: 1px solid #bb86fc; border-radius: {self.s(4)}px; font-weight: bold; font-size: {self.s(12)}px; }}
            #qty_btn:hover {{ background-color: #3a2a5a; border-color: #cc99ff; }}
            QScrollBar:vertical {{ border: none; background: #0a0b12; width: {self.s(10)}px; border-radius: {self.s(5)}px; margin: 0px {self.s(2)}px 0px {self.s(2)}px; }}
            QScrollBar::handle:vertical {{ background: #784da9; border-radius: {self.s(5)}px; min-height: {self.s(20)}px; }}
            QScrollBar::handle:vertical:hover {{ background: #8a5fb9; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
            #details_btn, #clear_btn {{ background: #2a1a4a; color: #bb86fc; border: 1px solid #bb86fc; border-radius: {self.s(6)}px; font-weight: bold; font-size: {self.s(12)}px; }}
            #details_btn:hover, #clear_btn:hover {{ background: #3a2a5a; color: #fff; }}
            #clear_btn {{ color: #ff9acb; border-color: #5b1b3b; }}
            #clear_btn:hover {{ background: #5b1b3b; color: #ffffff; }}
        """)

    def update_window_height(self, animate=True):
        if not self.is_expanded:
            table_target_h = 0
            self.table.hide()
            self.footer_widget.hide()
            self.search_input.hide()
            self.info_row_widget.show()
        else:
            self.table.show()
            self.footer_widget.show()
            self.search_input.show()
            self.info_row_widget.show()
            
            # Calculate total height of all rows
            total_rows_h = 0
            for i in range(self.table.rowCount()):
                total_rows_h += self.table.rowHeight(i)
            
            header_height = self.table.horizontalHeader().height() or self.s(30)
            content_height = total_rows_h + header_height + self.s(5)
            table_target_h = min(content_height, self.MAX_TABLE_HEIGHT)
        
        self.table.setFixedHeight(table_target_h)

        if not self.is_expanded:
            target_h = self.s(50) + self.s(40) + self.s(10)
        else:
            target_h = self.s(50) + self.s(40) + self.s(45) + table_target_h + self.s(75) + self.s(30) 
            
        if animate:
            self.anim = QPropertyAnimation(self, b"minimumHeight"); self.anim.setDuration(300); self.anim.setEndValue(target_h); self.anim.setEasingCurve(QEasingCurve.OutCubic)
            self.anim_max = QPropertyAnimation(self, b"maximumHeight"); self.anim_max.setDuration(300); self.anim_max.setEndValue(target_h); self.anim_max.setEasingCurve(QEasingCurve.OutCubic)
            self.anim.start(); self.anim_max.start()
        else:
            self.setMinimumHeight(target_h); self.setMaximumHeight(target_h)

    def toggle_expansion(self):
        self.is_expanded = not self.is_expanded
        self.btn_minimize.setText("⌵" if self.is_expanded else "⌃")
        self.update_window_height(animate=True)

    def load_inventory_from_config(self):
        if not os.path.exists(self.config_path): return
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                saved_list = config.get("inventory", [])
            
            if not saved_list: return
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            self.items_data = []
            
            for saved_item in saved_list:
                name = saved_item.get("display")
                variant = saved_item.get("variant", "Normal")
                qty = saved_item.get("quantity", 1)
                query = "SELECT [Pet Name], Value, Exist, Demand, [Value Change], RAP, [Last Updated] FROM master WHERE [Pet Name] = ? COLLATE NOCASE AND Variant = ? COLLATE NOCASE LIMIT 1"
                cursor.execute(query, (name, variant))
                r = cursor.fetchone()
                if r:
                    self.items_data.append({
                        'display': r[0], 'variant': variant, 'value_s': r[1], 'value_float': parse_price(r[1]),
                        'exist_s': r[2], 'demand_s': r[3], 'demand_f': parse_demand(r[3]),
                        'change_s': r[4], 'rap_s': r[5], 'updated_s': r[6], 'quantity': qty
                    })
            conn.close()
            self.refresh_table()
        except Exception as e:
            print(f"Inventory Load Error: {e}")

    def save_inventory_to_config(self):
        try:
            config = {}
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            save_list = []
            for item in self.items_data:
                save_list.append({"display": item['display'], "variant": item['variant'], "quantity": item['quantity']})
            config["inventory"] = save_list
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Inventory Save Error: {e}")

    def add_pet(self, data):
        if not data.get("found"): return
        fn = data.get("full_name", data.get("base_name", data.get("detected_name")))
        vt = data.get("detected_variant", data.get("Variant", "Normal"))
        for item in self.items_data:
            if item['display'].upper() == fn.upper() and item['variant'].upper() == vt.upper():
                item['quantity'] += 1
                self.refresh_table()
                self.save_inventory_to_config()
                return
        self.items_data.insert(0, {
            'display': fn, 'variant': vt, 'value_s': data.get("Value", "0"), 'value_float': parse_price(data.get("Value", "0")),
            'exist_s': data.get("Exist", "?"), 'demand_s': data.get("Demand", "-"), 'demand_f': parse_demand(data.get("Demand", "-")),
            'change_s': data.get("value_change", "-"), 'rap_s': data.get("RAP", "-"), 'updated_s': data.get("last_updated", "Recently"), 'quantity': 1
        })
        self.refresh_table()
        self.save_inventory_to_config()

    def refresh_table(self):
        self.table.setRowCount(0)
        self.items_data.sort(key=lambda x: x['value_float'], reverse=True)
        
        search_text = self.search_input.text().strip().lower()
        for item in self.items_data:
            if search_text and search_text not in item['display'].lower(): continue
            row = self.table.rowCount(); self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(item['display']))
            val_item = QTableWidgetItem(item['value_s']); val_item.setTextAlignment(Qt.AlignCenter); val_item.setFont(QFont("Segoe UI", 11, QFont.Bold)); self.table.setItem(row, 1, val_item)
            
            qw = QWidget(); ql = QHBoxLayout(qw); ql.setContentsMargins(self.s(2), self.s(2), self.s(2), self.s(2)); ql.setSpacing(self.s(3))
            ent_qty = QLineEdit(str(item['quantity']))
            ent_qty.setValidator(QIntValidator(0, 999999))
            ent_qty.setFixedWidth(self.s(35)); ent_qty.setAlignment(Qt.AlignCenter)
            ent_qty.setStyleSheet(f"background: #0a0b12; color: #bb86fc; border: 1px solid #3a3d66; border-radius: {self.s(4)}px; font-weight: bold; font-size: {self.s(13)}px;")
            m_btn = QPushButton("-"); p_btn = QPushButton("+")
            for b in [m_btn, p_btn]: b.setFixedSize(22, 22); b.setObjectName("qty_btn")
            p_btn.clicked.connect(lambda checked=False, i=item, e=ent_qty: self.update_qty(i, 1, e))
            m_btn.clicked.connect(lambda checked=False, i=item, e=ent_qty: self.update_qty(i, -1, e))
            ent_qty.textChanged.connect(lambda text, i=item: self.manual_qty_edit(i, text))
            ql.addWidget(ent_qty); ql.addWidget(m_btn); ql.addWidget(p_btn)
            self.table.setCellWidget(row, 2, qw)
            
            def create_item(text, color=None):
                it = QTableWidgetItem(text)
                it.setTextAlignment(Qt.AlignCenter); it.setFont(QFont("Segoe UI", 11))
                if color: it.setForeground(QColor(color))
                return it

            self.table.setItem(row, 3, create_item(item['exist_s']))
            d_val = item['demand_f']; dem_color = "#4ade80" if d_val >= 7 else ("#facc15" if d_val >= 4 else "#ef4444")
            self.table.setItem(row, 4, create_item(item['demand_s'], dem_color))
            chg_color = "#4ade80" if "▲" in item['change_s'] else ("#ef4444" if "▼" in item['change_s'] else None)
            self.table.setItem(row, 5, create_item(item['change_s'], chg_color))
            self.table.setItem(row, 6, create_item(item['rap_s']))
            self.table.setItem(row, 7, create_item(item['updated_s'], "#a0a0a0"))
            
            # Dynamic height: adjust row to fit multiline content
            self.table.resizeRowToContents(row)
            # Ensure row height is at least the default ROW_HEIGHT
            if self.table.rowHeight(row) < self.s(47):
                self.table.setRowHeight(row, self.s(47))
            
        self.recalculate_totals()
        self.update_window_height(animate=True)

    def update_qty(self, item, delta, edit_widget):
        item['quantity'] = max(0, item['quantity'] + delta)
        if item['quantity'] <= 0:
            if item in self.items_data: self.items_data.remove(item)
            self.refresh_table()
        else:
            edit_widget.setText(str(item['quantity']))
            self.recalculate_totals()
        self.save_inventory_to_config()

    def manual_qty_edit(self, item, text):
        try:
            val = int(text) if text else 0
            item['quantity'] = val
            if val == 0:
                if item in self.items_data: self.items_data.remove(item)
                QTimer.singleShot(100, self.refresh_table)
            else: self.recalculate_totals()
            self.save_inventory_to_config()
        except: pass

    def clear_inventory(self):
        self.items_data = []
        self.refresh_table()
        self.save_inventory_to_config()

    def recalculate_totals(self):
        total_val, total_qty = 0.0, 0
        for item in self.items_data:
            total_val += item['value_float'] * item['quantity']
            total_qty += item['quantity']
        self.total_lbl.setText(format_price(total_val))
        self.lbl_qty_val.setText(str(total_qty))

    def toggle_details(self):
        self.details_visible = not self.details_visible
        for i in range(3, 8): self.table.setColumnHidden(i, not self.details_visible)
        if self.details_visible:
            self.setFixedWidth(self.s(900)); self.btn_details.setText("Hide Details")
            header = self.table.horizontalHeader(); header.setSectionResizeMode(7, QHeaderView.Stretch) 
        else:
            self.setFixedWidth(self.s(420)); self.btn_details.setText("Show Details")
            header = self.table.horizontalHeader(); header.setSectionResizeMode(0, QHeaderView.Stretch) 
        self.update_window_height(animate=False)

    def perform_search(self): self.refresh_table()

    def close_app(self):
        self.hide()
        if os.path.basename(sys.argv[0]).lower() == "inventory.py":
            QApplication.quit()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: self.dragging, self.drag_offset = True, event.globalPosition().toPoint() - self.pos()
    def mouseMoveEvent(self, event):
        if self.dragging: self.move(event.globalPosition().toPoint() - self.drag_offset)
    def mouseReleaseEvent(self, event): self.dragging = False

if __name__ == "__main__":
    app = QApplication(sys.argv); w = InventoryWindow(); w.show(); sys.exit(app.exec())
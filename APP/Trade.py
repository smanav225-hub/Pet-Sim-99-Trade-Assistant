import sys
import sqlite3
import os
import re
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QFrame, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QStyledItemDelegate, QStyle,
    QGraphicsDropShadowEffect, QLineEdit
)
from PySide6.QtCore import Qt, QPoint, QRect, QPropertyAnimation, QEasingCurve, QSize, QEvent
from PySide6.QtGui import QFont, QColor, QPainter, QTextOption, QIntValidator

# ============================================================================
# MODERN PS99 TRADE GUI - V3 (COSMIC STYLE)
# ============================================================================

def format_price(value):
    """Helper to format back to K/M/B."""
    if value >= 1_000_000_000: return f"{value/1_000_000_000:.2f}B"
    if value >= 1_000_000: return f"{value/1_000:.2f}M"
    if value >= 1_000: return f"{value/1_000:.2f}K"
    return str(value)

def parse_price(price_str):
    """Helper to parse K/M/B strings into floats."""
    if not price_str: return 0.0
    price_str = price_str.upper().replace(",", "").replace("$", "").replace(" ", "").strip()
    price_str = re.sub(r'[▲▼%]', '', price_str)
    multiplier = 1
    if "B" in price_str: multiplier = 1_000_000_000; price_str = price_str.replace("B", "")
    elif "M" in price_str: multiplier = 1_000_000; price_str = price_str.replace("M", "")
    elif "K" in price_str: multiplier = 1_000; price_str = price_str.replace("K", "")
    try: return float(price_str) * multiplier
    except ValueError: return 0.0

class PetNameDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        bg_color = QColor(40, 40, 40) if (option.state & QStyle.State_Selected) else QColor("#000000")
        painter.fillRect(option.rect, bg_color)
        painter.setPen(QColor("#333333"))
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

class TradeSideWindow(QWidget):
    def __init__(self, title_text="Your Offer", initial_pos=None):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.is_expanded = True
        self.details_visible = False
        self.dragging, self.resizing = False, False
        self.drag_offset = QPoint()
        self.items_data = []
        self.total_value = 0.0
        self.gems_value = 0.0
        self.other_side = None
        self.title_text = title_text
        self.MAX_DROPDOWN_HEIGHT = 500
        
        self.setup_ui()
        self.apply_styles()
        if initial_pos: self.move(initial_pos)

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self); self.main_layout.setContentsMargins(0, 0, 0, 0); self.main_layout.setSpacing(0)
        self.header_frame = QFrame(); self.header_frame.setObjectName("header_frame"); self.header_frame.setFixedHeight(130)
        header_layout = QVBoxLayout(self.header_frame); header_layout.setContentsMargins(15, 8, 15, 8); header_layout.setSpacing(4)
        top_line = QHBoxLayout(); top_line.setSpacing(10); top_line.setAlignment(Qt.AlignVCenter)
        self.title_lbl = QLabel(self.title_text); self.title_lbl.setObjectName("window_title")
        self.total_lbl = QLabel("0"); self.total_lbl.setObjectName("total_lbl")
        total_shadow = QGraphicsDropShadowEffect(); total_shadow.setBlurRadius(2); total_shadow.setColor(QColor("#00008B")); total_shadow.setOffset(1, 1)
        self.total_lbl.setGraphicsEffect(total_shadow)
        self.diff_lbl = QLabel(""); self.diff_lbl.setObjectName("diff_lbl"); self.diff_lbl.setStyleSheet("font-size: 14px; font-weight: bold;")
        diff_shadow = QGraphicsDropShadowEffect(); diff_shadow.setBlurRadius(2); diff_shadow.setColor(QColor("#00008B")); diff_shadow.setOffset(1, 1)
        self.diff_lbl.setGraphicsEffect(diff_shadow)
        self.btn_info = QPushButton("i"); self.btn_info.setObjectName("info_btn"); self.btn_info.setFixedSize(24, 24); self.btn_info.installEventFilter(self)
        self.btn_close = QPushButton("✕"); self.btn_close.setObjectName("close_btn"); self.btn_close.setFixedSize(24, 24); self.btn_close.clicked.connect(self.close)
        top_line.addWidget(self.title_lbl); top_line.addWidget(self.total_lbl); top_line.addWidget(self.diff_lbl); top_line.addStretch(); top_line.addWidget(self.btn_info); top_line.addWidget(self.btn_close)
        
        middle_line = QHBoxLayout(); middle_line.setSpacing(10); middle_line.setAlignment(Qt.AlignVCenter)
        self.pet_val_lbl = QLabel("Pets: 0"); self.pet_val_lbl.setStyleSheet("color: #a0a0a0; font-size: 14px; font-weight: bold;")
        self.gem_entry = QLineEdit(); self.gem_entry.setPlaceholderText("💎 Diamonds")
        self.gem_entry.setFixedWidth(130); self.gem_entry.setFixedHeight(28)
        self.gem_entry.setAlignment(Qt.AlignCenter)
        self.gem_entry.setStyleSheet("background: #0a0b12; color: #00BFFF; border: 1px solid #3a3d66; border-radius: 6px; font-size: 13px; font-weight: bold;")
        self.gem_entry.textChanged.connect(self.on_gems_changed)
        middle_line.addWidget(self.pet_val_lbl); middle_line.addStretch(); middle_line.addWidget(self.gem_entry); middle_line.addSpacing(20)
        
        header_layout.addLayout(top_line)
        header_layout.addLayout(middle_line)
        
        second_line = QHBoxLayout(); second_line.setSpacing(12); second_line.setAlignment(Qt.AlignVCenter)
        self.demand_lbl = QLabel("Demand: -"); self.demand_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #E0E0E0;")
        self.count_lbl = QLabel("Qty: 0"); self.count_lbl.setObjectName("count_lbl")
        self.expand_btn = QPushButton("Hide List"); self.expand_btn.setObjectName("expand_btn"); self.expand_btn.setFixedSize(100, 28); self.expand_btn.clicked.connect(self.toggle_expansion)
        self.details_btn = QPushButton("Details"); self.details_btn.setObjectName("details_btn"); self.details_btn.setFixedSize(80, 28); self.details_btn.clicked.connect(self.toggle_details)
        second_line.addWidget(self.demand_lbl); second_line.addWidget(self.count_lbl); second_line.addStretch(); second_line.addWidget(self.expand_btn); second_line.addWidget(self.details_btn)
        header_layout.addLayout(second_line); self.main_layout.addWidget(self.header_frame)
        self.dropdown_frame = QFrame(); self.dropdown_frame.setObjectName("dropdown_frame")
        dropdown_layout = QVBoxLayout(self.dropdown_frame); dropdown_layout.setContentsMargins(0, 0, 0, 0); dropdown_layout.setSpacing(0)
        self.table = QTableWidget(); self.table.setColumnCount(6); self.table.setHorizontalHeaderLabels(["PET NAME", "VALUE", "CHANGE", "DEMAND", "UPDATED", "QUANTITY"])
        self.table.verticalHeader().setVisible(False); self.table.setShowGrid(False); self.table.setSelectionMode(QAbstractItemView.NoSelection); self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setObjectName("pet_table"); self.table.setItemDelegateForColumn(0, PetNameDelegate(self.table))
        header = self.table.horizontalHeader(); header.setSectionResizeMode(0, QHeaderView.Stretch); header.setSectionResizeMode(1, QHeaderView.ResizeToContents); header.setSectionResizeMode(2, QHeaderView.ResizeToContents); header.setSectionResizeMode(3, QHeaderView.ResizeToContents); header.setSectionResizeMode(5, QHeaderView.Fixed); self.table.setColumnWidth(5, 135)
        self.table.setColumnHidden(2, True); self.table.setColumnHidden(4, True)
        dropdown_layout.addWidget(self.table)
        self.resize_handle = QFrame(); self.resize_handle.setFixedHeight(8); self.resize_handle.setCursor(Qt.SizeVerCursor); self.resize_handle.setObjectName("resize_handle")
        dropdown_layout.addWidget(self.resize_handle); self.main_layout.addWidget(self.dropdown_frame)
        self.update_window_height(animate=False)

    def update_window_height(self, animate=True):
        if not self.is_expanded: target_dropdown = 0
        else:
            num_rows = self.table.rowCount()
            header_height = self.table.horizontalHeader().height() or 30
            content_height = (num_rows * 47) + header_height + 10
            target_dropdown = min(content_height, self.MAX_DROPDOWN_HEIGHT)
        target_window = 130 + target_dropdown
        if animate:
            self.anim_drop = QPropertyAnimation(self.dropdown_frame, b"maximumHeight"); self.anim_drop.setDuration(300); self.anim_drop.setEndValue(target_dropdown); self.anim_drop.setEasingCurve(QEasingCurve.OutCubic)
            self.anim_win = QPropertyAnimation(self, b"minimumHeight"); self.anim_win.setDuration(300); self.anim_win.setEndValue(target_window); self.anim_win.setEasingCurve(QEasingCurve.OutCubic)
            self.anim_win_max = QPropertyAnimation(self, b"maximumHeight"); self.anim_win_max.setDuration(300); self.anim_win_max.setEndValue(target_window); self.anim_win_max.setEasingCurve(QEasingCurve.OutCubic)
            self.anim_drop.start(); self.anim_win.start(); self.anim_win_max.start()
        else: self.dropdown_frame.setMaximumHeight(target_dropdown); self.setMinimumHeight(target_window); self.setMaximumHeight(target_window)

    def add_pet(self, data, qty=1):
        if not data.get("found"): return
        fn, vt = data.get("full_name", data.get("base_name")), data.get("detected_variant", data.get("Variant", "Normal"))
        for i, item in enumerate(self.items_data):
            if item['name'] == fn and item['variant'] == vt: self.update_qty(i, qty); return
        row_idx = 0; self.table.insertRow(row_idx)
        item_data = {'name': fn, 'variant': vt, 'value_str': data.get("Value", "0"), 'value_float': parse_price(data.get("Value", "0")), 'demand_str': data.get("Demand", "5/10"), 'updated': data.get("last_updated", "Recently"), 'change': data.get("value_change", "-"), 'quantity': qty}
        self.items_data.insert(0, item_data)
        self.table.setItem(row_idx, 0, QTableWidgetItem(fn))
        val_item = QTableWidgetItem(item_data['value_str']); val_item.setForeground(QColor("#ffffff")); val_item.setFont(QFont("Segoe UI", 10, QFont.Bold)); val_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter); self.table.setItem(row_idx, 1, val_item)
        chg_str = item_data['change']; chg_color = "#4ade80" if "▲" in chg_str or "+" in chg_str else ("#ef4444" if "▼" in chg_str or "-" in chg_str else "#ffffff")
        chg_item = QTableWidgetItem(chg_str); chg_item.setForeground(QColor(chg_color)); chg_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter); self.table.setItem(row_idx, 2, chg_item)
        dem_val = 5
        try: dem_val = int(item_data['demand_str'].split("/")[0])
        except: pass
        dem_color = "#4ade80" if dem_val >= 7 else ("#facc15" if dem_val >= 4 else "#ef4444")
        dem_item = QTableWidgetItem(item_data['demand_str']); dem_item.setForeground(QColor(dem_color)); dem_item.setTextAlignment(Qt.AlignCenter); self.table.setItem(row_idx, 3, dem_item)
        upd_item = QTableWidgetItem(item_data['updated']); upd_item.setForeground(QColor("#a0a0a0")); self.table.setItem(row_idx, 4, upd_item)
        qw = QWidget(); ql = QHBoxLayout(qw); ql.setContentsMargins(4, 2, 4, 2); ql.setSpacing(6)
        ent_qty = QLineEdit(str(qty))
        ent_qty.setValidator(QIntValidator(0, 999999))
        ent_qty.setFixedWidth(35)
        ent_qty.setAlignment(Qt.AlignCenter)
        ent_qty.setStyleSheet("background: #0a0b12; color: #bb86fc; border: 1px solid #3a3d66; border-radius: 4px; font-weight: bold; font-size: 11px;")
        
        m_btn = QPushButton("-"); p_btn = QPushButton("+")
        for b in [m_btn, p_btn]: b.setFixedSize(24, 24); b.setObjectName("qty_btn")
        
        p_btn.clicked.connect(lambda: self.update_pet_qty(item_data, 1, ent_qty))
        m_btn.clicked.connect(lambda: self.update_pet_qty(item_data, -1, ent_qty))
        ent_qty.textChanged.connect(lambda text: self.manual_qty_edit(item_data, text))
        
        ql.addWidget(ent_qty); ql.addWidget(m_btn); ql.addWidget(p_btn)
        self.table.setCellWidget(row_idx, 5, qw); self.table.setRowHeight(row_idx, 47); self.recalculate_totals()
        if self.is_expanded: self.update_window_height(animate=True)

    def remove_pet_row(self, item_dict):
        try:
            idx = self.items_data.index(item_dict); self.items_data.pop(idx); self.table.removeRow(idx); self.recalculate_totals()
            if self.is_expanded: self.update_window_height(animate=True)
        except: pass

    def update_pet_qty(self, item_dict, delta, edit_widget):
        item_dict['quantity'] = max(0, item_dict['quantity'] + delta)
        if item_dict['quantity'] <= 0: self.remove_pet_row(item_dict); return
        edit_widget.setText(str(item_dict['quantity'])); self.recalculate_totals()

    def manual_qty_edit(self, item_dict, text):
        try:
            val = int(text) if text else 0
            item_dict['quantity'] = val
            self.recalculate_totals()
        except: pass

    def update_qty(self, idx, delta):
        if idx >= len(self.items_data): return
        item = self.items_data[idx]; item['quantity'] = max(0, item['quantity'] + delta)
        if item['quantity'] <= 0: self.remove_pet_row(item); return
        widget = self.table.cellWidget(idx, 5)
        if widget:
            edit = widget.findChild(QLineEdit)
            if edit: edit.setText(str(item['quantity']))
        self.recalculate_totals()

    def on_gems_changed(self, text):
        self.gems_value = parse_price(text)
        self.recalculate_totals()

    def recalculate_totals(self):
        total_pet_val, total_qty, total_dem, dem_count = 0.0, 0, 0.0, 0
        for item in self.items_data:
            qty = item['quantity']
            if qty > 0:
                total_pet_val += item['value_float'] * qty; total_qty += qty
                try: d_val = int(item['demand_str'].split("/")[0]); total_dem += (d_val * qty); dem_count += qty
                except: pass
        self.pet_val_lbl.setText(f"Pets: {format_price(total_pet_val)}")
        self.total_value = total_pet_val + self.gems_value
        self.total_lbl.setText(format_price(self.total_value))
        if dem_count > 0:
            avg_dem = total_dem / dem_count
            color = "#4ade80" if avg_dem >= 7 else ("#facc15" if avg_dem >= 4 else "#ef4444")
            self.demand_lbl.setText(f"Demand: <span style='color:{color};'>{avg_dem:.1f}/10</span>")
        else:
            self.demand_lbl.setText("Demand: <span style='color:#E0E0E0;'>-</span>")
        self.count_lbl.setText(f"Qty: <span style='color:#E0E0E0;'>{total_qty}</span>")
        self.update_diff_label()
        if self.other_side: self.other_side.update_diff_label()

    def update_diff_label(self):
        if not self.other_side: return
        diff = self.total_value - self.other_side.total_value
        if diff > 0: self.diff_lbl.setText(f"| <span style='color:#4ade80;'>▲ {format_price(diff)}</span>")
        elif diff < 0: self.diff_lbl.setText(f"| <span style='color:#ef4444;'>▼ {format_price(abs(diff))}</span>")
        else: self.diff_lbl.setText("| <span style='color:#a0a0a0;'>0</span>")

    def toggle_expansion(self): self.is_expanded = not self.is_expanded; self.update_window_height(animate=True); self.expand_btn.setText("Hide List" if self.is_expanded else "Show List")
    def toggle_details(self):
        self.details_visible = not self.details_visible; self.table.setColumnHidden(2, not self.details_visible); self.table.setColumnHidden(4, not self.details_visible)
        if self.details_visible: self.setFixedWidth(650); self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents); self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        else: self.setFixedWidth(400)

    def apply_styles(self):
        self.setStyleSheet("""
            QWidget { font-family: 'Segoe UI', 'Roboto', sans-serif; background-color: transparent; }
            #header_frame { background-color: #000000; border-bottom: 1px solid #333333; }
            #window_title { color: #D1C4E9; font-size: 14px; font-weight: 800; text-transform: uppercase; }
            #total_lbl { color: #00BFFF; font-size: 16px; font-weight: bold; }
            #count_lbl { color: #E0E0E0; font-size: 14px; font-weight: bold; }
            #diff_lbl { font-size: 14px; font-weight: bold; }
            #expand_btn, #details_btn { background-color: #2a1a4a; color: #bb86fc; border: 1px solid #bb86fc; border-radius: 4px; font-weight: bold; font-size: 12px; }
            #expand_btn:hover, #details_btn:hover { background-color: #3a2a5a; border-color: #cc99ff; }
            #info_btn, #close_btn { background: #151515; color: #555555; border: 1px solid #252525; border-radius: 12px; font-weight: bold; }
            #info_btn:hover { background-color: #3a2a5a; color: #ffffff; }
            #close_btn:hover { background-color: #ef4444; color: #ffffff; border-color: #ef4444; }
            #pet_table { background-color: #000000; border: none; gridline-color: #333333; color: #ffffff; }
            QTableWidget::item { border-bottom: 1px solid #333333; border-right: 1px solid #333333; padding: 6px 8px; }
            QHeaderView::section { background-color: #2D1B4D; color: #E0E0E0; padding: 6px; border: none; border-bottom: 1px solid #333333; border-right: 1px solid #333333; font-size: 10px; font-weight: bold; text-transform: uppercase; }
            #qty_btn { background-color: #2a1a4a; color: #ffffff; border: 1px solid #bb86fc; border-radius: 4px; font-weight: bold; font-size: 12px; }
            #qty_btn:hover { background-color: #3a2a5a; border-color: #cc99ff; }
            QScrollBar:vertical { border: none; background: #0a0a0a; width: 8px; }
            QScrollBar::handle:vertical { background: #bb86fc; border-radius: 4px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #cc99ff; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            #resize_handle { background: transparent; }
        """)
        self.setFixedWidth(400)

    def eventFilter(self, source, event):
        if source == self.btn_info:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self.dragging, self.drag_offset = True, event.globalPosition().toPoint() - self.pos(); return True
            elif event.type() == QEvent.MouseMove and self.dragging: self.move(event.globalPosition().toPoint() - self.drag_offset); return True
            elif event.type() == QEvent.MouseButtonRelease: self.dragging = False; return True
        return super().eventFilter(source, event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.header_frame.geometry().contains(event.pos()): self.dragging, self.drag_offset = True, event.globalPosition().toPoint() - self.pos()
            elif self.resize_handle.geometry().translated(0, self.header_frame.height() + self.dropdown_frame.height() - self.resize_handle.height()).contains(event.pos()):
                if self.is_expanded: self.resizing, self.drag_offset = True, event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.dragging: self.move(event.globalPosition().toPoint() - self.drag_offset)
        elif self.resizing:
            delta = event.globalPosition().toPoint().y() - self.drag_offset.y()
            new_h = max(150, self.dropdown_frame.maximumHeight() + delta)
            self.dropdown_frame.setMaximumHeight(new_h); self.drag_offset = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event): self.dragging, self.resizing = False, False

class TradeBackend:
    def __init__(self):
        screen = QApplication.primaryScreen().geometry(); cx, cy = screen.center().x(), screen.center().y()
        self.your_offer = TradeSideWindow("Your Offer", QPoint(cx - 500, cy - 400))
        self.their_offer = TradeSideWindow("Their Offer", QPoint(cx + 100, cy - 400))
        self.your_offer.other_side, self.their_offer.other_side = self.their_offer, self.your_offer
        self.your_offer.show(); self.their_offer.show()
    def route_pet(self, side, data, qty=1):
        if side == "left": self.your_offer.add_pet(data, qty)
        else: self.their_offer.add_pet(data, qty)
    def close(self): self.your_offer.close(); self.their_offer.close()

class TradeApp:
    def __init__(self): self.app = QApplication(sys.argv); self.backend = TradeBackend()
    def run(self): sys.exit(self.app.exec())

if __name__ == "__main__": TradeApp().run()
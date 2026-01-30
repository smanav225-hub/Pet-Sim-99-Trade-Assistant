import sys
import os
import json
import asyncio
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QFrame, QLayout, QCheckBox, QLineEdit, QGridLayout, QToolTip
)
from PySide6.QtCore import Qt, QPoint, QEvent, Signal, QThread, QObject
from PySide6.QtGui import QFont, QColor, QIntValidator, QCursor

# Import the scrapper function
try:
    from Cosmic_webscrapper import start_scraping_process
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from Cosmic_webscrapper import start_scraping_process

class ScraperWorker(QThread):
    progress_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, choices, max_p, concurrent_p):
        super().__init__()
        self.choices = choices
        self.max_p = max_p
        self.concurrent_p = concurrent_p

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                start_scraping_process(
                    self.choices, 
                    self.max_p, 
                    self.concurrent_p, 
                    progress_callback=self.progress_signal.emit
                )
            )
        except Exception as e:
            self.progress_signal.emit(f"Error: {str(e)}")
        finally:
            loop.close()
            self.finished_signal.emit()

class InfoLabel(QLabel):
    def __init__(self, tooltip_text):
        super().__init__("ⓘ")
        self.setFixedSize(18, 18)
        self.setAlignment(Qt.AlignCenter)
        self.setToolTip(tooltip_text)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QLabel { color: #8a8fa8; font-size: 14px; border: 1px solid #3a3d66; border-radius: 9px; background: #2a2c45; }
            QLabel:hover { color: #ffffff; background: #3a3d66; border-color: #cfd3ff; }
        """)
    def enterEvent(self, event):
        QToolTip.showText(QCursor.pos(), self.toolTip(), self)
        super().enterEvent(event)
    def leaveEvent(self, event):
        QToolTip.hideText()
        super().leaveEvent(event)

class ValuesWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(self.script_dir, "settings_config.json")
        self.settings = self.load_settings()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.dragging = False
        self.drag_offset = QPoint()
        self.worker = None
        self.build_ui()

    def load_settings(self):
        defaults = {"max_pages": 9999, "concurrent_pages": 3, "active_categories": []}
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
        outer = QVBoxLayout(self); outer.setContentsMargins(10, 10, 10, 10); outer.setSizeConstraint(QLayout.SetFixedSize)
        self.card = QFrame(); self.card.setObjectName("card"); self.card.setFixedWidth(340)
        card_layout = QVBoxLayout(self.card); card_layout.setSpacing(12); card_layout.setContentsMargins(15, 10, 15, 20)
        
        header_row = QHBoxLayout()
        self.title_lbl = QLabel("UPDATE VALUES"); self.title_lbl.setObjectName("title")
        header_row.addWidget(self.title_lbl); header_row.addStretch()
        self.btn_close = QPushButton("✕"); self.btn_close.setObjectName("close_btn")
        self.btn_close.setFixedSize(22, 22); self.btn_close.clicked.connect(self.close_app)
        header_row.addWidget(self.btn_close); card_layout.addLayout(header_row)

        # Row 1: Max Pages
        row_max = QHBoxLayout()
        row_max.addWidget(QLabel("Max Pages to Scan")); row_max.addWidget(InfoLabel("Maximum number of pages to crawl per category.")); row_max.addStretch()
        self.max_input = QLineEdit(str(self.settings.get("max_pages", 9999)))
        self.max_input.setFixedWidth(60); self.max_input.setValidator(QIntValidator(1, 9999)); self.max_input.setObjectName("config_input")
        self.max_input.editingFinished.connect(self.update_config)
        row_max.addWidget(self.max_input); card_layout.addLayout(row_max)

        # Row 2: Concurrent Pages
        row_con = QHBoxLayout()
        row_con.addWidget(QLabel("Simultaneous Windows")); row_con.addWidget(InfoLabel("no of chrome webpages opened simultanenously at once.")); row_con.addStretch()
        self.con_input = QLineEdit(str(self.settings.get("concurrent_pages", 3)))
        self.con_input.setFixedWidth(60); self.con_input.setValidator(QIntValidator(1, 10)); self.con_input.setObjectName("config_input")
        self.con_input.editingFinished.connect(self.update_config)
        row_con.addWidget(self.con_input); card_layout.addLayout(row_con)

        # Grid
        grid_frame = QFrame(); grid = QGridLayout(grid_frame); grid.setContentsMargins(0, 5, 0, 5); grid.setSpacing(10)
        self.cat_map = {"Titanics": "1", "Gargantuans": "2", "Huges": "3", "Exclusives": "4", "Clans": "5", "Misc": "6", "Eggs": "7", "All": "8"}
        self.categories = list(self.cat_map.keys())
        self.checkboxes = {}
        cb_style = "QCheckBox { color: #cfd3ff; font-size: 12px; font-weight: 500; } QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #3a3d66; background: #1a1c2b; } QCheckBox::indicator:checked { background: #784da9; border-color: #bb86fc; }"
        for i, cat in enumerate(self.categories):
            cb = QCheckBox(cat); cb.setChecked(False); cb.setStyleSheet(cb_style); self.checkboxes[cat] = cb; grid.addWidget(cb, i // 2, i % 2)
            if cat == "All": 
                cb.clicked.connect(self.toggle_all_checkboxes)
            else:
                cb.clicked.connect(self.on_category_clicked)
        card_layout.addWidget(grid_frame)

        self.status_lbl = QLabel("Status: Idle"); self.status_lbl.setObjectName("status_lbl"); self.status_lbl.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.status_lbl)
        self.btn_start = QPushButton("START SCAN"); self.btn_start.setObjectName("start_btn"); self.btn_start.setFixedHeight(35); self.btn_start.clicked.connect(self.start_scan)
        card_layout.addWidget(self.btn_start)

        outer.addWidget(self.card)
        self.setStyleSheet("QLabel { color: #eaeaf0; font-family: 'Segoe UI', sans-serif; font-weight: bold; } #card { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1b1c2b, stop:1 #11121c); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 18px; } #title { font-size: 19px; font-weight: bold; color: #ffffff; } #config_input { background: #1a1c2b; color: #ffffff; border: 1px solid #3a3d66; border-radius: 6px; padding: 4px; font-size: 12px; } #status_lbl { color: #8a8fa8; font-size: 11px; font-style: italic; } #start_btn { background: #2a2c45; color: #cfd3ff; border-radius: 8px; font-size: 13px; font-weight: bold; border: 1px solid #3a3d66; } #start_btn:hover { background: #3dff84; color: #11121c; border-color: #3dff84; } QPushButton#close_btn { border: none; background: transparent; color: #cfd3ff; font-weight: bold; outline: none; } QPushButton#close_btn:hover { color: #ffffff; background-color: #ef4444; border-radius: 4px; } QToolTip { background-color: #000000; color: #ffffff; border: 1px solid #3a3d66; padding: 8px; font-size: 13px; border-radius: 5px; }")

    def update_config(self):
        self.settings["max_pages"] = int(self.max_input.text() or 9999)
        self.settings["concurrent_pages"] = int(self.con_input.text() or 3); self.save_settings()

    def toggle_all_checkboxes(self, checked):
        """When 'All' is clicked, select/unselect everything else."""
        for cat, cb in self.checkboxes.items():
            if cat != "All": cb.setChecked(checked)

    def on_category_clicked(self):
        """When a single category is clicked, update the 'All' checkbox state."""
        all_checked = True
        for cat, cb in self.checkboxes.items():
            if cat != "All" and not cb.isChecked():
                all_checked = False
                break
        
        # Rule: if any of the 7 is unchecked, 'All' must uncheck.
        # Rule: if all 7 are manually checked, 'All' should check.
        self.checkboxes["All"].setChecked(all_checked)

    def start_scan(self):
        if self.worker and self.worker.isRunning():
            self.status_lbl.setText("Status: Scan already in progress...")
            return

        choices = []
        # If 'All' is checked, we ONLY send '8' to the scrapper logic
        if self.checkboxes["All"].isChecked():
            choices = ["8"]
        else:
            for cat, cb in self.checkboxes.items():
                if cb.isChecked() and cat != "All":
                    choices.append(self.cat_map[cat])
        
        if not choices:
            self.status_lbl.setText("Status: No categories selected!")
            return

        max_p = int(self.max_input.text() or 9999)
        con_p = int(self.con_input.text() or 3)
        
        self.btn_start.setEnabled(False)
        self.btn_start.setText("SCRAPING...")
        self.status_lbl.setText("Status: Initializing Browser...")
        
        self.worker = ScraperWorker(choices, max_p, con_p)
        self.worker.progress_signal.connect(self.status_lbl.setText)
        self.worker.finished_signal.connect(self.on_scan_finished)
        self.worker.start()

    def on_scan_finished(self):
        self.btn_start.setEnabled(True)
        self.btn_start.setText("START SCAN")
        self.status_lbl.setText("Status: Idle (Complete)")

    def close_app(self):
        """Hides the window and quits if running as a standalone script."""
        self.hide()
        # If running directly (not imported), the first argument is this script
        if os.path.basename(sys.argv[0]).lower() == "values.py":
            QApplication.quit()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: self.dragging, self.drag_offset = True, event.globalPosition().toPoint() - self.pos()
    def mouseMoveEvent(self, event):
        if self.dragging: self.move(event.globalPosition().toPoint() - self.drag_offset)
    def mouseReleaseEvent(self, event): self.dragging = False

if __name__ == "__main__":
    app = QApplication(sys.argv); window = ValuesWindow(); window.show(); sys.exit(app.exec())

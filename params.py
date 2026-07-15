import sys
import json
import os
import re
from pprint import pprint
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QColor

JSON_FILE = "parameters.json"

DEFAULT_PARAMETERS = {
    "Gimbal": {
        "PORT": {"value": "/dev/ttyUSB0", "type": "string", "desc": "Gimbal communication serial port connection interface"},
        "BAUD": {"value": 115200, "type": "int", "desc": "Baudrate standard speed for serial data transmission telemetry"}
    },
    "Camera": {
        "PORT": {"value": "/dev/ttyACM0", "type": "string", "desc": "Primary camera payload hardware connection interface port"},
        "DEVICE_ID": {"value": 0, "type": "int", "desc": "Hardware bus system device identifier number"},
        "CAMERA": {"value": "EO", "type": "enum", "choices": ["EO", "IR", "ANALOG"], "desc": "Active video sensor capture hardware optics module mode option"},
        "ZOOM_COUNT": {"value": 4, "type": "int", "desc": "Configured limit of dynamic focal magnification stepping levels available"},
        "ZOOMS": {"value": [1, 2, 4, 8], "type": "list", "desc": "Static magnification configuration multipliers matrix array track layout indices"},
        "FOV": {"value": [60, 55, 30, 20], "type": "list", "desc": "Horizontal Field of View degrees metrics corresponding by step layer map"}
    },
    "Tracking": {
        "BBOX_SIZE": {"value": 30, "type": "int", "desc": "Target visual tracking bounding box window pixel dimension limits selection"},
        "Tracker": {
            "value": "TrackerCSRT",
            "type": "enum",
            "choices": ["TrackerCSRT", "TrackerDasiamRPN", "TrackerKCF", "TrackerNano"],
            "desc": "Active correlation computer vision object tracking engine algorithm selector execution framework"
        }
    },
    "Vehicle": {
        "PORT": {"value": "/dev/ttyACM1", "type": "string", "desc": "Autopilot telemetry core flight controller serial physical communication link"},
        "BAUD": {"value": 9600, "type": "int", "desc": "Serial interface transmission baudrate timing step"},
        "SERVO_TRIGGER": {"value": 2000, "type": "int", "desc": "PWM microcontroller pulse timing microsecond limit value threshold switch trigger"},
        "SERVO_NUMBER": {"value": 9, "type": "int", "desc": "Assigned physical servo pin out mapping layout target index"}
    }
}

if os.path.exists(JSON_FILE):
    with open(JSON_FILE, "r") as f:
        PARAMETERS = json.load(f)
else:
    PARAMETERS = DEFAULT_PARAMETERS


class OverlayWidget(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # We removed self.setFixedSize(...) because size will now be managed dynamically by the parent.
        self.setFrameShape(QFrame.Box)
        
        # Custom dark-theme matching QGC
        self.setStyleSheet("""
            OverlayWidget {
                background-color: #212121;
                border: 2px solid #007ACC;
                border-radius: 6px;
            }
            QListWidget { background-color: #2D2D2D; border: 1px solid #3D3D3D; color: #E0E0E0; font-size: 13px; }
            QListWidget::item { padding: 6px; border-bottom: 1px solid #353535; }
            QListWidget::item:selected { background-color: #4A4A4A; color: #FFF; font-weight: bold; }
            QTableWidget { background-color: #252525; gridline-color: #2D2D2D; border: none; }
            QHeaderView::section { background-color: #2D2D2D; color: #AAAAAA; padding: 4px; border: 1px solid #212121; font-weight: bold; }
            QLineEdit, QSpinBox, QComboBox { background-color: #333333; border: 1px solid #555555; padding: 3px; color: #FFF; }
            QPushButton { background-color: #3A3A3A; border: 1px solid #555555; padding: 4px 10px; color: #E0E0E0; }
            QPushButton:hover { background-color: #4A4A4A; }
        """)

        self.widgets = {}
        self.current_module = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # Header with Search & Save Buttons
        header = QHBoxLayout()
        header.addWidget(QLabel("Search:"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter parameters...")
        header.addWidget(self.search)
        
        self.clear_btn = QPushButton("Clear")
        header.addWidget(self.clear_btn)
        header.addStretch()
        
        self.save_btn = QPushButton("Save All to Disk")
        self.save_btn.setStyleSheet("background-color: #1B5E20; color: #FFF; border: 1px solid #2E7D32;")
        header.addWidget(self.save_btn)
        layout.addLayout(header)

        # Splitter Layout: Module Selector & Details Grid
        splitter = QSplitter(Qt.Horizontal)
        
        self.module_list = QListWidget()
        for module in PARAMETERS.keys():
            self.module_list.addItem(module)
        splitter.addWidget(self.module_list)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Parameter", "Value", "Description"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnWidth(1, 190)
        splitter.addWidget(self.table)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        layout.addWidget(splitter)

        # Connect internal component signals
        self.module_list.currentTextChanged.connect(self.load_parameters)
        self.search.textChanged.connect(self.filter_parameters)
        self.clear_btn.clicked.connect(self.search.clear)
        self.save_btn.clicked.connect(self.save)

        self.module_list.setCurrentRow(0)
        self.hide()

    def load_parameters(self, module_name):
        if not module_name: return
        self.current_module = module_name
        
        self.table.setRowCount(0)
        self.widgets.clear()
        
        params = PARAMETERS[self.current_module]
        for name, info in params.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Name
            lbl_item = QTableWidgetItem(name)
            lbl_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 0, lbl_item)
            
            # Widget Editor
            widget = self.create_widget(info)
            self.widgets[name] = widget
            self.table.setCellWidget(row, 1, widget)
            
            # Auto-height for list parameters
            if info["type"] == "list":
                self.table.setRowHeight(row, 110)
            else:
                self.table.setRowHeight(row, 34)
            
            # Description
            desc_text = info.get("desc", "No description available.")
            desc_item = QTableWidgetItem(desc_text)
            desc_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            desc_item.setForeground(QColor("#AAAAAA"))
            self.table.setItem(row, 2, desc_item)
            
        if self.current_module == "Camera" and "ZOOM_COUNT" in self.widgets:
            self.widgets["ZOOM_COUNT"].valueChanged.connect(self.update_dynamic_lists)

    def create_widget(self, info):
        t = info["type"]
        value = info["value"]

        if t == "string":
            return QLineEdit(str(value))
        elif t == "int":
            w = QSpinBox()
            w.setMaximum(1000000)
            w.setValue(int(value))
            return w
        elif t == "enum":
            w = QComboBox()
            w.addItems(info["choices"])
            w.setCurrentText(str(value))
            return w
        elif t == "list":
            list_widget = QListWidget()
            for idx, item in enumerate(value):
                list_item = QListWidgetItem(f"[{idx}]  {item}")
                list_item.setFlags(list_item.flags() | Qt.ItemIsEditable)
                list_widget.addItem(list_item)
            list_widget.itemChanged.connect(self.sanitize_list_display)
            return list_widget
        return QLabel("Unknown")

    def sanitize_list_display(self, item):
        list_widget = item.listWidget()
        if not list_widget: return
        list_widget.blockSignals(True)
        for idx in range(list_widget.count()):
            current_item = list_widget.item(idx)
            clean_text = re.sub(r"^\[\d+\]\s*", "", current_item.text())
            current_item.setText(f"[{idx}]  {clean_text}")
        list_widget.blockSignals(False)

    def update_dynamic_lists(self, new_count):
        for list_name in ["ZOOMS", "FOV"]:
            if list_name in self.widgets and isinstance(self.widgets[list_name], QListWidget):
                list_widget = self.widgets[list_name]
                current_count = list_widget.count()

                if new_count > current_count:
                    for idx in range(current_count, new_count):
                        list_item = QListWidgetItem(f"[{idx}]  0")
                        list_item.setFlags(list_item.flags() | Qt.ItemIsEditable)
                        list_widget.addItem(list_item)
                elif new_count < current_count:
                    for _ in range(current_count - new_count):
                        list_widget.takeItem(list_widget.count() - 1)

    def filter_parameters(self, text):
        text = text.lower()
        for row in range(self.table.rowCount()):
            param_name_item = self.table.item(row, 0)
            param_desc_item = self.table.item(row, 2)
            match_found = (text in param_name_item.text().lower()) or (text in param_desc_item.text().lower())
            self.table.setRowHidden(row, not match_found)

    def save(self):
        if not self.current_module: return
        m = self.current_module

        for name, widget in self.widgets.items():
            if isinstance(widget, QLineEdit):
                PARAMETERS[m][name]["value"] = widget.text()
            elif isinstance(widget, QSpinBox):
                PARAMETERS[m][name]["value"] = widget.value()
            elif isinstance(widget, QComboBox):
                PARAMETERS[m][name]["value"] = widget.currentText()
            elif isinstance(widget, QListWidget):
                data = []
                for i in range(widget.count()):
                    clean_val = re.sub(r"^\[\d+\]\s*", "", widget.item(i).text()).strip()
                    if clean_val.isdigit():
                        data.append(int(clean_val))
                    else:
                        try: data.append(float(clean_val))
                        except ValueError: data.append(clean_val)
                PARAMETERS[m][name]["value"] = data

        try:
            with open(JSON_FILE, "w") as f:
                json.dump(PARAMETERS, f, indent=4)
            print("Disk Configuration Write: Success.")
        except Exception as e:
            print(f"Error saving JSON to disk: {e}")


class MainPage(QWidget):

    def __init__(self, stack):
        super().__init__()
        self.stack = stack

        self.menu_button = QPushButton("Status")
        self.menu_button.setFixedSize(120, 30)
        self.menu_button.setStyleSheet(
            "background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, "
            "stop:0 rgba(0, 255, 0, 255), stop:1 rgba(255, 255, 255, 255)); border: none; color: #000;"
        )

        self.popup_button = QPushButton("Params Editor")
        self.popup_button.setFixedSize(120, 30)
        
        self.overlay = OverlayWidget(self)
        # Using frameless tool layout so it behaves nicely as an overlay sheet inside this window
        self.overlay.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.menu_button)
        top_layout.addStretch()
        top_layout.addWidget(self.popup_button)

        main_layout = QVBoxLayout()
        main_layout.addLayout(top_layout)

        center_label = QLabel("QGC Like Main Window")
        center_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(center_label)

        self.setLayout(main_layout)

        self.menu_button.clicked.connect(self.show_menu)
        self.popup_button.clicked.connect(self.toggle_overlay)

    def update_overlay_geometry(self):
        """Calculates and applies 75% width/height coordinates dynamically centered."""
        # Get 75% of parent dimensions
        new_width = int(self.width() * 0.75)
        new_height = int(self.height() * 0.75)
        
        # Center coordinates
        new_x = (self.width() - new_width) // 2
        new_y = (self.height() - new_height) // 2
        
        # Apply the geometry relative to the parent's global screen position
        global_pos = self.mapToGlobal(QPoint(new_x, new_y))
        self.overlay.setGeometry(global_pos.x(), global_pos.y(), new_width, new_height)

    def toggle_overlay(self):
        if self.overlay.isVisible():
            self.overlay.hide()
        else:
            self.update_overlay_geometry()
            self.overlay.show()
            self.overlay.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Keep the overlay dynamically bound to 75% of the screen limits even when resized
        if self.overlay.isVisible():
            self.update_overlay_geometry()

    def show_menu(self):
        menu = QMenu()
        structure = {
            "Motor 1": 1, "Motor 2": 0, "Motor 3": 0, "Motor 4": 1,
            "Motor 5": 0, "Motor 6": 1, "Servo 1": 1, "Servo 2": 0,
            "Servo 3": 0, "Servo 4": 1, "Servo 5": 0, "Servo 6": 1,
        }

        vehicle_menu = menu.addMenu("Vehicle")
        vehicle_menu.addAction("Connect")
        vehicle_menu.addAction("Disconnect")
        vehicle_menu.addAction("Arm")

        menu.addMenu("Troubleshooting")
        gimbal_menu = menu.addMenu("Control")

        for name, value in structure.items():
            if value:
                gimbal_menu.addAction(f"🟢 {name}")
            else:
                gimbal_menu.addAction(f"🔴 {name}")

        exit_action = menu.addAction("Exit")

        menu.setStyleSheet("""
            QMenu::item { padding: 10px 30px; margin: 10px; border-radius: 10px; }
        """)

        action = menu.exec_(
            self.menu_button.mapToGlobal(QPoint(0, self.menu_button.height()))
        )

        if action == exit_action:
            self.goto_home()

    def goto_home(self):
        self.stack.setCurrentIndex(1)


class MainApplication(QStackedWidget):

    def __init__(self):
        super().__init__()
        self.main_page = MainPage(self)
        self.addWidget(self.main_page)
        
        self.dummy_page = QWidget()
        dummy_layout = QVBoxLayout(self.dummy_page)
        dummy_layout.addWidget(QLabel("Returned Home! Reset Application or Exit."))
        self.addWidget(self.dummy_page)

        self.setCurrentIndex(0)
        self.setWindowTitle("Ground Station")
        self.resize(1000, 700) # Resized parent window slightly to showcase dynamic centering


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApplication()
    window.show()
    sys.exit(app.exec())

import sys
import json
import os
import re
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

JSON_FILE = "parameters.json"

DEFAULT_PARAMETERS = {
    "M1": {
        "PORT": {
            "value": "/dev/ttyUSB0",
            "type": "string",
            "desc": "M1 communication serial port connection interface",
        },
        "BAUD": {
            "value": 115200,
            "type": "int",
            "desc": "Baudrate standard speed for serial data transmission telemetry",
        },
    },
    "M2": {
        "PORT": {
            "value": "/dev/ttyACM0",
            "type": "string",
            "desc": "Primary camera payload hardware connection interface port",
        },
        "DEVICE_ID": {
            "value": 0,
            "type": "int",
            "desc": "Hardware bus system device identifier number",
        },
        "CAMERA": {
            "value": "EO",
            "type": "enum",
            "choices": ["EO", "IR", "ANALOG"],
            "desc": "Active video sensor capture hardware optics module mode option",
        },
        "ZOOM_COUNT": {
            "value": 4,
            "type": "int",
            "desc": "Configured limit of dynamic focal magnification stepping levels available",
        },
        "ZOOMS": {
            "value": [1, 2, 4, 8],
            "type": "list",
            "desc": "Static magnification configuration multipliers matrix array track layout indices",
        },
        "FOV": {
            "value": [60, 55, 30, 20],
            "type": "list",
            "desc": "Horizontal Field of View degrees metrics corresponding by step layer map",
        },
    },
    "T1": {
        "BBOX_SIZE": {
            "value": 30,
            "type": "int",
            "desc": "Target visual tracking bounding box window pixel dimension limits selection",
        },
        "Tracker": {
            "value": "TrackerCSRT",
            "type": "enum",
            "choices": ["TrackerCSRT", "TrackerDasiamRPN", "TrackerKCF", "TrackerNano"],
            "desc": "Active correlation computer vision object tracking engine algorithm selector execution framework",
        },
    },
    "V1": {
        "PORT": {
            "value": "/dev/ttyACM1",
            "type": "string",
            "desc": "Autopilot telemetry core flight controller serial physical communication link",
        },
        "BAUD": {
            "value": 9600,
            "type": "int",
            "desc": "Serial interface transmission baudrate timing step",
        },
        "SERVO_TRIGGER": {
            "value": 2000,
            "type": "int",
            "desc": "PWM microcontroller pulse timing microsecond limit value threshold switch trigger",
        },
        "SERVO_NUMBER": {
            "value": 9,
            "type": "int",
            "desc": "Assigned physical servo pin out mapping layout target index",
        },
    },
}

if os.path.exists(JSON_FILE):
    with open(JSON_FILE, "r") as f:
        PARAMETERS = json.load(f)
else:
    PARAMETERS = DEFAULT_PARAMETERS


class ParameterWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PX4 Style Parameter Editor")
        self.resize(1200, 750)

        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #212121; color: #E0E0E0; font-family: 'Segoe UI', Arial; }
            QListWidget { background-color: #2D2D2D; border: 1px solid #3D3D3D; color: #E0E0E0; font-size: 13px; padding: 2px; }
            QListWidget::item { margin: 6px; border-bottom: 1px solid #353535; }
            QListWidget::item:selected { background-color: #4A4A4A; color: #FFF; font-weight: bold; }
            QTableWidget { background-color: #252525; gridline-color: #2D2D2D; border: none; }
            QTableWidget::item { padding: 1px; }
            QHeaderView::section { background-color: #2D2D2D; color: #AAAAAA; padding: 1px; border: 1px solid #212121; font-weight: bold; }
            QLineEdit, QSpinBox, QComboBox { background-color: #333333; border: 1px solid #555555; padding: 1px; color: #FFF; border-radius: 2px; }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid #007ACC; }
            QPushButton { background-color: #3A3A3A; border: 1px solid #555555; padding: 1px 1px; color: #E0E0E0; font-weight: bold; }
            QPushButton:hover { background-color: #4A4A4A; border-color: #007ACC; }
            QPushButton:pressed { background-color: #2A2A2A; }
            QLabel { font-size: 13px; }
        """)

        self.widgets = {}
        self.current_module = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # Top Bar
        top = QHBoxLayout()
        top.setContentsMargins(10, 5, 10, 5)
        top.addWidget(QLabel("Search:"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Enter parameter key name...")
        self.search.setFixedWidth(250)
        top.addWidget(self.search)
        self.clear_btn = QPushButton("Clear")
        top.addWidget(self.clear_btn)
        top.addStretch()

        self.save_btn = QPushButton("Save All to Disk")
        self.save_btn.setStyleSheet(
            "background-color: #1B5E20; color: #FFF; border: 1px solid #2E7D32;"
        )
        top.addWidget(self.save_btn)
        root.addLayout(top)

        # Two-Column Splitter Layout
        main_splitter = QSplitter(Qt.Horizontal)

        self.module_list = QListWidget()
        for module in PARAMETERS.keys():
            self.module_list.addItem(module)
        main_splitter.addWidget(self.module_list)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(
            ["Parameter Name", "Value Configuration", "Description"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        main_splitter.addWidget(self.table)

        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 5)
        root.addWidget(main_splitter)

        # Set default width for Value Configuration column
        self.table.setColumnWidth(1, 220)

        # Signals
        self.module_list.currentTextChanged.connect(self.load_parameters)
        self.search.textChanged.connect(self.filter_parameters)
        self.clear_btn.clicked.connect(lambda: self.search.clear())
        self.save_btn.clicked.connect(self.save)

        self.module_list.setCurrentRow(0)

    def load_parameters(self, module_name):
        if not module_name:
            return
        self.current_module = module_name

        self.table.setRowCount(0)
        self.widgets.clear()

        params = PARAMETERS[self.current_module]

        for name, info in params.items():
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Column 0: Parameter Name
            lbl_item = QTableWidgetItem(name)
            lbl_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 0, lbl_item)

            # Column 1: Control Widget
            widget = self.create_widget(info)
            self.widgets[name] = widget
            self.table.setCellWidget(row, 1, widget)

            # Adjust row height dynamically if the type is a list
            if info["type"] == "list":
                self.table.setRowHeight(
                    row, 140
                )  # Give ample space to view multiple items
            else:
                self.table.setRowHeight(row, 36)  # Standard height for texts/spinboxes

            # Column 2: Description
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
            w = QLineEdit(str(value))
        elif t == "int":
            w = QSpinBox()
            w.setMaximum(1000000)
            w.setValue(int(value))
        elif t == "enum":
            w = QComboBox()
            w.addItems(info["choices"])
            w.setCurrentText(str(value))
        elif t == "list":
            # Create a true QListWidget instead of a combobox lookalike
            list_widget = QListWidget()
            for idx, item in enumerate(value):
                list_item = QListWidgetItem(f"[{idx}]  {item}")
                list_item.setFlags(list_item.flags() | Qt.ItemIsEditable)
                list_widget.addItem(list_item)
            list_widget.itemChanged.connect(self.sanitize_list_display)
            return list_widget
        else:
            w = QLabel("Unknown Layout Type")
        return w

    def sanitize_list_display(self, item):
        list_widget = item.listWidget()
        if not list_widget:
            return
        list_widget.blockSignals(True)
        for idx in range(list_widget.count()):
            current_item = list_widget.item(idx)
            clean_text = re.sub(r"^\[\d+\]\s*", "", current_item.text())
            current_item.setText(f"[{idx}]  {clean_text}")
        list_widget.blockSignals(False)

    def update_dynamic_lists(self, new_count):
        for list_name in ["ZOOMS", "FOV"]:
            if list_name in self.widgets and isinstance(
                self.widgets[list_name], QListWidget
            ):
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
            match_found = (text in param_name_item.text().lower()) or (
                text in param_desc_item.text().lower()
            )
            self.table.setRowHidden(row, not match_found)

    def save(self):
        if not self.current_module:
            return
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
                    clean_val = re.sub(
                        r"^\[\d+\]\s*", "", widget.item(i).text()
                    ).strip()
                    if clean_val.isdigit():
                        data.append(int(clean_val))
                    else:
                        try:
                            data.append(float(clean_val))
                        except ValueError:
                            data.append(clean_val)
                PARAMETERS[m][name]["value"] = data

        try:
            with open(JSON_FILE, "w") as f:
                json.dump(PARAMETERS, f, indent=4)
            print("Disk Configuration Write: Success.")
        except Exception as e:
            print(f"Error saving JSON to disk: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = ParameterWindow()
    w.show()
    sys.exit(app.exec())

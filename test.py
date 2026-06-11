import os

# Forces the application to use the traditional X11 platform layer (often prevents the error on Linux)
os.environ["QT_QPA_PLATFORM"] = "xcb"

import sys
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QStackedWidget,
    QMessageBox,
    QMenu,
    QFrame,
    QHBoxLayout,
)
from PyQt5.QtCore import Qt, QPoint


class LoginPage(QWidget):

    def __init__(self, stack):
        super().__init__()

        self.stack = stack

        self.user_edit = QLineEdit()
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.Password)

        login_btn = QPushButton("Login")

        layout = QVBoxLayout()

        layout.addWidget(QLabel("User ID"))
        layout.addWidget(self.user_edit)

        layout.addWidget(QLabel("Password"))
        layout.addWidget(self.pass_edit)

        layout.addWidget(login_btn)

        self.setLayout(layout)

        login_btn.clicked.connect(self.login)

    def login(self):

        user = self.user_edit.text()
        pwd = self.pass_edit.text()

        if user == "admin" and pwd == "1234":
            self.stack.setCurrentIndex(1)
        else:
            QMessageBox.warning(self, "Error", "Invalid Login")


class HomePage(QWidget):

    def __init__(self, stack):
        super().__init__()

        self.stack = stack

        start_btn = QPushButton("Start Ground Station")
        exit_btn = QPushButton("Close Application")

        layout = QVBoxLayout()

        layout.addWidget(QLabel("HOME PAGE"))
        layout.addWidget(start_btn)
        layout.addWidget(exit_btn)

        self.setLayout(layout)

        start_btn.clicked.connect(lambda: self.stack.setCurrentIndex(2))

        exit_btn.clicked.connect(QApplication.instance().quit)


class OverlayWidget(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedSize(250, 300)

        self.setFrameShape(QFrame.Box)

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Telemetry"))
        layout.addWidget(QLabel("COM Status"))
        layout.addWidget(QLabel("CPU Usage"))
        layout.addWidget(QLabel("Vehicle Mode"))

        self.setLayout(layout)

        self.hide()


class MainPage(QWidget):

    def __init__(self, stack):
        super().__init__()

        self.stack = stack

        self.menu_button = QPushButton("Status")
        self.menu_button.setFixedSize(120, 30)

        self.menu_button.setStyleSheet(
            "background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 rgba(0, 255, 0, 255), stop:1 rgba(255, 255, 255, 255)); border: none;"
        )

        self.popup_button = QPushButton("Popup")
        self.overlay = OverlayWidget(self)
        self.overlay.move(self.width() - self.overlay.width() - 20, 50)
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

    def toggle_overlay(self):

        if self.overlay.isVisible():
            self.overlay.hide()
        else:
            self.overlay.move(
                (self.width() - self.overlay.width()) // 2,
                (self.height() - self.overlay.height()) // 2,
            )

            self.overlay.show()
            self.overlay.raise_()

    def resizeEvent(self, event):

        super().resizeEvent(event)

        self.overlay.move(self.width() - self.overlay.width() - 20, 50)

    def show_menu(self):
        menu = QMenu()

        vehicle_menu = menu.addMenu("Vehicle")
        vehicle_menu.addAction("Connect")
        vehicle_menu.addAction("Disconnect")
        vehicle_menu.addAction("Arm")

        settings_menu = menu.addMenu("Settings")
        settings_menu.addAction("General")
        settings_menu.addAction("Display")

        comm_menu = settings_menu.addMenu("Communication")
        comm_menu.addAction("UART")
        comm_menu.addAction("CAN")
        comm_menu.addAction("UDP")

        trouble_menu = menu.addMenu("Troubleshooting")

        gimbal_menu = trouble_menu.addMenu("Control")
        gimbal_menu.addAction("Item 1")
        gimbal_menu.addAction("Item 2")
        gimbal_menu.addAction("Item 3")

        menu.addAction("Telemetry")
        menu.addAction("Logs")
        menu.addAction("About")
        exit_action = menu.addAction("Exit")

        action = menu.exec_(
            self.menu_button.mapToGlobal(QPoint(0, self.menu_button.height()))
        )

        if action == exit_action:
            self.goto_home()

    def goto_home(self):
        self.stack.setCurrentIndex(1)

    def closeEvent(self, event):
        event.ignore()
        QMessageBox.information(self, "Info", "Use Exit button.")
        event.ignore()


class MainApplication(QStackedWidget):

    def __init__(self):
        super().__init__()

        self.login_page = LoginPage(self)
        self.home_page = HomePage(self)
        self.main_page = MainPage(self)

        self.addWidget(self.login_page)
        self.addWidget(self.home_page)
        self.addWidget(self.main_page)

        self.setCurrentIndex(0)

        self.setWindowTitle("Ground Station")
        self.resize(900, 600)

    def closeEvent(self, event):
        # Ignore the close request
        event.ignore()

        # QMessageBox.warning(self, "Action Prohibited", "You cannot close this window!")


app = QApplication(sys.argv)

window = MainApplication()
window.show()

sys.exit(app.exec_())

import sys
import os
import re
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QPoint, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QTextCursor

# 1. Worker Thread to handle the SSH blocking read
class SSHWorker(QThread):
    # Signals to pass console output or status back to the GUI
    line_received = pyqtSignal(str)
    connection_failed = pyqtSignal(str)
    finished_running = pyqtSignal()

    def __init__(self, hostname, username, password, command):
        super().__init__()
        self.hostname = hostname
        self.username = username
        self.password = password
        self.command = command
        self._is_running = True

    def run(self):
        import paramiko  # Import inside the thread to avoid delay at app startup
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            self.line_received.emit(f"Connecting to {self.hostname}...\n")
            client.connect(hostname=self.hostname, username=self.username, password=self.password, timeout=5)
            self.line_received.emit("Connected successfully! Starting server application...\n")
            
            # "-u" is critical for unbuffered output so we get stdout in real-time
            stdin, stdout, stderr = client.exec_command(self.command)
            
            # Read line-by-line continuously
            while self._is_running:
                line = stdout.readline()
                if not line:
                    break  # Stream ended
                self.line_received.emit(line.strip())
                
        except Exception as e:
            self.connection_failed.emit(str(e))
        finally:
            client.close()
            self.finished_running.emit()

    def stop(self):
        self._is_running = False


# 2. Virtual Terminal Overlay UI (Takes 75% of parent, styled like a terminal)
class SSHConsoleOverlay(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Box)
        
        # Matrix Terminal Styling
        self.setStyleSheet("""
            SSHConsoleOverlay {
                background-color: #0C0C0C;
                border: 2px solid #00FF00;
                border-radius: 6px;
            }
            QPlainTextEdit {
                background-color: #0C0C0C;
                color: #00FF00;
                border: none;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
            }
            QPushButton {
                background-color: #222;
                border: 1px solid #00FF00;
                padding: 6px 12px;
                color: #00FF00;
                font-family: monospace;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00FF00;
                color: #000;
            }
            QLabel {
                color: #00FF00;
                font-family: monospace;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # Top Control Bar
        header = QHBoxLayout()
        self.title_lbl = QLabel("SSH REMOTE CONSOLE:")
        header.addWidget(self.title_lbl)
        header.addStretch()
        
        self.action_btn = QPushButton("Start App")
        header.addWidget(self.action_btn)
        layout.addLayout(header)

        # Virtual Terminal Display
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        # Force autoscroll handling limits
        self.console.setMaximumBlockCount(1000)
        layout.addWidget(self.console)

        # Thread setup reference
        self.worker = None
        self.action_btn.clicked.connect(self.toggle_session)
        self.hide()

    def append_output(self, text):
        """Appends output line-by-line and automatically scrolls to the bottom."""
        self.console.appendPlainText(text)
        self.console.moveCursor(QTextCursor.End)

    def toggle_session(self):
        if self.worker and self.worker.isRunning():
            self.append_output("\nStopping session manually...")
            self.worker.stop()
        else:
            self.console.clear()
            self.action_btn.setText("Stop App")
            
            # Spawn background thread execution
            self.worker = SSHWorker(
                hostname="19.168.12.80", 
                username="raj", 
                password="pass1234", 
                command="python3 -u server_application.py"
            )
            self.worker.line_received.connect(self.append_output)
            self.worker.connection_failed.connect(lambda err: self.append_output(f"\n[ERROR] Connection failed: {err}"))
            self.worker.finished_running.connect(self.on_session_finished)
            self.worker.start()

    def on_session_finished(self):
        self.action_btn.setText("Start App")
        self.append_output("\n--- Connection Closed ---")
        self.worker = None

    def closeEvent(self, event):
        # Prevent threading memory leak if window is closed
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        super().closeEvent(event)

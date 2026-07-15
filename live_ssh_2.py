class SSHWorker(QThread):
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
        self.channel = None  # Reference to the active channel descriptor
        self.client = None

    def run(self):
        import paramiko
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            self.line_received.emit(f"Connecting to {self.hostname}...\n")
            self.client.connect(hostname=self.hostname, username=self.username, password=self.password, timeout=5)
            self.line_received.emit("Connected successfully! Starting server application...\n")
            
            # 1. Obtain the transport channel to gain execution controls
            transport = self.client.get_transport()
            self.channel = transport.open_session()
            
            # 2. Execute the process directly through the open channel session
            self.channel.exec_command(self.command)
            
            # 3. Read incoming bytes line-by-line using a file-like buffer
            stdout_stream = self.channel.makefile('r', bufsize=1)
            
            while self._is_running:
                # Check if channel closed on the remote side
                if self.channel.exit_status_ready():
                    break
                    
                line = stdout_stream.readline()
                if not line:
                    break
                self.line_received.emit(line.strip())
                
        except Exception as e:
            self.connection_failed.emit(str(e))
        finally:
            self.cleanup()
            self.finished_running.emit()

    def stop(self):
        """Called externally when user clicks 'Stop App'."""
        self._is_running = False
        self.cleanup()

    def cleanup(self):
        """Forcibly shuts down channels and connections to kill remote tasks."""
        try:
            if self.channel:
                # Shuts down both reading and writing pipelines on the remote host
                self.channel.shutdown(2) 
                self.channel.close()
                self.channel = None
        except Exception:
            pass

        try:
            if self.client:
                self.client.close()
                self.client = None
        except Exception:
            pass

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                                 QLineEdit, QPushButton, QTextEdit, QMessageBox, QGroupBox)
from PySide6.QtCore import Qt

class DiagnosticDialog(QDialog):
    """
    Serial Hardware Diagnostic & Command Console.
    Allows engineers to send raw ASCII/HEX handshake commands (e.g. PC, CMDSTART, S)
    and inspect real-time responses from the DAQ box without cluttering the main operator UI.
    """
    def __init__(self, serial_manager, parent=None):
        super().__init__(parent)
        self.serial_manager = serial_manager
        
        self.setWindowTitle("Hardware Diagnostic & Serial Console")
        self.setMinimumSize(600, 420)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Info
        lbl_info = QLabel("Send raw commands directly to the machine DAQ box to test communication protocols.")
        lbl_info.setStyleSheet("color: #64748b;")
        layout.addWidget(lbl_info)
        
        # Quick Command Presets Group
        grp_presets = QGroupBox("Quick Handshake Presets")
        presets_layout = QHBoxLayout(grp_presets)
        
        common_cmds = [("Wake Up (PC)", "PC"), ("Start (CMDSTART)", "CMDSTART"), 
                       ("Tare (T)", "T"), ("Query (?)", "?"), ("Status (S)", "S")]
        
        for name, cmd in common_cmds:
            btn = QPushButton(name)
            btn.clicked.connect(lambda _, c=cmd: self._send_command_str(c))
            presets_layout.addWidget(btn)
            
        layout.addWidget(grp_presets)
        
        # Custom Command Input
        cmd_layout = QHBoxLayout()
        self.in_custom_cmd = QLineEdit()
        self.in_custom_cmd.setPlaceholderText("Enter custom command (e.g. PC, O, R, 0x05)...")
        self.in_custom_cmd.returnPressed.connect(self._send_custom_cmd)
        
        btn_send = QPushButton("Send Command")
        btn_send.setObjectName("btnPrimary")
        btn_send.clicked.connect(self._send_custom_cmd)
        
        cmd_layout.addWidget(self.in_custom_cmd)
        cmd_layout.addWidget(btn_send)
        layout.addLayout(cmd_layout)
        
        # Activity Console Log
        layout.addWidget(QLabel("Console Output Log:"))
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("font-family: 'Consolas', monospace; font-size: 12px;")
        layout.addWidget(self.txt_log, 1)
        
        # Bottom controls
        btn_clear = QPushButton("Clear Log")
        btn_clear.clicked.connect(self.txt_log.clear)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(btn_clear)
        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_close)
        layout.addLayout(bottom_layout)

    def _send_command_str(self, cmd_text: str):
        if not self.serial_manager.is_connected or not self.serial_manager.serial_conn:
            QMessageBox.warning(self, "Not Connected", "Serial port is not connected! Connect on the dashboard first.")
            return
            
        try:
            full_cmd = (cmd_text + "\r\n").encode('ascii')
            self.serial_manager.serial_conn.write(full_cmd)
            self.txt_log.append(f">>> SENT: {cmd_text} ({full_cmd})")
        except Exception as e:
            self.txt_log.append(f"[!] ERROR: {e}")

    def _send_custom_cmd(self):
        cmd_text = self.in_custom_cmd.text().strip()
        if cmd_text:
            self._send_command_str(cmd_text)
            self.in_custom_cmd.clear()

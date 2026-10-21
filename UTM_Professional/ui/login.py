from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                                 QPushButton, QLabel, QComboBox, QLineEdit, 
                                 QMessageBox, QFrame)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from communication.serial_manager import SerialManager
from ui.theme import Theme

class LoginScreen(QDialog):
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings = settings_manager
        
        self.setWindowTitle("UTM Professional - Operator Authentication")
        self.setFixedSize(460, 360)
        
        # Apply clean light theme
        self.setStyleSheet(Theme.get_stylesheet())
        
        self._setup_ui()
        self._populate_ports()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(20)
        
        # Header Badge & Title
        header = QVBoxLayout()
        header.setSpacing(4)
        
        lbl_brand = QLabel("🔬 UTM PROFESSIONAL")
        lbl_brand.setFont(QFont("Segoe UI", 18, QFont.Bold))
        lbl_brand.setAlignment(Qt.AlignCenter)
        lbl_brand.setStyleSheet("color: #0284c7;")
        
        lbl_sub = QLabel("Universal Testing Machine Workstation")
        lbl_sub.setAlignment(Qt.AlignCenter)
        lbl_sub.setStyleSheet("color: #64748b; font-size: 12px; font-weight: 500;")
        
        header.addWidget(lbl_brand)
        header.addWidget(lbl_sub)
        main_layout.addLayout(header)
        
        # Form Container
        form_card = QFrame()
        form_card.setObjectName("card")
        form_card.setStyleSheet("""
            #card {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        form_layout = QVBoxLayout(form_card)
        form_layout.setSpacing(14)
        
        # Port Selection
        port_layout = QHBoxLayout()
        lbl_port = QLabel("Serial Port:")
        lbl_port.setStyleSheet("font-weight: 600; color: #0f172a;")
        self.cb_ports = QComboBox()
        port_layout.addWidget(lbl_port)
        port_layout.addWidget(self.cb_ports, 1)
        form_layout.addLayout(port_layout)
        
        # Password
        pwd_layout = QHBoxLayout()
        lbl_pwd = QLabel("Password:")
        lbl_pwd.setStyleSheet("font-weight: 600; color: #0f172a;")
        self.in_password = QLineEdit()
        self.in_password.setEchoMode(QLineEdit.Password)
        self.in_password.setText(self.settings.get("password", "admin"))
        self.in_password.setPlaceholderText("Enter operator password (default: admin)...")
        self.in_password.returnPressed.connect(self._authenticate)
        pwd_layout.addWidget(lbl_pwd)
        pwd_layout.addWidget(self.in_password, 1)
        form_layout.addLayout(pwd_layout)
        
        main_layout.addWidget(form_card)
        
        # Action Button
        self.btn_start = QPushButton("INITIALIZE WORKSTATION")
        self.btn_start.setObjectName("btnStart")
        self.btn_start.clicked.connect(self._authenticate)
        main_layout.addWidget(self.btn_start)

    def _populate_ports(self):
        ports = SerialManager.get_available_ports()
        self.cb_ports.addItems(ports)
        
        saved_port = self.settings.get("com_port")
        if saved_port and saved_port in ports:
            self.cb_ports.setCurrentText(saved_port)

    def _authenticate(self):
        entered = self.in_password.text()
        expected = self.settings.get("password")
        
        if entered == expected:
            selected_port = self.cb_ports.currentText()
            if selected_port:
                self.settings.set("com_port", selected_port)
            self.accept()
        else:
            QMessageBox.critical(self, "Access Denied", "Incorrect Operator Password! Please try again.")
            self.in_password.clear()
            self.in_password.setFocus()

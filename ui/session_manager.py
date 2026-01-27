from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
                             QDialogButtonBox, QSpinBox, QTabWidget, QWidget,
                             QCheckBox, QGroupBox, QLabel)

class SessionManager(QDialog):
    def __init__(self, parent=None, session_data=None):
        super().__init__(parent)
        self.setWindowTitle("Session Settings")
        self.resize(500, 450)
        
        self.main_layout = QVBoxLayout(self)
        
        # Tab Widget
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)
        
        # Basic Settings Tab
        self.basic_tab = self.create_basic_tab()
        self.tabs.addTab(self.basic_tab, "Basic")
        
        # Network Settings Tab
        self.network_tab = self.create_network_tab()
        self.tabs.addTab(self.network_tab, "Network")
        
        # Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.main_layout.addWidget(self.buttons)

        # Pre-fill if editing
        if session_data:
            self.load_session_data(session_data)
    
    def create_basic_tab(self):
        """Create basic settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        form_layout = QFormLayout()
        
        self.name_input = QLineEdit()
        self.host_input = QLineEdit()
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(22)
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        form_layout.addRow("Session Name:", self.name_input)
        form_layout.addRow("Remote Host:", self.host_input)
        form_layout.addRow("Port:", self.port_input)
        form_layout.addRow("Username:", self.username_input)
        form_layout.addRow("Password:", self.password_input)
        
        layout.addLayout(form_layout)
        layout.addStretch()
        
        return widget
    
    def create_network_tab(self):
        """Create network settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # SSH Proxy Settings
        proxy_group = QGroupBox("SSH Proxy (SOCKS)")
        proxy_layout = QFormLayout()
        
        self.use_proxy_checkbox = QCheckBox()
        self.use_proxy_checkbox.toggled.connect(self.toggle_proxy_fields)
        
        self.proxy_host_input = QLineEdit()
        self.proxy_port_input = QSpinBox()
        self.proxy_port_input.setRange(1, 65535)
        self.proxy_port_input.setValue(1080)
        
        proxy_layout.addRow("Use SSH Proxy:", self.use_proxy_checkbox)
        proxy_layout.addRow("Proxy Host:", self.proxy_host_input)
        proxy_layout.addRow("Proxy Port:", self.proxy_port_input)
        
        proxy_group.setLayout(proxy_layout)
        layout.addWidget(proxy_group)
        
        # Proxy Jump Settings
        jump_group = QGroupBox("Proxy Jump (Bastion Host)")
        jump_layout = QFormLayout()
        
        self.use_jump_checkbox = QCheckBox()
        self.use_jump_checkbox.toggled.connect(self.toggle_jump_fields)
        
        self.jump_host_input = QLineEdit()
        self.jump_port_input = QSpinBox()
        self.jump_port_input.setRange(1, 65535)
        self.jump_port_input.setValue(22)
        self.jump_username_input = QLineEdit()
        self.jump_password_input = QLineEdit()
        self.jump_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        jump_layout.addRow("Use Proxy Jump:", self.use_jump_checkbox)
        jump_layout.addRow("Jump Host:", self.jump_host_input)
        jump_layout.addRow("Jump Port:", self.jump_port_input)
        jump_layout.addRow("Jump Username:", self.jump_username_input)
        jump_layout.addRow("Jump Password:", self.jump_password_input)
        
        # Info label
        info_label = QLabel("Proxy Jump connects through a bastion/jump host to reach the target server.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888; font-style: italic; font-size: 9pt;")
        jump_layout.addRow("", info_label)
        
        jump_group.setLayout(jump_layout)
        layout.addWidget(jump_group)
        
        layout.addStretch()
        
        # Initialize field states
        self.toggle_proxy_fields(False)
        self.toggle_jump_fields(False)
        
        return widget
    
    def toggle_proxy_fields(self, enabled):
        """Enable/disable proxy fields based on checkbox"""
        self.proxy_host_input.setEnabled(enabled)
        self.proxy_port_input.setEnabled(enabled)
    
    def toggle_jump_fields(self, enabled):
        """Enable/disable jump fields based on checkbox"""
        self.jump_host_input.setEnabled(enabled)
        self.jump_port_input.setEnabled(enabled)
        self.jump_username_input.setEnabled(enabled)
        self.jump_password_input.setEnabled(enabled)
    
    def load_session_data(self, session_data):
        """Load session data into form fields"""
        # Basic settings
        self.name_input.setText(session_data.get("name", ""))
        self.host_input.setText(session_data.get("host", ""))
        self.port_input.setValue(session_data.get("port", 22))
        self.username_input.setText(session_data.get("username", ""))
        self.password_input.setText(session_data.get("password", ""))
        
        # Network settings - Proxy
        proxy_settings = session_data.get("proxy", {})
        use_proxy = proxy_settings.get("enabled", False)
        self.use_proxy_checkbox.setChecked(use_proxy)
        if use_proxy:
            self.proxy_host_input.setText(proxy_settings.get("host", ""))
            self.proxy_port_input.setValue(proxy_settings.get("port", 1080))
        
        # Network settings - Proxy Jump
        jump_settings = session_data.get("proxy_jump", {})
        use_jump = jump_settings.get("enabled", False)
        self.use_jump_checkbox.setChecked(use_jump)
        if use_jump:
            self.jump_host_input.setText(jump_settings.get("host", ""))
            self.jump_port_input.setValue(jump_settings.get("port", 22))
            self.jump_username_input.setText(jump_settings.get("username", ""))
            self.jump_password_input.setText(jump_settings.get("password", ""))

    def get_session_data(self):
        """Get session data from form fields"""
        data = {
            "name": self.name_input.text() or self.host_input.text(),
            "host": self.host_input.text(),
            "port": self.port_input.value(),
            "username": self.username_input.text(),
            "password": self.password_input.text()
        }
        
        # Add proxy settings if enabled
        if self.use_proxy_checkbox.isChecked():
            data["proxy"] = {
                "enabled": True,
                "host": self.proxy_host_input.text(),
                "port": self.proxy_port_input.value()
            }
        else:
            data["proxy"] = {"enabled": False}
        
        # Add proxy jump settings if enabled
        if self.use_jump_checkbox.isChecked():
            data["proxy_jump"] = {
                "enabled": True,
                "host": self.jump_host_input.text(),
                "port": self.jump_port_input.value(),
                "username": self.jump_username_input.text(),
                "password": self.jump_password_input.text()
            }
        else:
            data["proxy_jump"] = {"enabled": False}
        
        return data

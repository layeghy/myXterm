from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, 
                             QWidget, QLabel, QComboBox, QSpinBox, QPushButton,
                             QColorDialog, QGroupBox, QRadioButton, QButtonGroup,
                             QPlainTextEdit, QFormLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from .settings_manager import SettingsManager

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(600, 500)
        
        self.settings_manager = SettingsManager()
        self.current_settings = self.settings_manager.get_all()
        
        # Initialize colors with defaults BEFORE creating UI
        self.fg_color = QColor("#FFFFFF")
        self.bg_color = QColor("#000000")
        
        self.init_ui()
        self.load_current_settings()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Tab Widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Terminal Tab
        self.terminal_tab = self.create_terminal_tab()
        self.tabs.addTab(self.terminal_tab, "Terminal")
        
        # Appearance Tab
        self.appearance_tab = self.create_appearance_tab()
        self.tabs.addTab(self.appearance_tab, "Appearance")
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_settings)
        button_layout.addWidget(self.apply_button)
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.ok_clicked)
        button_layout.addWidget(self.ok_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
    
    def create_terminal_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Font Settings Group
        font_group = QGroupBox("Font Settings")
        font_layout = QFormLayout()
        
        # Font Family
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems([
            "Consolas",
            "Courier New",
            "Monaco",
            "Lucida Console",
            "DejaVu Sans Mono",
            "Liberation Mono",
            "Menlo",
            "Source Code Pro"
        ])
        self.font_family_combo.currentTextChanged.connect(self.update_preview)
        font_layout.addRow("Font Family:", self.font_family_combo)
        
        # Font Size
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.valueChanged.connect(self.update_preview)
        font_layout.addRow("Font Size:", self.font_size_spin)
        
        font_group.setLayout(font_layout)
        layout.addWidget(font_group)
        
        # Color Settings Group
        color_group = QGroupBox("Color Settings")
        color_layout = QFormLayout()
        
        # Foreground Color
        fg_layout = QHBoxLayout()
        self.fg_color_label = QLabel()
        self.fg_color_label.setFixedSize(50, 25)
        self.fg_color_label.setStyleSheet("border: 1px solid #666;")
        fg_layout.addWidget(self.fg_color_label)
        
        self.fg_color_button = QPushButton("Choose...")
        self.fg_color_button.clicked.connect(self.choose_fg_color)
        fg_layout.addWidget(self.fg_color_button)
        fg_layout.addStretch()
        
        color_layout.addRow("Foreground Color:", fg_layout)
        
        # Background Color
        bg_layout = QHBoxLayout()
        self.bg_color_label = QLabel()
        self.bg_color_label.setFixedSize(50, 25)
        self.bg_color_label.setStyleSheet("border: 1px solid #666;")
        bg_layout.addWidget(self.bg_color_label)
        
        self.bg_color_button = QPushButton("Choose...")
        self.bg_color_button.clicked.connect(self.choose_bg_color)
        bg_layout.addWidget(self.bg_color_button)
        bg_layout.addStretch()
        
        color_layout.addRow("Background Color:", bg_layout)
        
        color_group.setLayout(color_layout)
        layout.addWidget(color_group)
        
        # Preview Group
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout()
        
        self.preview_text = QPlainTextEdit()
        self.preview_text.setPlainText("user@server:~$ ls -la\ntotal 48\ndrwxr-xr-x  6 user user 4096 Dec  4 08:30 .\ndrwxr-xr-x 24 user user 4096 Dec  3 15:22 ..\n-rw-r--r--  1 user user  220 Dec  1 10:15 .bash_logout")
        self.preview_text.setReadOnly(True)
        self.preview_text.setFixedHeight(120)
        preview_layout.addWidget(self.preview_text)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        layout.addStretch()
        
        return widget
    
    def create_appearance_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Theme Settings Group
        theme_group = QGroupBox("Application Theme")
        theme_layout = QVBoxLayout()
        
        self.theme_group = QButtonGroup()
        
        self.dark_theme_radio = QRadioButton("Dark Theme")
        self.theme_group.addButton(self.dark_theme_radio, 0)
        theme_layout.addWidget(self.dark_theme_radio)
        
        self.light_theme_radio = QRadioButton("Light Theme")
        self.theme_group.addButton(self.light_theme_radio, 1)
        theme_layout.addWidget(self.light_theme_radio)
        
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)
        
        # Info label
        info_label = QLabel("Note: Theme changes will apply to the entire application.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        return widget
    
    def load_current_settings(self):
        """Load current settings into UI controls"""
        # Terminal settings
        font_family = self.current_settings["terminal"]["font_family"]
        index = self.font_family_combo.findText(font_family)
        if index >= 0:
            self.font_family_combo.setCurrentIndex(index)
        
        self.font_size_spin.setValue(self.current_settings["terminal"]["font_size"])
        
        self.fg_color = QColor(self.current_settings["terminal"]["foreground_color"])
        self.bg_color = QColor(self.current_settings["terminal"]["background_color"])
        self.update_color_labels()
        
        # Appearance settings
        theme = self.current_settings["appearance"]["theme"]
        if theme == "dark":
            self.dark_theme_radio.setChecked(True)
        else:
            self.light_theme_radio.setChecked(True)
        
        self.update_preview()
    
    def choose_fg_color(self):
        color = QColorDialog.getColor(self.fg_color, self, "Choose Foreground Color")
        if color.isValid():
            self.fg_color = color
            self.update_color_labels()
            self.update_preview()
    
    def choose_bg_color(self):
        color = QColorDialog.getColor(self.bg_color, self, "Choose Background Color")
        if color.isValid():
            self.bg_color = color
            self.update_color_labels()
            self.update_preview()
    
    def update_color_labels(self):
        """Update the color preview labels"""
        self.fg_color_label.setStyleSheet(f"background-color: {self.fg_color.name()}; border: 1px solid #666;")
        self.bg_color_label.setStyleSheet(f"background-color: {self.bg_color.name()}; border: 1px solid #666;")
    
    def update_preview(self):
        """Update the preview text with current settings"""
        font_family = self.font_family_combo.currentText()
        font_size = self.font_size_spin.value()
        
        font = QFont(font_family, font_size)
        self.preview_text.setFont(font)
        
        style = f"""
            background-color: {self.bg_color.name()};
            color: {self.fg_color.name()};
            border: 1px solid #666;
        """
        self.preview_text.setStyleSheet(style)
    
    def apply_settings(self):
        """Apply settings without closing dialog"""
        self.save_settings()
    
    def ok_clicked(self):
        """Save settings and close dialog"""
        self.save_settings()
        self.accept()
    
    def save_settings(self):
        """Save current UI values to settings"""
        new_settings = {
            "terminal": {
                "font_family": self.font_family_combo.currentText(),
                "font_size": self.font_size_spin.value(),
                "foreground_color": self.fg_color.name(),
                "background_color": self.bg_color.name()
            },
            "appearance": {
                "theme": "dark" if self.dark_theme_radio.isChecked() else "light"
            }
        }
        
        self.settings_manager.update_settings(new_settings)
        self.current_settings = new_settings

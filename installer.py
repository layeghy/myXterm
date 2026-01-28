import sys
import os
import shutil
import winshell
from PyQt6.QtWidgets import (QApplication, QWizard, QWizardPage, QVBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt

def resource_path(*relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.normpath(os.path.join(base_path, *relative_path))

class InstallerWizard(QWizard):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("myXterm Installer")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        
        self.addPage(WelcomePage())
        self.addPage(LocationPage())
        self.addPage(InstallationPage())
        
        self.resize(600, 400)

class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Welcome to myXterm Installer")
        
        layout = QVBoxLayout()
        label = QLabel("This wizard will install myXterm on your computer.\n\n"
                       "Click Next to continue.")
        label.setWordWrap(True)
        layout.addWidget(label)
        self.setLayout(layout)

class LocationPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Installation Location")
        self.setSubTitle("Choose where to install myXterm")
        
        layout = QVBoxLayout()
        
        # Default path: %LOCALAPPDATA%\myXterm
        default_path = os.path.join(os.environ['LOCALAPPDATA'], 'myXterm')
        
        self.path_input = QLineEdit(default_path)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse)
        
        layout.addWidget(QLabel("Install to:"))
        layout.addWidget(self.path_input)
        layout.addWidget(self.browse_btn)
        
        self.setLayout(layout)
        
        self.registerField("installPath", self.path_input)

    def browse(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Install Directory")
        if directory:
            self.path_input.setText(os.path.join(directory, 'myXterm'))

class InstallationPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Installing")
        self.setSubTitle("Please wait while myXterm is being installed...")
        
        layout = QVBoxLayout()
        self.status_label = QLabel("Ready to install...")
        layout.addWidget(self.status_label)
        self.setLayout(layout)
    
    def initializePage(self):
        # Disable back button during installation
        self.wizard().button(QWizard.WizardButton.BackButton).setEnabled(False)
        
        # Start installation
        self.install()
        
    def install(self):
        install_path = self.field("installPath")
        self.status_label.setText(f"Installing to {install_path}...")
        QApplication.processEvents()
        
        try:
            # Create directory
            if not os.path.exists(install_path):
                os.makedirs(install_path)
            
            # Extract executable
            # In a real installer, we would extract files. 
            # Here, we assume the payload is bundled as 'myXterm.exe' in the installer's data
            source_exe = resource_path("myXterm.exe")
            dest_exe = os.path.join(install_path, "myXterm.exe")
            
            if os.path.exists(source_exe):
                self.status_label.setText("Copying files...")
                QApplication.processEvents()
                shutil.copy2(source_exe, dest_exe)
            else:
                raise FileNotFoundError("Could not find payload myXterm.exe")
            
            # Create Shortcut
            self.status_label.setText("Creating shortcuts...")
            QApplication.processEvents()
            
            desktop = winshell.desktop()
            start_menu = winshell.programs()
            
            # Desktop Shortcut
            shortcut_path = os.path.join(desktop, "myXterm.lnk")
            with winshell.shortcut(shortcut_path) as link:
                link.path = dest_exe
                link.description = "myXterm SSH Client"
                link.working_directory = install_path
            
            # Start Menu Shortcut
            start_menu_path = os.path.join(start_menu, "myXterm.lnk")
            with winshell.shortcut(start_menu_path) as link:
                link.path = dest_exe
                link.description = "myXterm SSH Client"
                link.working_directory = install_path
            
            self.status_label.setText("Installation Complete!")
            self.wizard().button(QWizard.WizardButton.FinishButton).setEnabled(True)
            
        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            QMessageBox.critical(self, "Installation Failed", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    wizard = InstallerWizard()
    wizard.show()
    sys.exit(app.exec())

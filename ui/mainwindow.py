from PyQt6.QtWidgets import QMainWindow, QSplitter, QTabWidget, QWidget, QVBoxLayout, QMessageBox, QFileDialog, QInputDialog, QLineEdit
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, pyqtSignal
from .sidebar import Sidebar
from .session_manager import SessionManager
from .terminal import Terminal
from .settings_dialog import SettingsDialog
from .settings_manager import SettingsManager
from ssh.backend import SSHSession
import threading

class MainWindow(QMainWindow):
    session_connected = pyqtSignal(object, str) # session, host
    session_failed = pyqtSignal(str) # error message
    mfa_requested = pyqtSignal(str, object) # prompt, event_container

    def __init__(self):
        super().__init__()
        self.setWindowTitle("myXterm")
        self.resize(1200, 800)
        
        # Initialize settings manager
        self.settings_manager = SettingsManager()
        self.settings_manager.add_callback(self.on_settings_changed)
        
        # Menu Bar
        self.create_menu_bar()
        
        # Main Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(self.splitter)
        
        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.new_session_clicked.connect(self.open_session_manager)
        self.sidebar.session_double_clicked.connect(self.start_ssh_session)
        self.splitter.addWidget(self.sidebar)
        
        # Tab Widget (Terminal Area)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.splitter.addWidget(self.tabs)
        
        # Set initial sizes (Sidebar 20%, Tabs 80%)
        self.splitter.setSizes([200, 800])
        
        # Add a local terminal tab instead of dummy tab
        self.add_local_terminal_tab()

        # Connect signal
        self.session_connected.connect(self.add_terminal_tab)
        self.session_failed.connect(self.show_error_message)
        self.mfa_requested.connect(self.handle_mfa_request)

    def add_local_terminal_tab(self):
        """Add a local terminal tab (PowerShell on Windows)"""
        from ssh.local_session import LocalSession
        
        # Create local session
        local_session = LocalSession("powershell.exe")
        if local_session.connect():
            settings = self.settings_manager.get_all()
            terminal = Terminal(local_session, settings)
            self.tabs.addTab(terminal, "Local Terminal")
            terminal.setFocus()
            
            # Connect session_closed signal to auto-close tab
            terminal.session_closed.connect(lambda: self.close_tab_by_widget(terminal))
        else:
            # Fallback to empty tab if local terminal fails
            dummy = QWidget()
            dummy.setStyleSheet("background-color: #1e1e1e;")
            self.tabs.addTab(dummy, "Welcome")

    def open_session_manager(self):
        dialog = SessionManager(self)
        if dialog.exec():
            data = dialog.get_session_data()
            self.sidebar.add_session(data)
            self.start_ssh_session(data)

    def start_ssh_session(self, data):
        host = data['host']
        port = data['port']
        username = data['username']
        password = data.get('password')
        
        if not password:
            password, ok = QInputDialog.getText(self, "SSH Password", f"Enter password for {username}@{host}:", echo=QLineEdit.EchoMode.Password)
            if not ok:
                return
            
            # Save the password
            print(f"DEBUG: Saving password for {username}@{host}")
            data['password'] = password
            # Use sidebar.update_password to ensure it's saved in the store AND the UI is refreshed
            if self.sidebar.update_password(data, password):
                print("DEBUG: Password updated in store and UI refreshed")
            else:
                print("DEBUG: Failed to update password in store - session not found?")

        
        # Extract proxy settings
        proxy_settings = data.get('proxy', {})
        proxy_jump_settings = data.get('proxy_jump', {})

        # Create session
        session = SSHSession(
            host, 
            port, 
            username, 
            password=password,
            proxy_settings=proxy_settings,
            proxy_jump_settings=proxy_jump_settings,
            auth_callback=self.get_mfa_response
        )
        
        # Connect in a separate thread
        threading.Thread(target=self._connect_thread, args=(session, host), daemon=True).start()

    def get_mfa_response(self, title, instructions, prompt_list):
        """
        Thread-safe callback for paramiko auth_interactive.
        prompt_list is a list of (prompt_string, echo_bool) tuples.
        """
        responses = []
        for prompt, echo in prompt_list:
             # We need to ask the user on the main thread
             event_container = {"response": None, "event": threading.Event()}
             self.mfa_requested.emit(prompt, event_container)
             # Wait for UI thread to process
             event_container["event"].wait()
             responses.append(event_container["response"] or "")
        return responses

    def handle_mfa_request(self, prompt, event_container):
        """Slot to handle MFA request on main thread"""
        text, ok = QInputDialog.getText(self, "MFA Authentication", prompt, echo=QLineEdit.EchoMode.Normal)
        if ok:
            event_container["response"] = text
        else:
            event_container["response"] = "" # Return empty string on cancel
        event_container["event"].set()

    def _connect_thread(self, session, host):
        if session.connect():
            self.session_connected.emit(session, host)
        else:
            self.session_failed.emit(f"Failed to connect to {host}")

    def show_error_message(self, message):
        QMessageBox.critical(self, "Connection Error", message)

    def add_terminal_tab(self, session, host):
        settings = self.settings_manager.get_all()
        terminal = Terminal(session, settings)
        self.tabs.addTab(terminal, host)
        self.tabs.setCurrentWidget(terminal)
        terminal.setFocus()
        
        # Connect session_closed signal to auto-close tab
        terminal.session_closed.connect(lambda: self.close_tab_by_widget(terminal))

    def close_tab(self, index):
        widget = self.tabs.widget(index)
        if isinstance(widget, Terminal):
            widget.session.close()
        self.tabs.removeTab(index)

    def close_tab_by_widget(self, widget):
        # Find and close tab by widget reference
        for i in range(self.tabs.count()):
            if self.tabs.widget(i) == widget:
                self.close_tab(i)
                break

    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("File")
        
        # Settings Action
        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        # Import Action
        import_action = QAction("Import Sessions...", self)
        import_action.triggered.connect(self.import_sessions)
        file_menu.addAction(import_action)
        
        # Export Action
        export_action = QAction("Export Sessions...", self)
        export_action.triggered.connect(self.export_sessions)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        # Exit Action
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def import_sessions(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Import Sessions", "", "XML Files (*.xml);;All Files (*)")
        if filename:
            count = self.sidebar.import_sessions(filename)
            if count > 0:
                QMessageBox.information(self, "Import Successful", f"{count} sessions imported successfully.")
            elif count == 0:
                QMessageBox.warning(self, "Import Warning", "No sessions found in the file.")
            else:
                QMessageBox.critical(self, "Import Failed", "Failed to import sessions.")

    def export_sessions(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Export Sessions", "sessions.xml", "XML Files (*.xml);;All Files (*)")
        if filename:
            if self.sidebar.export_sessions(filename):
                QMessageBox.information(self, "Export Successful", "Sessions exported successfully.")
            else:
                QMessageBox.critical(self, "Export Failed", "Failed to export sessions.")
    
    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self)
        dialog.exec()
    
    def on_settings_changed(self, settings):
        """Handle settings changes - apply theme"""
        theme = settings.get("appearance", {}).get("theme", "dark")
        self.apply_theme(theme)
    
    def apply_theme(self, theme):
        """Apply the selected theme to the application"""
        from PyQt6.QtWidgets import QApplication
        from utils import resource_path
        
        if theme == "light":
            stylesheet_path = resource_path("ui/style_light.qss")
        else:
            stylesheet_path = resource_path("ui/style.qss")
        
        try:
            with open(stylesheet_path, "r") as f:
                QApplication.instance().setStyleSheet(f.read())
        except Exception as e:
            print(f"Error loading stylesheet: {e}")

from PyQt6.QtWidgets import QMainWindow, QSplitter, QTabWidget, QWidget, QVBoxLayout, QMessageBox, QFileDialog, QInputDialog, QLineEdit, QToolBar
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
    mfa_requested = pyqtSignal(str, str, str, bool, object) # title, instructions, prompt, echo, event_container
    password_requested = pyqtSignal(str, object) # prompt, event_container

    def __init__(self):
        super().__init__()
        self.setWindowTitle("myXterm")
        self.resize(1200, 800)
        
        # Initialize settings manager
        self.settings_manager = SettingsManager()
        self.settings_manager.add_callback(self.on_settings_changed)
        
        # Menu Bar
        self.create_menu_bar()
        
        # Toolbar
        self.create_toolbar()
        
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
        self.password_requested.connect(self.handle_password_request)

    def add_local_terminal_tab(self):
        """Add a local terminal tab (PowerShell on Windows)"""
        from ssh.local_session import LocalSession
        
        # Create local session
        local_session = LocalSession("powershell.exe")
        if local_session.connect():
            print("DEBUG: Local session connected successfully")
            settings = self.settings_manager.get_all()
            terminal = Terminal(local_session, settings)
            self.tabs.addTab(terminal, "Local Terminal")
            terminal.setFocus()
            
            # Connect session_closed signal to auto-close tab
            terminal.session_closed.connect(lambda: self.close_tab_by_widget(terminal))
        else:
            print("DEBUG: Local session failed to connect")
            
            # Read debug log for user feedback
            log_content = "Could not read debug log."
            if os.path.exists("session_debug.log"):
                try:
                    with open("session_debug.log", "r") as f:
                        # Get last 20 lines
                        lines = f.readlines()
                        log_content = "".join(lines[-20:])
                except:
                    pass
            
            QMessageBox.critical(self, "Local Terminal Error", 
                                f"Failed to start local terminal.\n\nDebug Log:\n{log_content}")
            
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
        proxy_jump_settings = data.setdefault('proxy_jump', {'enabled': False})
        
        # Check for Jump Host password
        if proxy_jump_settings and proxy_jump_settings.get("enabled"):
            jump_user = proxy_jump_settings.get("username")
            jump_host = proxy_jump_settings.get("host")
            jump_pass = proxy_jump_settings.get("password")
            
            if not jump_pass:
                jump_pass, ok = QInputDialog.getText(self, "Jump Host Password", f"Enter password for jump host {jump_user}@{jump_host}:", echo=QLineEdit.EchoMode.Password)
                if not ok:
                    return # User cancelled
                proxy_jump_settings['password'] = jump_pass
                # We don't necessarily need to save it to store unless we want persistence
                # self.sidebar.update_jump_password(data, jump_pass) # TODO: add this if needed

        # Create session
        session = SSHSession(
            host, 
            port, 
            username, 
            password=password,
            proxy_settings=proxy_settings,
            proxy_jump_settings=proxy_jump_settings,
            auth_callback=self.get_mfa_response,
            password_callback=self.get_password_response
        )
        
        # Connect in a separate thread
        threading.Thread(target=self._connect_thread, args=(session, host), daemon=True).start()

    def get_password_response(self, prompt):
        """Thread-safe callback to get a new password from user"""
        event_container = {"response": None, "event": threading.Event()}
        self.password_requested.emit(prompt, event_container)
        if not event_container["event"].wait(timeout=120):
            return None
        return event_container["response"]

    def handle_password_request(self, prompt, event_container):
        """Slot to handle password request on main thread"""
        text, ok = QInputDialog.getText(self, "Authentication Failed", prompt, echo=QLineEdit.EchoMode.Password)
        if ok:
            event_container["response"] = text
        else:
            event_container["response"] = None
        event_container["event"].set()

    def get_mfa_response(self, title, instructions, prompt_list):
        """
        Thread-safe callback for paramiko auth_interactive.
        """
        print(f"DEBUG: get_mfa_response called - Title: {title}, Instructions: {instructions}, Prompts: {len(prompt_list)}")
        responses = []
        for prompt, echo in prompt_list:
             # We need to ask the user on the main thread
             event_container = {"response": None, "event": threading.Event()}
             print(f"DEBUG: Emitting mfa_requested for prompt: {prompt}")
             self.mfa_requested.emit(title, instructions, prompt, echo, event_container)
             # Wait for UI thread to process
             if not event_container["event"].wait(timeout=120): # 2 minute timeout
                 print("DEBUG: MFA timeout reached")
                 responses.append("")
                 continue
             print(f"DEBUG: Received MFA response: {'***' if not echo else event_container['response']}")
             responses.append(event_container["response"] or "")
        return responses

    def handle_mfa_request(self, title, instructions, prompt, echo, event_container):
        """Slot to handle MFA request on main thread"""
        print(f"MFA Request: {prompt}")
        
        # Format a nice message for the user
        display_title = title or "MFA Authentication"
        if instructions:
            # If instructions are long, use them as the main text
            display_prompt = f"{instructions}\n\n{prompt}"
        else:
            display_prompt = prompt

        text, ok = QInputDialog.getText(
            self, 
            display_title,
            display_prompt, 
            echo=QLineEdit.EchoMode.Normal if echo else QLineEdit.EchoMode.Password
        )
        
        if ok:
            event_container["response"] = text
        else:
            event_container["response"] = ""
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

    def create_toolbar(self):
        """Create the main toolbar"""
        self.toolbar = QToolBar("Main Toolbar")
        self.addToolBar(self.toolbar)
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        
        from PyQt6.QtWidgets import QStyle
        
        # New SSH Session Action
        ssh_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogStart)
        ssh_action = QAction(ssh_icon, "New SSH", self)
        ssh_action.setToolTip("Open Session Manager")
        ssh_action.triggered.connect(self.open_session_manager)
        self.toolbar.addAction(ssh_action)
        
        self.toolbar.addSeparator()
        
        # New Local Terminal Action
        local_term_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        local_term_action = QAction(local_term_icon, "Local Terminal", self)
        local_term_action.setToolTip("Open a new local terminal tab")
        local_term_action.triggered.connect(self.add_local_terminal_tab)
        self.toolbar.addAction(local_term_action)
        
        self.toolbar.addSeparator()
        
        # Settings Action
        settings_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        settings_action = QAction(settings_icon, "Settings", self)
        settings_action.setToolTip("Open application settings")
        settings_action.triggered.connect(self.open_settings)
        self.toolbar.addAction(settings_action)

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
            stylesheet_path = resource_path("ui", "style_light.qss")
        else:
            stylesheet_path = resource_path("ui", "style.qss")
        
        try:
            with open(stylesheet_path, "r") as f:
                QApplication.instance().setStyleSheet(f.read())
        except Exception as e:
            print(f"Error loading stylesheet: {e}")

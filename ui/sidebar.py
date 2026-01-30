from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QPushButton, QLabel, QMenu, QMessageBox, QInputDialog
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, pyqtSignal
from utils import resource_path
from .session_manager import SessionManager

from .session_store import SessionStore

class Sidebar(QWidget):
    new_session_clicked = pyqtSignal()
    session_double_clicked = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        self.header = QLabel("Sessions")
        self.header.setStyleSheet("font-weight: bold; padding: 5px;")
        self.layout.addWidget(self.header)

        # Session Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.layout.addWidget(self.tree)
        
        # Session Store
        self.session_store = SessionStore()
        self.load_sessions()
        
        # Buttons
        self.new_session_btn = QPushButton("New Session")
        self.new_session_btn.clicked.connect(self.new_session_clicked.emit)
        self.layout.addWidget(self.new_session_btn)

    def load_sessions(self):
        self.tree.clear()
        user_sessions = QTreeWidgetItem(self.tree)
        user_sessions.setText(0, "User Sessions")
        from PyQt6.QtWidgets import QStyle
        user_sessions.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        user_sessions.setExpanded(True)
        
        sessions = self.session_store.get_sessions()
        terminal_icon = QIcon(resource_path("resources", "terminal.png"))
        for session in sessions:
            item = QTreeWidgetItem(user_sessions)
            name = session.get("name", f"{session['host']} ({session['username']})")
            item.setText(0, name)
            item.setIcon(0, terminal_icon)
            item.setData(0, Qt.ItemDataRole.UserRole, session)

    def add_session(self, session_data):
        self.session_store.add_session(session_data)
        self.load_sessions()

    def update_password(self, session_data, password):
        if self.session_store.update_password(session_data, password):
            self.load_sessions()
            return True
        return False

    def import_sessions(self, filename):
        result = self.session_store.import_from_xml(filename)
        if result > 0:
            self.load_sessions()
        return result

    def export_sessions(self, filename):
        return self.session_store.export_to_xml(filename)

    def show_context_menu(self, position):
        item = self.tree.itemAt(position)
        if not item or not item.parent(): # Ignore top-level items or empty space
            return
        
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        menu = QMenu()
        edit_action = menu.addAction("Edit Session")
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        
        action = menu.exec(self.tree.viewport().mapToGlobal(position))
        
        if action == edit_action:
            self.edit_session(data)
        elif action == rename_action:
            self.rename_session(data)
        elif action == delete_action:
            self.delete_session(data)

    def edit_session(self, data):
        dialog = SessionManager(self, session_data=data)
        if dialog.exec():
            new_data = dialog.get_session_data()
            if self.session_store.update_session(data, new_data):
                self.load_sessions()

    def rename_session(self, data):
        new_name, ok = QInputDialog.getText(self, "Rename Session", "New Name:", text=data.get("name", ""))
        if ok and new_name:
            new_data = data.copy()
            new_data["name"] = new_name
            if self.session_store.update_session(data, new_data):
                self.load_sessions()

    def delete_session(self, data):
        confirm = QMessageBox.question(self, "Delete Session", f"Are you sure you want to delete '{data.get('name', 'this session')}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            if self.session_store.delete_session(data):
                self.load_sessions()

    def on_item_double_clicked(self, item, column):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data:
            self.session_double_clicked.emit(data)

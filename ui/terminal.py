from PyQt6.QtWidgets import QPlainTextEdit, QTextEdit
from PyQt6.QtCore import pyqtSignal, QThread, Qt, QTimer
import sys
import pyte
from PyQt6.QtGui import QFont, QTextCursor, QColor

class SSHReaderThread(QThread):
    data_received = pyqtSignal(str)
    session_closed = pyqtSignal()

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.running = True

    def run(self):
        while self.running and self.session.running:
            data = self.session.read_output()
            if data:
                self.data_received.emit(data)
            else:
                # Check if session is still active
                if not self.session.is_active():
                    self.session_closed.emit()
                    break
                self.msleep(10)

    def stop(self):
        self.running = False

class TerminalScreen(pyte.HistoryScreen):
    def __init__(self, columns, lines, history=100, ratio=0.5):
        super().__init__(columns, lines, history, ratio)
        self.cleared_callback = None

    def erase_in_display(self, how=0, private=False):
        # how=2 is "clear entire screen"
        # how=0 is "clear from cursor to end of screen".
        # If cursor is at the top (x=0, y=0), how=0 effectively clears the whole screen.
        # SSH sessions often use ESC[H (Home) + ESC[J (Clear Down) instead of ESC[2J (Clear All).
        
        soft_clear = (how == 2) or (how == 0 and self.cursor.y == 0)

        if soft_clear:
            # Implement "Soft Clear": Push current screen lines to history
            # This preserves the content in the scrollback so the user can scroll up.
            
            for i in range(self.lines):
                line = self.display[i]
                # pyte history stores the line object.
                # In some cases (like empty lines optimization), line might be a string (or immutable).
                if isinstance(line, str):
                   self.history.top.append(line)
                else:
                   self.history.top.append(line.copy())
            
            if self.cleared_callback:
                self.cleared_callback()
        
        super().erase_in_display(how, private)

class Terminal(QPlainTextEdit):
    session_closed = pyqtSignal()
    
    def __init__(self, session, settings=None):
        super().__init__()
        self.session = session
        self.setReadOnly(False) # Allow scrolling and selection
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap) # Disable wrapping for correct cursor positioning
        self.setUndoRedoEnabled(False) # Disable undo/redo to prevent issues
        
        # Apply settings or use defaults
        if settings is None:
            settings = {
                "terminal": {
                    "font_family": "Consolas",
                    "font_size": 10,
                    "foreground_color": "#FFFFFF",
                    "background_color": "#000000"
                }
            }
        
        terminal_settings = settings.get("terminal", {})
        font_family = terminal_settings.get("font_family", "Consolas")
        font_size = terminal_settings.get("font_size", 10)
        fg_color = terminal_settings.get("foreground_color", "#FFFFFF")
        bg_color = terminal_settings.get("background_color", "#000000")
        
        # Apply styling with settings
        self.setStyleSheet(f"background-color: {bg_color}; color: {fg_color}; font-family: {font_family}, monospace; font-size: {font_size}pt;")
        
        # Ensure cursor color is correct via Palette
        from PyQt6.QtGui import QPalette, QColor
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(bg_color))
        palette.setColor(QPalette.ColorRole.Text, QColor(fg_color))
        self.setPalette(palette)
        
        # Start reader thread
        self.reader = SSHReaderThread(session)
        self.reader.data_received.connect(self.on_data_received)
        self.reader.session_closed.connect(self.session_closed.emit)
        self.reader.start()

        # Custom Blinking Cursor -- DISABLED
        # self.cursor_blink_timer = QTimer(self)
        # self.cursor_blink_timer.timeout.connect(self.toggle_cursor)
        # self.cursor_blink_timer.start(500) # Blink every 500ms
        self.cursor_visible = True
        
        # Set up context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)


        # Terminal Emulator with scrollback
        self.cols = 80
        self.rows = 24
        self.scrollback_lines = 10000  # Number of lines to keep in history
        # Use our custom screen to detect clears
        self.screen = TerminalScreen(self.cols, self.rows, history=self.scrollback_lines)
        self.screen.cleared_callback = self.on_screen_cleared
        self.stream = pyte.Stream(self.screen)
        
        # Initialize display with empty lines
        self.refresh_display()

    def on_screen_cleared(self):
        """Called when the screen is cleared (e.g. Ctrl+L)"""
        self.should_scroll_to_top = True

    # def toggle_cursor(self):
    #     self.cursor_visible = not self.cursor_visible
    #     self.draw_cursor()

    def draw_cursor(self):
        # Calculate where the cursor SHOULD be based on the screen buffer
        # This prevents the cursor from jumping when the user clicks elsewhere (changing textCursor)
        history_offset = len(self.screen.history.top)
        cursor_y = history_offset + self.screen.cursor.y
        cursor_x = self.screen.cursor.x
        
        # Create a cursor at the correct position
        cursor = self.textCursor() # Get a copy
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.movePosition(QTextCursor.MoveOperation.Down, n=cursor_y)
        cursor.movePosition(QTextCursor.MoveOperation.Right, n=cursor_x)
        
        # Create extra selection for the cursor
        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        
        # Determine cursor color
        if self.cursor_visible:
            selection.format.setBackground(QColor("white"))
            selection.format.setForeground(QColor("black"))
            # Try to select the character
            if selection.cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor):
                pass
        else:
            selection.format.clearBackground()
            
        self.setExtraSelections([selection])

    def on_data_received(self, text):
        self.stream.feed(text)
        self.refresh_display()

    def refresh_display(self):
        # Build the text from the screen buffer including history
        display_text = ""
        
        # Add history lines (lines that have scrolled off the top)
        for line_dict in self.screen.history.top:
            # Convert the line to a string by extracting characters
            line = "".join(char.data for char in line_dict.values())
            # Pad line to full width
            if len(line) < self.cols:
                line += " " * (self.cols - len(line))
            display_text += line + "\n"
        
        # Add current screen lines
        for i in range(self.rows):
            line = self.screen.display[i]
            # Pad line to full width to ensure cursor positioning works correctly
            if len(line) < self.cols:
                line += " " * (self.cols - len(line))
            display_text += line + "\n"
        
    def refresh_display(self):
        # Build the text from the screen buffer including history
        display_text = ""
        
        # Add history lines (lines that have scrolled off the top)
        for line_obj in self.screen.history.top:
            if isinstance(line_obj, str):
                 line = line_obj
            else:
                 # It's a defaultdict/dict from pyte
                 line = "".join(char.data for char in line_obj.values())
            
            # Pad line to full width
            if len(line) < self.cols:
                line += " " * (self.cols - len(line))
            display_text += line + "\n"
        
        # Add current screen lines
        for i in range(self.rows):
            line_obj = self.screen.display[i]
            if isinstance(line_obj, str):
                 line = line_obj
            else:
                 line = "".join(char.data for char in line_obj.values())
                 
            # Pad line to full width
            if len(line) < self.cols:
                line += " " * (self.cols - len(line))
            display_text += line + "\n"
        
        # Update the text edit
        # Capture current scroll position to restore it after setPlainText (which resets it)
        vbar = self.verticalScrollBar()
        current_scroll = vbar.value()
        
        self.setPlainText(display_text)
        
        # Restore scroll position
        vbar.setValue(current_scroll)
        
        # Draw the visual block cursor
        self.draw_cursor()
        
        # Calculate cursor line index
        history_lines = len(self.screen.history.top)
        cursor_line_idx = history_lines + self.screen.cursor.y
        
        # Handle scroll-to-top if screen was just cleared (Ctrl+L)
        if hasattr(self, 'should_scroll_to_top') and self.should_scroll_to_top:
            self.should_scroll_to_top = False
            
            # For QPlainTextEdit with NoWrap, the vertical scrollbar usually tracks lines (or blocks).
            # We want the first line of the new screen (which is at index `history_lines`) to be at the top.
            
            vbar.setValue(history_lines)
            return

        # Improved Auto-scroll: Ensure the TERMINAL CURSOR is visible
        # We calculate where the terminal cursor is, and ensure that line is in view.
        # We use a temporary cursor to avoid messing with selection if possible (though setPlainText clears it anyway for now)
        
        block = self.document().findBlockByNumber(cursor_line_idx)
        if block.isValid():
             # We want to scroll ONLY if the cursor is out of view?
             # Or always ensure it's in view? Standard terminal follows cursor.
             
             # Only scroll if we are not looking at history? 
             # For now, let's fundamentally ensure the line is visible, but if we just restored the scroll and it's visible, do nothing.
             
             t_cursor = self.textCursor()
             t_cursor.setPosition(block.position())
             self.setTextCursor(t_cursor)
             self.ensureCursorVisible()

    def resizeEvent(self, event):
        # Update terminal size on resize
        # Calculate rows and cols based on font size
        font_metrics = self.fontMetrics()
        char_width = font_metrics.horizontalAdvance('M')
        char_height = font_metrics.height()
        
        self.cols = max(1, event.size().width() // char_width)
        self.rows = max(1, event.size().height() // char_height)
        
        self.screen.resize(lines=self.rows, columns=self.cols)
        self.setCursorWidth(char_width) # Make cursor a block
        
        # Notify session about resize (for PTY support)
        if hasattr(self.session, 'resize'):
            self.session.resize(self.rows, self.cols)
        
        self.refresh_display()
        
        super().resizeEvent(event)

    def closeEvent(self, event):
        # Stop the cursor blink timer when terminal is closed
        # if hasattr(self, 'cursor_blink_timer'):
        #     self.cursor_blink_timer.stop()
        if hasattr(self, 'reader'):
            self.reader.stop()
        super().closeEvent(event)

    def event(self, event):
        # Intercept Tab key before Qt's focus system handles it
        if event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Tab or event.key() == Qt.Key.Key_Backtab:
                # Handle Tab in keyPressEvent instead of letting Qt use it for focus
                self.keyPressEvent(event)
                return True
        return super().event(event)

    def keyPressEvent(self, event):
        text = event.text()
        key = event.key()
        modifiers = event.modifiers()

        # Handle paste shortcuts (Ctrl+V or Shift+Insert)
        if (modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_V) or \
           (modifiers == Qt.KeyboardModifier.ShiftModifier and key == Qt.Key.Key_Insert):
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            paste_text = clipboard.text()
            if paste_text:
                self.session.send_command(paste_text)
            event.accept()
            return

        # Handle Ctrl+L for Clear Screen
        if modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_L:
            self.session.send_command('\x0c')  # Send Form Feed (Ctrl+L)
            event.accept()
            return
        
        # Handle special keys that don't have text or need specific codes
        if key == Qt.Key.Key_Up:
            self.session.send_command('\x1b[A')
        elif key == Qt.Key.Key_Down:
            self.session.send_command('\x1b[B')
        elif key == Qt.Key.Key_Right:
            self.session.send_command('\x1b[C')
        elif key == Qt.Key.Key_Left:
            self.session.send_command('\x1b[D')
        elif key == Qt.Key.Key_Home:
            self.session.send_command('\x1b[H')
        elif key == Qt.Key.Key_End:
            self.session.send_command('\x1b[F')
        elif key == Qt.Key.Key_Tab or key == Qt.Key.Key_Backtab:
            # Send tab character for command completion
            self.session.send_command('\t')
        elif text:
            # For normal characters (including Enter=\r, Backspace=\x08), just send the text
            self.session.send_command(text)
        
        # Prevent default behavior (inserting text into the widget)
        event.accept()
    
    def show_context_menu(self, position):
        """Show context menu on right-click"""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction
        
        menu = QMenu(self)
        
        # Copy action
        copy_action = QAction("Copy", self)
        copy_action.triggered.connect(self.copy)
        copy_action.setEnabled(self.textCursor().hasSelection())
        menu.addAction(copy_action)
        
        # Paste action
        paste_action = QAction("Paste", self)
        paste_action.triggered.connect(self.paste_from_clipboard)
        menu.addAction(paste_action)
        
        menu.addSeparator()
        
        # Select All action
        select_all_action = QAction("Select All", self)
        select_all_action.triggered.connect(self.selectAll)
        menu.addAction(select_all_action)
        
        # Show menu at cursor position
        menu.exec(self.mapToGlobal(position))
    
    def paste_from_clipboard(self):
        """Paste text from clipboard to terminal"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        paste_text = clipboard.text()
        if paste_text:
            self.session.send_command(paste_text)

from PyQt6.QtWidgets import QPlainTextEdit, QTextEdit
from PyQt6.QtCore import pyqtSignal, QThread, Qt, QTimer
import sys
import pyte
from PyQt6.QtGui import QFont, QTextCursor, QColor

class SSHReaderThread(QThread):
    """Optimized SSH reader thread with signal batching and reduced latency"""
    data_received = pyqtSignal(str)
    session_closed = pyqtSignal()

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.running = True
        # Performance: Batch small reads together
        self.batch_buffer = []
        self.batch_threshold = 5  # Batch up to 5 small reads

    def run(self):
        """Main thread loop - optimized for low latency"""
        # Set higher thread priority for better responsiveness
        self.setPriority(QThread.Priority.HighPriority)
        
        while self.running and self.session.running:
            data = self.session.read_output()
            if data:
                # Emit data immediately for large chunks, batch for small ones
                if len(data) > 1024 or not self.batch_buffer:
                    # Emit any pending batched data first
                    if self.batch_buffer:
                        self.data_received.emit(''.join(self.batch_buffer))
                        self.batch_buffer = []
                    # Emit current data
                    self.data_received.emit(data)
                else:
                    # Batch small chunks to reduce signal overhead
                    self.batch_buffer.append(data)
                    if len(self.batch_buffer) >= self.batch_threshold:
                        self.data_received.emit(''.join(self.batch_buffer))
                        self.batch_buffer = []
            else:
                # Emit any pending batched data before checking session
                if self.batch_buffer:
                    self.data_received.emit(''.join(self.batch_buffer))
                    self.batch_buffer = []
                
                # Check if session is still active
                if not self.session.is_active():
                    self.session_closed.emit()
                    break
                # Reduced sleep from 10ms to 5ms for better responsiveness
                self.msleep(5)

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
        
        # Terminal Emulator with scrollback
        self.cols = 80
        self.rows = 24
        self.scrollback_lines = 10000  # Number of lines to keep in history
        
        # Performance: Cache font metrics to avoid repeated calculations
        self._cached_char_width = None
        self._cached_char_height = None
        
        # Performance: Track last rendered state for incremental updates
        self._last_history_len = 0
        self._last_display_hash = None
        
        # Use our custom screen to detect clears
        self.screen = TerminalScreen(self.cols, self.rows, history=self.scrollback_lines)
        self.screen.cleared_callback = self.on_screen_cleared
        self.stream = pyte.Stream(self.screen)
        
        # Performance optimization: Batch updates to prevent excessive redraws
        self.pending_updates = False
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._do_refresh)
        self.refresh_timer.setInterval(16)  # ~60 FPS (1000ms / 60 ≈ 16ms)
        
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
        """Process incoming data and schedule a display update"""
        self.stream.feed(text)
        
        # Mark that we have pending updates
        if not self.pending_updates:
            self.pending_updates = True
            # Start the timer if not already running
            if not self.refresh_timer.isActive():
                self.refresh_timer.start()
    
    def _do_refresh(self):
        """Actually perform the display refresh (called by timer)"""
        if self.pending_updates:
            self.pending_updates = False
            self.refresh_display()

    def refresh_display(self):
        """Ultra-optimized incremental display refresh - only updates what changed"""
        # Cache commonly used values
        cols = self.cols
        rows = self.rows
        
        # Get current state
        history = self.screen.history.top
        history_len = len(history)
        
        # Check if we need a full rebuild (screen cleared, resized, or first run)
        need_full_rebuild = (
            self._last_history_len is None or
            self._last_history_len > history_len or  # History was cleared
            hasattr(self, 'should_scroll_to_top') and self.should_scroll_to_top
        )
        
        if need_full_rebuild:
            # Full rebuild using the old method (rare)
            lines = []
            
            # Process history lines (scrollback)
            for line_obj in history:
                if isinstance(line_obj, str):
                    line = line_obj
                else:
                    line = ''.join(char.data for char in line_obj.values())
                
                if len(line) < cols:
                    line += ' ' * (cols - len(line))
                lines.append(line)
            
            # Process current screen lines
            for i in range(rows):
                line_obj = self.screen.display[i]
                if isinstance(line_obj, str):
                    line = line_obj
                else:
                    line = ''.join(char.data for char in line_obj.values())
                
                if len(line) < cols:
                    line += ' ' * (cols - len(line))
                lines.append(line)
            
            # Single join operation
            display_text = '\n'.join(lines) + '\n'
            
            # Full rebuild
            vbar = self.verticalScrollBar()
            current_scroll = vbar.value()
            self.setPlainText(display_text)
            
            if hasattr(self, 'should_scroll_to_top') and self.should_scroll_to_top:
                self.should_scroll_to_top = False
                vbar.setValue(history_len)
            else:
                vbar.setValue(current_scroll)
            
            self._last_history_len = history_len
            
        else:
            # INCREMENTAL UPDATE - Only append new history lines and update current view
            # This is 10-100x faster than full rebuild!
            
            # How many new history lines since last update?
            new_history_lines = history_len - self._last_history_len
            
            if new_history_lines > 0:
                # Append new history lines using QTextCursor (very fast)
                cursor = QTextCursor(self.document())
                cursor.beginEditBlock()  # Batch the changes
                
                # Move to the position where history ends and current screen starts
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                cursor.movePosition(QTextCursor.MoveOperation.Down, n=self._last_history_len)
                
                # Insert new history lines BEFORE the current screen
                for i in range(history_len - new_history_lines, history_len):
                    line_obj = history[i]
                    if isinstance(line_obj, str):
                        line = line_obj
                    else:
                        line = ''.join(char.data for char in line_obj.values())
                    
                    if len(line) < cols:
                        line += ' ' * (cols - len(line))
                    
                    cursor.insertText(line + '\n')
                
                cursor.endEditBlock()
                self._last_history_len = history_len
            
            # Always update the current visible screen (last 'rows' lines)
            # This is necessary because content changes even if history doesn't grow
            cursor = QTextCursor(self.document())
            cursor.beginEditBlock()
            
            # Move to where current screen starts (after all history)
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(QTextCursor.MoveOperation.Down, n=history_len)
            
            # Select and replace the current screen content
            cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.KeepAnchor, n=rows)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            
            # Build current screen text
            screen_lines = []
            for i in range(rows):
                line_obj = self.screen.display[i]
                if isinstance(line_obj, str):
                    line = line_obj
                else:
                    line = ''.join(char.data for char in line_obj.values())
                
                if len(line) < cols:
                    line += ' ' * (cols - len(line))
                screen_lines.append(line)
            
            # Replace current screen content
            cursor.insertText('\n'.join(screen_lines) + '\n')
            cursor.endEditBlock()
        
        # Draw the visual block cursor
        self.draw_cursor()
        
        # Auto-scroll to follow cursor
        history_lines = len(self.screen.history.top)
        cursor_line_idx = history_lines + self.screen.cursor.y
        
        block = self.document().findBlockByNumber(cursor_line_idx)
        if block.isValid():
            t_cursor = self.textCursor()
            t_cursor.setPosition(block.position())
            self.setTextCursor(t_cursor)
            self.ensureCursorVisible()





    def resizeEvent(self, event):
        """Update terminal size on resize - optimized with cached metrics"""
        # Cache font metrics to avoid repeated expensive calls
        if self._cached_char_width is None or self._cached_char_height is None:
            font_metrics = self.fontMetrics()
            self._cached_char_width = font_metrics.horizontalAdvance('M')
            self._cached_char_height = font_metrics.height()
        
        char_width = self._cached_char_width
        char_height = self._cached_char_height
        
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
        # Stop timers when terminal is closed
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
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
        elif key == Qt.Key.Key_Backspace:
            # Send DEL character for backspace (standard for most SSH sessions)
            self.session.send_command('\x7f')
        elif key == Qt.Key.Key_Delete:
            # Send VT100 delete sequence
            self.session.send_command('\x1b[3~')
        elif text:
            # For normal characters (including Enter=\r), just send the text
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

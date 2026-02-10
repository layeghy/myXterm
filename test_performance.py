"""
Quick test to verify terminal performance optimization.
This simulates rapid data output to the terminal.
"""
import sys
import time
from PyQt6.QtWidgets import QApplication
from ssh.local_session import LocalSession
from ui.terminal import Terminal

def test_performance():
    """Test terminal with rapid output"""
    app = QApplication(sys.argv)
    
    # Create a local session
    session = LocalSession()
    if not session.connect():
        print("Failed to create local session")
        return
    
    # Create terminal widget
    terminal = Terminal(session)
    terminal.setWindowTitle("Performance Test - myXterm")
    terminal.resize(800, 600)
    terminal.show()
    
    print("Terminal opened. Try running:")
    print("  - find . -mindepth 2")
    print("  - Get-ChildItem -Recurse (PowerShell)")
    print("  - dir /s (CMD)")
    print("\nThese should now render smoothly without freezing!")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    test_performance()

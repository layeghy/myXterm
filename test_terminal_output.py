"""
Test script to capture terminal output and see what's being rendered
"""
import sys
import time
from ssh.local_session import LocalSession

# Create a local session
session = LocalSession()
print("Connecting to local terminal...")
if session.connect():
    print(f"Connected! Using PTY: {session.use_pty}")
    
    # Read initial output - wait longer for shell to fully initialize
    print("Waiting for shell to initialize...")
    time.sleep(5)
    output = session.read_output()
    
    print(f"\n=== INITIAL OUTPUT (length: {len(output)}) ===")
    print(repr(output[:1000]))  # Show first 1000 chars as repr to see escape codes
    print("\n=== RAW OUTPUT ===")
    print(output[:1000])
    
    # Send a simple command
    print("\n\nSending 'dir' command...")
    session.send_command("dir\r\n")
    time.sleep(2)
    output = session.read_output()
    
    print(f"\n=== AFTER DIR COMMAND (length: {len(output)}) ===")
    print(repr(output[:1000]))
    print("\n=== RAW OUTPUT ===")
    print(output[:1000])
    
    session.close()
else:
    print("Failed to connect!")

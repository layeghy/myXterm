import threading
import queue
import os
import sys

class LocalSession:
    """Local terminal session using Windows ConPTY or fallback"""
    def __init__(self, shell="powershell.exe"):
        self.shell = shell
        self.process = None
        self.running = False
        self.output_queue = queue.Queue()
        self.use_pty = False
        
    def connect(self):
        """Start the local shell process"""
        try:
            # Try to use winpty for proper PTY support on Windows
            if os.name == 'nt':
                try:
                    import winpty
                    self.use_pty = True
                    return self._connect_pty()
                except ImportError as e:
                    with open("session_debug.log", "a") as f:
                        f.write(f"ImportError for winpty: {e}. using fallback mode\n")
                    print("winpty not available, using fallback mode")
                    return self._connect_fallback()
            else:
                # On Unix-like systems, use pty module
                import pty
                self.use_pty = True
                return self._connect_unix_pty()
        except Exception as e:
            with open("session_debug.log", "a") as f:
                f.write(f"Failed to start local terminal: {e}\n")
            print(f"Failed to start local terminal: {e}")
            return False
    
    def _connect_pty(self):
        """Connect using winpty for proper Windows PTY support"""
        try:
            # In frozen app, we may need to ensure binaries are in the PATH
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
                winpty_bin_path = os.path.join(base_path, 'winpty')
                
                # Add both MEIPASS and winpty subfolder to PATH
                new_paths = [base_path, winpty_bin_path]
                for p in new_paths:
                    if os.path.exists(p) and p not in os.environ['PATH']:
                        os.environ['PATH'] = p + os.pathsep + os.environ['PATH']
                
                with open("session_debug.log", "a") as f:
                    f.write(f"Frozen mode. MEIPASS: {base_path}\n")
                    f.write(f"winpty path: {winpty_bin_path}\n")
                    # Check in root AND winpty subfolder
                    f.write(f"winpty.dll (root) Exists: {os.path.exists(os.path.join(base_path, 'winpty.dll'))}\n")
                    f.write(f"winpty.dll (bin) Exists: {os.path.exists(os.path.join(winpty_bin_path, 'winpty.dll'))}\n")
                    f.write(f"winpty-agent.exe (root) Exists: {os.path.exists(os.path.join(base_path, 'winpty-agent.exe'))}\n")
                    f.write(f"winpty-agent.exe (bin) Exists: {os.path.exists(os.path.join(winpty_bin_path, 'winpty-agent.exe'))}\n")

            # Import winpty AFTER setting up the environment
            import winpty
            with open("session_debug.log", "a") as f:
                f.write("Successfully imported winpty\n")
        except ImportError as e:
            with open("session_debug.log", "a") as f:
                f.write(f"Failed to import winpty: {e}\n")
            raise

        # Create PTY process with proper configuration
        try:
            # Create PTY with VT100 support enabled
            self.process = winpty.PTY(80, 24)  # cols, rows
            
            # For PowerShell, we need to force VT100 mode
            # We'll modify the shell command to set the environment and enable VT processing
            if "powershell" in self.shell.lower():
                # PowerShell command that enables VT100 processing
                # $Host.UI.RawUI is used to enable VT100 escape sequences
                shell_cmd = f'{self.shell} -NoLogo -Command "$Host.UI.RawUI.ForegroundColor = \'White\'; $Host.UI.RawUI.BackgroundColor = \'Black\'; [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $env:TERM = \'xterm-256color\'; powershell -NoExit"'
            else:
                shell_cmd = self.shell
            
            self.process.spawn(shell_cmd)
            self.running = True
            with open("session_debug.log", "a") as f:
                f.write(f"Successfully spawned PTY process with command: {shell_cmd}\n")
        except Exception as spawn_err:
             with open("session_debug.log", "a") as f:
                f.write(f"Failed to spawn PTY: {spawn_err}\n")
             raise
        
        # Start output reader thread
        threading.Thread(target=self._read_pty_output, daemon=True).start()
        return True
    
    def _connect_unix_pty(self):
        """Connect using Unix PTY"""
        import pty
        import select
        import subprocess
        
        master, slave = pty.openpty()
        self.process = subprocess.Popen(
            [self.shell],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            preexec_fn=os.setsid
        )
        os.close(slave)
        self.master_fd = master
        self.running = True
        
        threading.Thread(target=self._read_unix_pty_output, daemon=True).start()
        return True
    
    def _connect_fallback(self):
        """Fallback to basic subprocess (limited functionality)"""
        import subprocess
        
        self.process = subprocess.Popen(
            [self.shell],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        self.running = True
        
        # Start output reader thread
        threading.Thread(target=self._read_fallback_output, daemon=True).start()
        return True
    
    def _read_pty_output(self):
        """Read output from winpty PTY"""
        while self.running and self.process:
            try:
                # winpty 3.0+ expects blocking parameter (bool) not buffer size
                data = self.process.read(blocking=False)
                if data:
                    self.output_queue.put(data)
                else:
                    # No data available, sleep briefly to avoid busy loop
                    import time
                    time.sleep(0.01)
            except Exception as e:
                if self.running:
                    print(f"Error reading PTY output: {e}")
                break
    
    def _read_unix_pty_output(self):
        """Read output from Unix PTY"""
        import select
        
        while self.running:
            try:
                r, _, _ = select.select([self.master_fd], [], [], 0.1)
                if r:
                    data = os.read(self.master_fd, 1024)
                    if data:
                        self.output_queue.put(data.decode('utf-8', errors='replace'))
                    else:
                        break
            except Exception as e:
                if self.running:
                    print(f"Error reading PTY output: {e}")
                break
    
    def _read_fallback_output(self):
        """Read output from subprocess (fallback)"""
        while self.running and self.process:
            try:
                char = self.process.stdout.read(1)
                if char:
                    self.output_queue.put(char.decode('utf-8', errors='replace'))
                else:
                    break
            except Exception as e:
                if self.running:
                    print(f"Error reading output: {e}")
                break
    
    def read_output(self):
        """Read available output"""
        output = ""
        try:
            while not self.output_queue.empty():
                output += self.output_queue.get_nowait()
        except queue.Empty:
            pass
        return output
    
    def send_command(self, command):
        """Send command to the shell"""
        try:
            if self.use_pty and hasattr(self.process, 'write'):
                # winpty PTY
                self.process.write(command)
            elif hasattr(self, 'master_fd'):
                # Unix PTY
                os.write(self.master_fd, command.encode('utf-8'))
            elif self.process and self.process.stdin:
                # Fallback subprocess
                self.process.stdin.write(command.encode('utf-8'))
                self.process.stdin.flush()
        except Exception as e:
            print(f"Error sending command: {e}")
    
    def is_active(self):
        """Check if the session is still active"""
        if self.use_pty and hasattr(self.process, 'isalive'):
            return self.running and self.process.isalive()
        elif hasattr(self, 'master_fd'):
            # For Unix PTY, check if the underlying process is still running
            return self.running and self.process.poll() is None
        else:
            return self.running and self.process and self.process.poll() is None
    
    def resize(self, rows, cols):
        """Resize the terminal"""
        try:
            if self.use_pty and hasattr(self.process, 'set_size'):
                self.process.set_size(cols, rows)
        except Exception as e:
            print(f"Error resizing terminal: {e}")
    
    def close(self):
        """Close the session"""
        self.running = False
        if self.process:
            try:
                if self.use_pty:
                    # winpty PTY doesn't have close(), just set running=False
                    # The process will be cleaned up when PTY is garbage collected
                    pass
                else:
                    self.process.terminate()
                    self.process.wait(timeout=2)
            except:
                if hasattr(self.process, 'kill'):
                    self.process.kill()
        if hasattr(self, 'master_fd'):
            try:
                os.close(self.master_fd)
            except:
                pass

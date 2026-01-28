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
                
                # Add base_path to PATH if not already there
                if base_path not in os.environ['PATH']:
                     os.environ['PATH'] = base_path + os.pathsep + os.environ['PATH']
                
                # On Python 3.8+, we often need to explicitly add DLL directories
                if hasattr(os, 'add_dll_directory'):
                    try:
                        os.add_dll_directory(base_path)
                        # Also add a winpty subfolder if it exists
                        if os.path.exists(os.path.join(base_path, 'winpty')):
                            os.add_dll_directory(os.path.join(base_path, 'winpty'))
                    except Exception as e:
                        with open("session_debug.log", "a") as f:
                            f.write(f"Failed to add DLL directory: {e}\n")

                with open("session_debug.log", "a") as f:
                    f.write(f"Frozen mode. MEIPASS: {base_path}\n")
                    f.write(f"winpty-agent.exe Exists: {os.path.exists(os.path.join(base_path, 'winpty-agent.exe'))}\n")
                    f.write(f"OpenConsole.exe Exists: {os.path.exists(os.path.join(base_path, 'OpenConsole.exe'))}\n")
                    f.write(f"conpty.dll Exists: {os.path.exists(os.path.join(base_path, 'conpty.dll'))}\n")
                    f.write(f"PATH: {os.environ['PATH']}\n")

            # Import winpty AFTER setting up the environment
            import winpty
            with open("session_debug.log", "a") as f:
                f.write(f"Successfully imported winpty from: {winpty.__file__ if hasattr(winpty, '__file__') else 'unknown'}\n")
        except ImportError as e:
            with open("session_debug.log", "a") as f:
                f.write(f"Failed to import winpty: {e}\n")
            raise

        # Create PTY process with proper configuration
        try:
            # Create PTY with VT100 support enabled
            self.process = winpty.PTY(80, 24)  # cols, rows
            
            # Use absolute path for shell if possible
            import shutil
            primary_shell = shutil.which(self.shell) or self.shell
            
            # Fallback shells to try if primary fails
            shells_to_try = [primary_shell]
            if "powershell" in primary_shell.lower():
                shells_to_try.append("cmd.exe")
            
            success = False
            for shell_cmd in shells_to_try:
                try:
                    with open("session_debug.log", "a") as f:
                        f.write(f"Attempting to spawn PTY with: {shell_cmd}\n")
                    
                    self.process.spawn(shell_cmd)
                    
                    # Check if it STAYS alive
                    import time
                    time.sleep(0.5)
                    
                    if self.process.isalive():
                        with open("session_debug.log", "a") as f:
                            f.write(f"Successfully spawned and confirmed alive: {shell_cmd}\n")
                        success = True
                        break
                    else:
                        exit_code = "unknown"
                        try:
                            exit_code = self.process.get_exitstatus()
                        except: pass
                        with open("session_debug.log", "a") as f:
                            f.write(f"Shell {shell_cmd} exited immediately with code: {exit_code}\n")
                        # If it failed, we'll try the next shell in the list
                except Exception as spawn_err:
                    with open("session_debug.log", "a") as f:
                        f.write(f"Exception spawning {shell_cmd}: {spawn_err}\n")
                    # Try next shell
            
            if not success:
                raise RuntimeError("All shell spawn attempts failed or exited immediately.")

            self.running = True
        except Exception as err:
             with open("session_debug.log", "a") as f:
                f.write(f"Setup error in _connect_pty: {err}\n")
             raise
        except BaseException as be:
             # Catch low-level panics or other base exceptions
             with open("session_debug.log", "a") as f:
                f.write(f"CRITICAL: Caught BaseException during PTY setup: {be}\n")
                if "Panic" in str(be):
                    f.write("A low-level Panic occurred. This usually means winpty binaries are mismatched or missing.\n")
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
            if self.use_pty and self.process and hasattr(self.process, 'set_size'):
                # Handle cases where process might have died
                try:
                    self.process.set_size(cols, rows)
                except Exception as inner_e:
                    # Ignore "handle is invalid" if process is dying
                    if "handle is invalid" not in str(inner_e).lower():
                        print(f"Error calling set_size: {inner_e}")
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

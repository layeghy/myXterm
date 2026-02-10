import paramiko
import threading
import time

class SSHSession:
    def __init__(self, host, port, username, password=None, key_filename=None, proxy_settings=None, proxy_jump_settings=None, auth_callback=None, password_callback=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.proxy_settings = proxy_settings
        self.proxy_jump_settings = proxy_jump_settings
        self.auth_callback = auth_callback
        self.password_callback = password_callback
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.shell = None
        self.running = False
        self.jump_client = None # Keep reference to jump client
        self.jump_transport = None
        
        # Performance optimizations
        self.buffer_size = 8192  # Start with 8KB
        self.max_buffer_size = 32768  # Can grow to 32KB
        self.reads_since_last_check = 0
        self.enable_compression = True  # SSH compression for slow links


    def _smart_interactive_callback(self, title, instructions, prompt_list, username, password):
        """
        Callback wrapper that automatically satisfies the first 'Password' prompt 
        using stored credentials, otherwise falls back to the UI callback.
        """
        print(f"DEBUG: Smart interactive callback for {username} - Prompts: {[p[0] for p in prompt_list]}")
        
        # If we have a password and this looks like a password prompt, try to use it
        responses = []
        for prompt, echo in prompt_list:
            p_lower = prompt.lower()
            if password and ("password" in p_lower or "passcode" in p_lower) and not getattr(self, '_sent_initial_password', False):
                print(f"DEBUG: Auto-injecting stored password for prompt: {prompt}")
                responses.append(password)
                self._sent_initial_password = True
            elif self.auth_callback:
                # Fallback to UI
                print(f"DEBUG: Falling back to UI for prompt: {prompt}")
                ui_responses = self.auth_callback(title, instructions, [(prompt, echo)])
                if ui_responses:
                    responses.append(ui_responses[0])
                else:
                    responses.append("")
            else:
                responses.append("")
        return responses

    def _authenticate(self, transport, username, password):
        """Helper to handle authentication (Smart Interactive -> Password fallback)"""
        try:
            if not transport.is_active():
                print(f"Auth Error: Transport for {username} is not active")
                return False

            self._sent_initial_password = False
            
            # 1. Try Smart Interactive first (MFA)
            print(f"Authenticating {username} (interactive/MFA)...")
            try:
                # We use a lambda to pass our stateful wrapper
                callback = lambda t, i, p: self._smart_interactive_callback(t, i, p, username, password)
                transport.auth_interactive(username, callback)
                if transport.is_authenticated():
                    print(f"Auth Success: Interactive auth for {username}")
                    return True
            except paramiko.auth_handler.AuthenticationException as e:
                if "partial" in str(e).lower():
                     print(f"Auth Partial: Further factors required for {username}")
                else:
                     print(f"Auth Failed: Interactive auth for {username}: {e}")
            except Exception as e:
                print(f"Auth Error: Interactive auth for {username}: {e}")

            # 2. Try standard password auth fallback
            if not transport.is_authenticated():
                current_password = password
                attempts = 0
                while attempts < 2:
                    if current_password:
                        print(f"Authenticating {username} (password fallback, attempt {attempts+1})...")
                        try:
                            transport.auth_password(username, current_password)
                            if transport.is_authenticated():
                                print(f"Auth Success: Password auth for {username}")
                                if username == self.username:
                                    self.password = current_password
                                return True
                        except paramiko.auth_handler.AuthenticationException:
                            print(f"Auth Failed: Password auth for {username}")
                        except Exception as e:
                            print(f"Auth Error: Password auth for {username}: {e}")
                    
                    if self.password_callback and not transport.is_authenticated():
                        new_pass = self.password_callback(f"Authentication failed for {username}@{self.host}. Please enter a new password:")
                        if new_pass:
                            current_password = new_pass
                            attempts += 1
                        else:
                            break
                    else:
                        break
            
            return transport.is_authenticated()
        except Exception as e:
            print(f"Critical Auth Error for {username}: {e}")
            return False

    def connect(self):
        try:
            sock = None
            
            # Handle Proxy Jump
            if self.proxy_jump_settings and self.proxy_jump_settings.get("enabled"):
                jump_host = self.proxy_jump_settings.get("host")
                jump_port = self.proxy_jump_settings.get("port", 22)
                jump_user = self.proxy_jump_settings.get("username")
                jump_pass = self.proxy_jump_settings.get("password")
                
                print(f"Connecting to jump host: {jump_user}@{jump_host}:{jump_port}")
                
                self.jump_transport = paramiko.Transport((jump_host, jump_port))
                self.jump_transport.start_client()
                
                if not self._authenticate(self.jump_transport, jump_user, jump_pass):
                    raise Exception(f"Jump host authentication failed for {jump_user}@{jump_host}")

                # Create a channel to the target
                print(f"Opening channel to target: {self.host}:{self.port}")
                sock = self.jump_transport.open_channel(
                    "direct-tcpip", 
                    (self.host, self.port), 
                    ("127.0.0.1", 0) 
                )

            # Main Connection
            # Try high-level connect first. 
            print(f"Connecting to target host: {self.username}@{self.host}:{self.port}")
            try:
                self.client.connect(
                    self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    key_filename=self.key_filename,
                    sock=sock,
                    allow_agent=True,
                    look_for_keys=True,
                    timeout=15,
                    compress=self.enable_compression  # Enable compression for better throughput
                )
                
                # Get the transport and enable TCP keepalive for better connection stability
                transport = self.client.get_transport()
                if transport:
                    transport.set_keepalive(60)  # Send keepalive every 60 seconds
                    # Request larger TCP window for better throughput
                    transport.window_size = 2097152  # 2MB window
                    transport.packetizer.REKEY_BYTES = pow(2, 40)  # Avoid frequent rekeying
                
                self.shell = self.client.invoke_shell()
                print(f"DEBUG: High-level connect successful for {self.host}")
            except (paramiko.AuthenticationException, paramiko.SSHException) as e:
                print(f"DEBUG: High-level connect failed or needs MFA: {e}. Trying robust manual fallback...")
                
                # IMPORTANT: If connect failed, the previous socket/channel is often corrupted/closed.
                # We should close it and open a NEW one if we're using a jump host.
                if sock:
                    try: sock.close()
                    except: pass
                    print("DEBUG: Opening NEW channel to target via jump host for MFA fallback...")
                    sock = self.jump_transport.open_channel("direct-tcpip", (self.host, self.port), ("127.0.0.1", 0))
                
                # Create a fresh transport
                if sock:
                    transport = paramiko.Transport(sock)
                else:
                    transport = paramiko.Transport((self.host, self.port))
                
                transport.start_client()
                
                if not self._authenticate(transport, self.username, self.password):
                    transport.close()
                    raise Exception(f"Target host authentication failed for {self.username}@{self.host}")
                
                # Success! Manual session setup.
                self.shell = transport.open_session()
                self.shell.get_pty()
                self.shell.invoke_shell()
                print(f"DEBUG: Manual transport auth successful for {self.host}")

            self.running = True
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            if self.jump_transport:
                self.jump_transport.close()
                self.jump_transport = None
            return False

    def send_command(self, command):
        if self.shell:
            self.shell.send(command)

    def read_output(self):
        """Read output with adaptive buffer sizing for optimal performance"""
        if self.shell and self.shell.recv_ready():
            # Adaptive buffer sizing: grow buffer if we're consistently reading full buffers
            self.reads_since_last_check += 1
            
            # Every 10 reads, check if we should increase buffer size
            if self.reads_since_last_check >= 10 and self.buffer_size < self.max_buffer_size:
                # Increase buffer size for high-throughput connections
                self.buffer_size = min(self.buffer_size * 2, self.max_buffer_size)
                self.reads_since_last_check = 0
                print(f"DEBUG: Increased buffer size to {self.buffer_size} bytes")
            
            try:
                data = self.shell.recv(self.buffer_size)
                return data.decode('utf-8', errors='replace')  # Replace invalid UTF-8 instead of crashing
            except UnicodeDecodeError:
                # Fallback for encoding issues
                return data.decode('latin-1')
        return None


    def is_active(self):
        # Check if the shell channel is still open
        if self.shell:
            return not self.shell.closed
        return False

    def close(self):
        self.running = False
        print("DEBUG: Closing SSH session...")
        try:
            if self.shell:
                self.shell.close()
            if self.client:
                self.client.close()
            if self.jump_transport:
                self.jump_transport.close()
                self.jump_transport = None
            if self.jump_client:
                self.jump_client.close()
                self.jump_client = None
        except Exception as e:
            print(f"DEBUG: Error during close: {e}")

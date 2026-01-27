import paramiko
import threading
import time

class SSHSession:
    def __init__(self, host, port, username, password=None, key_filename=None, proxy_settings=None, proxy_jump_settings=None, auth_callback=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.proxy_settings = proxy_settings
        self.proxy_jump_settings = proxy_jump_settings
        self.auth_callback = auth_callback
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.shell = None
        self.running = False
        self.jump_client = None # Keep reference to jump client
        self.jump_transport = None

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
                
                # Use Transport directly for granular auth control (MFA)
                self.jump_transport = paramiko.Transport((jump_host, jump_port))
                self.jump_transport.start_client()
                
                authenticated = False
                try:
                    # Try password first
                    self.jump_transport.auth_password(username=jump_user, password=jump_pass)
                    authenticated = True
                except paramiko.AuthenticationException:
                    # Fallback to interactive/MFA if password fails or is partial
                    if self.auth_callback:
                        print("Password auth failed/partial, trying interactive (MFA)...")
                        try:
                            self.jump_transport.auth_interactive(username=jump_user, handler=self.auth_callback)
                            authenticated = True
                        except Exception as e:
                            print(f"Interactive auth failed: {e}")
                
                if not authenticated:
                    raise Exception("Jump host authentication failed")

                # Create a channel to the target
                print(f"Opening channel to target: {self.host}:{self.port}")
                sock = self.jump_transport.open_channel(
                    "direct-tcpip", 
                    (self.host, self.port), 
                    ("127.0.0.1", 0) 
                )

            self.client.connect(
                self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                key_filename=self.key_filename,
                sock=sock # Pass the channel as the socket
            )
            self.shell = self.client.invoke_shell()
            self.running = True
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            # Clean up jump transport if main connection failed
            if self.jump_transport:
                self.jump_transport.close()
                self.jump_transport = None
            return False

    def send_command(self, command):
        if self.shell:
            self.shell.send(command)

    def read_output(self):
        if self.shell and self.shell.recv_ready():
            return self.shell.recv(1024).decode('utf-8')
        return None

    def is_active(self):
        # Check if the shell channel is still open
        if self.shell:
            return not self.shell.closed
        return False

    def close(self):
        self.running = False
        if self.client:
            self.client.close()
        if self.jump_client:
            self.jump_client.close()

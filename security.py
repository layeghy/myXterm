from cryptography.fernet import Fernet
import os
import sys

class SecurityManager:
    """Manages encryption and decryption of sensitive data"""
    def __init__(self):
        self.key_file = "secret.key"
        self.key = self.load_key()
        self.cipher_suite = Fernet(self.key)
    
    def load_key(self):
        """Load the encryption key from the current directory or generate it"""
        if os.path.exists(self.key_file):
            with open(self.key_file, "rb") as key_file:
                return key_file.read()
        else:
            return self.generate_key()
    
    def generate_key(self):
        """Generate a key and save it into a file"""
        key = Fernet.generate_key()
        with open(self.key_file, "wb") as key_file:
            key_file.write(key)
        return key
    
    def encrypt(self, text):
        """Encrypts a string"""
        if not text:
            return ""
        try:
            encrypted_text = self.cipher_suite.encrypt(text.encode())
            return encrypted_text.decode()
        except Exception as e:
            print(f"Encryption error: {e}")
            return text
    
    def decrypt(self, encrypted_text):
        """Decrypts a string"""
        if not encrypted_text:
            return ""
        try:
            decrypted_text = self.cipher_suite.decrypt(encrypted_text.encode())
            return decrypted_text.decode()
        except Exception:
            # If decryption fails, assume it's plain text (migration scenario)
            return encrypted_text

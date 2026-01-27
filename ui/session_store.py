import json
import os
import xml.etree.ElementTree as ET
from security import SecurityManager
import copy

class SessionStore:
    def __init__(self, filename="sessions.json"):
        self.filename = filename
        self.security = SecurityManager()
        self.sessions = []
        self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r") as f:
                    self.sessions = json.load(f)
                
                # Decrypt passwords and migrate if needed
                migrated = False
                for session in self.sessions:
                    if "password" in session and session["password"]:
                        # Try to decrypt - if it returns same text, it was plain text
                        original = session["password"]
                        decrypted = self.security.decrypt(original)
                        
                        # Store decrypted in memory
                        session["password"] = decrypted
                        
                        # Check if we need to migrate (if it was plain text)
                        if original == decrypted and not original.startswith("gAAAA"):
                             migrated = True
                    
                    # Handle proxy jump password
                    if "proxy_jump" in session and "password" in session["proxy_jump"]:
                        original = session["proxy_jump"]["password"]
                        if original:
                            session["proxy_jump"]["password"] = self.security.decrypt(original)
                
                # If we detected plain text passwords, save them encrypted now
                if migrated:
                    self.save()
                    
            except Exception as e:
                print(f"Error loading sessions: {e}")
                self.sessions = []
        else:
            self.sessions = []

    def save(self):
        try:
            # Create a deep copy to encrypt passwords for storage
            sessions_to_save = copy.deepcopy(self.sessions)
            
            for session in sessions_to_save:
                if "password" in session and session["password"]:
                    session["password"] = self.security.encrypt(session["password"])
                
                if "proxy_jump" in session and "password" in session["proxy_jump"]:
                    session["proxy_jump"]["password"] = self.security.encrypt(session["proxy_jump"]["password"])
            
            with open(self.filename, "w") as f:
                json.dump(sessions_to_save, f, indent=4)
        except Exception as e:
            print(f"Error saving sessions: {e}")

    def add_session(self, session_data):
        self.sessions.append(session_data)
        self.save()

    def get_sessions(self):
        return self.sessions

    def update_session(self, old_data, new_data):
        try:
            index = self.sessions.index(old_data)
            self.sessions[index] = new_data
            self.save()
            return True
        except ValueError:
            return False

    def delete_session(self, session_data):
        try:
            self.sessions.remove(session_data)
            self.save()
            return True
        except ValueError:
            return False

    def update_password(self, session_data, password):
        # Find session by matching host, port, username
        for s in self.sessions:
            if s.get('host') == session_data.get('host') and \
               s.get('port') == session_data.get('port') and \
               s.get('username') == session_data.get('username') and \
               s.get('name') == session_data.get('name'):
                s['password'] = password
                self.save()
                return True
        return False

    def export_to_xml(self, filename):
        root = ET.Element("Sessions")
        for session in self.sessions:
            s_elem = ET.SubElement(root, "Session")
            for key, value in session.items():
                child = ET.SubElement(s_elem, key)
                child.text = str(value)
        
        tree = ET.ElementTree(root)
        try:
            tree.write(filename, encoding="utf-8", xml_declaration=True)
            return True
        except Exception as e:
            print(f"Error exporting to XML: {e}")
            return False

    def import_from_xml(self, filename):
        try:
            tree = ET.parse(filename)
            root = tree.getroot()
            new_sessions = []
            
            # Recursive search for all session nodes, case-insensitive logic
            # We look for "Session" and "session" anywhere in the tree
            session_nodes = root.findall(".//Session") + root.findall(".//session")
            
            for s_elem in session_nodes:
                session = {}
                
                # Check for 'name' attribute (MobaXterm style)
                if "name" in s_elem.attrib:
                    session["name"] = s_elem.attrib["name"]
                
                for child in s_elem:
                    # Normalize tag to lowercase
                    tag = child.tag.lower()
                    
                    # Handle MobaXterm specific tags or standard ones
                    if tag == "host":
                        session["host"] = child.text or ""
                    elif tag == "port":
                        try:
                            session["port"] = int(child.text)
                        except:
                            session["port"] = 22
                    elif tag == "username":
                        session["username"] = child.text or ""
                    elif tag == "name" and "name" not in session:
                        session["name"] = child.text or ""
                    # We can add more fields if needed
                
                # Ensure required fields exist
                if "host" not in session: session["host"] = ""
                if "username" not in session: session["username"] = ""
                if "port" not in session: session["port"] = 22
                
                # Use host as name if name is missing
                if "name" not in session or not session["name"]:
                    session["name"] = session["host"]

                # Only add if we have at least a host
                if session["host"]:
                    new_sessions.append(session)
            
            if not new_sessions:
                return 0

            self.sessions.extend(new_sessions)
            self.save()
            return len(new_sessions)
        except Exception as e:
            print(f"Error importing from XML: {e}")
            return -1

import json
import os
import sys
from utils import resource_path

class SettingsManager:
    """Singleton class to manage application settings"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        # Use a path that works for both dev and frozen environments
        if getattr(sys, 'frozen', False):
            # In frozen app, settings should be in the same folder as the .exe
            base_dir = os.path.dirname(sys.executable)
        else:
            # In dev, use current working directory or script directory
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        self.settings_file = os.path.join(base_dir, "settings.json")
        self.settings = self.load_settings()
        self._callbacks = []  # List of callbacks to call when settings change
    
    def get_default_settings(self):
        """Return default settings"""
        return {
            "terminal": {
                "font_family": "Consolas",
                "font_size": 10,
                "foreground_color": "#FFFFFF",
                "background_color": "#000000"
            },
            "appearance": {
                "theme": "dark"  # "dark" or "light"
            }
        }
    
    def load_settings(self):
        """Load settings from file, or return defaults if file doesn't exist"""
        # 1. Try to load from "writable" location (next to exe or in dev root)
        path = self.settings_file
        
        if not os.path.exists(path):
            # 2. Fallback to bundled settings if frozen
            path = resource_path("settings.json")
            
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    loaded_settings = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    defaults = self.get_default_settings()
                    for category in defaults:
                        if category not in loaded_settings:
                            loaded_settings[category] = defaults[category]
                        else:
                            for key in defaults[category]:
                                if key not in loaded_settings[category]:
                                    loaded_settings[category][key] = defaults[category][key]
                    return loaded_settings
            except Exception as e:
                print(f"Error loading settings: {e}")
                return self.get_default_settings()
        return self.get_default_settings()
    
    def save_settings(self):
        """Save current settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False
    
    def get(self, category, key):
        """Get a specific setting value"""
        return self.settings.get(category, {}).get(key)
    
    def set(self, category, key, value):
        """Set a specific setting value"""
        if category not in self.settings:
            self.settings[category] = {}
        self.settings[category][key] = value
    
    def update_settings(self, new_settings):
        """Update settings with new values and save"""
        self.settings = new_settings
        self.save_settings()
        # Call all registered callbacks
        for callback in self._callbacks:
            try:
                callback(self.settings)
            except Exception as e:
                print(f"Error in settings callback: {e}")
    
    def add_callback(self, callback):
        """Add a callback to be called when settings change"""
        if callback not in self._callbacks:
            self._callbacks.append(callback)
    
    def remove_callback(self, callback):
        """Remove a callback"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def get_all(self):
        """Get all settings"""
        return self.settings.copy()

import json
import os

class SettingsManager:
    """Manages application configuration, such as saved COM ports."""
    
    def __init__(self, config_file="config/settings.json"):
        self.config_file = config_file
        self.settings = {
            "com_port": "",
            "password": "admin" # Default password
        }
        self._ensure_config_dir()
        self.load()

    def _ensure_config_dir(self):
        directory = os.path.dirname(self.config_file)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

    def load(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.settings.update(data)
            except Exception as e:
                print(f"Error loading settings: {e}")

    def save(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save()

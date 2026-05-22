import os
import json

CONFIG_DIR = os.path.expanduser("~/.config/Leaf-Downloader")

class ConfigManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.init_config()
        return cls._instance
        
    def init_config(self):
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR)
            
        self.settings_file = os.path.join(CONFIG_DIR, "settings.json")
        self.history_file = os.path.join(CONFIG_DIR, "history.json")
        self.queue_file = os.path.join(CONFIG_DIR, "queue.json")
        
        self.settings = self._load(self.settings_file, {
            "multithread": False,
            "fragments": 4,
            "monitor_clipboard": False,
            "api_server_enabled": True,
            "api_server_port": 9549
        })
        self.history = self._load(self.history_file, [])
        self.queue = self._load(self.queue_file, [])
        
    def _load(self, path, default):
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading {path}: {e}")
                return default
        else:
            self._save(path, default)
            return default
            
    def _save(self, path, data):
        try:
            with open(path, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving {path}: {e}")
            
    def get_setting(self, key, default=None):
        return self.settings.get(key, default)
        
    def set_setting(self, key, value):
        self.settings[key] = value
        self._save(self.settings_file, self.settings)
        
    def get_history(self):
        return self.history
        
    def add_history(self, entry):
        self.history.insert(0, entry) # add to top
        self._save(self.history_file, self.history)
        
    def remove_history(self, index):
        if 0 <= index < len(self.history):
            self.history.pop(index)
            self._save(self.history_file, self.history)
            
    def get_queue(self):
        return self.queue
        
    def add_queue(self, entry):
        self.queue.append(entry)
        self._save(self.queue_file, self.queue)
        
    def remove_queue(self, index):
        if 0 <= index < len(self.queue):
            item = self.queue.pop(index)
            self._save(self.queue_file, self.queue)
            return item
        return None

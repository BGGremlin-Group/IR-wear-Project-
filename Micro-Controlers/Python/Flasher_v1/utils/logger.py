import time
import json
from pathlib import Path
from PyQt6.QtCore import QObject

class SimpleLogger(QObject):
    def __init__(self, log_file: str):
        super().__init__()
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write session header
        with open(self.log_file, "a") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"SESSION START: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*60}\n")
    
    def log(self, event: str, data: dict):
        """Log event with timestamp and JSON data"""
        try:
            entry = {
                "timestamp": time.time(),
                "event": event,
                "data": data
            }
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            # Fail silently to avoid disrupting operations
            print(f"Logger error: {e}")

class NullLogger(QObject):
    """Logger that discards all messages (for testing)"""
    def log(self, event: str, data: dict):
        pass

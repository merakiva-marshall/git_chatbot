import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

class SettingsManager:
    def __init__(self, settings_dir: str = "data"):
        self.settings_dir = Path(settings_dir)
        self.settings_file = self.settings_dir / "settings.json"
        self.chats_dir = self.settings_dir / "chats"
        self._init_directories()

    def _init_directories(self):
        """Initialize necessary directories"""
        self.settings_dir.mkdir(exist_ok=True)
        self.chats_dir.mkdir(exist_ok=True)
        if not self.settings_file.exists():
            self._save_settings({
                "custom_instructions": "",
                "last_repo": "",
                "selected_model": "claude-3-sonnet-20240229"
            })

    def _save_settings(self, settings: Dict):
        """Save settings to file"""
        with open(self.settings_file, 'w') as f:
            json.dump(settings, f, indent=2)

    def get_settings(self) -> Dict:
        """Get current settings"""
        try:
            with open(self.settings_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "custom_instructions": "",
                "last_repo": "",
                "selected_model": "claude-3-sonnet-20240229"
            }

    def update_settings(self, settings: Dict):
        """Update settings"""
        current_settings = self.get_settings()
        current_settings.update(settings)
        self._save_settings(current_settings)

    def save_chat_session(
        self, 
        messages: List[Dict], 
        repo_info: Optional[Dict] = None,
        title: Optional[str] = None
    ) -> str:
        """Save chat session"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        chat_id = f"chat_{timestamp}"
        
        chat_data = {
            "id": chat_id,
            "title": title or f"Chat {timestamp}",
            "messages": messages,
            "repo_info": repo_info,
            "timestamp": timestamp
        }
        
        with open(self.chats_dir / f"{chat_id}.json", 'w') as f:
            json.dump(chat_data, f, indent=2)
        
        return chat_id

    def get_chat_sessions(self) -> List[Dict]:
        """Get all chat sessions"""
        sessions = []
        for file in sorted(self.chats_dir.glob("*.json"), reverse=True):
            try:
                with open(file, 'r') as f:
                    chat_data = json.load(f)
                    sessions.append({
                        "id": chat_data.get("id", file.stem),
                        "title": chat_data.get("title", file.stem),
                        "timestamp": chat_data.get("timestamp")
                    })
            except Exception:
                continue
        return sessions

    def load_chat_session(self, chat_id: str) -> Optional[Dict]:
        """Load specific chat session"""
        try:
            with open(self.chats_dir / f"{chat_id}.json", 'r') as f:
                return json.load(f)
        except Exception:
            return None
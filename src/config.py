import os
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass
class AppConfig:
    """Application configuration"""
    def __init__(self):
        load_dotenv()
        
        # Required environment variables
        self.anthropic_api_key = self._get_required_env("ANTHROPIC_API_KEY")
        self.github_token = self._get_required_env("GITHUB_TOKEN")
        self.qdrant_url = self._get_required_env("QDRANT_URL")
        self.qdrant_api_key = self._get_required_env("QDRANT_API_KEY")
        
        # Optional configurations with defaults
        self.max_file_size = int(os.getenv("MAX_FILE_SIZE", "1000000"))  # 1MB
        self.collection_name = os.getenv("COLLECTION_NAME", "github_code")
    
    def _get_required_env(self, key: str) -> str:
        """Get required environment variable or raise error"""
        value = os.getenv(key)
        if value is None:
            raise ValueError(f"Missing required environment variable: {key}")
        return value
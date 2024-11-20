from typing import Dict, List, Optional, Union
import tiktoken
import logging
from pathlib import Path
import os

class TokenCounter:
    def __init__(self, model: str = "claude-3-5-sonnet-latest"):
        self.logger = logging.getLogger(__name__)
        self.model = model
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

        # Updated pricing including embedding costs
        self.pricing = {
            "claude-3-5-haiku-latest": {
                "input": 0.001,
                "output": 0.005,
                "embedding": 0.0001  # per 1K tokens
            },
            "claude-3-5-sonnet-latest": {
                "input": 0.003,
                "output": 0.015,
                "embedding": 0.0001
            },
            "embedding-3-small": {  # OpenAI's ada-002 equivalent
                "input": 0.0001,
                "output": 0.0,
                "embedding": 0.0001
            }
        }

        # Token limits by model
        self.token_limits = {
            "claude-3-5-haiku-latest": 200000,
            "claude-3-5-sonnet-latest": 200000,
            "embedding-3-small": 8191
        }

    def count_tokens(self, text: Union[str, List[Dict], Dict]) -> int:
        """Count tokens in text or message structure"""
        try:
            if isinstance(text, str):
                return len(self.tokenizer.encode(text))
            elif isinstance(text, list):
                return sum(self.count_tokens(msg) for msg in text)
            elif isinstance(text, dict):
                total = 0
                for key, value in text.items():
                    total += self.count_tokens(str(key))
                    total += self.count_tokens(str(value))
                return total
            else:
                raise ValueError(f"Unsupported type for token counting: {type(text)}")
        except Exception as e:
            self.logger.error(f"Error counting tokens: {str(e)}")
            return 0

    def estimate_cost(self, 
                     input_tokens: int, 
                     output_tokens: int, 
                     embedding_tokens: int = 0,
                     model: Optional[str] = None) -> Dict[str, float]:
        """
        Estimate cost based on current model pricing
        Returns breakdown of costs by type
        """
        if not model:
            model = self.model

        if model not in self.pricing:
            self.logger.warning(f"Unknown model {model}, using Sonnet pricing")
            model_pricing = self.pricing["claude-3-5-sonnet-latest"]
        else:
            model_pricing = self.pricing[model]

        input_cost = (input_tokens / 1000) * model_pricing["input"]
        output_cost = (output_tokens / 1000) * model_pricing["output"]
        embedding_cost = (embedding_tokens / 1000) * model_pricing["embedding"]

        return {
            "input_cost": input_cost,
            "output_cost": output_cost,
            "embedding_cost": embedding_cost,
            "total_cost": input_cost + output_cost + embedding_cost
        }

    def check_token_limit(self, total_tokens: int, model: Optional[str] = None) -> bool:
        """Check if total tokens are within model's limit"""
        if not model:
            model = self.model

        if model not in self.token_limits:
            self.logger.warning(f"Unknown model {model}, using Sonnet limits")
            limit = self.token_limits["claude-3-5-sonnet-latest"]
        else:
            limit = self.token_limits[model]

        return total_tokens <= limit

    def get_token_limit(self, model: Optional[str] = None) -> int:
        """Get token limit for specified model"""
        if not model:
            model = self.model

        return self.token_limits.get(model, self.token_limits["claude-3-5-sonnet-latest"])

    def format_token_count(self, count: int) -> str:
        """Format token count with commas and 'tokens' suffix"""
        return f"{count:,} tokens"

    def get_model_pricing(self, model: Optional[str] = None) -> Dict[str, float]:
        """Get pricing details for specified model"""
        if not model:
            model = self.model

        return self.pricing.get(model, self.pricing["claude-3-5-sonnet-latest"])
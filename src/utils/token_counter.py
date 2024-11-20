# src/utils/token_counter.py
from typing import Dict, List, Optional, Union
import tiktoken
import json
from datetime import datetime
import logging
from pathlib import Path
import os

class TokenCounter:
    def __init__(self, model: str = "claude-3-5-sonnet-latest"):
        self.logger = logging.getLogger(__name__)
        self.model = model
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.pricing = {
            "claude-3-5-haiku-latest": {
                "input": 0.001,
                "output": 0.005
            },
            "claude-3-5-sonnet-latest": {
                "input": 0.003,
                "output": 0.015
            }
        }

    def count_tokens(self, text: Union[str, List[Dict], Dict]) -> int:
        """Count tokens in text or message structure"""
        try:
            if isinstance(text, str):
                return len(self.tokenizer.encode(text))
            elif isinstance(text, list):
                # Handle message list format
                return sum(self.count_tokens(msg) for msg in text)
            elif isinstance(text, dict):
                # Handle message dict format
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

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost based on current model pricing"""
        if self.model not in self.pricing:
            self.logger.warning(f"Unknown model {self.model}, using Sonnet pricing")
            model_pricing = self.pricing["claude-3-5-sonnet-latest"]
        else:
            model_pricing = self.pricing[self.model]

        input_cost = (input_tokens / 1000) * model_pricing["input"]
        output_cost = (output_tokens / 1000) * model_pricing["output"]
        return input_cost + output_cost
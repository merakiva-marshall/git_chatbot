# src/utils/usage_tracker.py
from datetime import datetime
from pathlib import Path
import json
import logging
from typing import Dict, List, Optional
import os
from dataclasses import dataclass
from .token_counter import TokenCounter

@dataclass
class UsageRecord:
    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    conversation_id: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'model': self.model,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'cost': self.cost,
            'conversation_id': self.conversation_id
        }

class UsageTracker:
    def __init__(self, storage_dir: str = "data/usage"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.current_month_file = self.storage_dir / f"{datetime.now().strftime('%Y_%m')}_usage.json"
        self.logger = logging.getLogger(__name__)
        self.token_counters = {}  # Dictionary to store model-specific token counters

    def _get_token_counter(self, model: str) -> TokenCounter:
        """Get or create a token counter for specific model"""
        if model not in self.token_counters:
            self.token_counters[model] = TokenCounter(model=model)
        return self.token_counters[model]

    def track_usage(
        self, 
        input_content: str,
        output_content: str,
        model: str,
        conversation_id: Optional[str] = None
    ) -> UsageRecord:
        """Track usage for a single API call"""
        try:
            # Get the appropriate token counter for this model
            token_counter = self._get_token_counter(model)

            # Count tokens
            input_tokens = token_counter.count_tokens(input_content)
            output_tokens = token_counter.count_tokens(output_content)

            # Calculate cost using model-specific pricing
            cost = token_counter.estimate_cost(input_tokens, output_tokens)

            # Create usage record
            record = UsageRecord(
                timestamp=datetime.now().isoformat(),
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                conversation_id=conversation_id
            )

            # Save to storage
            self._save_record(record)

            return record

        except Exception as e:
            self.logger.error(f"Error tracking usage: {str(e)}")
            raise

    def _save_record(self, record: UsageRecord):
        """Save usage record to current month's file"""
        try:
            # Load existing records
            if self.current_month_file.exists():
                with open(self.current_month_file, 'r') as f:
                    records = json.load(f)
            else:
                records = []

            # Add new record
            records.append(record.to_dict())

            # Save updated records
            with open(self.current_month_file, 'w') as f:
                json.dump(records, f, indent=2)

        except Exception as e:
            self.logger.error(f"Error saving usage record: {str(e)}")
            raise

    def get_usage_summary(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict:
        """Get usage summary for date range"""
        try:
            total_input_tokens = 0
            total_output_tokens = 0
            total_cost = 0.0
            usage_by_model = {}

            # Get all usage files
            usage_files = list(self.storage_dir.glob("*_usage.json"))

            for file in usage_files:
                if not file.exists():
                    continue

                with open(file, 'r') as f:
                    records = json.load(f)

                for record in records:
                    # Skip if outside date range
                    record_date = datetime.fromisoformat(record['timestamp'])
                    if start_date and record_date < datetime.fromisoformat(start_date):
                        continue
                    if end_date and record_date > datetime.fromisoformat(end_date):
                        continue

                    # Update totals
                    total_input_tokens += record['input_tokens']
                    total_output_tokens += record['output_tokens']
                    total_cost += record['cost']

                    # Update model-specific stats
                    model = record['model']
                    if model not in usage_by_model:
                        usage_by_model[model] = {
                            'input_tokens': 0,
                            'output_tokens': 0,
                            'cost': 0.0
                        }
                    usage_by_model[model]['input_tokens'] += record['input_tokens']
                    usage_by_model[model]['output_tokens'] += record['output_tokens']
                    usage_by_model[model]['cost'] += record['cost']

            return {
                'total_input_tokens': total_input_tokens,
                'total_output_tokens': total_output_tokens,
                'total_cost': total_cost,
                'usage_by_model': usage_by_model
            }

        except Exception as e:
            self.logger.error(f"Error getting usage summary: {str(e)}")
            raise
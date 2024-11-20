from typing import Dict, Optional, List
import json
from datetime import datetime
from pathlib import Path
import logging
from dataclasses import dataclass
from .token_counter import TokenCounter

@dataclass
class UsageRecord:
    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    embedding_tokens: int
    cost: float
    embedding_cost: float
    conversation_id: Optional[str] = None

class UsageTracker:
    def __init__(self, storage_dir: str = "data/usage"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.token_counter = TokenCounter()

        # Initialize current month's file
        self.current_month = datetime.now().strftime("%Y-%m")
        self.current_file = self.storage_dir / f"usage_{self.current_month}.json"
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Ensure the usage file exists with proper structure"""
        if not self.current_file.exists():
            with open(self.current_file, 'w') as f:
                json.dump([], f)

    def track_usage(self, 
                   input_content: str,
                   output_content: str,
                   model: str,
                   conversation_id: Optional[str] = None,
                   embedding_tokens: int = 0) -> UsageRecord:
        """Track API usage including embeddings"""
        try:
            # Count tokens
            input_tokens = self.token_counter.count_tokens(input_content)
            output_tokens = self.token_counter.count_tokens(output_content)

            # Calculate costs
            costs = self.token_counter.estimate_cost(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                embedding_tokens=embedding_tokens,
                model=model
            )

            # Create usage record
            record = UsageRecord(
                timestamp=datetime.now().isoformat(),
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                embedding_tokens=embedding_tokens,
                cost=costs["input_cost"] + costs["output_cost"],
                embedding_cost=costs["embedding_cost"],
                conversation_id=conversation_id
            )

            # Save the record
            self._save_usage_record(vars(record))

            return record

        except Exception as e:
            self.logger.error(f"Error tracking usage: {str(e)}")
            raise

    def track_embedding_usage(self, 
                            total_tokens: int, 
                            model: str = "embedding-3-small",
                            conversation_id: Optional[str] = None):
        """Track embedding-specific usage"""
        try:
            costs = self.token_counter.estimate_cost(
                input_tokens=0,
                output_tokens=0,
                embedding_tokens=total_tokens,
                model=model
            )

            record = UsageRecord(
                timestamp=datetime.now().isoformat(),
                model=model,
                input_tokens=0,
                output_tokens=0,
                embedding_tokens=total_tokens,
                cost=0,
                embedding_cost=costs["embedding_cost"],
                conversation_id=conversation_id
            )

            self._save_usage_record(vars(record))

        except Exception as e:
            self.logger.error(f"Error tracking embedding usage: {str(e)}")
            raise

    def _save_usage_record(self, record: Dict):
        """Save a usage record to the current month's file"""
        try:
            # Check if we need to create a new month's file
            current_month = datetime.now().strftime("%Y-%m")
            if current_month != self.current_month:
                self.current_month = current_month
                self.current_file = self.storage_dir / f"usage_{self.current_month}.json"
                self._ensure_file_exists()

            # Read existing records
            with open(self.current_file, 'r') as f:
                records = json.load(f)

            # Add new record
            records.append(record)

            # Save updated records
            with open(self.current_file, 'w') as f:
                json.dump(records, f, indent=2)

        except Exception as e:
            self.logger.error(f"Error saving usage record: {str(e)}")
            raise

    def get_usage_summary(self, 
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None) -> Dict:
        """Get usage summary for date range"""
        try:
            all_records = []

            # Collect records from all relevant files
            for file in self.storage_dir.glob("usage_*.json"):
                with open(file, 'r') as f:
                    records = json.load(f)
                    all_records.extend(records)

            # Filter by date range if specified
            if start_date:
                all_records = [r for r in all_records if r['timestamp'] >= start_date]
            if end_date:
                all_records = [r for r in all_records if r['timestamp'] <= end_date]

            # Calculate totals
            summary = {
                'total_input_tokens': sum(r['input_tokens'] for r in all_records),
                'total_output_tokens': sum(r['output_tokens'] for r in all_records),
                'total_embedding_tokens': sum(r['embedding_tokens'] for r in all_records),
                'total_cost': sum(r['cost'] for r in all_records),
                'total_embedding_cost': sum(r['embedding_cost'] for r in all_records),
                'usage_by_model': {}
            }

            # Calculate per-model statistics
            for record in all_records:
                model = record['model']
                if model not in summary['usage_by_model']:
                    summary['usage_by_model'][model] = {
                        'input_tokens': 0,
                        'output_tokens': 0,
                        'embedding_tokens': 0,
                        'cost': 0,
                        'embedding_cost': 0
                    }

                model_stats = summary['usage_by_model'][model]
                model_stats['input_tokens'] += record['input_tokens']
                model_stats['output_tokens'] += record['output_tokens']
                model_stats['embedding_tokens'] += record['embedding_tokens']
                model_stats['cost'] += record['cost']
                model_stats['embedding_cost'] += record['embedding_cost']

            return summary

        except Exception as e:
            self.logger.error(f"Error getting usage summary: {str(e)}")
            raise

    def get_conversation_usage(self, conversation_id: str) -> Dict:
        """Get usage statistics for a specific conversation"""
        try:
            all_records = []

            # Collect records from all files
            for file in self.storage_dir.glob("usage_*.json"):
                with open(file, 'r') as f:
                    records = json.load(f)
                    all_records.extend(records)

            # Filter by conversation ID
            conv_records = [r for r in all_records if r.get('conversation_id') == conversation_id]

            return {
                'total_input_tokens': sum(r['input_tokens'] for r in conv_records),
                'total_output_tokens': sum(r['output_tokens'] for r in conv_records),
                'total_embedding_tokens': sum(r['embedding_tokens'] for r in conv_records),
                'total_cost': sum(r['cost'] for r in conv_records),
                'total_embedding_cost': sum(r['embedding_cost'] for r in conv_records),
                'message_count': len(conv_records)
            }

        except Exception as e:
            self.logger.error(f"Error getting conversation usage: {str(e)}")
            raise
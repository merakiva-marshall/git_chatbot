from typing import Dict, List, Optional
from pathlib import Path
import logging
from ..core.codebase_structure import CodebaseStructure
from ..analysis.code_analyzer import CodeAnalyzer
from ..query.contextual_search import ContextualSearch

class CodeService:
    """Handles code-specific operations and analysis"""

    def __init__(self,
                 codebase: CodebaseStructure,
                 code_analyzer: CodeAnalyzer,
                 contextual_search: ContextualSearch):
        self.codebase = codebase
        self.code_analyzer = code_analyzer
        self.contextual_search = contextual_search
        self.logger = logging.getLogger(__name__)

    async def find_implementation_examples(self, 
                                        pattern: str,
                                        language: Optional[str] = None,
                                        limit: int = 5) -> List[Dict]:
        """Find implementation examples in the codebase"""
        try:
            results = await self.contextual_search.search_by_pattern(
                pattern_type=pattern,
                limit=limit
            )

            if language:
                results = [r for r in results 
                          if r.metadata.get('language') == language]

            return results

        except Exception as e:
            self.logger.error(f"Error finding implementations: {str(e)}")
            raise

    async def analyze_code_quality(self, file_path: str) -> Dict:
        """Analyze code quality for a file"""
        try:
            # Get file components
            components = self.codebase.get_file_components(file_path)

            # Analyze patterns and practices
            patterns = []
            issues = []
            metrics = {}

            for component in components:
                # Analyze component
                analysis = await self.code_analyzer.analyze_component_quality(
                    component
                )

                patterns.extend(analysis.get('patterns', []))
                issues.extend(analysis.get('issues', []))

                # Update metrics
                for metric, value in analysis.get('metrics', {}).items():
                    if metric not in metrics:
                        metrics[metric] = []
                    metrics[metric].append(value)

            return {
                'patterns': patterns,
                'issues': issues,
                'metrics': {
                    k: sum(v) / len(v) for k, v in metrics.items()
                }
            }

        except Exception as e:
            self.logger.error(f"Error analyzing code quality: {str(e)}")
            raise
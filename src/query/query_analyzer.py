from datetime import datetime
from typing import Dict, List, Optional
import re
from enum import Enum
from pydantic import BaseModel
import logging

class QueryType(Enum):
    """Types of code queries"""
    FILE = "file"
    COMPONENT = "component"
    IMPLEMENTATION = "implementation"
    RELATIONSHIP = "relationship"
    PATTERN = "pattern"
    DOCUMENTATION = "documentation"

class QueryTarget(BaseModel):
    """Target of the query"""
    type: QueryType
    name: Optional[str]
    attributes: Dict[str, str]
    constraints: List[str]

class QueryAnalysis(BaseModel):
    """Complete query analysis"""
    query_type: QueryType
    targets: List[QueryTarget]
    context_needs: List[str]
    action_type: str
    metadata: Dict

class QueryAnalyzer:
    """Analyzes and categorizes code queries"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Query patterns
        self.patterns = {
            QueryType.FILE: [
                r"show (?:me )?(?:the )?(?:content of |)?file[s]? (.+)",
                r"find (?:all )?files? (?:that |where )?(.+)",
                r"search for files? (?:with |containing )?(.+)"
            ],
            QueryType.COMPONENT: [
                r"show (?:me )?(?:the )?(?:implementation of |)?(?:class|function|method) (.+)",
                r"find (?:all )?(?:classes|functions|methods) (?:that |where )?(.+)",
                r"how (?:is|does) (.+) (?:implemented|work)"
            ],
            QueryType.IMPLEMENTATION: [
                r"how to implement (.+)",
                r"show (?:me )?examples? of (.+)",
                r"what's the best way to (.+)"
            ],
            QueryType.RELATIONSHIP: [
                r"how (?:does|is) (.+) (?:related to|used in|connected with) (.+)",
                r"what (?:uses|calls|imports) (.+)",
                r"show (?:me )?(?:the )?dependencies (?:of|for) (.+)"
            ]
        }

    async def analyze_query(self, query: str) -> QueryAnalysis:
        """Analyze a natural language code query"""
        try:
            # Determine query type
            query_type = self._determine_query_type(query)

            # Extract targets
            targets = self._extract_targets(query, query_type)

            # Identify context needs
            context_needs = self._identify_context_needs(query, query_type)

            # Determine action type
            action_type = self._determine_action(query)

            # Build metadata
            metadata = self._build_query_metadata(query, query_type, targets)

            return QueryAnalysis(
                query_type=query_type,
                targets=targets,
                context_needs=context_needs,
                action_type=action_type,
                metadata=metadata
            )

        except Exception as e:
            self.logger.error(f"Error analyzing query: {str(e)}")
            raise

    def _determine_query_type(self, query: str) -> QueryType:
        """Determine the type of query"""
        query = query.lower()

        for query_type, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, query):
                    return query_type

        # Default to implementation if no specific type is matched
        return QueryType.IMPLEMENTATION

    def _extract_targets(self, query: str, query_type: QueryType) -> List[QueryTarget]:
        """Extract target elements from query"""
        targets = []
        query = query.lower()

        patterns = self.patterns.get(query_type, [])
        for pattern in patterns:
            matches = re.finditer(pattern, query)
            for match in matches:
                target_name = match.group(1)
                targets.append(
                    QueryTarget(
                        type=query_type,
                        name=target_name,
                        attributes=self._extract_attributes(query),
                        constraints=self._extract_constraints(query)
                    )
                )

        return targets

    def _identify_context_needs(self, query: str, query_type: QueryType) -> List[str]:
        """Identify required context for query"""
        context_needs = []

        # Always include basic context
        context_needs.append('basic')

        if query_type == QueryType.RELATIONSHIP:
            context_needs.extend(['dependencies', 'imports'])

        if 'implementation' in query.lower():
            context_needs.extend(['patterns', 'examples'])

        if 'how' in query.lower():
            context_needs.append('documentation')

        return list(set(context_needs))

    def _determine_action(self, query: str) -> str:
        """Determine the required action type"""
        query = query.lower()

        if any(word in query for word in ['show', 'display', 'print']):
            return 'display'
        elif any(word in query for word in ['find', 'search', 'look for']):
            return 'search'
        elif any(word in query for word in ['how', 'explain', 'describe']):
            return 'explain'
        elif any(word in query for word in ['implement', 'create', 'write']):
            return 'implement'
        else:
            return 'explain'

    def _extract_attributes(self, query: str) -> Dict[str, str]:
        """Extract attribute constraints from query"""
        attributes = {}

        # Extract language constraints
        lang_match = re.search(r'in (?:language )?(\w+)', query)
        if lang_match:
            attributes['language'] = lang_match.group(1)

        # Extract type constraints
        type_match = re.search(r'type[s]? (?:of |is )?(\w+)', query)
        if type_match:
            attributes['type'] = type_match.group(1)

        return attributes

    def _extract_constraints(self, query: str) -> List[str]:
        """Extract general constraints from query"""
        constraints = []

        # Time constraints
        if re.search(r'recent|latest|new', query):
            constraints.append('recent')

        # Size constraints
        if re.search(r'small|large|big', query):
            constraints.append('size')

        # Complexity constraints
        if re.search(r'simple|complex|basic', query):
            constraints.append('complexity')

        return constraints

    def _build_query_metadata(self, 
                            query: str, 
                            query_type: QueryType,
                            targets: List[QueryTarget]) -> Dict:
        """Build query metadata"""
        return {
            'original_query': query,
            'query_type': query_type.value,
            'target_count': len(targets),
            'timestamp': datetime.utcnow().isoformat()
        }
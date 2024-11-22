from typing import Dict, List, Optional, Union
from pydantic import BaseModel
import logging
from .query_analyzer import QueryAnalysis, QueryType
from src.storage.vector_store import CodebaseVectorStore
from src.storage.context_store import ContextStorage
from src.embedding.hierarchical_embedder import HierarchicalEmbedding

class SearchResult(BaseModel):
    """Represents a search result with context"""
    score: float
    content: Dict
    context: Dict
    metadata: Dict
    relationships: List[str]

class ContextualSearch:
    """Performs context-aware code search"""

    def __init__(self,
                 vector_store: CodebaseVectorStore,
                 context_store: ContextStorage,
                 embedder: HierarchicalEmbedding):
        self.vector_store = vector_store
        self.context_store = context_store
        self.embedder = embedder
        self.logger = logging.getLogger(__name__)

    async def search(self, 
                    query: str,
                    query_analysis: QueryAnalysis,
                    limit: int = 5) -> List[SearchResult]:
        """Perform context-aware search"""
        try:
            # Generate query embedding
            query_embedding = await self.embedder._generate_embedding(
                content=query,
                context={'query_type': query_analysis.query_type.value},
                element_type='query'
            )

            # Determine collection based on query type
            collection_name = self._get_collection_name(query_analysis.query_type)

            # Perform vector search
            vector_results = await self.vector_store.search(
                query_vector=query_embedding,
                collection_name=collection_name,
                limit=limit
            )

            # Enhance results with context
            results = []
            for result in vector_results:
                # Get full context
                context = await self.context_store.get_context(result['key'])

                if context:
                    # Get related contexts if needed
                    related_contexts = []
                    if 'relationships' in query_analysis.context_needs:
                        related_contexts = await self.context_store.get_related_contexts(
                            result['key']
                        )

                    results.append(SearchResult(
                        score=result['score'],
                        content=result['metadata'],
                        context=context.content,
                        metadata={
                            **result['metadata'],
                            'related_contexts': [r.dict() for r in related_contexts]
                        },
                        relationships=context.relationships
                    ))

            return results

        except Exception as e:
            self.logger.error(f"Error in contextual search: {str(e)}")
            raise

    def _get_collection_name(self, query_type: QueryType) -> str:
        """Get appropriate vector collection name for query type"""
        collection_mapping = {
            QueryType.FILE: 'code_files',
            QueryType.COMPONENT: 'code_components',
            QueryType.RELATIONSHIP: 'code_relationships',
            QueryType.IMPLEMENTATION: 'code_components',
            QueryType.PATTERN: 'code_patterns'
        }
        return collection_mapping.get(query_type, 'code_components')

    async def search_by_pattern(self,
                              pattern_type: str,
                              limit: int = 5) -> List[SearchResult]:
        """Search for specific implementation patterns"""
        try:
            results = await self.vector_store.search(
                query_vector=None,  # We'll use metadata filtering instead
                collection_name='code_patterns',
                limit=limit,
                filter_conditions={'pattern_type': pattern_type}
            )

            # Enhance results with context
            return await self._enhance_results_with_context(results)

        except Exception as e:
            self.logger.error(f"Error in pattern search: {str(e)}")
            raise

    async def search_by_relationship(self,
                                   source: str,
                                   relationship_type: str,
                                   limit: int = 5) -> List[SearchResult]:
        """Search for specific relationships"""
        try:
            results = await self.vector_store.search(
                query_vector=None,  # We'll use metadata filtering instead
                collection_name='code_relationships',
                limit=limit,
                filter_conditions={
                    'source': source,
                    'type': relationship_type
                }
            )

            return await self._enhance_results_with_context(results)

        except Exception as e:
            self.logger.error(f"Error in relationship search: {str(e)}")
            raise

    async def _enhance_results_with_context(self,
                                          results: List[Dict]) -> List[SearchResult]:
        """Enhance search results with context information"""
        enhanced_results = []

        for result in results:
            context = await self.context_store.get_context(result['key'])
            if context:
                enhanced_results.append(SearchResult(
                    score=result['score'],
                    content=result['metadata'],
                    context=context.content,
                    metadata=result['metadata'],
                    relationships=context.relationships
                ))

        return enhanced_results
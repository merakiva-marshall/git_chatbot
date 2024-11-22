from typing import Dict, List, Optional, Union
import numpy as np
from pathlib import Path
import logging
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.http import models
from src.embedding.hierarchical_embedder import EmbeddingVector

class CodebaseVectorStore:
    """Manages vector storage for code elements"""

    def __init__(self, qdrant_client: QdrantClient):
        self.client = qdrant_client
        self.logger = logging.getLogger(__name__)

        # Initialize collections
        self.collections = {
            'files': 'code_files',
            'components': 'code_components',
            'relationships': 'code_relationships',
            'patterns': 'code_patterns'
        }

        self._init_collections()

    def _init_collections(self):
        """Initialize vector collections"""
        try:
            existing_collections = [
                c.name for c in self.client.get_collections().collections
            ]

            for collection_name in self.collections.values():
                if collection_name not in existing_collections:
                    self.client.create_collection(
                        collection_name=collection_name,
                        vectors_config=models.VectorParams(
                            size=1536,  # Claude embedding size
                            distance=models.Distance.COSINE
                        )
                    )

        except Exception as e:
            self.logger.error(f"Error initializing collections: {str(e)}")
            raise

    async def store_embeddings(self, 
                             embeddings: Dict[str, Dict[str, EmbeddingVector]]) -> None:
        """Store embeddings in appropriate collections"""
        try:
            for element_type, elements in embeddings.items():
                collection_name = self.collections.get(element_type)
                if not collection_name:
                    continue

                points = []
                for key, embedding in elements.items():
                    points.append(
                        models.PointStruct(
                            id=str(hash(key)),
                            vector=embedding.vector,
                            payload={
                                'key': key,
                                'type': embedding.type,
                                'context': embedding.context,
                                'metadata': embedding.metadata
                            }
                        )
                    )

                if points:
                    self.client.upsert(
                        collection_name=collection_name,
                        points=points
                    )

        except Exception as e:
            self.logger.error(f"Error storing embeddings: {str(e)}")
            raise

    async def search(self, 
                    query_vector: List[float],
                    collection_name: str,
                    limit: int = 5,
                    score_threshold: float = 0.7) -> List[Dict]:
        """Search for similar vectors"""
        try:
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold
            )

            return [
                {
                    'score': hit.score,
                    'key': hit.payload['key'],
                    'type': hit.payload['type'],
                    'context': hit.payload['context'],
                    'metadata': hit.payload['metadata']
                }
                for hit in results
            ]

        except Exception as e:
            self.logger.error(f"Error searching vectors: {str(e)}")
            raise
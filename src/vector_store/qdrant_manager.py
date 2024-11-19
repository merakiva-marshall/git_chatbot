from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import Dict, List, Optional
import numpy as np
from datetime import datetime
import uuid

class QdrantManager:
    def __init__(self, path: str = "data/qdrant"):
        """Initialize local Qdrant instance"""
        self.client = QdrantClient(path=path)
        self.collection_name = "code_vectors"
        self._init_collections()
    
    def _init_collections(self):
        """Initialize collections if they don't exist"""
        try:
            self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "size": 1536,  # OpenAI embedding size
                    "distance": models.Distance.COSINE
                }
            )
        except Exception as e:
            print(f"Collection already exists or error: {e}")

    async def store_code_vectors(
        self,
        embeddings: List[np.ndarray],
        metadata: List[Dict],
        ids: Optional[List[str]] = None
    ):
        """Store code embeddings with metadata"""
        points = []
        for i, (embedding, meta) in enumerate(zip(embeddings, metadata)):
            point_id = ids[i] if ids else str(uuid.uuid4())
            points.append(models.PointStruct(
                id=point_id,
                vector=embedding.tolist(),
                payload=meta
            ))
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )

    async def search_code(
        self,
        query_vector: np.ndarray,
        limit: int = 5
    ) -> List[Dict]:
        """Search for similar code segments"""
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector.tolist(),
            limit=limit
        )
        return [hit.payload for hit in results]
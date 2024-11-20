from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse
from typing import Dict, List, Optional, Union
import numpy as np
from datetime import datetime
import uuid
import logging
import asyncio
from pathlib import Path
import json

class QdrantManager:
    def __init__(self, 
                 path: str = "data/qdrant",
                 collection_name: str = "code_vectors",
                 vector_size: int = 1536):  # OpenAI's embedding size
        """Initialize Qdrant manager with support for concurrent operations"""
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)

        self.collection_name = collection_name
        self.vector_size = vector_size
        self.logger = logging.getLogger(__name__)

        # Initialize client
        self.client = QdrantClient(path=str(self.path))

        # Setup concurrency control
        self._setup_concurrency()

        # Initialize collection
        self._init_collection()

    def _setup_concurrency(self):
        """Setup concurrency controls"""
        self._write_lock = asyncio.Lock()
        self._read_lock = asyncio.Lock()
        self._operation_semaphore = asyncio.Semaphore(10)  # Limit concurrent operations

    def _init_collection(self):
        """Initialize vector collection with error handling"""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            existing_collections = [c.name for c in collections.collections]

            if self.collection_name not in existing_collections:
                self.logger.info(f"Creating collection: {self.collection_name}")

                # Create collection with optimized settings
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.vector_size,
                        distance=models.Distance.COSINE
                    ),
                    optimizers_config=models.OptimizersConfigDiff(
                        indexing_threshold=20000,  # Optimize for larger datasets
                        memmap_threshold=50000
                    ),
                    hnsw_config=models.HnswConfigDiff(
                        m=16,  # Number of connections per element
                        ef_construct=100  # Size of the beam search
                    )
                )

                # Create necessary indexes
                self._create_indexes()
            else:
                self.logger.info(f"Collection {self.collection_name} already exists")

        except Exception as e:
            self.logger.error(f"Error initializing collection: {str(e)}")
            raise

    def _create_indexes(self):
        """Create necessary indexes for efficient searching"""
        try:
            # Create payload indexes for common fields
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="file_path",
                field_schema=models.PayloadSchemaType.KEYWORD
            )

            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="code_type",
                field_schema=models.PayloadSchemaType.KEYWORD
            )

            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="last_modified",
                field_schema=models.PayloadSchemaType.DATETIME
            )

        except Exception as e:
            self.logger.warning(f"Error creating indexes: {str(e)}")

    async def store_code_vectors(self,
                               embeddings: List[np.ndarray],
                               metadata: List[Dict],
                               batch_size: int = 100) -> None:
        """Store code embeddings with batching and concurrency control"""
        async with self._write_lock:
            try:
                # Process in batches
                for i in range(0, len(embeddings), batch_size):
                    batch_embeddings = embeddings[i:i + batch_size]
                    batch_metadata = metadata[i:i + batch_size]

                    points = []
                    for embedding, meta in zip(batch_embeddings, batch_metadata):
                        # Generate a deterministic ID based on content
                        content_hash = str(hash(meta.get('content', '')))
                        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, content_hash))

                        points.append(models.PointStruct(
                            id=point_id,
                            vector=embedding.tolist(),
                            payload={
                                'file_path': meta.get('file_path', ''),
                                'code_type': meta.get('code_type', ''),
                                'content': meta.get('content', ''),
                                'language': meta.get('language', ''),
                                'last_modified': meta.get('last_modified', ''),
                                'metadata': meta
                            }
                        ))

                    async with self._operation_semaphore:
                        self.client.upsert(
                            collection_name=self.collection_name,
                            points=points
                        )

                    self.logger.info(f"Stored batch of {len(points)} vectors")

            except Exception as e:
                self.logger.error(f"Error storing vectors: {str(e)}")
                raise

    async def search_code(self,
                         query_vector: np.ndarray,
                         limit: int = 5,
                         score_threshold: float = 0.7,
                         filter_conditions: Optional[Dict] = None) -> List[Dict]:
        """Search for similar code segments with filtering"""
        async with self._read_lock:
            try:
                search_params = {
                    "collection_name": self.collection_name,
                    "query_vector": query_vector.tolist(),
                    "limit": limit,
                    "score_threshold": score_threshold
                }

                if filter_conditions:
                    search_params["query_filter"] = models.Filter(
                        must=self._build_filter_conditions(filter_conditions)
                    )

                async with self._operation_semaphore:
                    results = self.client.search(**search_params)

                # Process and format results
                formatted_results = []
                for hit in results:
                    result = {
                        'file_path': hit.payload.get('file_path', ''),
                        'code_type': hit.payload.get('code_type', ''),
                        'content': hit.payload.get('content', ''),
                        'similarity_score': hit.score,
                        'metadata': hit.payload.get('metadata', {})
                    }
                    formatted_results.append(result)

                return formatted_results

            except Exception as e:
                self.logger.error(f"Error searching vectors: {str(e)}")
                raise

    def _build_filter_conditions(self, filter_conditions: Dict) -> List[models.FieldCondition]:
        """Build Qdrant filter conditions from dict"""
        conditions = []

        for field, value in filter_conditions.items():
            if isinstance(value, (list, tuple)):
                conditions.append(models.FieldCondition(
                    key=field,
                    match=models.MatchAny(any=value)
                ))
            elif isinstance(value, dict):
                if 'range' in value:
                    conditions.append(models.FieldCondition(
                        key=field,
                        range=models.Range(**value['range'])
                    ))
            else:
                conditions.append(models.FieldCondition(
                    key=field,
                    match=models.MatchValue(value=value)
                ))

        return conditions

    async def delete_collection(self):
        """Delete the entire collection"""
        try:
            self.client.delete_collection(self.collection_name)
            self.logger.info(f"Deleted collection: {self.collection_name}")
        except Exception as e:
            self.logger.error(f"Error deleting collection: {str(e)}")
            raise

    async def get_collection_info(self) -> Dict:
        """Get information about the collection"""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return {
                'vectors_count': collection_info.vectors_count,
                'indexed_vectors_count': collection_info.indexed_vectors_count,
                'points_count': collection_info.points_count,
                'segments_count': collection_info.segments_count,
                'status': collection_info.status
            }
        except Exception as e:
            self.logger.error(f"Error getting collection info: {str(e)}")
            raise

    def backup_collection(self, backup_dir: Optional[str] = None):
        """Backup the collection to a specified directory"""
        if not backup_dir:
            backup_dir = self.path / "backups"

        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_path / f"{self.collection_name}_{timestamp}.snapshot"

            self.client.create_snapshot(
                collection_name=self.collection_name,
                snapshot_path=str(backup_file)
            )

            self.logger.info(f"Created backup at: {backup_file}")

        except Exception as e:
            self.logger.error(f"Error creating backup: {str(e)}")
            raise
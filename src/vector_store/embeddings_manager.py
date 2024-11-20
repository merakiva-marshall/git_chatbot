from typing import Dict, List, Optional
import numpy as np
import logging
from anthropic import Anthropic
from pathlib import Path
import json
from datetime import datetime
from .qdrant_manager import QdrantManager
from .code_processor import CodeProcessor
from openai import OpenAI
import os
import streamlit as st 

class EmbeddingsManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(EmbeddingsManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, anthropic_client: Anthropic, cache_dir: str = "data/embeddings_cache"):
        if not hasattr(self, 'initialized'):
            self.anthropic_client = anthropic_client
            self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.qdrant = QdrantManager()
            self.processor = CodeProcessor()
            self.cache_dir = Path(cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.logger = logging.getLogger(__name__)
            self.initialized = True

    async def process_repository(self, repo_url: str, files: List[Dict]) -> None:
        """Process repository files and generate embeddings"""
        with st.sidebar.expander("🧮 Embeddings Debug", expanded=True):
            st.write("Processing repository for embeddings...")
            st.write(f"Number of files: {len(files)}")
            
            # Show files being processed
            st.write("\n📄 Files to process:")
            for file in files:
                st.write(f"- {file['path']} (size: {file['size']} bytes)")
            
            # Process files into chunks
            chunks_with_metadata = []
            st.write("\n🔍 Processing chunks:")
            
            for file_info in files:
                try:
                    chunks = self.processor.process_file(
                        file_info['path'],
                        file_info['content']
                    )
                    st.write(f"\nFile: {file_info['path']}")
                    st.write(f"Chunks found: {len(chunks)}")
                    for chunk, metadata in chunks:
                        st.write(f"- {metadata.get('type', 'unknown')}: {metadata.get('name', 'unnamed')}")
                    chunks_with_metadata.extend(chunks)
                except Exception as e:
                    st.write(f"❌ Error processing {file_info['path']}: {str(e)}")

            st.write(f"\nTotal chunks generated: {len(chunks_with_metadata)}")
            
            # Generate and store embeddings
            st.write("\n🔤 Generating embeddings:")
            batch_size = 10
            for i in range(0, len(chunks_with_metadata), batch_size):
                batch = chunks_with_metadata[i:i + batch_size]
                try:
                    texts = [self._prepare_text_for_embedding(chunk[0], chunk[1]) 
                            for chunk in batch]
                    embeddings = await self._generate_embeddings(texts)
                    await self.qdrant.store_code_vectors(embeddings, [chunk[1] for chunk in batch])
                    st.write(f"✅ Processed batch {i//batch_size + 1}")
                except Exception as e:
                    st.write(f"❌ Error in batch {i//batch_size + 1}: {str(e)}")

    async def search_code(self, query: str, limit: int = 5) -> List[Dict]:
        """Search for relevant code using semantic search"""
        try:
            # Generate embedding for query
            query_embedding = await self._generate_embeddings([query])
            
            # Search Qdrant
            results = await self.qdrant.search_code(
                query_vector=query_embedding[0],
                limit=limit
            )
            
            # Ensure code content is included in results
            for result in results:
                if 'content' not in result and 'file' in result:
                    # Try to get content from original file if not in metadata
                    try:
                        with open(result['file'], 'r') as f:
                            result['content'] = f.read()
                    except Exception:
                        pass
            
            return results
        except Exception as e:
            self.logger.error(f"Error searching code: {str(e)}")
            return []

    async def _generate_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings using OpenAI's API"""
        try:
            embeddings = []
            for text in texts:
                response = self.openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text,
                    encoding_format="float"
                )
                embeddings.append(np.array(response.data[0].embedding))
            return embeddings
        except Exception as e:
            self.logger.error(f"Error generating embeddings: {str(e)}")
            raise

    def _prepare_text_for_embedding(self, code: str, metadata: Dict) -> str:
        """Prepare code text for embedding"""
        # Include the actual code content in metadata
        """Prepare code text for embedding with enhanced async awareness"""
        metadata['content'] = code
        
        context_parts = [
            f"File: {metadata.get('file', '')}",
            f"Type: {metadata.get('code_type', 'unknown')}"
        ]
        
        if metadata.get('is_async'):
            context_parts.append("Async: Yes")
        
        if metadata.get('name'):
            context_parts.append(f"Name: {metadata.get('name')}")
        
        # Add decorator information
        if metadata.get('decorators'):
            context_parts.append(f"Decorators: {', '.join(metadata.get('decorators', []))}")
        
        context = "\n".join(context_parts)
        
        # Enhance code context for better semantic search
        return f"{context}\n\nCode Content:\n{code}"

    def _generate_repo_hash(self, repo_url: str, files: List[Dict]) -> str:
        """Generate a hash for the repository state"""
        content = repo_url + json.dumps([
            {
                'path': f.get('path', ''),
                'last_modified': str(f.get('last_modified', '')),
                'size': f.get('size', 0)
            }
            for f in files
        ])
        return str(hash(content))

    def _has_cached_embeddings(self, repo_hash: str) -> bool:
        """Check if we have cached embeddings"""
        cache_file = self.cache_dir / f"{repo_hash}.json"
        return cache_file.exists()

    def _cache_embeddings(self, repo_hash: str):
        """Cache repository embeddings state"""
        cache_file = self.cache_dir / f"{repo_hash}.json"
        cache_file.write_text(json.dumps({
            'cached_at': datetime.now().isoformat(),
            'hash': repo_hash
        }))
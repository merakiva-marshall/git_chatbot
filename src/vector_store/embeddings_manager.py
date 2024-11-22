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
import re 

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
        # Add a progress indicator
        progress_placeholder = st.sidebar.empty()
        progress_bar = st.sidebar.progress(0)
        total_batches = 0
        processed_batches = 0

        with st.sidebar.expander("🧮 Embeddings Debug", expanded=True):
            st.write("Processing repository for embeddings...")
            st.write(f"Number of files: {len(files)}")

            # Process chunks
            chunks_with_metadata = []
            for file_info in files:
                try:
                    chunks = self.processor.process_file(
                        file_info['path'],
                        file_info['content']
                    )
                    chunks_with_metadata.extend(chunks)
                except Exception as e:
                    st.write(f"❌ Error processing {file_info['path']}: {str(e)}")

            # Calculate total batches
            batch_size = 10
            total_batches = (len(chunks_with_metadata) + batch_size - 1) // batch_size

            st.write(f"\nProcessing {len(chunks_with_metadata)} chunks in {total_batches} batches")

            # Generate and store embeddings
            for i in range(0, len(chunks_with_metadata), batch_size):
                batch = chunks_with_metadata[i:i + batch_size]
                try:
                    texts = [self._prepare_text_for_embedding(chunk[0], chunk[1]) 
                            for chunk in batch]

                    # Debug output for what's being embedded
                    for idx, (text, chunk) in enumerate(zip(texts, batch)):
                        st.write(f"""
                        🔤 Embedding chunk {i + idx + 1}:
                        📄 File: {chunk[1].get('file', 'unknown')}
                        📝 Type: {chunk[1].get('type', 'unknown')}
                        📊 Content length: {len(text)} chars
                        """)

                    embeddings = await self._generate_embeddings(texts)
                    await self.qdrant.store_code_vectors(embeddings, [chunk[1] for chunk in batch])
                    processed_batches += 1
                    progress_bar.progress(processed_batches / total_batches)
                    progress_placeholder.text(f"Processing batch {processed_batches}/{total_batches}")
                except Exception as e:
                    st.write(f"❌ Error in batch {i//batch_size + 1}: {str(e)}")

            # Clear progress indicators
            progress_bar.empty()
            progress_placeholder.empty()

            # Show completion message
            st.success(f"✅ Completed processing {len(chunks_with_metadata)} chunks with embeddings")

    # In src/vector_store/embeddings_manager.py, modify search_code:

    async def search_code(self, query: str, limit: int = 5) -> List[Dict]:
        """Search for relevant code using semantic search with enhanced results"""
        try:
            st.write("🔍 Debug: Searching for:", query)

            # Check if this is a direct file content request
            file_request_match = re.search(r'(?:show|get|give|display).*?(?:content|lines?).*?([\w\-./]+\.\w+)', query, re.IGNORECASE)

            query_embedding = await self._generate_embeddings([query])

            # Debug the search conditions
            search_params = {
                'query_vector': query_embedding[0],
                'limit': limit * 2,
                'score_threshold': 0.5
            }

            if file_request_match:
                file_name = file_request_match.group(1)
                st.write(f"📁 Looking specifically for file: {file_name}")
                search_params['filter_conditions'] = {'file_path': f"*{file_name}*"}
                search_params['score_threshold'] = 0.3

            st.write("🔍 Search parameters:", search_params)

            # Get results from Qdrant
            results = await self.qdrant.search_code(**search_params)

            st.write(f"📊 Debug: Found {len(results)} initial results")

            # Debug the full result structure
            st.write("🔍 Raw result structure (first result):")
            if results:
                st.write({
                    k: v for k, v in results[0].items() 
                    if k != 'content'  # Exclude content for cleaner output
                })

            processed_results = []
            for result in results:
                # Debug content availability
                st.write(f"""
                📄 Result from: {result.get('file_path', 'unknown')}
                📈 Score: {result.get('similarity_score', 0)}
                💡 Type: {result.get('code_type', 'unknown')}
                🗂 Has content: {'content' in result}
                📝 Content length: {len(result.get('content', ''))} chars
                🔑 Available keys: {list(result.keys())}
                """)

                # Try to get content from different possible locations
                content = (
                    result.get('content') or 
                    result.get('raw_content') or 
                    result.get('metadata', {}).get('raw_content') or 
                    result.get('metadata', {}).get('content', '')
                )

                processed_result = {
                    'file': result.get('file_path', ''),
                    'type': result.get('code_type', 'unknown'),
                    'content': content,
                    'similarity_score': result.get('similarity_score', 0),
                    'metadata': result.get('metadata', {}),
                }
                processed_results.append(processed_result)

            processed_results.sort(key=lambda x: x['similarity_score'], reverse=True)
            return processed_results[:limit]

        except Exception as e:
            st.error(f"Search error: {str(e)}")
            st.error("Full error:", exc_info=True)
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
        """Prepare code text for embedding with enhanced context"""
        # Store the actual code content in metadata
        metadata['raw_content'] = code

        context_parts = [
            f"File: {metadata.get('file', '')}",
            f"Type: {metadata.get('code_type', 'unknown')}",
            f"Content Type: {metadata.get('type', 'unknown')}"
        ]

        # Add line numbers if available
        if 'line_start' in metadata and 'line_end' in metadata:
            context_parts.append(f"Lines: {metadata['line_start']}-{metadata['line_end']}")

        # Add name if available
        if metadata.get('name'):
            context_parts.append(f"Name: {metadata['name']}")

        context = "\n".join(context_parts)

        # Include the full content with context
        full_text = f"{context}\n\nFull Content:\n{code}"

        return full_text

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
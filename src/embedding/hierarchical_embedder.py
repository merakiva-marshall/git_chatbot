from typing import Dict, List, Optional, Union
import numpy as np
from pathlib import Path
import logging
from pydantic import BaseModel
from ..core.codebase_structure import CodebaseStructure
from ..core.components import Component
import asyncio
from anthropic import Anthropic
from src.core.codebase_structure import FileInfo

class EmbeddingVector(BaseModel):
    """Represents an embedding vector with metadata"""
    vector: List[float]
    type: str
    context: Dict
    metadata: Dict

class HierarchicalEmbedding:
    """Manages hierarchical embeddings for different code elements"""

    def __init__(self, anthropic_client: Anthropic):
        self.client = anthropic_client
        self.logger = logging.getLogger(__name__)
        self.embeddings_cache = {}

    async def embed_codebase(self, codebase: CodebaseStructure) -> Dict[str, Dict[str, EmbeddingVector]]:
        """Generate hierarchical embeddings for the entire codebase"""
        try:
            embeddings = {
                'files': await self._embed_files(codebase),
                'components': await self._embed_components(codebase),
                'relationships': await self._embed_relationships(codebase),
                'patterns': await self._embed_patterns(codebase)
            }

            # Generate cross-reference embeddings
            embeddings['cross_references'] = await self._generate_cross_references(embeddings)

            return embeddings

        except Exception as e:
            self.logger.error(f"Error generating codebase embeddings: {str(e)}")
            raise

    async def _embed_files(self, codebase: CodebaseStructure) -> Dict[str, EmbeddingVector]:
        """Generate embeddings for source files"""
        file_embeddings = {}

        for file_path, file_info in codebase.files.items():
            try:
                # Prepare file context
                context = self._prepare_file_context(file_info, codebase)

                # Generate embedding
                vector = await self._generate_embedding(
                    content=file_info.content,
                    context=context,
                    element_type='file'
                )

                file_embeddings[str(file_path)] = EmbeddingVector(
                    vector=vector,
                    type='file',
                    context=context,
                    metadata={
                        'language': file_info.language,
                        'size': file_info.size,
                        'last_modified': file_info.last_modified
                    }
                )

            except Exception as e:
                self.logger.error(f"Error embedding file {file_path}: {str(e)}")

        return file_embeddings

    async def _embed_components(self, codebase: CodebaseStructure) -> Dict[str, EmbeddingVector]:
        """Generate embeddings for code components"""
        component_embeddings = {}

        for comp_key, component in codebase.components.items():
            try:
                # Prepare component context
                context = self._prepare_component_context(component, codebase)

                # Generate embedding
                vector = await self._generate_embedding(
                    content=self._get_component_content(component),
                    context=context,
                    element_type='component'
                )

                component_embeddings[comp_key] = EmbeddingVector(
                    vector=vector,
                    type=component.type,
                    context=context,
                    metadata={
                        'name': component.name,
                        'file_path': str(component.file_path),
                        'doc_string': component.doc_string
                    }
                )

            except Exception as e:
                self.logger.error(f"Error embedding component {comp_key}: {str(e)}")

        return component_embeddings

    async def _embed_relationships(self, codebase: CodebaseStructure) -> Dict[str, EmbeddingVector]:
        """Generate embeddings for component relationships"""
        relationship_embeddings = {}

        for rel_key, relationships in codebase.relationships.items():
            try:
                for rel in relationships:
                    # Prepare relationship context
                    context = self._prepare_relationship_context(rel, codebase)

                    # Generate embedding
                    vector = await self._generate_embedding(
                        content=self._get_relationship_content(rel),
                        context=context,
                        element_type='relationship'
                    )

                    relationship_embeddings[f"{rel_key}_{hash(str(rel))}"] = EmbeddingVector(
                        vector=vector,
                        type=rel['type'],
                        context=context,
                        metadata=rel
                    )

            except Exception as e:
                self.logger.error(f"Error embedding relationship {rel_key}: {str(e)}")

        return relationship_embeddings

    async def _generate_embedding(self, content: str, context: Dict, element_type: str) -> List[float]:
        """Generate embedding vector using Claude API"""
        try:
            # Format context and content for embedding
            formatted_text = self._format_for_embedding(content, context, element_type)

            # Generate embedding using Claude
            response = await self.client.embeddings.create(
                model="claude-3-haiku-20240307",
                input=formatted_text
            )

            return response.embeddings[0].values

        except Exception as e:
            self.logger.error(f"Error generating embedding: {str(e)}")
            raise

    def _format_for_embedding(self, content: str, context: Dict, element_type: str) -> str:
        """Format content and context for embedding generation"""
        formatted_text = f"Type: {element_type}\n\n"

        # Add context information
        formatted_text += "Context:\n"
        for key, value in context.items():
            formatted_text += f"{key}: {value}\n"

        # Add main content
        formatted_text += f"\nContent:\n{content}"

        return formatted_text

    def _prepare_file_context(self, file_info: 'FileInfo', codebase: CodebaseStructure) -> Dict:
        """Prepare context information for file embedding"""
        return {
            'language': file_info.language,
            'path': str(file_info.path),
            'size': file_info.size,
            'components': len([c for c in codebase.components.values() 
                             if c.file_path == file_info.path])
        }

    def _prepare_component_context(self, component: Component, codebase: CodebaseStructure) -> Dict:
        """Prepare context information for component embedding"""
        return {
            'type': component.type,
            'name': component.name,
            'file': str(component.file_path),
            'doc_string': component.doc_string,
            'relationships': len(codebase.get_component_relationships(component.name))
        }

    def _get_component_content(self, component: Component) -> str:
        """Extract relevant content from a component"""
        # Implementation depends on component type
        return ""  # Placeholder

    def _get_relationship_content(self, relationship: Dict) -> str:
        """Extract relevant content from a relationship"""
        # Implementation depends on relationship type
        return ""  # Placeholder
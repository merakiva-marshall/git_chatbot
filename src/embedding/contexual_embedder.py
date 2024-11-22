from typing import Dict, List, Optional, Union
import numpy as np
from pathlib import Path
import logging
from pydantic import BaseModel
from src.embedding.hierarchical_embedder import EmbeddingVector
from ..core.codebase_structure import CodebaseStructure

class ContextualEmbedder:
    """Manages context-aware embedding generation"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.context_cache = {}

    async def prepare_context(self, 
                            element: Union[str, Dict], 
                            context_type: str,
                            codebase: CodebaseStructure) -> Dict:
        """Prepare rich context for embedding generation"""
        try:
            cache_key = f"{context_type}:{hash(str(element))}"

            if cache_key in self.context_cache:
                return self.context_cache[cache_key]

            if context_type == 'file':
                context = await self._prepare_file_context(element, codebase)
            elif context_type == 'component':
                context = await self._prepare_component_context(element, codebase)
            elif context_type == 'relationship':
                context = await self._prepare_relationship_context(element, codebase)
            else:
                raise ValueError(f"Unknown context type: {context_type}")

            self.context_cache[cache_key] = context
            return context

        except Exception as e:
            self.logger.error(f"Error preparing context: {str(e)}")
            raise

    async def _prepare_file_context(self, file_path: str, codebase: CodebaseStructure) -> Dict:
        """Prepare context for file embedding"""
        try:
            # Get file information
            file_info = codebase.files[file_path]

            # Get components in file
            components = codebase.get_file_components(file_path)

            # Get file relationships
            relationships = self._get_file_relationships(file_path, codebase)

            # Build context
            context = {
                'file_info': {
                    'path': str(file_info.path),
                    'language': file_info.language,
                    'size': file_info.size,
                    'last_modified': file_info.last_modified
                },
                'components': [
                    {
                        'name': comp.name,
                        'type': comp.type,
                        'doc_string': comp.doc_string
                    }
                    for comp in components
                ],
                'relationships': relationships,
                'patterns': self._get_file_patterns(file_path, codebase)
            }

            return context

        except Exception as e:
            self.logger.error(f"Error preparing file context: {str(e)}")
            raise

    async def _prepare_component_context(self, component: Dict, codebase: CodebaseStructure) -> Dict:
        """Prepare context for component embedding"""
        try:
            # Get component relationships
            relationships = codebase.get_component_relationships(component['name'])

            # Get implementation patterns
            patterns = codebase.get_implementation_patterns(component['name'])

            # Build context
            context = {
                'component_info': {
                    'name': component['name'],
                    'type': component['type'],
                    'file_path': str(component['file_path']),
                    'doc_string': component.get('doc_string')
                },
                'relationships': relationships,
                'patterns': patterns,
                'dependencies': self._get_component_dependencies(component, codebase)
            }

            return context

        except Exception as e:
            self.logger.error(f"Error preparing component context: {str(e)}")
            raise

    def _get_file_relationships(self, file_path: str, codebase: CodebaseStructure) -> List[Dict]:
        """Get all relationships involving a file"""
        relationships = []

        for rel_key, rels in codebase.relationships.items():
            if file_path in rel_key:
                relationships.extend(rels)

        return relationships

    def _get_file_patterns(self, file_path: str, codebase: CodebaseStructure) -> List[Dict]:
        """Get implementation patterns in a file"""
        return [
            pattern for pattern in codebase.implementation_patterns.values()
            if file_path in pattern.get('files', [])
        ]

    def _get_component_dependencies(self, component: Dict, codebase: CodebaseStructure) -> List[Dict]:
        """Get dependencies for a component"""
        dependencies = []

        # Implementation depends on component type
        return dependencies
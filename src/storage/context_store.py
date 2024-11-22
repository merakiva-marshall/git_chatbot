from typing import Dict, List, Optional, Union
import json
from pathlib import Path
import logging
from datetime import datetime
from pydantic import BaseModel
import asyncio
from ..core.codebase_structure import CodebaseStructure

class ContextEntry(BaseModel):
    """Represents a stored context entry"""
    id: str
    type: str
    content: Dict
    metadata: Dict
    relationships: List[str]
    timestamp: datetime

class ContextStorage:
    """Manages storage and retrieval of code context"""

    def __init__(self, storage_path: str = "data/context"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self._cache = {}
        self._lock = asyncio.Lock()

    async def store_context(self, 
                          element_id: str,
                          context_type: str,
                          content: Dict,
                          metadata: Dict,
                          relationships: List[str]) -> str:
        """Store context information"""
        try:
            async with self._lock:
                entry = ContextEntry(
                    id=element_id,
                    type=context_type,
                    content=content,
                    metadata=metadata,
                    relationships=relationships,
                    timestamp=datetime.utcnow()
                )

                # Save to file
                file_path = self.storage_path / f"{element_id}.json"
                with open(file_path, 'w') as f:
                    json.dump(entry.dict(), f, default=str)

                # Update cache
                self._cache[element_id] = entry

                return element_id

        except Exception as e:
            self.logger.error(f"Error storing context: {str(e)}")
            raise

    async def get_context(self, element_id: str) -> Optional[ContextEntry]:
        """Retrieve context information"""
        try:
            # Check cache first
            if element_id in self._cache:
                return self._cache[element_id]

            # Load from file
            file_path = self.storage_path / f"{element_id}.json"
            if file_path.exists():
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    entry = ContextEntry(**data)
                    self._cache[element_id] = entry
                    return entry

            return None

        except Exception as e:
            self.logger.error(f"Error retrieving context: {str(e)}")
            return None

    async def update_context(self,
                           element_id: str,
                           updates: Dict) -> Optional[ContextEntry]:
        """Update existing context"""
        try:
            async with self._lock:
                entry = await self.get_context(element_id)
                if not entry:
                    return None

                # Update fields
                updated_data = entry.dict()
                updated_data.update(updates)
                updated_data['timestamp'] = datetime.utcnow()

                # Create new entry
                updated_entry = ContextEntry(**updated_data)

                # Save to file
                file_path = self.storage_path / f"{element_id}.json"
                with open(file_path, 'w') as f:
                    json.dump(updated_entry.dict(), f, default=str)

                # Update cache
                self._cache[element_id] = updated_entry

                return updated_entry

        except Exception as e:
            self.logger.error(f"Error updating context: {str(e)}")
            raise

    async def get_related_contexts(self, 
                                 element_id: str,
                                 max_depth: int = 2) -> List[ContextEntry]:
        """Get related context entries up to specified depth"""
        try:
            related = []
            visited = set()

            async def traverse(current_id: str, depth: int):
                if depth > max_depth or current_id in visited:
                    return

                visited.add(current_id)
                entry = await self.get_context(current_id)

                if entry:
                    related.append(entry)
                    for rel_id in entry.relationships:
                        await traverse(rel_id, depth + 1)

            await traverse(element_id, 0)
            return related

        except Exception as e:
            self.logger.error(f"Error getting related contexts: {str(e)}")
            return []

    async def build_context_graph(self, codebase: CodebaseStructure):
        """Build and store context graph for entire codebase"""
        try:
            # Store file contexts
            for file_path, file_info in codebase.files.items():
                await self.store_context(
                    element_id=str(file_path),
                    context_type='file',
                    content={'content': file_info.content},
                    metadata={
                        'language': file_info.language,
                        'size': file_info.size,
                        'last_modified': file_info.last_modified
                    },
                    relationships=[
                        str(comp.file_path) 
                        for comp in codebase.get_file_components(str(file_path))
                    ]
                )

            # Store component contexts
            for comp_key, component in codebase.components.items():
                await self.store_context(
                    element_id=comp_key,
                    context_type='component',
                    content={'content': component.__dict__},
                    metadata={
                        'type': component.type,
                        'name': component.name,
                        'file_path': str(component.file_path)
                    },
                    relationships=list(codebase.get_component_relationships(comp_key).keys())
                )

        except Exception as e:
            self.logger.error(f"Error building context graph: {str(e)}")
            raise
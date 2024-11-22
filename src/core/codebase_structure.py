import networkx as nx
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

@dataclass
class FileInfo:
    """Information about a source code file"""
    path: Path
    content: str
    language: str
    last_modified: str
    size: int
    version: Optional[str] = None

@dataclass
class ComponentInfo:
    """Information about a code component (class, function, etc)"""
    name: str
    type: str  # class, function, variable
    file_path: Path
    start_line: int
    end_line: int
    dependencies: List[str]
    callers: List[str]
    implementations: List[str]
    doc_string: Optional[str] = None

class CodebaseStructure:
    """Main class for storing codebase structure and relationships"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Storage structures
        self.files: Dict[str, FileInfo] = {}
        self.components: Dict[str, ComponentInfo] = {}
        self.relationships: Dict[str, List[Dict]] = {}
        self.implementation_patterns: Dict[str, Dict] = {}

        # Relationship graphs
        self.import_graph = nx.DiGraph()
        self.call_graph = nx.DiGraph()
        self.inheritance_graph = nx.DiGraph()

    def add_file(self, file_info: FileInfo) -> None:
        """Add a file to the codebase structure"""
        try:
            file_key = str(file_info.path)
            self.files[file_key] = file_info
            self.logger.info(f"Added file: {file_key}")
        except Exception as e:
            self.logger.error(f"Error adding file {file_info.path}: {str(e)}")
            raise

    def add_component(self, component: ComponentInfo) -> None:
        """Add a code component to the structure"""
        try:
            component_key = f"{component.file_path}:{component.name}"
            self.components[component_key] = component
            self.logger.info(f"Added component: {component_key}")
        except Exception as e:
            self.logger.error(f"Error adding component {component.name}: {str(e)}")
            raise

    def add_relationship(self, source: str, target: str, rel_type: str, metadata: Dict) -> None:
        """Add a relationship between components"""
        try:
            rel_key = f"{source}:{target}:{rel_type}"
            if rel_key not in self.relationships:
                self.relationships[rel_key] = []

            self.relationships[rel_key].append(metadata)

            # Update appropriate graph
            if rel_type == 'import':
                self.import_graph.add_edge(source, target, **metadata)
            elif rel_type == 'calls':
                self.call_graph.add_edge(source, target, **metadata)
            elif rel_type == 'inherits':
                self.inheritance_graph.add_edge(source, target, **metadata)

            self.logger.info(f"Added relationship: {rel_key}")
        except Exception as e:
            self.logger.error(f"Error adding relationship {rel_key}: {str(e)}")
            raise

    def get_file_components(self, file_path: str) -> List[ComponentInfo]:
        """Get all components in a file"""
        return [
            comp for comp in self.components.values()
            if str(comp.file_path) == file_path
        ]

    def get_component_relationships(self, component_name: str) -> Dict[str, List[Dict]]:
        """Get all relationships for a component"""
        return {
            rel_key: rel_data
            for rel_key, rel_data in self.relationships.items()
            if component_name in rel_key
        }

    def get_implementation_patterns(self, component_name: str) -> List[Dict]:
        """Get implementation patterns related to a component"""
        return [
            pattern for pattern in self.implementation_patterns.values()
            if component_name in pattern.get('components', [])
        ]
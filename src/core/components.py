from dataclasses import dataclass
from typing import List, Optional, Dict
from pathlib import Path

@dataclass
class Component:
    """Base class for code components"""
    name: str
    type: str
    file_path: Path
    start_line: int
    end_line: int
    doc_string: Optional[str] = None
    metadata: Optional[Dict] = None

@dataclass
class ClassComponent(Component):
    """Class component information"""
    methods: List[str]
    base_classes: List[str]
    instance_variables: List[str]
    class_variables: List[str]
    name: str
    type: str = "class"
    file_path: Optional[Path] = None
    start_line: int = 0
    end_line: int = 0
    doc_string: Optional[str] = None
    metadata: Optional[Dict] = None

@dataclass
class FunctionComponent(Component):
    """Function component information"""
    parameters: List[str]
    return_type: Optional[str]
    decorators: List[str]
    is_async: bool
    name: str
    type: str = "function"
    file_path: Optional[Path] = None
    start_line: int = 0
    end_line: int = 0
    doc_string: Optional[str] = None
    metadata: Optional[Dict] = None

@dataclass
class ModuleComponent(Component):
    """Module component information"""
    imports: List[str]
    exports: List[str]
    global_variables: List[str]
    name: str
    type: str = "module"
    file_path: Optional[Path] = None
    start_line: int = 0
    end_line: int = 0
    doc_string: Optional[str] = None
    metadata: Optional[Dict] = None
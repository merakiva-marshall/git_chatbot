from dataclasses import dataclass
from typing import Dict, Optional
from typing import List

@dataclass
class Relationship:
    """Base class for component relationships"""
    source: str
    target: str
    type: str
    weight: float
    context: Dict
    metadata: Optional[Dict] = None

@dataclass
class ImportRelationship(Relationship):
    """Import relationship between components"""
    is_relative: bool
    alias: Optional[str] = None

@dataclass
class CallRelationship(Relationship):
    """Function call relationship"""
    parameters: Dict
    call_type: str  # direct, indirect, super

@dataclass
class InheritanceRelationship(Relationship):
    """Class inheritance relationship"""
    inheritance_type: str  # single, multiple, interface
    override_methods: List[str]
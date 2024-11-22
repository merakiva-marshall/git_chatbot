import ast
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging
from dataclasses import dataclass
from core.components import (
    Component, ClassComponent, FunctionComponent, ModuleComponent
)
from core.codebase_structure import CodebaseStructure, FileInfo

@dataclass
class AnalysisResult:
    """Container for analysis results"""
    components: List[Component]
    imports: List[str]
    patterns: Dict[str, Dict]
    api_usage: Dict[str, List[Dict]]
    errors: List[str]

class CodeAnalyzer:
    """Analyzes source code files and extracts structured information"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.codebase = CodebaseStructure()

    async def analyze_file(self, file_path: Path, content: str) -> AnalysisResult:
        """Analyze a single file and extract its components and relationships"""
        try:
            file_info = FileInfo(
                path=file_path,
                content=content,
                language=self._detect_language(file_path),
                last_modified=None,  # Will be set by GitHub service
                size=len(content)
            )
            self.codebase.add_file(file_info)

            if file_path.suffix == '.py':
                return await self._analyze_python_file(file_path, content)
            elif file_path.suffix in ['.js', '.ts']:
                return await self._analyze_javascript_file(file_path, content)
            else:
                return await self._analyze_generic_file(file_path, content)

        except Exception as e:
            self.logger.error(f"Error analyzing {file_path}: {str(e)}")
            return AnalysisResult([], [], {}, {}, [str(e)])

    async def _analyze_python_file(self, file_path: Path, content: str) -> AnalysisResult:
        """Analyze Python source code"""
        try:
            tree = ast.parse(content)
            analyzer = PythonAnalyzer(file_path, content)

            # Collect components
            components = []
            imports = []
            patterns = {}
            api_usage = {}

            for node in ast.walk(tree):
                # Analyze classes
                if isinstance(node, ast.ClassDef):
                    class_component = analyzer.analyze_class(node)
                    components.append(class_component)

                # Analyze functions
                elif isinstance(node, ast.FunctionDef):
                    func_component = analyzer.analyze_function(node)
                    components.append(func_component)

                # Collect imports
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    imports.extend(analyzer.analyze_import(node))

            # Analyze patterns and API usage
            patterns = analyzer.identify_patterns(tree)
            api_usage = analyzer.analyze_api_usage(tree)

            return AnalysisResult(
                components=components,
                imports=imports,
                patterns=patterns,
                api_usage=api_usage,
                errors=[]
            )

        except Exception as e:
            self.logger.error(f"Error in Python analysis: {str(e)}")
            return AnalysisResult([], [], {}, {}, [str(e)])

    def _detect_language(self, file_path: Path) -> str:
        """Detect the programming language of a file"""
        extensions = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.jsx': 'React',
            '.tsx': 'React TypeScript',
            '.vue': 'Vue',
            '.java': 'Java',
            '.cpp': 'C++',
            '.h': 'C/C++ Header'
        }
        return extensions.get(file_path.suffix, 'Unknown')

class PythonAnalyzer:
    """Specialized analyzer for Python code"""

    def __init__(self, file_path: Path, content: str):
        self.file_path = file_path
        self.content = content
        self.lines = content.split('\n')

    def analyze_class(self, node: ast.ClassDef) -> ClassComponent:
        """Analyze a Python class definition"""
        methods = []
        instance_vars = []
        class_vars = []

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods.append(item.name)
            elif isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name):
                    instance_vars.append(item.target.id)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        class_vars.append(target.id)

        return ClassComponent(
            name=node.name,
            type='class',
            file_path=self.file_path,
            start_line=node.lineno,
            end_line=node.end_lineno,
            doc_string=ast.get_docstring(node),
            methods=methods,
            base_classes=[base.id for base in node.bases if isinstance(base, ast.Name)],
            instance_variables=instance_vars,
            class_variables=class_vars
        )

    def analyze_function(self, node: ast.FunctionDef) -> FunctionComponent:
        """Analyze a Python function definition"""
        return FunctionComponent(
            name=node.name,
            type='function',
            file_path=self.file_path,
            start_line=node.lineno,
            end_line=node.end_lineno,
            doc_string=ast.get_docstring(node),
            parameters=[arg.arg for arg in node.args.args],
            return_type=self._get_return_type(node),
            decorators=[self._get_decorator_name(dec) for dec in node.decorator_list],
            is_async=isinstance(node, ast.AsyncFunctionDef)
        )

    def analyze_import(self, node: ast.AST) -> List[str]:
        """Analyze Python import statements"""
        imports = []
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            imports.extend(f"{module}.{alias.name}" for alias in node.names)
        return imports

    def identify_patterns(self, tree: ast.AST) -> Dict[str, Dict]:
        """Identify common implementation patterns"""
        patterns = {}

        # Singleton pattern detection
        patterns.update(self._detect_singleton_pattern(tree))

        # Factory pattern detection
        patterns.update(self._detect_factory_pattern(tree))

        # Decorator pattern detection
        patterns.update(self._detect_decorator_pattern(tree))

        return patterns

    def analyze_api_usage(self, tree: ast.AST) -> Dict[str, List[Dict]]:
        """Analyze external API usage patterns"""
        api_usage = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    api_name = self._get_api_name(node)
                    if api_name:
                        if api_name not in api_usage:
                            api_usage[api_name] = []
                        api_usage[api_name].append({
                            'line': node.lineno,
                            'context': self._get_call_context(node)
                        })

        return api_usage

    def _get_return_type(self, node: ast.FunctionDef) -> Optional[str]:
        """Extract return type annotation if present"""
        if node.returns:
            return ast.unparse(node.returns)
        return None

    def _get_decorator_name(self, node: ast.AST) -> str:
        """Get the string representation of a decorator"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return node.func.id
        return ast.unparse(node)

    def _get_api_name(self, node: ast.Call) -> Optional[str]:
        """Get the full API name from a call node"""
        try:
            if isinstance(node.func, ast.Attribute):
                parts = []
                current = node.func
                while isinstance(current, ast.Attribute):
                    parts.append(current.attr)
                    current = current.value
                if isinstance(current, ast.Name):
                    parts.append(current.id)
                return '.'.join(reversed(parts))
        except:
            return None
        return None
from typing import Dict, List, Tuple, Optional
import ast
from pathlib import Path
import re
import logging
from dataclasses import dataclass
from functools import lru_cache
import tokenize
from io import StringIO

@dataclass
class CodeChunk:
    """Represents a processed code chunk with metadata"""
    content: str
    metadata: Dict
    importance: float = 1.0  # Higher values indicate more important chunks

class CodeProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Language-specific patterns
        self.LANGUAGE_PATTERNS = {
            'python': {
                'class': r'class\s+(\w+)',
                'function': r'(?:async\s+)?def\s+(\w+)',
                'import': r'^(?:from\s+[\w.]+\s+)?import\s+.*$',
                'decorator': r'@[\w.]+'
            },
            'javascript': {
                'class': r'class\s+(\w+)',
                'function': r'(?:async\s+)?function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s+)?\(',
                'import': r'import\s+.+\s+from\s+[\'"].*[\'"]',
                'export': r'export\s+(?:default\s+)?(?:class|function|const|let|var)'
            },
            'typescript': {
                'interface': r'interface\s+(\w+)',
                'type': r'type\s+(\w+)',
                'class': r'class\s+(\w+)',
                'function': r'(?:async\s+)?function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s+)?\(',
                'import': r'import\s+.+\s+from\s+[\'"].*[\'"]',
                'export': r'export\s+(?:default\s+)?(?:class|function|const|let|var)'
            }
        }

    def process_file(self, file_path: str, content: str) -> List[Tuple[str, Dict]]:
        """Process a code file into chunks with metadata"""
        try:
            ext = Path(file_path).suffix.lower()

            # Determine language and processing method
            if ext in ['.py']:
                return self._process_python(file_path, content)
            elif ext in ['.js', '.jsx']:
                return self._process_javascript(file_path, content, is_react='jsx' in ext)
            elif ext in ['.ts', '.tsx']:
                return self._process_typescript(file_path, content, is_react='tsx' in ext)
            else:
                return self._process_generic(file_path, content)

        except Exception as e:
            self.logger.error(f"Error processing {file_path}: {str(e)}")
            return self._process_generic(file_path, content)

    def _process_python(self, file_path: str, content: str) -> List[Tuple[str, Dict]]:
        """Process Python files with enhanced AST analysis"""
        chunks = []
        try:
            tree = ast.parse(content)

            # Extract imports first
            imports = self._extract_python_imports(tree)
            if imports:
                chunks.append((
                    imports,
                    {
                        'file': file_path,
                        'type': 'imports',
                        'code_type': 'python_imports',
                        'line_start': 1,
                        'importance': 0.8
                    }
                ))

            for node in ast.walk(tree):
                if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef)):
                    chunk_content = ast.get_source_segment(content, node)
                    if chunk_content:
                        # Get docstring if available
                        docstring = ast.get_docstring(node)

                        # Get decorators
                        decorators = [
                            ast.get_source_segment(content, d)
                            for d in node.decorator_list
                        ]

                        # Determine chunk type and importance
                        chunk_type = (
                            'async_function' if isinstance(node, ast.AsyncFunctionDef)
                            else 'function' if isinstance(node, ast.FunctionDef)
                            else 'class'
                        )

                        importance = self._calculate_importance(
                            chunk_type,
                            bool(decorators),
                            bool(docstring),
                            len(chunk_content)
                        )

                        chunks.append((
                            chunk_content,
                            {
                                'file': file_path,
                                'type': chunk_type,
                                'name': node.name,
                                'line_start': node.lineno,
                                'line_end': node.end_lineno,
                                'decorators': decorators,
                                'docstring': docstring,
                                'code_type': 'python',
                                'importance': importance
                            }
                        ))

            return chunks

        except Exception as e:
            self.logger.error(f"Error in Python processing: {str(e)}")
            return self._process_generic(file_path, content)

    def _process_javascript(self, file_path: str, content: str, is_react: bool = False) -> List[Tuple[str, Dict]]:
        """Process JavaScript/JSX files with React awareness"""
        chunks = []
        patterns = self.LANGUAGE_PATTERNS['javascript']

        # Extract imports first
        imports = self._extract_js_imports(content)
        if imports:
            chunks.append((
                imports,
                {
                    'file': file_path,
                    'type': 'imports',
                    'code_type': 'javascript_imports',
                    'importance': 0.8
                }
            ))

        # Split content into potential chunks
        lines = content.split('\n')
        current_chunk = []
        in_component = False

        for i, line in enumerate(lines):
            # React component detection
            if is_react and re.search(r'function\s+\w+\s*\([^)]*\)\s*{.*return\s*\(', line):
                in_component = True
                current_chunk = [line]
                continue

            # Class detection
            if re.search(patterns['class'], line):
                if current_chunk:
                    chunks.extend(self._process_chunk(current_chunk, file_path, i))
                current_chunk = [line]
                continue

            # Function detection
            if re.search(patterns['function'], line):
                if current_chunk:
                    chunks.extend(self._process_chunk(current_chunk, file_path, i))
                current_chunk = [line]
                continue

            if current_chunk:
                current_chunk.append(line)

        # Process final chunk
        if current_chunk:
            chunks.extend(self._process_chunk(current_chunk, file_path, len(lines)))

        return chunks

    def _process_typescript(self, file_path: str, content: str, is_react: bool = False) -> List[Tuple[str, Dict]]:
        """Process TypeScript/TSX files with type information"""
        chunks = []
        patterns = self.LANGUAGE_PATTERNS['typescript']

        # Extract imports and type definitions
        imports = self._extract_js_imports(content)
        if imports:
            chunks.append((
                imports,
                {
                    'file': file_path,
                    'type': 'imports',
                    'code_type': 'typescript_imports',
                    'importance': 0.8
                }
            ))

        # Process interfaces and types
        for match in re.finditer(patterns['interface'], content):
            interface_content = self._extract_block(content, match.start())
            if interface_content:
                chunks.append((
                    interface_content,
                    {
                        'file': file_path,
                        'type': 'interface',
                        'code_type': 'typescript',
                        'importance': 0.9
                    }
                ))

        # Process regular code chunks
        chunks.extend(self._process_javascript(file_path, content, is_react))

        return chunks

    def _process_generic(self, file_path: str, content: str) -> List[Tuple[str, Dict]]:
        """Process any file into reasonable chunks"""
        chunks = []
        lines = content.split('\n')
        chunk_size = 50  # Lines per chunk

        for i in range(0, len(lines), chunk_size):
            chunk_content = '\n'.join(lines[i:i + chunk_size])
            chunks.append((
                chunk_content,
                {
                    'file': file_path,
                    'type': 'generic',
                    'line_start': i + 1,
                    'line_end': min(i + chunk_size, len(lines)),
                    'code_type': 'unknown',
                    'importance': 0.5
                }
            ))

        return chunks

    @lru_cache(maxsize=100)
    def _calculate_importance(self, 
                            chunk_type: str, 
                            has_decorators: bool, 
                            has_docstring: bool,
                            length: int) -> float:
        """Calculate importance score for a code chunk"""
        base_score = {
            'class': 0.9,
            'async_function': 0.85,
            'function': 0.8,
            'imports': 0.7,
            'generic': 0.5
        }.get(chunk_type, 0.5)

        # Adjust for features
        if has_decorators:
            base_score += 0.1
        if has_docstring:
            base_score += 0.1

        # Adjust for length (prefer medium-sized chunks)
        length_factor = min(1.0, length / 500)  # Normalize length
        length_score = 1.0 - abs(0.5 - length_factor)  # Prefer chunks around 250 lines

        final_score = min(1.0, base_score + (length_score * 0.2))
        return round(final_score, 2)

    def _extract_python_imports(self, tree: ast.AST) -> Optional[str]:
        """Extract and format Python imports"""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(n.name for n in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                imports.extend(f"{module}.{n.name}" for n in node.names)

        return '\n'.join(f"import {imp}" for imp in imports) if imports else None

    def _extract_js_imports(self, content: str) -> Optional[str]:
        """Extract and format JavaScript/TypeScript imports"""
        import_pattern = r'^import\s+(?:{[^}]+}|[^;]+)\s+from\s+[\'"]([^\'"]+)[\'"];?\s*$'
        imports = re.findall(import_pattern, content, re.MULTILINE)
        return '\n'.join(imports) if imports else None

    def _extract_block(self, content: str, start_pos: int) -> Optional[str]:
        """Extract a complete code block starting from a position"""
        opener = '{'
        closer = '}'
        stack = []

        block_content = []
        in_block = False

        for i, char in enumerate(content[start_pos:]):
            if char == opener:
                stack.append(char)
                in_block = True
            elif char == closer:
                stack.pop()

            if in_block:
                block_content.append(char)

            if in_block and not stack:
                return ''.join(block_content)

        return None

    def _process_chunk(self, chunk_lines: List[str], file_path: str, line_number: int) -> List[Tuple[str, Dict]]:
        """Process a potential code chunk"""
        content = '\n'.join(chunk_lines)
        chunk_type = self._determine_chunk_type(content)

        return [(
            content,
            {
                'file': file_path,
                'type': chunk_type,
                'line_start': line_number - len(chunk_lines) + 1,
                'line_end': line_number,
                'code_type': 'javascript',
                'importance': self._calculate_importance(
                    chunk_type,
                    False,  # has_decorators
                    bool(re.search(r'/\*\*[\s\S]*?\*/', content)),  # has_docstring (JSDoc)
                    len(chunk_lines)
                )
            }
        )]

    def _determine_chunk_type(self, content: str) -> str:
        """Determine the type of a code chunk"""
        if re.search(r'class\s+\w+', content):
            return 'class'
        elif re.search(r'function\s+\w+', content):
            return 'function'
        elif re.search(r'const\s+\w+\s*=\s*\(', content):
            return 'arrow_function'
        elif re.search(r'interface\s+\w+', content):
            return 'interface'
        elif re.search(r'type\s+\w+', content):
            return 'type'
        else:
            return 'generic'
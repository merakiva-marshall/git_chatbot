from typing import Dict, List, Tuple
import ast
from pathlib import Path
import re

class CodeProcessor:
    def process_file(self, file_path: str, content: str) -> List[Tuple[str, Dict]]:
        """Process a code file into chunks with metadata"""
        ext = Path(file_path).suffix.lower()
        
        if ext == '.py':
            return self._process_python(file_path, content)
        elif ext in ['.js', '.ts', '.jsx', '.tsx']:
            return self._process_javascript(file_path, content)
        else:
            return self._process_generic(file_path, content)

    def _process_python(self, file_path: str, content: str) -> List[Tuple[str, Dict]]:
        """Process Python files into logical chunks with async support"""
        chunks = []
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                # Add AsyncFunctionDef to the check
                if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef)):
                    chunk_content = ast.get_source_segment(content, node)
                    if chunk_content:
                        chunks.append((
                            chunk_content,
                            {
                                'file': file_path,
                                'type': type(node).__name__,
                                'name': node.name,
                                'line_start': node.lineno,
                                'line_end': node.end_lineno,
                                'code_type': 'async_function' if isinstance(node, ast.AsyncFunctionDef) 
                                           else 'function' if isinstance(node, ast.FunctionDef) 
                                           else 'class',
                                'is_async': isinstance(node, ast.AsyncFunctionDef),
                                'decorators': [ast.get_source_segment(content, d) for d in node.decorator_list]
                            }
                        ))
            
            # Keep your existing imports handling
            imports = self._extract_imports(content)
            if imports:
                chunks.append((
                    imports,
                    {
                        'file': file_path,
                        'type': 'imports',
                        'line_start': 1,
                        'code_type': 'imports'
                    }
                ))
            
            return chunks
        except Exception:
            return self._process_generic(file_path, content)

    def _process_javascript(self, file_path: str, content: str) -> List[Tuple[str, Dict]]:
        """Process JavaScript/TypeScript files into logical chunks"""
        chunks = []
        
        # Extract imports
        import_pattern = r'^import\s+.+?;?\s*$'
        imports = '\n'.join(re.findall(import_pattern, content, re.MULTILINE))
        if imports:
            chunks.append((
                imports,
                {
                    'file': file_path,
                    'type': 'imports',
                    'code_type': 'imports'
                }
            ))
        
        # Extract functions and classes using regex
        patterns = [
            (r'(?:export\s+)?(?:default\s+)?class\s+(\w+)[^{]*{(?:[^{}]*|{[^{}]*})*}', 'class'),
            (r'(?:export\s+)?(?:async\s+)?function\s+(\w+)[^{]*{(?:[^{}]*|{[^{}]*})*}', 'function'),
            (r'const\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[^=]*)=>\s*{(?:[^{}]*|{[^{}]*})*}', 'arrow_function')
        ]
        
        for pattern, chunk_type in patterns:
            for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
                chunks.append((
                    match.group(0),
                    {
                        'file': file_path,
                        'type': chunk_type,
                        'name': match.group(1),
                        'code_type': chunk_type
                    }
                ))
        
        return chunks

    def _process_generic(self, file_path: str, content: str) -> List[Tuple[str, Dict]]:
        """Process any file into chunks"""
        # Split by reasonable chunk size
        chunk_size = 1000
        lines = content.splitlines()
        chunks = []
        
        for i in range(0, len(lines), chunk_size):
            chunk_content = '\n'.join(lines[i:i + chunk_size])
            chunks.append((
                chunk_content,
                {
                    'file': file_path,
                    'type': 'generic',
                    'line_start': i + 1,
                    'line_end': min(i + chunk_size, len(lines)),
                    'code_type': 'generic'
                }
            ))
        
        return chunks

    def _extract_imports(self, content: str) -> str:
        """Extract import statements"""
        import_lines = []
        for line in content.splitlines():
            if line.strip().startswith(('import ', 'from ')):
                import_lines.append(line)
        return '\n'.join(import_lines)
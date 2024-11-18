import ast
import re
from typing import Dict, List, Optional
import logging

class CodeAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_code(self, file_path: str, content: str) -> Dict:
        """Analyze code content based on file type"""
        ext = file_path.split('.')[-1].lower()
        
        try:
            if ext in ['py']:
                return self._analyze_python(content)
            elif ext in ['js', 'ts', 'jsx', 'tsx']:
                return self._analyze_javascript(content)
            else:
                return self._analyze_generic(content)
        except Exception as e:
            self.logger.warning(f"Error analyzing {file_path}: {str(e)}")
            return {}

    def _analyze_python(self, content: str) -> Dict:
        """Analyze Python code structure"""
        try:
            tree = ast.parse(content)
            analysis = {
                'imports': [],
                'classes': [],
                'functions': [],
                'variables': [],
                'entry_points': []
            }
            
            for node in ast.walk(tree):
                # Import statements
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            analysis['imports'].append(name.name)
                    else:
                        module = node.module or ''
                        for name in node.names:
                            analysis['imports'].append(f"{module}.{name.name}")
                
                # Class definitions
                elif isinstance(node, ast.ClassDef):
                    class_info = {
                        'name': node.name,
                        'methods': [m.name for m in node.body if isinstance(m, ast.FunctionDef)],
                        'line_number': node.lineno
                    }
                    analysis['classes'].append(class_info)
                
                # Function definitions
                elif isinstance(node, ast.FunctionDef):
                    func_info = {
                        'name': node.name,
                        'line_number': node.lineno,
                        'args': [arg.arg for arg in node.args.args]
                    }
                    analysis['functions'].append(func_info)
                
                # Main block detection
                elif isinstance(node, ast.If):
                    if isinstance(node.test, ast.Compare):
                        if isinstance(node.test.left, ast.Name):
                            if node.test.left.id == '__name__' and \
                               any('__main__' in str(comp) for comp in node.test.comparators):
                                analysis['entry_points'].append('__main__ block')
            
            return analysis
        except Exception as e:
            self.logger.warning(f"Error in Python analysis: {str(e)}")
            return {}

    def _analyze_javascript(self, content: str) -> Dict:
        """Analyze JavaScript/TypeScript code structure"""
        analysis = {
            'imports': [],
            'exports': [],
            'functions': [],
            'classes': [],
            'entry_points': []
        }
        
        try:
            # Import detection
            import_pattern = r'import\s+(?:{[^}]+}|[^;]+)\s+from\s+[\'"]([^\'"]+)[\'"]'
            analysis['imports'] = re.findall(import_pattern, content)
            
            # Export detection
            export_pattern = r'export\s+(?:default\s+)?(?:class|function|const|let|var)\s+(\w+)'
            analysis['exports'] = re.findall(export_pattern, content)
            
            # Function detection
            function_pattern = r'(?:function|const|let|var)\s+(\w+)\s*=?\s*(?:\(|\basync\b\s*\()'
            analysis['functions'] = re.findall(function_pattern, content)
            
            # Class detection
            class_pattern = r'class\s+(\w+)'
            analysis['classes'] = re.findall(class_pattern, content)
            
            # Entry point detection (e.g., Next.js pages, React components)
            if 'export default' in content:
                analysis['entry_points'].append('default export')
            if re.search(r'ReactDOM\.render|createRoot', content):
                analysis['entry_points'].append('React entry point')
            
            return analysis
        except Exception as e:
            self.logger.warning(f"Error in JavaScript analysis: {str(e)}")
            return {}

    def _analyze_generic(self, content: str) -> Dict:
        """Basic analysis for other file types"""
        return {
            'line_count': len(content.splitlines()),
            'byte_size': len(content.encode('utf-8')),
            'has_config': any(marker in content.lower() 
                            for marker in ['config', 'settings', 'env', 'secret'])
        }
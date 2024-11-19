from github import Github
from typing import Dict, List, Optional
import base64
import logging
from pathlib import Path
import os
import re
from vector_store.embeddings_manager import EmbeddingsManager

class GitHubService:
    def __init__(self, github_token: str, embeddings_manager: Optional[EmbeddingsManager] = None):
        self.client = Github(github_token)
        self.embeddings_manager = embeddings_manager
        self._setup_logging()
        
    def _setup_logging(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    async def analyze_repository(self, repo_url: str) -> Dict:
        """Analyze a GitHub repository comprehensively"""
        self.logger.info(f"Starting analysis of repository: {repo_url}")
               
        
        try:
            # Extract repository name from URL
            repo_name = repo_url.split('github.com/')[-1].rstrip('/')
            if repo_name.endswith('.git'):
                repo_name = repo_name[:-4]
            
            # Get repository
            repo = self.client.get_repo(repo_name)
            
            # Get basic info first
            repo_info = {
                'name': repo.name,
                'full_name': repo.full_name,
                'description': repo.description,
                'default_branch': repo.default_branch,
                'stars': repo.stargazers_count,
                'forks': repo.forks_count,
                'last_updated': repo.updated_at.isoformat(),
                'language': repo.language,
                'topics': repo.get_topics(),
                'visibility': 'private' if repo.private else 'public',
                'size': repo.size,
                'open_issues': repo.open_issues_count
            }

            # Get root contents for file count
            try:
                root_contents = repo.get_contents("")
                repo_info['root_files'] = len(root_contents) if isinstance(root_contents, list) else 1
            except Exception as e:
                self.logger.warning(f"Error getting root contents: {str(e)}")
                repo_info['root_files'] = 0

            # Try to get structure info
            try:
                structure_info = self._analyze_repository_structure(repo)
                repo_info.update(structure_info)
            except Exception as e:
                self.logger.warning(f"Error analyzing structure: {str(e)}")

            # Process files for embeddings if manager is available
            if self.embeddings_manager and structure_info.get('code_files'):
                files_content = []
                for file_info in structure_info.get('code_files', []):
                    try:
                        content = self.get_file_content(repo.full_name, file_info['path'])
                        if content:
                            files_content.append({
                                'path': file_info['path'],
                                'content': content,
                                'last_modified': file_info.get('last_modified')
                            })
                    except Exception as e:
                        self.logger.warning(f"Error getting content for {file_info['path']}: {str(e)}")

                # Process files and generate embeddings
                if files_content:
                    await self.embeddings_manager.process_repository(repo_url, files_content)

            # Add code relationships
            if structure_info.get('code_files'):
                code_relationships = self._analyze_code_relationships(repo, structure_info['code_files'])
                repo_info['code_relationships'] = code_relationships

            # Try to get dependency info
            try:
                dependencies = self._analyze_dependencies(repo)
                repo_info['dependencies'] = dependencies
            except Exception as e:
                self.logger.warning(f"Error analyzing dependencies: {str(e)}")

            # Try to get README
            try:
                readme_content = self._get_readme_content(repo)
                if readme_content:
                    repo_info['readme'] = readme_content
            except Exception as e:
                self.logger.warning(f"Error getting README: {str(e)}")

            self.logger.info("Repository analysis completed successfully")
            return repo_info
            
        except Exception as e:
            self.logger.error(f"Error in repository analysis: {str(e)}")
            raise Exception(f"Error analyzing repository: {str(e)}")

    def _analyze_repository_structure(self, repo) -> Dict:
        """Analyze the repository's file structure with debugging"""
        structure = {
            'file_types': {},
            'directories': [],
            'total_files': 0,
            'code_files': []
        }
        
        def process_contents(path: str = ''):
            try:
                # Debug log
                self.logger.info(f"Processing path: {path}")
                
                contents = repo.get_contents(path)
                if not isinstance(contents, list):
                    contents = [contents]
                
                for item in contents:
                    try:
                        if item.type == 'dir':
                            structure['directories'].append(item.path)
                            # Debug log
                            self.logger.info(f"Found directory: {item.path}")
                            process_contents(item.path)
                        else:
                            structure['total_files'] += 1
                            ext = Path(item.path).suffix
                            structure['file_types'][ext] = structure['file_types'].get(ext, 0) + 1
                            
                            if self._is_code_file(item.path):
                                # Debug log
                                self.logger.info(f"Found code file: {item.path}")
                                structure['code_files'].append({
                                    'path': item.path,
                                    'size': item.size,
                                    'type': ext
                                })
                    except Exception as e:
                        self.logger.warning(f"Error processing item {item.path}: {str(e)}")
            except Exception as e:
                self.logger.warning(f"Error accessing path {path}: {str(e)}")

        process_contents()
        
        # Debug summary
        self.logger.info(f"Analysis complete. Found:")
        self.logger.info(f"- {len(structure['directories'])} directories")
        self.logger.info(f"- {structure['total_files']} total files")
        self.logger.info(f"- {len(structure['code_files'])} code files")
        
        return structure

    def _analyze_dependencies(self, repo) -> Dict:
        """Analyze repository dependencies"""
        dependencies = {
            'package_json': None,
            'requirements_txt': None,
            'pipfile': None,
            'poetry': None
        }
        
        dependency_files = [
            'package.json',
            'requirements.txt',
            'Pipfile',
            'pyproject.toml'
        ]

        for file_name in dependency_files:
            try:
                file_content = repo.get_contents(file_name)
                content = base64.b64decode(file_content.content).decode('utf-8')
                key = file_name.replace('.', '_').replace('-', '_').lower()
                dependencies[key] = content
            except Exception:
                continue

        return dependencies
    
    def _analyze_code_relationships(self, repo, code_files: List[Dict]) -> Dict:
        """Analyze relationships between code files"""
        relationships = {
            'imports_graph': {},
            'entry_points': [],
            'component_hierarchy': {},
            'code_analysis': {}
        }
        
        for file_info in code_files:
            try:
                content = None
                try:
                    file_content = repo.get_contents(file_info['path'])
                    content = base64.b64decode(file_content.content).decode('utf-8')
                except Exception as e:
                    self.logger.warning(f"Error getting content for {file_info['path']}: {str(e)}")
                    continue

                if content:
                    # Basic code analysis based on file type
                    ext = file_info['type'].lower()
                    
                    # Track imports using simple regex patterns
                    imports = []
                    if ext in ['.py']:
                        # Python imports
                        import_patterns = [
                            r'from\s+(\S+)\s+import',
                            r'import\s+(\S+)'
                        ]
                        for pattern in import_patterns:
                            imports.extend(re.findall(pattern, content))
                    
                    elif ext in ['.js', '.jsx', '.ts', '.tsx']:
                        # JavaScript/TypeScript imports
                        import_pattern = r'import\s+(?:{[^}]+}|[^;]+)\s+from\s+[\'"]([^\'"]+)[\'"]'
                        imports.extend(re.findall(import_pattern, content))
                    
                    if imports:
                        relationships['imports_graph'][file_info['path']] = list(set(imports))
                    
                    # Track potential entry points
                    if 'main' in file_info['path'].lower() or 'index' in file_info['path'].lower():
                        relationships['entry_points'].append(file_info['path'])
                    
                    # Basic code analysis
                    relationships['code_analysis'][file_info['path']] = {
                        'size': file_info['size'],
                        'type': file_info['type'],
                        'line_count': len(content.splitlines()),
                    }

            except Exception as e:
                self.logger.warning(f"Error analyzing {file_info['path']}: {str(e)}")
        
        return relationships

    def _get_readme_content(self, repo) -> Optional[str]:
        """Get repository README content"""
        try:
            readme = repo.get_readme()
            return base64.b64decode(readme.content).decode('utf-8')
        except Exception:
            return None

    def _is_code_file(self, path: str) -> bool:
        """Determine if a file is a code file based on extension"""
        code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c',
            '.h', '.cs', '.rb', '.php', '.go', '.rs', '.swift', '.kt',
            '.dart', '.vue', '.scala', '.r', '.jl'
        }
        return Path(path).suffix.lower() in code_extensions
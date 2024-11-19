from github import Github
from typing import Dict, List, Optional, Union
import base64
import logging
from pathlib import Path
import os
import re
import aiohttp
import asyncio
from github.Repository import Repository
from github.ContentFile import ContentFile

class GitHubService:
    def __init__(self, github_token: str):
        self.client = Github(github_token)
        self._setup_logging()
        
    def _setup_logging(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    async def analyze_repository(self, repo_url: str) -> Dict:
        """Analyze a GitHub repository comprehensively using async operations"""
        self.logger.info(f"Starting analysis of repository: {repo_url}")

        try:
            # Extract repository name from URL
            repo_name = repo_url.split('github.com/')[-1].rstrip('/')
            if repo_name.endswith('.git'):
                repo_name = repo_name[:-4]

            # Get repository - this is synchronous but only done once
            repo = self.client.get_repo(repo_name)

            # Basic info gathering is synchronous but quick
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

            # Run all async operations concurrently
            structure_info, dependencies, readme_content = await asyncio.gather(
                self._analyze_repository_structure(repo),
                self._analyze_dependencies(repo),
                self._get_readme_content(repo)
            )

            # Update repo_info with results
            repo_info.update(structure_info)
            repo_info['dependencies'] = dependencies
            if readme_content:
                repo_info['readme'] = readme_content

            # If we have code files, analyze their relationships
            if structure_info.get('code_files'):
                code_relationships = await self._analyze_code_relationships(repo, structure_info['code_files'])
                repo_info['code_relationships'] = code_relationships

            self.logger.info("Repository analysis completed successfully")
            return repo_info

        except Exception as e:
            self.logger.error(f"Error in repository analysis: {str(e)}")
            raise Exception(f"Error analyzing repository: {str(e)}")

    async def _analyze_repository_structure(self, repo: Repository) -> Dict:
        """Analyze the repository's file structure asynchronously"""
        structure = {
            'file_types': {},
            'directories': [],
            'total_files': 0,
            'code_files': []
        }
        
        async def process_contents(path: str = ''):
            try:
                contents = await self._get_contents(repo, path)
                if not isinstance(contents, list):
                    contents = [contents]
                
                for item in contents:
                    try:
                        if item.type == 'dir':
                            structure['directories'].append(item.path)
                            await process_contents(item.path)
                        else:
                            structure['total_files'] += 1
                            ext = Path(item.path).suffix
                            structure['file_types'][ext] = structure['file_types'].get(ext, 0) + 1
                            
                            if self._is_code_file(item.path):
                                structure['code_files'].append({
                                    'path': item.path,
                                    'size': item.size,
                                    'type': ext
                                })
                    except Exception as e:
                        self.logger.warning(f"Error processing item {item.path}: {str(e)}")
            except Exception as e:
                self.logger.warning(f"Error accessing path {path}: {str(e)}")

        await process_contents()
        return structure

    async def _analyze_dependencies(self, repo: Repository) -> Dict:
        """Analyze repository dependencies asynchronously"""
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

        async def get_file_content(file_name: str):
            try:
                file_content = await self._get_contents(repo, file_name)
                if file_content:
                    content = base64.b64decode(file_content.content).decode('utf-8')
                    key = file_name.replace('.', '_').replace('-', '_').lower()
                    dependencies[key] = content
            except Exception:
                pass

        # Get all dependency files concurrently
        await asyncio.gather(*[get_file_content(file_name) for file_name in dependency_files])
        return dependencies

    async def _analyze_code_relationships(self, repo: Repository, code_files: List[Dict]) -> Dict:
        """Analyze relationships between code files asynchronously"""
        relationships = {
            'imports_graph': {},
            'entry_points': [],
            'component_hierarchy': {},
            'code_analysis': {}
        }

        async def analyze_file(file_info: Dict):
            try:
                content = await self._get_file_content(repo, file_info['path'])
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

        # Analyze all files concurrently
        await asyncio.gather(*[analyze_file(file_info) for file_info in code_files])
        return relationships

    async def _get_readme_content(self, repo: Repository) -> Optional[str]:
        """Get repository README content asynchronously"""
        try:
            readme = await self._get_contents(repo, "README.md")
            if not readme:
                readme = await self._get_contents(repo, "README.rst")
            if readme:
                return base64.b64decode(readme.content).decode('utf-8')
        except Exception:
            return None
        return None

    async def _get_contents(self, repo: Repository, path: str) -> Union[ContentFile, List[ContentFile]]:
        """Get repository contents asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, repo.get_contents, path)

    async def _get_file_content(self, repo: Repository, path: str) -> Optional[str]:
        """Get file content asynchronously"""
        try:
            content = await self._get_contents(repo, path)
            if content:
                return base64.b64decode(content.content).decode('utf-8')
        except Exception as e:
            self.logger.warning(f"Error getting content for {path}: {str(e)}")
        return None

    def _is_code_file(self, path: str) -> bool:
        """Determine if a file is a code file based on extension"""
        code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c',
            '.h', '.cs', '.rb', '.php', '.go', '.rs', '.swift', '.kt',
            '.dart', '.vue', '.scala', '.r', '.jl'
        }
        return Path(path).suffix.lower() in code_extensions
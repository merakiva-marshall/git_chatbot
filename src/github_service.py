from github import Github
from typing import Dict, List, Optional, Tuple, Union, Any
from urllib.parse import urlparse, unquote
from pathlib import Path
import logging
import asyncio
import base64
import re
from github.Repository import Repository
from github.ContentFile import ContentFile
import time

class GitHubService:
    def __init__(self, github_token: str):
        self.client = Github(github_token)
        self.logger = self._setup_logging()
        self._content_cache = {}  # Track content retrievals
        self._current_commit_sha = None  # Track content retrievals

    def _setup_logging(self) -> logging.Logger:
        """Initialize logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logger = logging.getLogger(__name__)
        return logger

    async def verify_branch_content(self, repo_url: str, file_path: str) -> None:
        """Verify the exact content and metadata we're getting from GitHub"""
        try:
            repo_full_name, branch, path = self._parse_github_url(repo_url)
            repo = self.client.get_repo(repo_full_name)
            
            # Get branch information
            if branch:
                branch_obj = repo.get_branch(branch)
                self.logger.info(f"""
    Branch Information:
    - Name: {branch}
    - Latest commit SHA: {branch_obj.commit.sha}
    - Commit date: {branch_obj.commit.commit.author.date}
    - Commit message: {branch_obj.commit.commit.message}
    """)

                # Get the file content directly using the commit SHA
                file_content = await self._get_contents(repo, file_path, ref=branch_obj.commit.sha)
                if file_content:
                    content = base64.b64decode(file_content.content).decode('utf-8')
                    self.logger.info(f"""
    File Information:
    - Path: {file_path}
    - SHA: {file_content.sha}
    - Size: {len(content)} bytes
    - First 200 chars: 
    {content[:200]}
    """)
                    return content
                
        except Exception as e:
            self.logger.error(f"Verification failed: {str(e)}")
            raise

    # Update _get_contents method to always use commit SHA when possible:
    async def _get_contents(self, repo: Repository, path: str, ref: Optional[str] = None) -> Union[ContentFile, List[ContentFile]]:
        """Get repository contents asynchronously with branch support"""
        loop = asyncio.get_event_loop()
        try:
            self.logger.info(f"Getting contents for path: {path}, ref: {ref}")
            
            # If ref is a SHA (40 characters hex), use it directly
            if ref and len(ref) == 40 and all(c in '0123456789abcdef' for c in ref.lower()):
                self.logger.info(f"Using provided SHA: {ref}")
            # If ref is a branch name and we have a stored SHA, use that
            elif ref and hasattr(self, '_current_commit_sha') and self._current_commit_sha:
                ref = self._current_commit_sha
                self.logger.info(f"Using stored SHA: {ref}")
            # Only try to get branch SHA if we don't have a stored one
            elif ref and '/' not in ref:
                try:
                    branch = repo.get_branch(ref)
                    ref = branch.commit.sha
                    self.logger.info(f"Using commit SHA {ref} for branch {branch.name}")
                except Exception as e:
                    self.logger.warning(f"Could not get branch SHA, using ref as-is: {e}")

            result = await loop.run_in_executor(
                None, 
                lambda: repo.get_contents(path, ref=ref)
            )
            
            return result
        except Exception as e:
            self.logger.warning(f"Error getting contents for path {path} with ref {ref}: {str(e)}")
            raise

    async def tracked_get_contents(self, repo: Repository, path: str, ref: Optional[str] = None) -> Union[ContentFile, List[ContentFile]]:
        """Track all content retrievals"""
        self.logger.info(f"Attempting to get contents for {path}:{ref}")
        key = f"{path}:{ref}"
        if key not in self._content_cache:
            self.logger.info(f"Cache miss for {key}")
            content = await self._get_contents(repo, path, ref)
            self._content_cache[key] = {
                'time': time.time(),
                'content': content,
                'sha': getattr(content, 'sha', None)
            }
            self.logger.info(f"Cached content for {key} with SHA: {self._content_cache[key]['sha']}")
        return self._content_cache[key]['content']

    def _parse_github_url(self, url: str) -> Tuple[str, Optional[str], Optional[str]]:
        """Parse GitHub URL to extract owner, repo name, and branch/ref"""
        # Clean the URL
        url = url.strip().rstrip('/')
        
        # Parse URL
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split('/') if p]

        # Handle simple owner/repo format
        if len(path_parts) < 2:
            raise ValueError("Invalid GitHub URL format")

        owner = path_parts[0]
        repo_name = path_parts[1].replace('.git', '')
        repo_full_name = f"{owner}/{repo_name}"
        
        # Default values
        branch = None
        path = None

        # Handle tree/blob/branch format
        if len(path_parts) > 2:
            if path_parts[2] in ['tree', 'blob']:
                if len(path_parts) > 3:
                    branch = path_parts[3]
                    if len(path_parts) > 4:
                        path = '/'.join(path_parts[4:])
            else:
                # Might be a branch directly specified
                branch = path_parts[2]
                if len(path_parts) > 3:
                    path = '/'.join(path_parts[3:])

        # Add detailed logging
        if branch:
            self.logger.info(f"""
    URL Parsing Details:
    - Full URL: {url}
    - Parsed path parts: {path_parts}
    - Detected branch: {branch}
    - Detected path: {path}
    - Repository: {repo_full_name}
    """)

        return repo_full_name, branch, path


    async def analyze_repository(self, repo_url: str) -> Dict:
        """Analyze a` GitHub repository comprehensively using async operations"""
        self.logger.info(f"Starting analysis of repository: {repo_url}")
        self._content_cache.clear()  # Clear cache on new analysis

        try:
            # Parse the GitHub URL
            repo_full_name, branch, path = self._parse_github_url(repo_url)

            # Get repository
            repo = self.client.get_repo(repo_full_name)

            # If branch is specified, verify it exists
            if branch:
                try:
                    branch_obj = repo.get_branch(branch)
                    commit_sha = branch_obj.commit.sha
                    commit_date = branch_obj.commit.commit.committer.date
                    self.logger.info(f"""
            Analysis Details:
            - Repository: {repo_full_name}
            - Branch: {branch}
            - Commit SHA: {commit_sha}
            - Last Commit: {commit_date}
            """)
                    # Store the commit SHA for use in content retrieval
                    self._current_commit_sha = commit_sha
                except Exception as e:
                    # Check if branch exists in list of branches
                    try:
                        branches = [b.name for b in repo.get_branches()]
                        if branch in branches:
                            self.logger.info(f"Branch {branch} exists but couldn't get details")
                            # Continue with branch name instead of SHA
                        else:
                            self.logger.error(f"Branch {branch} not found in {branches}")
                            raise Exception(f"Branch {branch} not found in repository")
                    except Exception as branch_e:
                        self.logger.error(f"Error listing branches: {str(branch_e)}")
                        raise Exception(f"Could not` verify branch {branch}")
            # Basic info gathering is synchronous but quick
            repo_info = {
                'name': repo.name,
                'full_name': repo.full_name,
                'description': repo.description,
                'default_branch': repo.default_branch,
                'current_branch': branch or repo.default_branch,
                'current_path': path,
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
                self._analyze_repository_structure(repo, branch, path),
                self._analyze_dependencies(repo, branch, path),
                self._get_readme_content(repo, branch, path)
            )

            # Update repo_info with results
            repo_info.update(structure_info)
            repo_info['dependencies'] = dependencies
            if readme_content:
                repo_info['readme'] = readme_content

            # Add this debug logging
            self.logger.info(f"Structure info contains code files: {'code_files' in structure_info}")
            if 'code_files' in structure_info:
                self.logger.info(f"Number of code files found: {len(structure_info['code_files'])}")

            # If we have code files, analyze their relationships
            if structure_info.get('code_files'):
                code_relationships = await self._analyze_code_relationships(
                    repo, 
                    structure_info['code_files'],
                    branch
                )
                repo_info['code_relationships'] = code_relationships
                self.logger.info(f"Code relationships analyzed. Files: {list(code_relationships['code_analysis'].keys())}")

                # Add the actual file contents to the analysis
                file_contents = {}
                for file_path in repo_info['code_relationships']['code_analysis'].keys():
                    self.logger.info(f"Attempting to get content for {file_path}")
                    try:
                        content = await self.tracked_get_contents(repo, file_path, self._current_commit_sha)
                        if content:
                            file_contents[file_path] = base64.b64decode(content.content).decode('utf-8')
                            self.logger.info(f"Successfully got content for {file_path}")
                    except Exception as e:
                        self.logger.warning(f"Could not decode content for {file_path}: {e}")
                
                repo_info['file_contents'] = file_contents
                self.logger.info(f"Added contents for {len(file_contents)} files")

            self.logger.info("Repository analysis completed successfully")
            return repo_info

        except Exception as e:
            self.logger.error(f"Error in repository analysis: {str(e)}")
            raise Exception(f"Error analyzing repository: {str(e)}")

    def get_retrieval_stats(self) -> Dict:
        """Get statistics about content retrievals"""
        return {
            'cache_entries': len(self._content_cache),
            'paths_accessed': list(self._content_cache.keys()),
            'timestamps': {k: v['time'] for k, v in self._content_cache.items()},
            'shas': {k: v['sha'] for k, v in self._content_cache.items()}
        }

    async def _analyze_repository_structure(
        self, 
        repo: Repository, 
        branch: Optional[str] = None,
        start_path: Optional[str] = None
    ) -> Dict:
        """Analyze the repository's file structure asynchronously"""
        structure = {
            'file_types': {},
            'directories': [],
            'total_files': 0,
            'code_files': []
        }
        
        async def process_contents(path: str = ''):
            try:
                # Change this line to use tracked_get_contents
                contents = await self.tracked_get_contents(repo, path, branch)  # Changed from _get_contents
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

        # Start from the specified path or root
        initial_path = start_path if start_path else ''
        await process_contents(initial_path)
        return structure

    async def _analyze_code_relationships(
        self, 
        repo: Repository, 
        code_files: List[Dict],
        branch: Optional[str] = None
    ) -> Dict:
        """Analyze relationships between code files asynchronously"""
        relationships = {
            'imports_graph': {},
            'entry_points': [],
            'component_hierarchy': {},
            'code_analysis': {}
        }

        async def analyze_file(file_info: Dict):
            try:
                content_obj = await self.tracked_get_contents(repo, file_info['path'], self._current_commit_sha)
                if content_obj:
                    # Decode the content from the ContentFile object
                    content = base64.b64decode(content_obj.content).decode('utf-8')
                    
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

    async def _analyze_dependencies(
        self, 
        repo: Repository, 
        branch: Optional[str] = None,
        path: Optional[str] = None
    ) -> Dict:
        """Analyze repository dependencies asynchronously"""
        dependencies = {
            'package_json': None,
            'requirements_txt': None,
            'pipfile': None,
            'poetry': None
        }
        
        # Adjust paths based on the starting path
        base_path = path if path else ''
        
        dependency_files = [
            f'{base_path}/package.json' if base_path else 'package.json',
            f'{base_path}/requirements.txt' if base_path else 'requirements.txt',
            f'{base_path}/Pipfile' if base_path else 'Pipfile',
            f'{base_path}/pyproject.toml' if base_path else 'pyproject.toml'
        ]

        async def get_file_content(file_name: str):
            try:
                file_content = await self._get_contents(repo, file_name, branch)
                if file_content:
                    content = base64.b64decode(file_content.content).decode('utf-8')
                    key = Path(file_name).name.replace('.', '_').replace('-', '_').lower()
                    dependencies[key] = content
            except Exception:
                pass

        await asyncio.gather(*[get_file_content(file_name) for file_name in dependency_files])
        return dependencies

    async def _get_file_content(self, repo: Repository, path: str, branch: Optional[str] = None) -> Optional[str]:
        """Get file content asynchronously"""
        try:
            content = await self.tracked_get_contents(repo, path, self._current_commit_sha)
            if content:
                return base64.b64decode(content.content).decode('utf-8')
        except Exception as e:
            self.logger.warning(f"Error getting content for {path}: {str(e)}")
        return None

    async def _get_readme_content(self, repo: Repository, branch: Optional[str] = None, path: Optional[str] = None) -> Optional[str]:
        try:
            paths_to_try = []
            if path:
                paths_to_try.extend([
                    f"{path}/README.md",
                    f"{path}/README.rst"
                ])
            paths_to_try.extend(["README.md", "README.rst"])

            for readme_path in paths_to_try:
                try:
                    readme = await self.tracked_get_contents(repo, readme_path, self._current_commit_sha)
                    if readme:
                        return base64.b64decode(readme.content).decode('utf-8')
                except Exception:
                    continue
            return None
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
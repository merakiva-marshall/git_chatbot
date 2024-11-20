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
from vector_store.embeddings_manager import EmbeddingsManager

class GitHubService:
    def __init__(self, github_token: str, embeddings_manager: Optional[EmbeddingsManager] = None):
        self.client = Github(github_token)
        self.logger = self._setup_logging()
        self._content_cache = {}  # Track content retrievals
        self._current_commit_sha = None  # Track current commit SHA
        self.embeddings_manager = embeddings_manager
        self._setup_rate_limiting()

    def _setup_logging(self) -> logging.Logger:
        """Initialize logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logger = logging.getLogger(__name__)
        return logger

    def _setup_rate_limiting(self):
        """Setup rate limiting for GitHub API"""
        self._request_lock = asyncio.Lock()
        self._last_request_time = 0
        self.MIN_REQUEST_INTERVAL = 1  # seconds between requests

    async def verify_branch_content(self, repo_url: str, file_path: str) -> Optional[str]:
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

    async def _get_contents(self, repo: Repository, path: str, ref: Optional[str] = None) -> Union[ContentFile, List[ContentFile]]:
        """Get repository contents asynchronously with rate limiting"""
        async with self._request_lock:
            current_time = time.time()
            time_since_last_request = current_time - self._last_request_time
            if time_since_last_request < self.MIN_REQUEST_INTERVAL:
                await asyncio.sleep(self.MIN_REQUEST_INTERVAL - time_since_last_request)

            loop = asyncio.get_event_loop()
            try:
                self.logger.info(f"Getting contents for path: {path}, ref: {ref}")

                # Use commit SHA when possible
                if ref and len(ref) == 40 and all(c in '0123456789abcdef' for c in ref.lower()):
                    self.logger.info(f"Using provided SHA: {ref}")
                elif ref and self._current_commit_sha:
                    ref = self._current_commit_sha
                    self.logger.info(f"Using stored SHA: {ref}")
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

                self._last_request_time = time.time()
                return result

            except Exception as e:
                self.logger.warning(f"Error getting contents for path {path} with ref {ref}: {str(e)}")
                raise

    async def tracked_get_contents(self, repo: Repository, path: str, ref: Optional[str] = None) -> Union[ContentFile, List[ContentFile]]:
        """Track all content retrievals with caching"""
        self.logger.info(f"Attempting to get contents for {path}:{ref}")
        key = f"{path}:{ref}"

        if key in self._content_cache:
            cache_entry = self._content_cache[key]
            # Check if cache is still valid (1 hour)
            if time.time() - cache_entry['time'] < 3600:
                self.logger.info(f"Cache hit for {key}")
                return cache_entry['content']
            else:
                self.logger.info(f"Cache expired for {key}")
                del self._content_cache[key]

        self.logger.info(f"Cache miss for {key}")
        content = await self._get_contents(repo, path, ref)
        self._content_cache[key] = {
            'time': time.time(),
            'content': content,
            'sha': getattr(content, 'sha', None)
        }
        self.logger.info(f"Cached content for {key} with SHA: {self._content_cache[key]['sha']}")
        return content

    def _parse_github_url(self, url: str) -> Tuple[str, Optional[str], Optional[str]]:
        """Parse GitHub URL to extract owner, repo name, and branch/ref"""
        url = url.strip().rstrip('/')
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split('/') if p]

        if len(path_parts) < 2:
            raise ValueError("Invalid GitHub URL format")

        owner = path_parts[0]
        repo_name = path_parts[1].replace('.git', '')
        repo_full_name = f"{owner}/{repo_name}"

        branch = None
        path = None

        if len(path_parts) > 2:
            if path_parts[2] in ['tree', 'blob']:
                if len(path_parts) > 3:
                    branch = path_parts[3]
                    if len(path_parts) > 4:
                        path = '/'.join(path_parts[4:])
            else:
                branch = path_parts[2]
                if len(path_parts) > 3:
                    path = '/'.join(path_parts[3:])

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
        """Analyze a GitHub repository comprehensively with embedding support"""
        self.logger.info(f"Starting analysis of repository: {repo_url}")
        self._content_cache.clear()  # Clear cache on new analysis

        try:
            # Parse the GitHub URL
            repo_full_name, branch, path = self._parse_github_url(repo_url)
            repo = self.client.get_repo(repo_full_name)

            # Handle branch verification
            if branch:
                try:
                    branch_obj = repo.get_branch(branch)
                    self._current_commit_sha = branch_obj.commit.sha
                    self.logger.info(f"""
Analysis Details:
- Repository: {repo_full_name}
- Branch: {branch}
- Commit SHA: {self._current_commit_sha}
- Last Commit: {branch_obj.commit.commit.committer.date}
""")
                except Exception as e:
                    await self._handle_branch_error(repo, branch, e)

            # Gather basic repository information
            repo_info = await self._gather_basic_info(repo, branch, path)

            # Run analysis tasks concurrently
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

            # Process code relationships and generate embeddings
            if structure_info.get('code_files'):
                await self._process_code_files(repo_info, repo, structure_info['code_files'])

            self.logger.info("Repository analysis completed successfully")
            return repo_info

        except Exception as e:
            self.logger.error(f"Error in repository analysis: {str(e)}")
            raise Exception(f"Error analyzing repository: {str(e)}")

    async def _handle_branch_error(self, repo: Repository, branch: str, error: Exception):
        """Handle branch verification errors"""
        try:
            branches = [b.name for b in repo.get_branches()]
            if branch in branches:
                self.logger.info(f"Branch {branch} exists but couldn't get details")
            else:
                self.logger.error(f"Branch {branch} not found in {branches}")
                raise Exception(f"Branch {branch} not found in repository")
        except Exception as branch_e:
            self.logger.error(f"Error listing branches: {str(branch_e)}")
            raise Exception(f"Could not verify branch {branch}")

    async def _gather_basic_info(self, repo: Repository, branch: str, path: str) -> Dict:
        """Gather basic repository information"""
        return {
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

    async def _process_code_files(self, repo_info: Dict, repo: Repository, code_files: List[Dict]):
        """Process code files for relationships and embeddings"""
        # Analyze code relationships
        code_relationships = await self._analyze_code_relationships(
            repo, 
            code_files,
            self._current_commit_sha
        )
        repo_info['code_relationships'] = code_relationships

        # Get file contents
        file_contents = {}
        files_for_embedding = []

        for file_path in code_relationships['code_analysis'].keys():
            try:
                content = await self.tracked_get_contents(repo, file_path, self._current_commit_sha)
                if content:
                    decoded_content = base64.b64decode(content.content).decode('utf-8')
                    file_contents[file_path] = decoded_content

                    # Prepare for embedding
                    files_for_embedding.append({
                        'path': file_path,
                        'content': decoded_content,
                        'last_modified': repo_info['last_updated']
                    })
            except Exception as e:
                self.logger.warning(f"Could not process content for {file_path}: {e}")

        repo_info['file_contents'] = file_contents

        # Generate embeddings if manager is available
        if self.embeddings_manager and files_for_embedding:
            try:
                embedding_stats = await self.embeddings_manager.process_repository(
                    repo_info['full_name'],
                    files_for_embedding
                )
                repo_info['embedding_stats'] = embedding_stats
                repo_info['embedded_files'] = len(files_for_embedding)
            except Exception as e:
                self.logger.error(f"Error generating embeddings: {str(e)}")
                repo_info['embedding_error'] = str(e)

    async def _analyze_repository_structure(self, repo: Repository, branch: Optional[str] = None, path: Optional[str] = None) -> Dict:
        """Analyze the repository's file structure with debugging"""
        structure = {
            'file_types': {},
            'directories': [],
            'total_files': 0,
            'code_files': []
        }

        try:
            async def process_contents(current_path: str = ''):
                try:
                    self.logger.info(f"Processing path: {current_path}")

                    # Get contents using tracked method with proper ref
                    contents = await self.tracked_get_contents(
                        repo, 
                        current_path, 
                        ref=self._current_commit_sha if self._current_commit_sha else branch
                    )

                    if not isinstance(contents, list):
                        contents = [contents]

                    for item in contents:
                        try:
                            # If a specific path is provided, only process that path
                            if path and not item.path.startswith(path):
                                continue

                            if item.type == 'dir':
                                structure['directories'].append(item.path)
                                self.logger.info(f"Found directory: {item.path}")
                                await process_contents(item.path)
                            else:
                                structure['total_files'] += 1
                                ext = Path(item.path).suffix
                                structure['file_types'][ext] = structure['file_types'].get(ext, 0) + 1

                                if self._is_code_file(item.path):
                                    self.logger.info(f"Found code file: {item.path}")
                                    structure['code_files'].append({
                                        'path': item.path,
                                        'size': item.size,
                                        'type': ext,
                                        'sha': item.sha,
                                        'url': item.html_url,
                                        'last_modified': None  # Will be populated when content is retrieved
                                    })
                        except Exception as e:
                            self.logger.warning(f"Error processing item {item.path}: {str(e)}")
                            continue

                except Exception as e:
                    self.logger.warning(f"Error accessing path {current_path}: {str(e)}")
                    return

            # Start processing from the specified path or root
            initial_path = path if path else ''
            await process_contents(initial_path)

            # Debug summary
            self.logger.info(f"""
    Analysis complete:
    - Directories: {len(structure['directories'])}
    - Total files: {structure['total_files']}
    - Code files: {len(structure['code_files'])}
    - File types: {dict(structure['file_types'])}
            """)

            return structure

        except Exception as e:
            self.logger.error(f"Error in repository structure analysis: {str(e)}")
            raise

    def _is_code_file(self, path: str) -> bool:
        """Determine if a file is a code file based on extension"""
        code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c',
            '.h', '.cs', '.rb', '.php', '.go', '.rs', '.swift', '.kt',
            '.dart', '.vue', '.scala', '.r', '.jl'
        }
        return Path(path).suffix.lower() in code_extensions
    async def _analyze_dependencies(self, repo: Repository, branch: Optional[str] = None, path: Optional[str] = None) -> Dict:
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
                # Use tracked_get_contents to handle rate limiting and caching
                file_content = await self.tracked_get_contents(
                    repo,
                    file_name,
                    ref=self._current_commit_sha if self._current_commit_sha else branch
                )

                if file_content:
                    content = base64.b64decode(file_content.content).decode('utf-8')
                    key = file_name.replace('.', '_').replace('-', '_').lower()
                    dependencies[key] = content
                    self.logger.info(f"Found dependency file: {file_name}")
            except Exception as e:
                self.logger.debug(f"Dependency file {file_name} not found: {str(e)}")
                continue

        # Additional dependency analysis
        try:
            # Look for other potential dependency files in the repository
            additional_patterns = [
                'yarn.lock',
                'package-lock.json',
                'poetry.lock',
                'Pipfile.lock',
                'setup.py'
            ]

            for pattern in additional_patterns:
                try:
                    file_content = await self.tracked_get_contents(
                        repo,
                        pattern,
                        ref=self._current_commit_sha if self._current_commit_sha else branch
                    )
                    if file_content:
                        dependencies[f'has_{pattern.replace(".", "_").lower()}'] = True
                except Exception:
                    continue

        except Exception as e:
            self.logger.warning(f"Error in additional dependency analysis: {str(e)}")

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

    async def _get_readme_content(self, repo: Repository, branch: Optional[str] = None, path: Optional[str] = None) -> Optional[str]:
        """Get repository README content"""
        try:
            # Use tracked_get_contents to handle rate limiting and caching
            readme_paths = ['README.md', 'README.rst', 'README', 'README.txt']

            for readme_path in readme_paths:
                try:
                    readme_content = await self.tracked_get_contents(
                        repo,
                        readme_path,
                        ref=self._current_commit_sha if self._current_commit_sha else branch
                    )

                    if readme_content:
                        content = base64.b64decode(readme_content.content).decode('utf-8')
                        self.logger.info(f"Found README at: {readme_path}")
                        return content

                except Exception as e:
                    self.logger.debug(f"README not found at {readme_path}: {str(e)}")
                    continue

            self.logger.info("No README found in repository")
            return None

        except Exception as e:
            self.logger.warning(f"Error getting README content: {str(e)}")
            return None

    def _is_code_file(self, path: str) -> bool:
        """Determine if a file is a code file based on extension"""
        code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c',
            '.h', '.cs', '.rb', '.php', '.go', '.rs', '.swift', '.kt',
            '.dart', '.vue', '.scala', '.r', '.jl'
        }
        return Path(path).suffix.lower() in code_extensions
    
    def get_retrieval_stats(self) -> Dict:
        """Get statistics about content retrievals and embeddings"""
        stats = {
            'cache_entries': len(self._content_cache),
            'paths_accessed': list(self._content_cache.keys()),
            'timestamps': {k: v['time'] for k, v in self._content_cache.items()},
            'shas': {k: v['sha'] for k, v in self._content_cache.items()}
        }

        if self.embeddings_manager:
            try:
                embedding_stats = self.embeddings_manager.get_stats()
                stats['embedding_stats'] = embedding_stats
            except Exception as e:
                self.logger.warning(f"Could not get embedding stats: {e}")

        return stats
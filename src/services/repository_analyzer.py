# src/services/repository_analyzer.py
from typing import Dict, Optional
from src.github_service import GitHubService
from src.embedding.hierarchical_embedder import HierarchicalEmbedding
import logging
import asyncio

class RepositoryAnalyzer:
    def __init__(self, 
                 github_service: GitHubService, 
                 hierarchical_embedder: Optional[HierarchicalEmbedding] = None):
        self.github_service = github_service
        self.embedder = hierarchical_embedder
        self.logger = logging.getLogger(__name__)

    async def analyze_repository(self, repo_url: str) -> Dict:
        """Perform complete repository analysis including embeddings"""
        try:
            # Get basic repository information
            repo_info = await self.github_service.analyze_repository(repo_url)

            # Process embeddings if manager is available
            if self.embeddings_manager and repo_info.get('file_contents'):
                files_to_process = [
                    {
                        'path': path,
                        'content': content,
                        'last_modified': repo_info.get('last_updated')
                    }
                    for path, content in repo_info['file_contents'].items()
                ]

                embedding_stats = await self.embeddings_manager.process_repository(
                    repo_url, 
                    files_to_process
                )

                # Add embedding statistics to repo_info
                repo_info['embedding_stats'] = embedding_stats
                repo_info['embedded_files'] = embedding_stats['processed_files']

            return repo_info

        except Exception as e:
            self.logger.error(f"Error in repository analysis: {str(e)}")
            raise
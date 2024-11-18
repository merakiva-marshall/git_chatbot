from github import Github
from typing import Dict
import logging

class GitHubService:
    def __init__(self, github_token: str):
        self.client = Github(github_token)

    def analyze_repository(self, repo_url: str) -> Dict:
        """Analyze a GitHub repository"""
        logging.info(f"Analyzing repository: {repo_url}")
        
        # Extract repository name from URL
        repo_name = repo_url.split('github.com/')[-1]
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
        
        try:
            # Get repository information
            repo = self.client.get_repo(repo_name)
            
            # Get basic repo stats
            stats = {
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
                'open_issues': repo.open_issues_count,
            }
            
            # Get root contents to verify access
            root_contents = repo.get_contents("")
            stats['files_count'] = len(root_contents) if isinstance(root_contents, list) else 1
            
            logging.info(f"Repository stats: {stats}")
            return stats
            
        except Exception as e:
            logging.error(f"Error accessing repository: {str(e)}")
            raise Exception(f"Error accessing repository: {str(e)}")
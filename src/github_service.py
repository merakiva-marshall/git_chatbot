from github import Github
from typing import Dict

class GitHubService:
    def __init__(self, github_token: str):
        self.client = Github(github_token)

    def analyze_repository(self, repo_url: str) -> Dict:
        """
        Analyze a GitHub repository
        
        Args:
            repo_url: URL of the GitHub repository
        
        Returns:
            Dict containing repository information
        """
        # Extract repository name from URL
        # Example URL: https://github.com/username/repo
        repo_name = repo_url.split('github.com/')[-1]
        
        try:
            # Get repository information
            repo = self.client.get_repo(repo_name)
            
            return {
                'name': repo.name,
                'full_name': repo.full_name,
                'description': repo.description,
                'default_branch': repo.default_branch,
                'stars': repo.stargazers_count,
                'forks': repo.forks_count,
                'last_updated': repo.updated_at.isoformat(),
            }
        except Exception as e:
            raise Exception(f"Error accessing repository: {str(e)}")
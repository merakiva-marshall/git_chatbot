from anthropic import Anthropic
from typing import Dict, Optional
import logging

class ChatService:
    def __init__(self, anthropic_client: Anthropic, model: str = "claude-3-sonnet-20240229", custom_instructions: str = ""):
        self.client = anthropic_client
        self.model = model
        self.custom_instructions = custom_instructions

    def generate_response(self, prompt: str, repo_info: Optional[Dict] = None) -> str:
        """Generate a response using the Anthropic API"""
        # Build system prompt
        system_prompt = "You are a helpful AI assistant that specializes in understanding GitHub repositories."
        
        if self.custom_instructions:
            system_prompt += f"\n\nCustom Instructions:\n{self.custom_instructions}"
        
        if repo_info:
            # Create a detailed repository description
            repo_desc = f"""
Currently analyzing repository: {repo_info.get('name', 'Unknown')}
Full Name: {repo_info.get('full_name')}
Description: {repo_info.get('description', 'No description available')}
Primary Language: {repo_info.get('language', 'Not specified')}
Topics: {', '.join(repo_info.get('topics', []))}
Statistics:
- Stars: {repo_info.get('stars', 0)}
- Forks: {repo_info.get('forks', 0)}
- Open Issues: {repo_info.get('open_issues', 0)}
- Size: {repo_info.get('size', 0)} KB
- Files in root: {repo_info.get('files_count', 0)}
Last Updated: {repo_info.get('last_updated', 'Unknown')}
Visibility: {repo_info.get('visibility', 'Unknown')}
"""
            system_prompt += f"\n\nRepository Information:\n{repo_desc}"
            
        logging.info(f"Generated system prompt: {system_prompt}")
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                system=system_prompt
            )
            
            return message.content[0].text
        except Exception as e:
            logging.error(f"Error generating response: {str(e)}")
            raise Exception(f"Error generating response: {str(e)}")
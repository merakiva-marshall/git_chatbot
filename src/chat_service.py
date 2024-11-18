from anthropic import Anthropic
from typing import Dict, Optional

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
            system_prompt += f"\n\nCurrently analyzing repository: {repo_info.get('name', 'Unknown')}"
            system_prompt += f"\nRepository description: {repo_info.get('description', 'No description available')}"
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                system=system_prompt
            )
            
            return message.content[0].text
        except Exception as e:
            raise Exception(f"Error generating response: {str(e)}")
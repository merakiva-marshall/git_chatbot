from anthropic import Anthropic
from typing import Dict, Optional
import logging

class ChatService:
    def __init__(self, anthropic_client: Anthropic, embeddings_manager=None, model: str = "claude-3-sonnet-20240229", custom_instructions: str = ""):
        self.client = anthropic_client
        self.model = model
        self.custom_instructions = custom_instructions
        self.embeddings_manager = embeddings_manager
        self.logger = logging.getLogger(__name__)

    async def generate_response(self, prompt: str, repo_info: Optional[Dict] = None) -> str:
        """Generate a response using the Anthropic API with enhanced context"""
        try:
            # Build detailed system prompt
            system_prompt = "You are a helpful AI assistant that specializes in understanding GitHub repositories. "
            system_prompt += "You have access to the repository's metadata and structure. "
            system_prompt += "When asked about files or structure, always check the repository context provided to you. "
            
            if self.custom_instructions:
                system_prompt += f"\n\nCustom Instructions:\n{self.custom_instructions}"
            
            if repo_info:
                # Add detailed repository structure
                system_prompt += "\n\nRepository Structure:\n"
                system_prompt += f"- Name: {repo_info.get('name')}\n"
                system_prompt += f"- Description: {repo_info.get('description')}\n"
                system_prompt += f"- Language: {repo_info.get('language')}\n"
                system_prompt += f"- Total Files: {repo_info.get('total_files', 0)}\n"
                
                # Add file types breakdown
                if 'file_types' in repo_info:
                    system_prompt += "\nFile Types:\n"
                    for ext, count in repo_info.get('file_types', {}).items():
                        system_prompt += f"- {ext or 'no extension'}: {count} files\n"
                
                # Add directories
                if 'directories' in repo_info:
                    system_prompt += "\nDirectories:\n"
                    for directory in repo_info.get('directories', []):
                        system_prompt += f"- {directory}\n"
                
                # Add specific instructions for file-related queries
                system_prompt += "\nWhen asked about files or repository structure, use this information to provide accurate responses. "
                system_prompt += "The repository information above is current and accurate."

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
            self.logger.error(f"Error generating response: {str(e)}")
            raise
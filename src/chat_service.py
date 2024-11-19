from anthropic import Anthropic
from typing import Dict, Optional, List
import logging

MAX_TOKENS = 8192
TEMPERATURE = 0.7

class ChatService:
    def __init__(self, anthropic_client: Anthropic, model: str = "claude-3-sonnet-20240229", custom_instructions: str = ""):
        self.client = anthropic_client
        self.model = model
        self.custom_instructions = custom_instructions
        self.conversation_history = []
        self._setup_logging()

    def _setup_logging(self):
        """Initialize logging"""
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _build_full_prompt(self, prompt: str, context: str = "") -> str:
        """Combine context with prompt"""
        if context:
            return f"Context:\n{context}\n\nQuestion: {prompt}"
        return prompt

    async def generate_response(self, prompt: str, repo_info: Optional[Dict] = None, messages: List[Dict] = None) -> str:
        """Generate a response using the Anthropic API"""
        try:
            system_prompt = self._build_system_prompt(repo_info)

            # Format messages for the API
            api_messages = []
            if messages:
                api_messages.extend([
                    {"role": msg["role"], "content": msg["content"]}
                    for msg in messages
                ])
            
            api_messages.append({
                "role": "user",
                "content": prompt
            })

            # Create the message using the sync API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                messages=api_messages,
                system=system_prompt
            )

            # Extract and return the response text
            return response.content[0].text

        except Exception as e:
            self.logger.error(f"Error generating response: {str(e)}")
            raise Exception(f"Error generating response: {str(e)}")

    def _build_system_prompt(self, repo_info: Optional[Dict]) -> str:
        """Build detailed system prompt with repository information"""
        system_prompt = "You are a helpful AI assistant that specializes in understanding GitHub repositories."
        
        if self.custom_instructions:
            system_prompt += f"\n\nCustom Instructions:\n{self.custom_instructions}"
        
        if repo_info:
            # Basic repo info
            repo_desc = f"""
Repository Information:
- Name: {repo_info.get('name', 'Unknown')}
- Description: {repo_info.get('description', 'No description available')}
- Primary Language: {repo_info.get('language', 'Not specified')}
- Topics: {', '.join(repo_info.get('topics', []))}
"""
            # Add code analysis information
            if 'code_relationships' in repo_info:
                code_rel = repo_info['code_relationships']
                
                # Add entry points
                if code_rel.get('entry_points'):
                    repo_desc += "\nEntry Points:\n"
                    for entry in code_rel['entry_points']:
                        repo_desc += f"- {entry}\n"
                
                # Add import relationships
                if code_rel.get('imports_graph'):
                    repo_desc += "\nFile Dependencies:\n"
                    for file, imports in code_rel['imports_graph'].items():
                        repo_desc += f"\n{file} imports:\n"
                        for imp in imports:
                            repo_desc += f"- {imp}\n"
                
            # Add structure information
            if 'file_types' in repo_info:
                repo_desc += "\nFile Structure:\n"
                for ext, count in repo_info['file_types'].items():
                    repo_desc += f"- {ext or 'no extension'}: {count} files\n"
            
            # Add directory information
            if 'directories' in repo_info:
                repo_desc += f"\nDirectories ({len(repo_info['directories'])} total):\n"
                for directory in sorted(repo_info['directories'])[:10]:  # Show first 10
                    repo_desc += f"- {directory}\n"
            
            # Add dependencies
            if 'dependencies' in repo_info and any(repo_info['dependencies'].values()):
                repo_desc += "\nDependencies:\n"
                for dep_file, content in repo_info['dependencies'].items():
                    if content:
                        repo_desc += f"- Found {dep_file}\n"

            system_prompt += f"\n\nDetailed Repository Analysis:\n{repo_desc}"
            
            # Add README content last
            if 'readme' in repo_info and repo_info['readme']:
                system_prompt += "\n\nREADME Content:\n" + repo_info['readme']

        return system_prompt
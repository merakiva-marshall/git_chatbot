from anthropic import Anthropic
from typing import Dict, Optional, List
import logging
import asyncio
import time
from utils.usage_tracker import UsageTracker
from utils.token_counter import TokenCounter
from uuid import uuid4

MAX_TOKENS = 8192
TEMPERATURE = 0.6
MIN_REQUEST_INTERVAL = 2  # Minimum seconds between requests

class ChatService:
    def __init__(self, 
                 anthropic_client: Anthropic, 
                 embeddings_manager=None,
                 model: str = "claude-3-5-sonnet-latest", 
                 custom_instructions: str = ""):
        # Basic attributes
        self.client = anthropic_client
        self.model = model
        self.custom_instructions = custom_instructions
        self.embeddings_manager = embeddings_manager
        self.conversation_history = []
        self.usage_tracker = UsageTracker()
        self.token_counter = TokenCounter(model)
        self.conversation_id = str(uuid4())
        self.current_query_stats = None

        # Internal state
        self._last_repo_info = None
        self._last_request_time = 0
        self._request_lock = asyncio.Lock()

        # Initialize logger
        self.logger = logging.getLogger(__name__)
        self._setup_logging()

    def _setup_logging(self):
        """Initialize logging configuration"""
        # Configure logging if not already configured
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    async def generate_response(self, 
                              prompt: str, 
                              repo_info: Optional[Dict] = None, 
                              messages: List[Dict] = None,
                              code_context: Optional[List[Dict]] = None) -> str:
        """Generate a response using the Anthropic API with rate limiting and embeddings"""
        try:
            # Track repository info changes
            if repo_info != self._last_repo_info:
                self.logger.info("Repository info changed from previous request")
                self._last_repo_info = repo_info.copy() if repo_info else None

            # Get relevant code context using embeddings
            if self.embeddings_manager:
                try:
                    relevant_code = await self.embeddings_manager.search_code(prompt)
                    if relevant_code:
                        code_context = relevant_code
                except Exception as e:
                    self.logger.warning(f"Error retrieving code context: {str(e)}")
                    # Continue without code context if there's an error

            async with self._request_lock:
                # Implement rate limiting
                current_time = time.time()
                time_since_last_request = current_time - self._last_request_time
                if time_since_last_request < MIN_REQUEST_INTERVAL:
                    await asyncio.sleep(MIN_REQUEST_INTERVAL - time_since_last_request)

            # Build the full prompt with code context
            system_prompt = self._build_system_prompt(repo_info, code_context)

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
            max_retries = 3
            retry_delay = 2

            for attempt in range(max_retries):
                try:
                    response = self.client.messages.create(
                        model=self.model,
                        max_tokens=MAX_TOKENS,
                        messages=api_messages,
                        system=system_prompt
                    )

                    output_content = response.content[0].text

                    # Update last request time
                    self._last_request_time = time.time()

                    return output_content

                except Exception as e:
                    if "overloaded" in str(e).lower() and attempt < max_retries - 1:
                        wait_time = retry_delay * (attempt + 1)
                        self.logger.warning(f"API overloaded, waiting {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                        continue
                    raise

        except Exception as e:
            self.logger.error(f"Error generating response: {str(e)}")
            raise

    def _build_system_prompt(self, repo_info: Optional[Dict], code_context: Optional[List[Dict]] = None) -> str:
        """Build detailed system prompt with repository information and code context"""
        system_prompt = "You are an expert software developer that has access to Github repositories. "
        system_prompt += "You will use your knowledge and understanding of the files & structure in the GitHub repository to write excellent code and troubleshoot problems. "
        system_prompt += "Before writing code, you'll think critically about dependencies and elements to include."

        if self.custom_instructions:
            system_prompt += f"\n\nCustom Instructions:\n{self.custom_instructions}"

        if code_context:
            system_prompt += "\n\nRelevant Code Context:\n"
            for ctx in code_context:
                system_prompt += f"\nFile: {ctx.get('file')}\n"
                system_prompt += f"Type: {ctx.get('type')}\n"
                system_prompt += f"Content:\n{ctx.get('content')}\n"

        if repo_info:
            # Basic repo info
            repo_desc = f"""
Repository Information:
- Name: {repo_info.get('name', 'Unknown')}
- Description: {repo_info.get('description', 'No description available')}
- Primary Language: {repo_info.get('language', 'Not specified')}
- Current Branch: {repo_info.get('current_branch', 'default branch')}
- Current Path: {repo_info.get('current_path', 'root')}
- Topics: {', '.join(repo_info.get('topics', []))}
"""
            # Add context about which version is being analyzed
            if repo_info.get('current_branch'):
                repo_desc += f"\nNote: All code and analysis is from the '{repo_info['current_branch']}' branch"
                if repo_info.get('current_path'):
                    repo_desc += f" at path '{repo_info['current_path']}'"
                repo_desc += ".\n"

            # Add file contents if available
            if 'file_contents' in repo_info:
                repo_desc += "\nFile Contents:\n"
                for file_path, content in repo_info['file_contents'].items():
                    repo_desc += f"\n--- {file_path} ---\n{content}\n"

            # Add code relationships
            if 'code_relationships' in repo_info:
                code_rel = repo_info['code_relationships']

                if code_rel.get('entry_points'):
                    repo_desc += "\nEntry Points:\n"
                    for entry in code_rel['entry_points']:
                        repo_desc += f"- {entry}\n"

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

            if 'directories' in repo_info:
                repo_desc += f"\nDirectories ({len(repo_info['directories'])} total):\n"
                for directory in sorted(repo_info['directories'])[:10]:
                    repo_desc += f"- {directory}\n"

            if 'dependencies' in repo_info and any(repo_info['dependencies'].values()):
                repo_desc += "\nDependencies:\n"
                for dep_file, content in repo_info['dependencies'].items():
                    if content:
                        repo_desc += f"- Found {dep_file}\n"

            system_prompt += f"\n\nDetailed Repository Analysis:\n{repo_desc}"

            if 'readme' in repo_info and repo_info['readme']:
                system_prompt += "\n\nREADME Content:\n" + repo_info['readme']

        return system_prompt
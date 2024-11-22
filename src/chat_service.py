from anthropic import Anthropic
from typing import Dict, Optional, List
import logging
import asyncio
import time
from utils.usage_tracker import UsageTracker
from utils.token_counter import TokenCounter
from uuid import uuid4
from src.query.query_analyzer import QueryAnalyzer
from src.query.contextual_search import ContextualSearch
from src.core.codebase_structure import CodebaseStructure
from src.analysis.code_analyzer import CodeAnalyzer

MAX_TOKENS = 8192
TEMPERATURE = 0.6
MIN_REQUEST_INTERVAL = 2  # Minimum seconds between requests

class ChatService:
    def __init__(self, 
                 anthropic_client: Anthropic,
                 codebase: CodebaseStructure,
                 code_analyzer: CodeAnalyzer,
                 contextual_search: ContextualSearch,
                 query_analyzer: QueryAnalyzer,
                 model: str = "claude-3-5-sonnet-latest",
                 custom_instructions: str = ""):
        # Basic attributes
        self.client = anthropic_client
        self.model = model
        self.custom_instructions = custom_instructions
        self.codebase = codebase
        self.code_analyzer = code_analyzer
        self.contextual_search = contextual_search
        self.query_analyzer = query_analyzer
        self.usage_tracker = UsageTracker()
        self.token_counter = TokenCounter(model)
        self.conversation_id = str(uuid4())

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
        """Generate a response using context-aware search and analysis"""
        try:
            # Analyze the query
            query_analysis = await self.query_analyzer.analyze_query(prompt)

            # Perform contextual search
            search_results = await self.contextual_search.search(
                prompt,
                query_analysis,
                limit=5
            )

            # Build the context for Claude
            context = self._build_context_for_claude(
                query_analysis,
                search_results,
                repo_info
            )

            # Format messages for the API
            api_messages = []
            if messages:
                api_messages.extend([
                    {"role": msg["role"], "content": msg["content"]}
                    for msg in messages
                ])

            api_messages.append({
                "role": "user",
                "content": f"{context}\n\nQuery: {prompt}"
            })

            # Generate response with Claude
            response = self.client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                messages=api_messages,
                system=self._build_system_prompt()
            )

            # Track usage
            self._track_usage(prompt, response.content[0].text)

            return response.content[0].text

        except Exception as e:
            self.logger.error(f"Error generating response: {str(e)}")
            raise

        except Exception as e:
            self.logger.error(f"Error generating response: {str(e)}")
            raise

    # Add new methods:
    def _build_context_for_claude(self,
                                query_analysis,
                                search_results,
                                repo_info: Optional[Dict]) -> str:
        """Build rich context for Claude's response"""
        context_parts = []

        # Add repository context if available
        if repo_info:
            context_parts.append(
                f"Repository Information:\n"
                f"Name: {repo_info.get('name', 'Unknown')}\n"
                f"Language: {repo_info.get('language', 'Unknown')}\n"
                f"Description: {repo_info.get('description', 'No description')}\n"
            )

        # Add search results context
        if search_results:
            context_parts.append("\nRelevant Code Context:")
            for result in search_results:
                context_parts.append(
                    f"\nFile: {result.content.get('file_path', 'Unknown')}\n"
                    f"Type: {result.content.get('type', 'Unknown')}\n"
                    f"Content:\n{result.content.get('content', '')}\n"
                    f"Context: {result.context}\n"
                )

        # Add query analysis context
        context_parts.append(
            f"\nQuery Analysis:\n"
            f"Type: {query_analysis.query_type.value}\n"
            f"Action: {query_analysis.action_type}\n"
        )

        return "\n".join(context_parts)

    def _build_system_prompt(self) -> str:
        """Build enhanced system prompt"""
        system_prompt = (
            "You are an expert software developer with deep knowledge of software "
            "architecture, design patterns, and best practices. You have access to "
            "a GitHub repository's code and structure.\n\n"
            "When responding:\n"
            "1. Consider the full context of the codebase\n"
            "2. Reference specific code examples when relevant\n"
            "3. Explain architectural decisions and patterns\n"
            "4. Suggest improvements while respecting existing patterns\n"
        )

        if self.custom_instructions:
            system_prompt += f"\nCustom Instructions:\n{self.custom_instructions}"

        return system_prompt
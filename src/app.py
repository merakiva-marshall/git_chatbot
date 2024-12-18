import streamlit as st
from anthropic import Anthropic
import os
from dotenv import load_dotenv
from github_service import GitHubService
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from functools import partial
import atexit
from qdrant_client import QdrantClient
from chat_service import ChatService
from github_service import GitHubService
from config import AppConfig
from utils.settings_manager import SettingsManager
from utils.usage_tracker import UsageTracker
from query.query_analyzer import QueryAnalyzer
from query.contextual_search import ContextualSearch
from core.codebase_structure import CodebaseStructure
from analysis.code_analyzer import CodeAnalyzer
from embedding.hierarchical_embedder import HierarchicalEmbedding
from embedding.contextual_embedder import ContextualEmbedder
from storage.vector_store import CodebaseVectorStore
from storage.context_store import ContextStorage
from vector_store.qdrant_manager import QdrantManager

# Load environment variables
load_dotenv()

if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.messages = []
    st.session_state.current_repo = None

CLAUDE_MODELS = {
    "Claude 3.5 Sonnet": "claude-3-5-sonnet-latest",
    "Claude 3.5 Haiku": "claude-3-5-haiku-latest",
}

def cleanup_resources():
    """Cleanup resources on application exit"""
    try:
        # Get the QdrantManager instance and clean up
        qdrant_manager = QdrantManager()
        asyncio.run(qdrant_manager.cleanup())
    except Exception as e:
        st.error(f"Error cleaning up resources: {str(e)}")

# Register cleanup function
    atexit.register(cleanup_resources)

# Register cleanup function
atexit.register(cleanup_resources)

def run_async(coroutine):
    """Helper function to run async functions in Streamlit"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coroutine)

def initialize_system():
    """Initialize all system components"""
    if 'system_initialized' not in st.session_state:
        try:
            # Load environment variables
            load_dotenv()

            # Initialize configuration
            config = AppConfig()

            # Initialize core services
            anthropic_client = Anthropic(api_key=config.anthropic_api_key)

            # Initialize core components
            codebase = CodebaseStructure()
            code_analyzer = CodeAnalyzer()

            # Initialize embedding and storage
            embedder = HierarchicalEmbedding(anthropic_client)
            contextual_embedder = ContextualEmbedder()

            # Initialize vector store
            qdrant_client = QdrantClient(url=config.qdrant_url)
            vector_store = CodebaseVectorStore(qdrant_client)
            context_store = ContextStorage()

            # Initialize query components
            query_analyzer = QueryAnalyzer()
            contextual_search = ContextualSearch(
                vector_store=vector_store,
                context_store=context_store,
                embedder=embedder
            )

            # Store in session state
            st.session_state.system_initialized = True
            st.session_state.config = config
            st.session_state.codebase = codebase
            st.session_state.code_analyzer = code_analyzer
            st.session_state.embedder = embedder
            st.session_state.contextual_search = contextual_search
            st.session_state.query_analyzer = query_analyzer

            return True
        except Exception as e:
            st.error(f"Error initializing system: {str(e)}")
            return False
    return True

def init_services():
    """Initialize all required services"""
    config = AppConfig()
    anthropic_client = Anthropic(api_key=config.anthropic_api_key)

    # Initialize core components
    codebase = CodebaseStructure()
    code_analyzer = CodeAnalyzer()

    # Initialize embedding and storage
    hierarchical_embedder = HierarchicalEmbedding(anthropic_client)
    contextual_embedder = ContextualEmbedder()
    vector_store = CodebaseVectorStore(qdrant_client=QdrantClient(url=config.qdrant_url))
    context_store = ContextStorage()

    # Initialize query components
    query_analyzer = QueryAnalyzer()
    contextual_search = ContextualSearch(vector_store, context_store, hierarchical_embedder)

    selected_model = st.session_state.get('selected_model', CLAUDE_MODELS["Claude 3.5 Sonnet"])

    # Initialize services with new components
    chat_service = ChatService(
        anthropic_client,
        codebase=codebase,
        code_analyzer=code_analyzer,
        contextual_search=contextual_search,
        query_analyzer=query_analyzer,
        model=selected_model,
        custom_instructions=st.session_state.get('custom_instructions', '')
    )

    github_service = GitHubService(
        config.github_token,
        codebase=codebase,
        code_analyzer=code_analyzer,
        hierarchical_embedder=hierarchical_embedder
    )

    return config, chat_service, github_service

def init_session_state(settings_manager: SettingsManager):
    """Initialize session state with saved settings"""
    settings = settings_manager.get_settings()
    defaults = {
        "messages": [],
        "current_repo": None,
        "selected_model": settings.get('selected_model', CLAUDE_MODELS["Claude 3.5 Sonnet"]),
        "custom_instructions": settings.get('custom_instructions', ''),
        "last_repo": settings.get('last_repo', ''),
        "waiting_for_response": False,
        "conversation_history": [],
        "current_session_tokens": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0.0,
            "embedding_tokens": 0,
            "embedding_cost": 0.0
        },
        "current_query_stats": None
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def format_conversation_history():
    """Format conversation history for the API"""
    formatted_messages = []
    for msg in st.session_state.conversation_history:
        formatted_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    return formatted_messages

async def handle_chat_input(prompt: str, chat_service: ChatService):
    if not prompt.strip():
        return

    with st.chat_message("user"):
        st.markdown(prompt)

    st.session_state.conversation_history.append({
        "role": "user",
        "content": prompt
    })

    try:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                messages = format_conversation_history()

                # Ensure current_repo information is available
                repo_info = st.session_state.get('current_repo', {})

                # Get relevant code context using embeddings
                relevant_code = None
                if chat_service.embeddings_manager:
                    try:
                        relevant_code = await chat_service.embeddings_manager.search_code(prompt)
                    except Exception as e:
                        st.warning(f"Error retrieving code context: {str(e)}")

                try:
                    response = await chat_service.generate_response(
                        prompt,
                        repo_info=repo_info,  # Pass repo_info explicitly
                        messages=messages[:-1],
                        code_context=relevant_code
                    )

                    if response:
                        st.session_state.conversation_history.append({
                            "role": "assistant",
                            "content": response
                        })
                        st.markdown(response)

                        # Update session state with current query stats
                        if chat_service.current_query_stats:
                            st.session_state.current_query_stats = chat_service.current_query_stats
                    else:
                        st.error("No response received from the assistant")
                except Exception as e:
                    if "overloaded" in str(e).lower():
                        st.error("The service is temporarily busy. Please wait a moment and try again.")
                    else:
                        st.error(f"Error: {str(e)}")
    except Exception as e:
        st.error(f"Error: {str(e)}")

def save_current_chat(settings_manager: SettingsManager):
    """Save current chat session with embedding context"""
    if st.session_state.conversation_history:
        chat_title = st.session_state.get('chat_title', f"Chat {len(settings_manager.get_chat_sessions()) + 1}")
        filename = settings_manager.save_chat_session(
            st.session_state.conversation_history,
            st.session_state.current_repo,
            chat_title,
            embedding_stats=st.session_state.current_session_tokens.get('embedding_stats', {})
        )
        st.success(f"Chat saved as: {chat_title}")

def main():
    st.set_page_config(
        page_title="Git Chatbot",
        page_icon="💬",
        layout="wide"
    )

    if not initialize_system():
        st.error("Failed to initialize system. Please check your configuration.")
        return

    settings_manager = SettingsManager()
    init_session_state(settings_manager)

    st.title("Git Chatbot")
    st.caption("Chat with your GitHub repositories using Claude")

    with st.sidebar:
        st.header("Settings")

        selected_model_name = st.selectbox(
            "Select Claude Model",
            options=list(CLAUDE_MODELS.keys()),
            index=1
        )
        new_model = CLAUDE_MODELS[selected_model_name]
        if new_model != st.session_state.selected_model:
            st.session_state.selected_model = new_model
            settings_manager.update_settings({"selected_model": new_model})

        # Custom instructions
        st.header("Custom Instructions")
        custom_instructions = st.text_area(
            "Enter custom instructions for the AI",
            value=st.session_state.custom_instructions,
            help="These instructions will be included in every chat"
        )
        if custom_instructions != st.session_state.custom_instructions:
            st.session_state.custom_instructions = custom_instructions
            settings_manager.update_settings({"custom_instructions": custom_instructions})

        # Repository settings
        st.header("Repository Settings")
        repo_url = st.text_input(
            "GitHub Repository URL",
            value=st.session_state.last_repo,
            placeholder="https://github.com/username/repository"
        )

        if repo_url != st.session_state.last_repo:
            st.session_state.last_repo = repo_url
            settings_manager.update_settings({"last_repo": repo_url})

        # Embedding settings
        with st.expander("Embedding Settings", expanded=False):
            st.checkbox("Enable Code Search", value=True, key="enable_embeddings",
                       help="Use embeddings for semantic code search")
            st.number_input("Max Results", min_value=1, max_value=10, value=5, key="max_embedding_results",
                          help="Maximum number of code snippets to retrieve")

            if st.button("Clear Embedding Cache"):
                try:
                    config, chat_service, _ = init_services()
                    chat_service.embeddings_manager.clear_cache()
                    st.success("Embedding cache cleared")
                except Exception as e:
                    st.error(f"Error clearing cache: {str(e)}")

        if st.button("Analyze Repository"):
            with st.spinner("Analyzing repository..."):
                try:
                    _, _, github_service = init_services()

                    # Add debug information
                    st.write("Initializing repository analysis...")
                    st.write(f"Repository URL: {repo_url}")

                    repo_info = run_async(github_service.analyze_repository(repo_url))
                    st.session_state.current_repo = repo_info

                    # Debug output
                    st.write("\nDebug Information:")
                    st.write(f"Files found: {repo_info.get('total_files', 0)}")
                    st.write(f"File types: {repo_info.get('file_types', {})}")
                    st.write(f"Directories: {len(repo_info.get('directories', []))}")

                    # Enhanced success message with embeddings info
                    success_msg = f"""
                    Repository analyzed successfully!
                    - Name: {repo_info['name']}
                    - Branch: {repo_info.get('current_branch', 'default')}
                    - Path: {repo_info.get('current_path', 'root')}
                    - Language: {repo_info.get('language', 'Not specified')}
                    - Files in scope: {repo_info.get('total_files', 0)}
                    - Directories: {len(repo_info.get('directories', []))}
                    - Last updated: {repo_info.get('last_updated', 'Unknown')}
                    """

                    if st.session_state.enable_embeddings:
                        success_msg += f"\nEmbeddings generated for {repo_info.get('embedded_files', 0)} files"

                    st.success(success_msg)

                    # Show additional info in expandable section
                    with st.expander("View Detailed Analysis"):
                        st.write("File Types:")
                        for ext, count in repo_info.get('file_types', {}).items():
                            st.write(f"- {ext}: {count} files")

                        if repo_info.get('dependencies', {}).get('package_json'):
                            st.write("📦 Found package.json (Node.js/JavaScript project)")
                        if repo_info.get('dependencies', {}).get('requirements_txt'):
                            st.write("📦 Found requirements.txt (Python project)")

                        # Show embedding statistics
                        if st.session_state.enable_embeddings:
                            st.write("\nEmbedding Statistics:")
                            embed_stats = repo_info.get('embedding_stats', {})
                            st.write(f"- Total tokens used: {embed_stats.get('total_tokens', 0)}")
                            st.write(f"- Embedding cost: ${embed_stats.get('cost', 0):.4f}")

                except Exception as e:
                    st.error(f"Error analyzing repository: {str(e)}")
                    st.write("Debug information:")
                    st.write(f"Exception type: {type(e).__name__}")
                    st.write(f"Exception details: {str(e)}")

        # Usage Statistics Section
        st.header("Usage Statistics")
        tracker = UsageTracker()

        now = datetime.now()
        last_24h = (now - timedelta(days=1)).isoformat()

        try:
            daily_usage = tracker.get_usage_summary(start_date=last_24h)
            total_usage = tracker.get_usage_summary()

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Last 24 Hours**")
                total_tokens = (daily_usage['total_input_tokens'] + 
                              daily_usage['total_output_tokens'] +
                              daily_usage.get('embedding_tokens', 0))
                total_cost = (daily_usage['total_cost'] + 
                            daily_usage.get('embedding_cost', 0))
                st.metric("Tokens", f"{total_tokens:,}", f"${total_cost:.2f}")

            with col2:
                st.markdown("**All Time**")
                all_time_tokens = (total_usage['total_input_tokens'] + 
                                 total_usage['total_output_tokens'] +
                                 total_usage.get('embedding_tokens', 0))
                all_time_cost = (total_usage['total_cost'] + 
                               total_usage.get('embedding_cost', 0))
                st.metric("Tokens", f"{all_time_tokens:,}", f"${all_time_cost:.2f}")

            # Detailed usage statistics
            with st.expander("View Detailed Usage"):
                cols = st.columns(2)
                with cols[0]:
                    start_date = st.date_input(
                        "Start Date",
                        value=now - timedelta(days=7),
                        key="usage_start_date"
                    )
                with cols[1]:
                    end_date = st.date_input(
                        "End Date",
                        value=now,
                        key="usage_end_date"
                    )

                custom_usage = tracker.get_usage_summary(
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat()
                )

                if custom_usage['usage_by_model']:
                    model_data = []
                    for model, stats in custom_usage['usage_by_model'].items():
                        model_data.append({
                            'Model': model,
                            'Input': stats['input_tokens'],
                            'Output': stats['output_tokens'],
                            'Embeddings': stats.get('embedding_tokens', 0),
                            'Cost': f"${stats['cost'] + stats.get('embedding_cost', 0):.2f}"
                        })

                    df = pd.DataFrame(model_data)
                    st.dataframe(df, hide_index=True)

                    # Create visualization
                    df_melted = pd.melt(
                        df,
                        id_vars=['Model'],
                        value_vars=['Input', 'Output', 'Embeddings'],
                        var_name='Type',
                        value_name='Tokens'
                    )

                    fig = px.bar(
                        df_melted,
                        x='Model',
                        y='Tokens',
                        color='Type',
                        barmode='group',
                        title='Token Usage by Model and Type'
                    )

                    fig.update_layout(
                        height=300,
                        margin=dict(t=30, l=30, r=30, b=30),
                    )

                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No usage data available for the selected date range.")

        except Exception as e:
            st.error(f"Error loading usage statistics: {str(e)}")

        # Chat session management
        st.header("Chat Sessions")
        chat_title = st.text_input(
            "Chat Title",
            value=st.session_state.get('chat_title', ''),
            placeholder="Enter a title for this chat session"
        )
        st.session_state.chat_title = chat_title

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Save Chat"):
                save_current_chat(settings_manager)

        # Load previous chats
        chat_sessions = settings_manager.get_chat_sessions()
        if chat_sessions:
            selected_chat = st.selectbox(
                "Previous Chats",
                options=chat_sessions,
                format_func=lambda x: x.get('title', x.get('id', 'Untitled'))
            )
            with col2:
                if st.button("Load Chat"):
                    chat_data = settings_manager.load_chat_session(selected_chat['id'])
                    if chat_data:
                        st.session_state.conversation_history = chat_data['messages']
                        st.session_state.current_repo = chat_data['repo_info']
                        st.session_state.chat_title = chat_data.get('title', '')
                        st.rerun()

    # Chat interface
    chat_container = st.container()

    # Display chat history
    with chat_container:
        for message in st.session_state.conversation_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask about the repository...", key="chat_input"):
        config, chat_service, _ = init_services()
        run_async(handle_chat_input(prompt, chat_service))

if __name__ == "__main__":
    main()
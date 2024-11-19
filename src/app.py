import streamlit as st
from anthropic import Anthropic
import os
from dotenv import load_dotenv
from config import AppConfig
from chat_service import ChatService
from github_service import GitHubService
from utils.settings_manager import SettingsManager
import asyncio
from vector_store.embeddings_manager import EmbeddingsManager

# Load environment variables
load_dotenv()

# Available Claude models
CLAUDE_MODELS = {
    "Claude 3 Sonnet": "claude-3-sonnet-20240229",
    "Claude 3 Haiku": "claude-3-haiku-20240307",
}

def analyze_repository_async(github_service: GitHubService, repo_url: str):
    """Run async repository analysis"""
    return asyncio.run(github_service.analyze_repository(repo_url))

def init_services():
    """Initialize all required services"""
    config = AppConfig()
    anthropic_client = Anthropic(api_key=config.anthropic_api_key)
    
    # Initialize embeddings manager
    embeddings_manager = EmbeddingsManager(anthropic_client)
    
    selected_model = st.session_state.get('selected_model', CLAUDE_MODELS["Claude 3 Sonnet"])
    custom_instructions = st.session_state.get('custom_instructions', '')
    
    # Initialize services with embeddings manager
    chat_service = ChatService(
        anthropic_client,
        embeddings_manager=embeddings_manager,
        model=selected_model,
        custom_instructions=custom_instructions
    )
    github_service = GitHubService(config.github_token, embeddings_manager=embeddings_manager)
    
    return config, chat_service, github_service

def init_session_state(settings_manager: SettingsManager):
    """Initialize session state with saved settings"""
    settings = settings_manager.get_settings()
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_repo" not in st.session_state:
        st.session_state.current_repo = None
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = settings.get('selected_model', CLAUDE_MODELS["Claude 3 Sonnet"])
    if "custom_instructions" not in st.session_state:
        st.session_state.custom_instructions = settings.get('custom_instructions', '')
    if "last_repo" not in st.session_state:
        st.session_state.last_repo = settings.get('last_repo', '')

def handle_chat_input(prompt: str, chat_service: ChatService):
    """Handle chat input with full debugging"""
    if not prompt.strip():
        return
    
    with st.sidebar.expander("🤖 Chat Debug", expanded=True):
        st.write("Processing chat input...")
        st.write(f"Prompt: {prompt}")
        st.write(f"Model: {chat_service.model}")
        st.write(f"Custom Instructions: {bool(chat_service.custom_instructions)}")
        
        if st.session_state.current_repo:
            st.write("\nRepository Context:")
            st.json(st.session_state.current_repo)
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    try:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # Get relevant code
                if chat_service.embeddings_manager:
                    relevant_code = asyncio.run(chat_service.embeddings_manager.search_code(prompt))
                
                # Generate response
                response = asyncio.run(chat_service.generate_response(
                    prompt,
                    st.session_state.current_repo
                ))
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response
                })
                st.markdown(response)
    except Exception as e:
        st.error(f"Error generating response: {str(e)}")

def save_current_chat(settings_manager: SettingsManager):
    """Save current chat session"""
    if st.session_state.messages:
        chat_title = st.session_state.get('chat_title', f"Chat {len(settings_manager.get_chat_sessions()) + 1}")
        filename = settings_manager.save_chat_session(
            st.session_state.messages,
            st.session_state.current_repo,
            chat_title
        )
        st.success(f"Chat saved as: {chat_title}")

def main():
    st.set_page_config(
        page_title="Git Chatbot",
        page_icon="💬",
        layout="wide"
    )
    
    settings_manager = SettingsManager()
    
    st.title("Git Chatbot")
    st.caption("Chat with your GitHub repositories using Claude")
    
    # Initialize session state
    init_session_state(settings_manager)
    
    # Sidebar for settings
    with st.sidebar:
        st.header("Settings")
        
        # Model selection
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
        
        if st.button("Analyze Repository"):
            with st.spinner("Analyzing repository..."):
                try:
                    _, _, github_service = init_services()
                    repo_info = analyze_repository_async(github_service, repo_url)
                    st.session_state.current_repo = repo_info
                    
                    # Enhanced success message
                    st.success(f"""
Repository analyzed successfully!
- Name: {repo_info['name']}
- Language: {repo_info.get('language', 'Not specified')}
- Files in root: {repo_info.get('root_files', 0)}
- Total files: {repo_info.get('total_files', 0)}
- Directories: {len(repo_info.get('directories', []))}
- Last updated: {repo_info.get('last_updated', 'Unknown')}
                    """)
                    
                    # Show additional info in expandable section
                    with st.expander("View Detailed Analysis"):
                        st.write("File Types:")
                        for ext, count in repo_info.get('file_types', {}).items():
                            st.write(f"- {ext}: {count} files")
                        
                        if repo_info.get('dependencies', {}).get('package_json'):
                            st.write("📦 Found package.json (Node.js/JavaScript project)")
                        if repo_info.get('dependencies', {}).get('requirements_txt'):
                            st.write("📦 Found requirements.txt (Python project)")
                            
                except Exception as e:
                    st.error(f"Error analyzing repository: {str(e)}")
        
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
                        st.session_state.messages = chat_data['messages']
                        st.session_state.current_repo = chat_data['repo_info']
                        st.session_state.chat_title = chat_data.get('title', '')
                        st.rerun()
    
    # Chat interface
    chat_container = st.container()
    
    # Display chat history
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask about the repository...", key="chat_input"):
        # Initialize services with embeddings manager
        config = AppConfig()
        anthropic_client = Anthropic(api_key=config.anthropic_api_key)
        embeddings_manager = EmbeddingsManager(anthropic_client)
        
        chat_service = ChatService(
            anthropic_client,
            embeddings_manager=embeddings_manager,
            model=st.session_state.selected_model,
            custom_instructions=st.session_state.custom_instructions
        )
        
        handle_chat_input(prompt, chat_service)

if __name__ == "__main__":
    main()
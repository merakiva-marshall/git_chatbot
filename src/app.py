import streamlit as st
from anthropic import Anthropic
import os
from dotenv import load_dotenv
from config import AppConfig
from chat_service import ChatService
from github_service import GitHubService
from utils.settings_manager import SettingsManager
import asyncio
from functools import partial

# Load environment variables
load_dotenv()

CLAUDE_MODELS = {
    "Claude 3.5 Sonnet": "claude-3-5-sonnet-latest",
    "Claude 3.5 Haiku": "claude-3-5-haiku-latest",
}

def run_async(coroutine):
    """Helper function to run async functions in Streamlit"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coroutine)

def init_services():
    config = AppConfig()
    anthropic_client = Anthropic(api_key=config.anthropic_api_key)
    selected_model = st.session_state.get('selected_model', CLAUDE_MODELS["Claude 3.5 Sonnet"])
    chat_service = ChatService(
        anthropic_client, 
        model=selected_model,
        custom_instructions=st.session_state.get('custom_instructions', '')
    )
    github_service = GitHubService(config.github_token)
    return config, chat_service, github_service

def init_session_state(settings_manager: SettingsManager):
    settings = settings_manager.get_settings()
    defaults = {
        "messages": [],
        "current_repo": None,
        "selected_model": settings.get('selected_model', CLAUDE_MODELS["Claude 3.5 Sonnet"]),
        "custom_instructions": settings.get('custom_instructions', ''),
        "last_repo": settings.get('last_repo', ''),
        "waiting_for_response": False,
        "conversation_history": []
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def format_conversation_history():
    formatted_messages = []
    for msg in st.session_state.conversation_history:
        formatted_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    return formatted_messages

def handle_chat_input(prompt: str, chat_service: ChatService):
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
                response = run_async(chat_service.generate_response(
                    prompt,
                    st.session_state.current_repo,
                    messages=messages[:-1]  # Exclude the current prompt
                ))
                
                if response:
                    st.session_state.conversation_history.append({
                        "role": "assistant",
                        "content": response
                    })
                    st.markdown(response)
                else:
                    st.error("No response received from the assistant")
    except Exception as e:
        st.error(f"Error: {str(e)}")

def save_current_chat(settings_manager: SettingsManager):
    if st.session_state.conversation_history:
        chat_title = st.session_state.get('chat_title', f"Chat {len(settings_manager.get_chat_sessions()) + 1}")
        filename = settings_manager.save_chat_session(
            st.session_state.conversation_history,
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
        
        if st.button("Analyze Repository"):
            with st.spinner("Analyzing repository..."):
                try:
                    _, _, github_service = init_services()
                    # Properly await the async analyze_repository method
                    repo_info = run_async(github_service.analyze_repository(repo_url))
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
        for message in st.session_state.conversation_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # Chat input 
    if prompt := st.chat_input("Ask about the repository...", key="chat_input"):
        chat_service = ChatService(
            Anthropic(api_key=AppConfig().anthropic_api_key),
            model=st.session_state.selected_model,
            custom_instructions=st.session_state.custom_instructions
        )
        handle_chat_input(prompt, chat_service)

if __name__ == "__main__":
    main()
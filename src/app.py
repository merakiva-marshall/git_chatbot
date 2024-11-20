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
from utils.usage_tracker import UsageTracker
import plotly.express as px  # Change this import
import pandas as pd
from datetime import datetime, timedelta

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
        "conversation_history": [],
        "current_session_tokens": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0.0,
        "current_query_stats": None
        }
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
                try:
                    response = run_async(chat_service.generate_response(
                        prompt,
                        st.session_state.current_repo,
                        messages=messages[:-1]
                    ))

                    if response:
                        st.session_state.conversation_history.append({
                            "role": "assistant",
                            "content": response
                        })
                        st.markdown(response)

                        # Update session state with current query stats AFTER response
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
                    repo_info = run_async(github_service.analyze_repository(repo_url))
                    st.session_state.current_repo = repo_info
                    
                    # Enhanced success message with branch and path info
                    st.success(f"""
        Repository analyzed successfully!
        - Name: {repo_info['name']}
        - Branch: {repo_info.get('current_branch', 'default')}
        - Path: {repo_info.get('current_path', 'root')}
        - Language: {repo_info.get('language', 'Not specified')}
        - Files in scope: {repo_info.get('total_files', 0)}
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
        
        #File Verification Debug
        if st.session_state.get('current_repo'):
            st.write("### Content Verification")
            verify_file = st.text_input("Enter file path to verify:")
            if verify_file and st.button("Verify File Content"):
                try:
                    # Initialize services first
                    config, _, github_service = init_services()
                    content = run_async(github_service.verify_branch_content(repo_url, verify_file))
                    st.code(content[:500] + "..." if len(content) > 500 else content)
                except Exception as e:
                    st.error(f"Error verifying file: {e}")

        if st.sidebar.button("Show Diagnostic Info"):
            if 'current_repo' in st.session_state:
                config, _, github_service = init_services()  # Initialize services first
                st.sidebar.json(github_service.get_retrieval_stats())
                st.sidebar.write("Session State Keys:", list(st.session_state.keys()))
                
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
        # Add a divider before usage stats
            st.divider()

            # Usage Statistics Section
            st.header("Usage Statistics")

            tracker = UsageTracker()

            # Get usage for last 24 hours and all time
            now = datetime.now()
            last_24h = (now - timedelta(days=1)).isoformat()

            try:
                # Get usage summaries
                daily_usage = tracker.get_usage_summary(start_date=last_24h)
                total_usage = tracker.get_usage_summary()

                # Create two columns for the metrics
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Last 24 Hours**")
                    st.metric(
                        "Tokens",
                        f"{daily_usage['total_input_tokens'] + daily_usage['total_output_tokens']:,}",
                        f"${daily_usage['total_cost']:.2f}"
                    )

                with col2:
                    st.markdown("**All Time**")
                    st.metric(
                        "Tokens",
                        f"{total_usage['total_input_tokens'] + total_usage['total_output_tokens']:,}",
                        f"${total_usage['total_cost']:.2f}"
                    )

                # Show detailed statistics in an expander
                with st.expander("View Detailed Usage"):
                    # Date range selection
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

                    # Get custom range usage
                    custom_usage = tracker.get_usage_summary(
                        start_date=start_date.isoformat(),
                        end_date=end_date.isoformat()
                    )

                    if custom_usage['usage_by_model']:
                        # Create DataFrame for model usage
                        model_data = []
                        for model, stats in custom_usage['usage_by_model'].items():
                            model_data.append({
                                'Model': model,
                                'Input': stats['input_tokens'],
                                'Output': stats['output_tokens'],
                                'Cost': f"${stats['cost']:.2f}"
                            })

                        df = pd.DataFrame(model_data)
                        st.dataframe(df, hide_index=True)

                        # Create bar chart using plotly express
                        df_melted = pd.melt(
                            df, 
                            id_vars=['Model'], 
                            value_vars=['Input', 'Output'],
                            var_name='Type',
                            value_name='Tokens'
                        )

                        fig = px.bar(
                            df_melted,
                            x='Model',
                            y='Tokens',
                            color='Type',
                            barmode='group',
                            title='Token Usage by Model'
                        )

                        fig.update_layout(
                            height=300,
                            margin=dict(t=30, l=30, r=30, b=30),
                        )

                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No usage data available for the selected date range.")

                if st.button("Refresh Usage Stats", key="refresh_usage"):
                    st.rerun()
                

                # Add a divider before current query stats
                st.divider()

                # Current Query Stats
                st.header("Current Query Stats")
                if st.session_state.get('current_query_stats'):
                    stats = st.session_state.current_query_stats
                    cols = st.columns(2)
                    cols[0].metric("Input Tokens", f"{stats['input_tokens']:,}")
                    cols[1].metric("Output Tokens", f"{stats['output_tokens']:,}")
                    cols = st.columns(2)
                    cols[0].metric("Total Tokens", f"{stats['total_tokens']:,}")
                    cols[1].metric("Cost", f"${stats['estimated_cost']:.4f}")
                else:
                    st.info("No query statistics available yet")

            except Exception as e:
                st.error(f"Error loading usage statistics: {str(e)}")
        
    
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
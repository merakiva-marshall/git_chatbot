# Git Chatbot

A Streamlit application that enables intelligent conversations about GitHub repositories using Claude 3 AI models. The application performs deep repository analysis and maintains contextual awareness across conversations.

## Features

### Repository Analysis
- Comprehensive repository structure analysis
- Branch-specific content examination
- File relationship and dependency mapping
- Support for multiple programming languages
- Real-time code verification capabilities

### AI Integration
- Supports Claude 3.5 Sonnet and Haiku models
- Context-aware responses with repository understanding
- Custom instruction support for AI behavior
- Rate-limited API interactions for stability
- Intelligent code analysis and relationship mapping

### Chat Management
- Persistent chat session storage
- Chat history management
- Named conversation saving
- Chat session loading and restoration
- Title customization for chat sessions

### User Interface
- Clean Streamlit-based interface
- Sidebar configuration options
- Real-time repository analysis feedback
- Diagnostic information display
- Model selection options

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/git_chatbot.git
cd git_chatbot
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with required credentials:
```plaintext
ANTHROPIC_API_KEY=your_key_here
GITHUB_TOKEN=your_github_token
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_api_key
```

5. Run the application:
```bash
streamlit run src/app.py
```

## Directory Structure

```
git_chatbot/
├── data/               # Settings and chat storage
│   ├── settings.json
│   └── chats/
├── src/
│   ├── utils/         # Utility functions
│   ├── vector_store/  # Vector storage (future implementation)
│   ├── app.py         # Main Streamlit application
│   ├── chat_service.py
│   ├── config.py
│   ├── github_service.py
│   └── embedding_service.py
```

## Key Components

### GitHub Service
- Repository content analysis
- Code relationship mapping
- File content verification
- Branch-specific analysis
- Caching system for API requests

### Chat Service
- Claude 3 API integration
- Rate-limited request handling
- Context management
- System prompt construction
- Message history tracking

### Settings Manager
- Configuration persistence
- Chat session management
- Settings customization
- Data directory management

## Current Limitations
- Vector store functionality is prepared but not fully implemented
- Rate limiting on GitHub API requests may affect large repositories
- Some language-specific code analysis features are basic

## Future Enhancements
- Complete vector store implementation for improved code search
- Enhanced language-specific code analysis
- Additional Claude model support as released
- Improved dependency analysis
- Repository comparison features

## Requirements
- Python 3.8+
- Streamlit
- Anthropic API access (Claude 3)
- GitHub API token
- Qdrant (prepared for future vector store implementation)

## Contributing
Contributions are welcome! Please feel free to submit pull requests.

## License
MIT License

## Note
This project is actively developed on the 'full-repo-context-var' branch, which contains the latest features and improvements.
# Git Chatbot

A Streamlit application that allows you to chat with your GitHub repositories using Claude AI. The application analyzes repository content and provides intelligent responses about your codebase.

## Features

- GitHub repository analysis
- Intelligent code understanding
- Context-aware responses using Claude AI
- Vector-based code search
- Streamlit-based user interface

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
```
ANTHROPIC_API_KEY=your_key_here
GITHUB_TOKEN=your_github_token
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_api_key
```

5. Run the application:
```bash
streamlit run src/app.py
```

## Usage

1. Enter a GitHub repository URL in the sidebar
2. Click "Analyze Repository" to process the codebase
3. Ask questions about the repository in the chat interface
4. Receive AI-powered responses about your code

## Deployment

The application can be deployed on Render.com using their free tier services.

## License

MIT License
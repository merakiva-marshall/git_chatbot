import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import asyncio
from anthropic import Anthropic
import os
from dotenv import load_dotenv
from vector_store.embeddings_manager import EmbeddingsManager
from chat_service import ChatService
from github_service import GitHubService

async def test_integration():
    load_dotenv()
    
    print("Initializing services...")
    anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    embeddings_manager = EmbeddingsManager(anthropic_client)
    
    # Initialize services
    chat_service = ChatService(
        anthropic_client,
        embeddings_manager=embeddings_manager,
        model="claude-3-haiku-20240307"  # Using Haiku to minimize costs
    )
    
    # Test repository data (minimal example)
    test_repo = {
        'name': 'test-repo',
        'description': 'Test repository for code analysis',
        'language': 'Python',
        'topics': ['testing', 'python'],
    }
    
    test_files = [{
        'path': 'main.py',
        'content': """
def process_data(data):
    '''Process input data and return results'''
    return [x * 2 for x in data]

class DataProcessor:
    def __init__(self):
        self.cache = {}
    
    def process(self, key, data):
        '''Process data and cache results'''
        if key in self.cache:
            return self.cache[key]
        result = process_data(data)
        self.cache[key] = result
        return result
""",
        'last_modified': '2024-01-01'
    }]
    
    print("\nProcessing test repository...")
    try:
        # Process repository for embeddings
        await embeddings_manager.process_repository("test-repo", test_files)
        print("✅ Repository processed")
        
        # Test questions that use code context
        test_questions = [
            "What does the process_data function do?",
            "How does the caching mechanism work?",
            "What classes are in the codebase?"
        ]
        
        print("\nTesting chat responses...")
        for question in test_questions:
            print(f"\nQ: {question}")
            try:
                response = await chat_service.generate_response(
                    question,
                    repo_info=test_repo
                )
                # Print first 100 chars of response to keep output manageable
                print(f"A: {response[:100]}...")
            except Exception as e:
                print(f"❌ Error: {str(e)}")
                
    except Exception as e:
        print(f"❌ Error in test: {str(e)}")

def main():
    print("Running Integration Test...\n")
    asyncio.run(test_integration())

if __name__ == "__main__":
    main()
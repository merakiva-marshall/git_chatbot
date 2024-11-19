import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import asyncio
from anthropic import Anthropic
from vector_store.embeddings_manager import EmbeddingsManager
import os
from dotenv import load_dotenv

async def test_embeddings():
    load_dotenv()
    
    print("Initializing Embeddings Manager...")
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    manager = EmbeddingsManager(client)
    
    # Test data
    test_files = [
        {
            'path': 'test.py',
            'content': """
import numpy as np
from typing import List

def calculate_similarity(a: List[float], b: List[float]) -> float:
    '''Calculate vector similarity using dot product'''
    return np.dot(a, b)

class VectorStore:
    def __init__(self):
        self.vectors = []
        
    def add_vector(self, vector: List[float]):
        '''Add a vector to the store'''
        self.vectors.append(vector)
""",
            'last_modified': '2024-01-01'
        },
        {
            'path': 'search.py',
            'content': """
from typing import List
import numpy as np

def search_vectors(query: List[float], vectors: List[List[float]]) -> List[int]:
    '''Search for similar vectors using cosine similarity'''
    similarities = [np.dot(query, v) / (np.linalg.norm(query) * np.linalg.norm(v)) 
                   for v in vectors]
    return sorted(range(len(similarities)), key=lambda i: similarities[i], reverse=True)
""",
            'last_modified': '2024-01-01'
        }
    ]
    
    print("\nProcessing test repository...")
    try:
        await manager.process_repository("test_repo", test_files)
        print("✅ Repository processed successfully")
    except Exception as e:
        print(f"❌ Error processing repository: {str(e)}")
    
    print("\nTesting code search...")
    search_queries = [
        "function to calculate similarity between vectors",
        "vector storage class",
        "search functionality"
    ]
    
    for query in search_queries:
        print(f"\nSearching for: '{query}'")
        try:
            results = await manager.search_code(query)
            print(f"Found {len(results)} results:")
            for i, result in enumerate(results, 1):
                print(f"\n{i}. Found in: {result.get('file')}")
                print(f"   Type: {result.get('type')}")
                if 'name' in result:
                    print(f"   Name: {result.get('name')}")
                print(f"   Code type: {result.get('code_type')}")
        except Exception as e:
            print(f"❌ Error searching: {str(e)}")

def main():
    print("Running Embeddings Manager tests...\n")
    asyncio.run(test_embeddings())

if __name__ == "__main__":
    main()
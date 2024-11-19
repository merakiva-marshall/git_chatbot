import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from vector_store.code_processor import CodeProcessor

def test_code_processor():
    processor = CodeProcessor()
    
    # Test Python code processing
    python_code = """
import numpy as np
from typing import List

def calculate_similarity(vec1: List[float], vec2: List[float]) -> float:
    '''Calculate cosine similarity between two vectors'''
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

class VectorSearch:
    def __init__(self):
        self.vectors = []
    
    def add_vector(self, vec: List[float]):
        self.vectors.append(vec)
"""

    # Test JavaScript/TypeScript code
    js_code = """
import React from 'react';
import { useState } from 'react';

export function SearchComponent() {
    const [query, setQuery] = useState('');
    
    const handleSearch = () => {
        console.log('Searching for:', query);
    };

    return (
        <div>
            <input value={query} onChange={e => setQuery(e.target.value)} />
            <button onClick={handleSearch}>Search</button>
        </div>
    );
}
"""

    print("Testing Python code processing...")
    python_chunks = processor.process_file("test.py", python_code)
    for chunk, metadata in python_chunks:
        print(f"\nChunk Type: {metadata['type']}")
        print(f"Metadata: {metadata}")
        print("Content:")
        print(chunk)
        print("-" * 50)

    print("\nTesting JavaScript code processing...")
    js_chunks = processor.process_file("test.tsx", js_code)
    for chunk, metadata in js_chunks:
        print(f"\nChunk Type: {metadata['type']}")
        print(f"Metadata: {metadata}")
        print("Content:")
        print(chunk)
        print("-" * 50)

if __name__ == "__main__":
    print("Running Code Processor tests...\n")
    test_code_processor()
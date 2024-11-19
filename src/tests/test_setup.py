import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from vector_store.qdrant_manager import QdrantManager
from vector_store.code_processor import CodeProcessor

def test_qdrant():
    """Test Qdrant setup"""
    try:
        manager = QdrantManager()
        print("✅ Qdrant manager initialized successfully")
    except Exception as e:
        print(f"❌ Error initializing Qdrant: {str(e)}")

def test_code_processor():
    """Test code processing"""
    processor = CodeProcessor()
    
    test_content = """
def test_function():
    print("Hello")

class TestClass:
    def method(self):
        pass
"""
    
    try:
        chunks = processor.process_file("test.py", test_content)
        print("\n✅ Code processor working")
        print("\nProcessed chunks:")
        for chunk, metadata in chunks:
            print(f"\nChunk type: {metadata['type']}")
            print(f"Content:\n{chunk}")
    except Exception as e:
        print(f"❌ Error processing code: {str(e)}")

if __name__ == "__main__":
    print("Running setup tests...\n")
    test_qdrant()
    test_code_processor()
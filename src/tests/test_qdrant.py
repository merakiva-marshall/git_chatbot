import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from qdrant_client import QdrantClient

def test_basic_qdrant():
    """Test basic Qdrant functionality"""
    try:
        # Create client
        client = QdrantClient(path="data/qdrant")
        print("✅ Successfully created Qdrant client")
        
        # Try to create a test collection
        client.recreate_collection(
            collection_name="test_collection",
            vectors_config={
                "size": 4,
                "distance": "Cosine"
            }
        )
        print("✅ Successfully created test collection")
        
        # List collections
        collections = client.get_collections()
        print(f"✅ Collections list: {collections}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    print("Testing basic Qdrant functionality...")
    test_basic_qdrant()
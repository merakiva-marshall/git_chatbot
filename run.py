import os
import sys
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Run the Streamlit app
if __name__ == "__main__":
    os.system(f"streamlit run {str(src_path / 'app.py')}")
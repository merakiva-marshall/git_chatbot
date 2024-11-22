import os
import sys
from pathlib import Path

# Get the absolute path to the project root directory
project_root = Path(__file__).parent.absolute()
src_path = project_root / "src"

# Add the src directory to Python path
sys.path.insert(0, str(src_path))

# Run the Streamlit app
if __name__ == "__main__":
    os.system(f"streamlit run {str(src_path / 'app.py')}")
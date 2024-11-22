import os
import sys
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent.absolute()
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
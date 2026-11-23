import sys
from pathlib import Path

# Ensure workspace root is always on sys.path for direct pytest invocation
sys.path.insert(0, str(Path(__file__).parent.resolve()))

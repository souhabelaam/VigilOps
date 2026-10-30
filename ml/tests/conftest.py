"""The ml scripts import each other as top-level modules (import windows), so tests do the same."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

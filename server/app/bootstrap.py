"""Only package-path adaptation point; member modules remain unchanged."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
for module in ('agent2', 'agent3', 'agent4'):
    path = str(ROOT / module)
    if path not in sys.path:
        sys.path.insert(0, path)

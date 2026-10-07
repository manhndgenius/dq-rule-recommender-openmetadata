"""Pytest configuration for advanced_rules tests."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Debug: verify path
import os
os.environ["PYTHONPATH"] = str(project_root)

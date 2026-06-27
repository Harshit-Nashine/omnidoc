# ================================================================
# tests/conftest.py
# ================================================================
# Adds the project root to Python path so tests can import
# from services.api.app without ModuleNotFoundError.
# This runs automatically before any test file is collected.
# ================================================================

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
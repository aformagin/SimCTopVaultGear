"""
Root conftest.py: ensure the project root is on sys.path so that
pytest can import the project modules (addon_parser, profileset_generator, etc.)
regardless of how it is invoked.
"""
import sys
import os

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(__file__))

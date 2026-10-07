#!/usr/bin/env python3
"""Portable entry point for the shared, human-reviewed learning workflow."""
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT / 'pocket-fde'))

from pocketfd.learning import main

if __name__ == '__main__':
    main()

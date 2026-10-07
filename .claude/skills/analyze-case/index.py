#!/usr/bin/env python3
"""
Pocket FDE Skill - Entry point for analyze-case skill invocation
Routes case number argument to analyzer
"""

import sys
import os

# Add current directory to path to import analyze module
sys.path.insert(0, os.path.dirname(__file__))

from analyze import load_case, analyze_case, main

if __name__ == "__main__":
    main()

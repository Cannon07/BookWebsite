#!/usr/bin/env python3
"""
Main Overleaf Monitor Pipeline for BookWebsite Integration
This script coordinates the complete pipeline from the main project
"""

import os
import sys

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Import the GitHub Actions compatible pipeline
try:
    from github_actions_pipeline import main as run_pipeline
    
    if __name__ == "__main__":
        success = run_pipeline()
        sys.exit(0 if success else 1)
        
except ImportError as e:
    print(f"❌ Error importing pipeline: {e}")
    print("   Make sure all required scripts are in place")
    sys.exit(1)

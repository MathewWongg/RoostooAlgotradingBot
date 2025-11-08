#!/usr/bin/env python
"""Simple script to run the trading bot"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file if it exists
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(__file__), 'config', '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"Loaded environment variables from {env_path}")
else:
    print(f"Warning: {env_path} not found. Using system environment variables.")

# Now import and run the bot
if __name__ == "__main__":
    try:
        from src.main import main
        main()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


#!/usr/bin/env python
"""Script to run backtesting on the trading bot"""

import sys
import os
import argparse
from datetime import datetime, timedelta

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file if it exists
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(__file__), 'config', '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"Loaded environment variables from {env_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run backtest on trading bot')
    parser.add_argument(
        '--config',
        type=str,
        default='config/config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date in YYYY-MM-DD format (default: 30 days ago)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='End date in YYYY-MM-DD format (default: today)'
    )
    parser.add_argument(
        '--pairs',
        type=str,
        nargs='+',
        help='Trading pairs to backtest (default: from config)'
    )
    parser.add_argument(
        '--initial-balance',
        type=float,
        default=50000.0,
        help='Initial balance for backtest (default: 50000)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='data/backtest_report.json',
        help='Output file for backtest report (default: data/backtest_report.json)'
    )
    
    args = parser.parse_args()
    
    try:
        from src.backtest import Backtester
        
        print("Initializing backtester...")
        backtester = Backtester(
            config_path=args.config,
            initial_balance=args.initial_balance
        )
        
        print("Running backtest...")
        result = backtester.run(
            start_date=args.start_date,
            end_date=args.end_date,
            pairs=args.pairs
        )
        
        print("Saving report...")
        backtester.save_report(result, output_path=args.output)
        
        print(f"\nBacktest completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


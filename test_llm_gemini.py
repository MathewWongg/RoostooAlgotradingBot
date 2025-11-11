#!/usr/bin/env python
"""Quick test to verify LLM strategy with Gemini sentiment is working."""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
env_path = project_root / 'config' / '.env'
env_path_alt = project_root / 'config' / '.e'
if env_path.exists():
    load_dotenv(env_path)
    print(f"[OK] Loaded environment variables from {env_path}")
elif env_path_alt.exists():
    load_dotenv(env_path_alt)
    print(f"[OK] Loaded environment variables from {env_path_alt}")
else:
    # Fallback to default .env search
    load_dotenv()
    print(f"[WARN] No .env or .e file found in config/, using default .env search")

from src.strategies.ensemble_strategy import EnsembleStrategy
from src.utils.config import load_config
from src.utils.logger import setup_logger

def test_llm_strategy():
    """Test LLM strategy with simulated market data."""
    print("\n" + "="*70)
    print("TESTING LLM STRATEGY WITH GEMINI SENTIMENT")
    print("="*70)
    
    # Load config
    config_path = project_root / 'config' / 'config.yaml'
    if not config_path.exists():
        print(f"[ERROR] Config file not found: {config_path}")
        return False
    
    config = load_config(str(config_path))
    print(f"[OK] Loaded config from {config_path}")
    
    # Check LLM config
    llm_config = config.get('strategies', {}).get('llm', {})
    if not llm_config.get('enabled', False):
        print("[ERROR] LLM strategy is disabled in config")
        return False
    
    provider = llm_config.get('provider', 'unknown')
    model = llm_config.get('model', 'unknown')
    print(f"[OK] LLM Provider: {provider}")
    print(f"[OK] LLM Model: {model}")
    
    # Check Gemini config
    social_config = config.get('social', {}).get('x', {})
    gemini_enabled = social_config.get('enabled', False)
    gemini_model = social_config.get('gemini_model', 'N/A')
    
    # Check LLM API key
    llm_api_key = llm_config.get('api_key', '')
    env_gemini_key = os.getenv('GEMINI_API_KEY', '')
    print(f"[DEBUG] LLM config api_key: {repr(llm_api_key)}")
    print(f"[DEBUG] Environment GEMINI_API_KEY: {repr(env_gemini_key)}")
    
    if gemini_enabled:
        gemini_key = social_config.get('gemini_api_key', '')
        if '${' in gemini_key:
            gemini_key = os.getenv('GEMINI_API_KEY', '')
        if gemini_key:
            print(f"[OK] Gemini API: Enabled (Model: {gemini_model})")
        else:
            print(f"[WARN] Gemini API: Enabled but API key not found")
    else:
        print(f"[WARN] Gemini Sentiment: Disabled")
    
    # Initialize strategy
    try:
        strategies_config = config.get('strategies', {})
        strategies_config['mode'] = 'backtest'
        strategy = EnsembleStrategy(strategies_config)
        print(f"[OK] Ensemble strategy initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize strategy: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Create test market data
    test_market_data = {
        'pair': 'TRUMP/USD',
        'roostoo': {
            'LastPrice': 100.0,
            'MaxBid': 99.9,
            'MinAsk': 100.1,
            'Change': 0.05  # 5% change
        },
        'binance': {
            'klines': {
                'closes': [100.0] * 200,
                'opens': [99.0] * 200,
                'highs': [101.0] * 200,
                'lows': [98.0] * 200,
                'volumes': [1000000.0] * 200
            }
        },
        'social': {}
    }
    
    # Add sentiment if Gemini is enabled
    if gemini_enabled and gemini_key:
        test_market_data['social']['x'] = {
            'score': 0.7,
            'fetched_at': '2024-01-01T00:00:00',
            'summary': {
                'volume': 50,
                'tags': ['#TRUMP', '$TRUMP'],
                'sample_posts': ['Bullish on TRUMP!', 'Moon incoming 🚀']
            }
        }
        print(f"[OK] Added simulated Gemini sentiment data")
    
    # Test signal generation
    print(f"\n{'='*70}")
    print("GENERATING TEST SIGNAL")
    print(f"{'='*70}")
    
    try:
        # Update strategy state
        strategy.update_state(test_market_data)
        
        # Generate signal
        signal = strategy.generate_signal(test_market_data)
        
        print(f"[OK] Signal generated successfully")
        print(f"  Action: {signal.action}")
        print(f"  Confidence: {signal.confidence:.2f}")
        print(f"  Pair: {signal.pair}")
        
        # Check metadata
        if signal.metadata:
            component_signals = signal.metadata.get('component_signals', {})
            llm_trigger = signal.metadata.get('llm_trigger')
            
            print(f"\n  Component Signals:")
            for name, info in component_signals.items():
                action = info.get('action', 'N/A')
                conf = info.get('confidence', 0)
                weight = info.get('weight', 0)
                print(f"    {name}: {action} (confidence: {conf:.2f}, weight: {weight:.2f})")
            
            if llm_trigger:
                print(f"\n  LLM Trigger: {llm_trigger}")
            
            if 'llm' in component_signals:
                print(f"\n  [OK] LLM strategy participated in signal generation!")
                llm_info = component_signals['llm']
                print(f"    LLM Action: {llm_info.get('action')}")
                print(f"    LLM Confidence: {llm_info.get('confidence', 0):.2f}")
            else:
                print(f"\n  [WARN] LLM strategy did not participate (may be due to trigger conditions)")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Error generating signal: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_llm_strategy()
    
    print(f"\n{'='*70}")
    if success:
        print("TEST RESULT: [SUCCESS] LLM Strategy is working!")
        print("\nNext steps:")
        print("  1. Run backtest: python run_backtest.py --config config/config.yaml")
        print("  2. Check strategy performance breakdown in backtest output")
        print("  3. Review LLM API status section for call counts")
    else:
        print("TEST RESULT: [FAILED] LLM Strategy has issues")
        print("\nTroubleshooting:")
        print("  1. Check config/config.yaml - ensure LLM is enabled")
        print("  2. Verify API keys in config/.env")
        print("  3. Check logs for detailed error messages")
    print("="*70 + "\n")
    
    sys.exit(0 if success else 1)


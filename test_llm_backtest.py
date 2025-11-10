"""Test script to simulate LLM API calls in backtest mode with simulated signals and X posts."""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List
import copy

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.strategies.ensemble_strategy import EnsembleStrategy
from src.utils.config import load_config
from src.utils.logger import setup_logger


def create_simulated_market_data(
    pair: str,
    price: float,
    price_history: List[float] = None,
    change_pct: float = 0.0,
    trend: str = "sideways",
    x_sentiment: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Create simulated market data for testing."""
    # Build price history if not provided
    if price_history is None:
        # Create a simple history with the current price
        price_history = [price] * 200
    
    # Ensure we have enough history for indicators (at least 200 for SMA)
    if len(price_history) < 200:
        # Pad with initial price
        padding = [price_history[0]] * (200 - len(price_history))
        price_history = padding + price_history
    
    # Use last 200 prices
    price_history = price_history[-200:]
    
    market_data = {
        'pair': pair,
        'roostoo': {
            'LastPrice': price,
            'MaxBid': price * 0.999,
            'MinAsk': price * 1.001,
            'Change': change_pct / 100.0
        },
        'binance': {
            'price': price,
            'klines': {
                'closes': price_history,
                'opens': [p * 0.999 for p in price_history],
                'highs': [p * 1.01 for p in price_history],
                'lows': [p * 0.99 for p in price_history],
                'volumes': [1000000.0] * len(price_history)
            }
        },
        'social': {}
    }
    
    if x_sentiment:
        market_data['social']['x'] = x_sentiment
    
    return market_data


def create_simulated_x_sentiment(
    score: float = 0.0,
    volume: int = 100,
    tags: List[str] = None,
    sample_posts: List[str] = None
) -> Dict[str, Any]:
    """Create simulated X sentiment data."""
    if tags is None:
        tags = ["crypto", "trading"]
    if sample_posts is None:
        sample_posts = [
            "Looking bullish on this coin! 🚀",
            "Great fundamentals, expecting a pump"
        ]
    
    return {
        'score': score,  # -1.0 to 1.0
        'fetched_at': datetime.now().isoformat(),
        'summary': {
            'volume': volume,
            'tags': tags,
            'sample_posts': sample_posts
        },
        'remaining_calls_today': 10
    }


def test_scenario_1_divergence():
    """Test Scenario 1: Force divergence between technical and baseline strategies."""
    print("\n" + "="*70)
    print("SCENARIO 1: Testing LLM Trigger via Signal Divergence")
    print("="*70)
    
    config = load_config("config/config.yaml")
    strategies_config = copy.deepcopy(config.get('strategies', {}))
    strategies_config['mode'] = 'backtest'
    
    # Ensure LLM is enabled and can be called
    strategies_config['llm']['enabled'] = True
    strategies_config['llm']['enable_in_backtest'] = True
    strategies_config['llm']['require_divergence'] = True
    strategies_config['llm']['trigger_confidence'] = 0.7
    strategies_config['llm']['max_calls_per_backtest'] = 10  # Allow multiple calls
    
    strategy = EnsembleStrategy(strategies_config)
    
    # Create market data that might cause divergence
    # We'll need to manipulate price history to force different signals
    pair = "TRUMP/USD"
    
    # Simulate volatile price movement to create divergence
    # Start high, drop sharply, then recover - this should create different signals
    prices = [100.0, 98.0, 95.0, 92.0, 88.0, 85.0, 82.0, 80.0, 78.0, 75.0, 73.0, 70.0, 68.0, 65.0, 63.0, 60.0]
    
    # Build price history as we go
    price_history = []
    
    for i, price in enumerate(prices):
        price_history.append(price)
        market_data = create_simulated_market_data(
            pair=pair,
            price=price,
            price_history=price_history,
            change_pct=-5.0 if i > 0 else 0.0,
            trend="downtrend"
        )
        
        # Update strategy state with price history
        strategy.update_state(market_data)
        
        # Generate signal
        signal = strategy.generate_signal(market_data)
        
        print(f"\nStep {i+1}: Price=${price:.2f}")
        print(f"  Signal: {signal.action} (confidence: {signal.confidence:.2f})")
        
        if signal.metadata:
            component_signals = signal.metadata.get('component_signals', {})
            llm_trigger = signal.metadata.get('llm_trigger')
            
            print(f"  Component signals:")
            for name, sig_data in component_signals.items():
                print(f"    {name}: {sig_data.get('action')} (conf: {sig_data.get('confidence', 0):.2f})")
            
            if llm_trigger:
                print(f"  [LLM] Triggered: {llm_trigger}")
                if 'llm' in component_signals:
                    llm_sig = component_signals['llm']
                    print(f"  LLM Response: {llm_sig.get('action')} (conf: {llm_sig.get('confidence', 0):.2f})")
    
    # Check LLM call count
    total_calls = sum(strategy.llm_backtest_calls.values())
    print(f"\n[STATS] Total LLM calls made: {total_calls}")
    print(f"        Calls by pair: {dict(strategy.llm_backtest_calls)}")


def test_scenario_2_high_confidence():
    """Test Scenario 2: Force high confidence technical signal."""
    print("\n" + "="*70)
    print("SCENARIO 2: Testing LLM Trigger via High Confidence")
    print("="*70)
    
    config = load_config("config/config.yaml")
    strategies_config = copy.deepcopy(config.get('strategies', {}))
    strategies_config['mode'] = 'backtest'
    
    # Configure for high confidence trigger
    strategies_config['llm']['enabled'] = True
    strategies_config['llm']['enable_in_backtest'] = True
    strategies_config['llm']['require_divergence'] = False  # Don't require divergence
    strategies_config['llm']['trigger_confidence'] = 0.6  # Lower threshold
    strategies_config['llm']['max_calls_per_backtest'] = 10
    
    strategy = EnsembleStrategy(strategies_config)
    
    pair = "SOL/USD"
    
    # Simulate strong uptrend (should trigger high confidence BUY)
    # Need more data points to build proper indicators
    base_price = 100.0
    prices = [base_price + (i * 2.5) for i in range(20)]  # Gradual uptrend
    
    # Build price history as we go
    price_history = []
    
    for i, price in enumerate(prices):
        price_history.append(price)
        market_data = create_simulated_market_data(
            pair=pair,
            price=price,
            price_history=price_history,
            change_pct=5.0 if i > 0 else 0.0,
            trend="uptrend"
        )
        
        strategy.update_state(market_data)
        signal = strategy.generate_signal(market_data)
        
        print(f"\nStep {i+1}: Price=${price:.2f}")
        print(f"  Signal: {signal.action} (confidence: {signal.confidence:.2f})")
        
        if signal.metadata:
            component_signals = signal.metadata.get('component_signals', {})
            llm_trigger = signal.metadata.get('llm_trigger')
            
            if llm_trigger:
                print(f"  [LLM] Triggered: {llm_trigger}")
                if 'llm' in component_signals:
                    llm_sig = component_signals['llm']
                    print(f"  LLM Response: {llm_sig.get('action')} (conf: {llm_sig.get('confidence', 0):.2f})")
    
    total_calls = sum(strategy.llm_backtest_calls.values())
    print(f"\n[STATS] Total LLM calls made: {total_calls}")
    print(f"        Calls by pair: {dict(strategy.llm_backtest_calls)}")


def test_scenario_3_with_x_sentiment():
    """Test Scenario 3: LLM call with simulated X sentiment data."""
    print("\n" + "="*70)
    print("SCENARIO 3: Testing LLM with Simulated X Sentiment")
    print("="*70)
    
    config = load_config("config/config.yaml")
    strategies_config = copy.deepcopy(config.get('strategies', {}))
    strategies_config['mode'] = 'backtest'
    
    strategies_config['llm']['enabled'] = True
    strategies_config['llm']['enable_in_backtest'] = True
    strategies_config['llm']['require_divergence'] = False
    strategies_config['llm']['trigger_confidence'] = 0.5  # Lower threshold
    strategies_config['llm']['max_calls_per_backtest'] = 10
    
    strategy = EnsembleStrategy(strategies_config)
    
    pair = "DOGE/USD"
    
    # Simulate bullish sentiment
    bullish_sentiment = create_simulated_x_sentiment(
        score=0.75,  # Strongly bullish
        volume=500,
        tags=["moon", "bullish", "pump"],
        sample_posts=[
            "DOGE to the moon! 🚀🚀🚀",
            "This is going to pump hard!",
            "Buy the dip, we're going up!"
        ]
    )
    
    # Simulate price with sentiment - need more data for indicators
    base_price = 0.10
    prices = [base_price + (i * 0.01) for i in range(15)]  # Gradual uptrend
    
    # Build price history as we go
    price_history = []
    
    for i, price in enumerate(prices):
        price_history.append(price)
        market_data = create_simulated_market_data(
            pair=pair,
            price=price,
            price_history=price_history,
            change_pct=10.0 if i > 0 else 0.0,
            trend="uptrend",
            x_sentiment=bullish_sentiment
        )
        
        strategy.update_state(market_data)
        signal = strategy.generate_signal(market_data)
        
        print(f"\nStep {i+1}: Price=${price:.4f}, Sentiment Score: {bullish_sentiment['score']:.2f}")
        print(f"  Signal: {signal.action} (confidence: {signal.confidence:.2f})")
        
        if signal.metadata:
            llm_trigger = signal.metadata.get('llm_trigger')
            if llm_trigger:
                print(f"  [LLM] Triggered: {llm_trigger}")
                if 'llm' in signal.metadata.get('component_signals', {}):
                    llm_sig = signal.metadata['component_signals']['llm']
                    print(f"  LLM Response: {llm_sig.get('action')} (conf: {llm_sig.get('confidence', 0):.2f})")
                    # Check if sentiment was included
                    if 'sentiment' in signal.metadata:
                        print(f"  Sentiment included in LLM analysis: [OK]")
    
    total_calls = sum(strategy.llm_backtest_calls.values())
    print(f"\n[STATS] Total LLM calls made: {total_calls}")
    print(f"        Calls by pair: {dict(strategy.llm_backtest_calls)}")


def test_scenario_4_rate_limiting():
    """Test Scenario 4: Verify rate limiting works correctly."""
    print("\n" + "="*70)
    print("SCENARIO 4: Testing LLM Rate Limiting")
    print("="*70)
    
    config = load_config("config/config.yaml")
    strategies_config = copy.deepcopy(config.get('strategies', {}))
    strategies_config['mode'] = 'backtest'
    
    strategies_config['llm']['enabled'] = True
    strategies_config['llm']['enable_in_backtest'] = True
    strategies_config['llm']['require_divergence'] = False
    strategies_config['llm']['trigger_confidence'] = 0.3  # Very low to trigger often
    strategies_config['llm']['max_calls_per_backtest'] = 3  # Limit to 3 calls
    
    strategy = EnsembleStrategy(strategies_config)
    
    pair = "ETH/USD"
    
    # Generate many signals to test rate limiting
    prices = [2000.0 + (i * 10) for i in range(20)]
    
    # Build price history as we go
    price_history = []
    call_count = 0
    
    for i, price in enumerate(prices):
        price_history.append(price)
        market_data = create_simulated_market_data(
            pair=pair,
            price=price,
            price_history=price_history,
            change_pct=0.5,
            trend="uptrend"
        )
        
        strategy.update_state(market_data)
        signal = strategy.generate_signal(market_data)
        
        if signal.metadata:
            llm_trigger = signal.metadata.get('llm_trigger')
            if llm_trigger and 'llm' in signal.metadata.get('component_signals', {}):
                call_count += 1
                print(f"Step {i+1}: LLM call #{call_count} triggered")
    
    total_calls = sum(strategy.llm_backtest_calls.values())
    print(f"\n[STATS] Total LLM calls made: {total_calls} (limit was 3)")
    print(f"        Expected: <=3, Actual: {total_calls}")
    
    if total_calls <= 3:
        print("   [OK] Rate limiting working correctly!")
    else:
        print("   [ERROR] Rate limiting not working!")


def main():
    """Run all test scenarios."""
    print("\n" + "="*70)
    print("LLM API BACKTEST SIMULATION TESTS")
    print("="*70)
    print("\nThis script tests LLM API integration in backtest mode by:")
    print("  1. Simulating market conditions that trigger LLM calls")
    print("  2. Injecting simulated X sentiment data")
    print("  3. Verifying rate limiting works correctly")
    print("\nNote: This will make actual API calls if LLM is enabled!")
    print("="*70)
    
    try:
        # Test all scenarios
        test_scenario_1_divergence()
        test_scenario_2_high_confidence()
        test_scenario_3_with_x_sentiment()
        test_scenario_4_rate_limiting()
        
        print("\n" + "="*70)
        print("ALL TESTS COMPLETED")
        print("="*70)
        print("\nCheck the output above to verify:")
        print("  [OK] LLM calls were triggered when expected")
        print("  [OK] LLM responses were received")
        print("  [OK] Rate limiting works correctly")
        print("  [OK] X sentiment data is included when available")
        
    except Exception as e:
        print(f"\n[ERROR] Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


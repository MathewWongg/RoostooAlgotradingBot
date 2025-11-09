"""Baseline Strategy with Momentum and Mean Reversion"""

from typing import Dict, Any, List
from .base_strategy import BaseStrategy, TradingSignal
from ..utils.logger import get_logger


class BaselineStrategy(BaseStrategy):
    """Simple baseline strategy using momentum and mean reversion."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize baseline strategy.
        
        Config parameters:
            momentum_window: Window for momentum calculation (default: 5)
            mean_reversion_threshold: Threshold for mean reversion (default: 0.02)
            momentum_weight: Weight for momentum signals (default: 0.6)
            mean_reversion_weight: Weight for mean reversion signals (default: 0.4)
        """
        super().__init__("BaselineStrategy", config)
        self.logger = get_logger("baseline_strategy")
        
        self.momentum_window = config.get('momentum_window', 5)
        self.mean_reversion_threshold = config.get('mean_reversion_threshold', 0.02)
        self.momentum_weight = config.get('momentum_weight', 0.6)
        self.mean_reversion_weight = config.get('mean_reversion_weight', 0.4)
        
        # Price history
        self.price_history: Dict[str, List[float]] = {}
    
    def update_state(self, market_data: Dict[str, Any]):
        """Update price history with new market data."""
        pair = market_data.get('pair', '')
        roostoo_data = market_data.get('roostoo', {})
        
        if not pair:
            return

        binance_data = market_data.get('binance', {}) or {}
        binance_klines = binance_data.get('klines', {}) if isinstance(binance_data, dict) else {}
        closes = binance_klines.get('closes') if isinstance(binance_klines, dict) else None

        if closes:
            max_history = max(self.momentum_window * 4, 100)
            self.price_history[pair] = closes[-max_history:]
            return

        if roostoo_data:
            price = roostoo_data.get('LastPrice')
            if price:
                history = self.price_history.setdefault(pair, [])
                history.append(price)
                max_history = max(self.momentum_window * 4, 100)
                if len(history) > max_history:
                    self.price_history[pair] = history[-max_history:]
    
    def _calculate_momentum_signal(self, prices: List[float]) -> tuple:
        """
        Calculate momentum signal.
        
        Returns:
            Tuple of (action, confidence)
        """
        if len(prices) < self.momentum_window + 1:
            return ("HOLD", 0.0)
        
        recent_prices = prices[-self.momentum_window:]
        previous_prices = prices[-self.momentum_window-1:-1]
        
        current_avg = sum(recent_prices) / len(recent_prices)
        previous_avg = sum(previous_prices) / len(previous_prices)
        
        momentum = (current_avg - previous_avg) / previous_avg if previous_avg > 0 else 0
        
        if momentum > 0.01:  # 1% positive momentum
            return ("BUY", min(0.7, abs(momentum) * 10))
        elif momentum < -0.01:  # 1% negative momentum
            return ("SELL", min(0.7, abs(momentum) * 10))
        else:
            return ("HOLD", 0.3)
    
    def _calculate_mean_reversion_signal(self, prices: List[float], current_price: float) -> tuple:
        """
        Calculate mean reversion signal.
        
        Returns:
            Tuple of (action, confidence)
        """
        if len(prices) < self.momentum_window:
            return ("HOLD", 0.0)
        
        mean_price = sum(prices[-self.momentum_window:]) / len(prices[-self.momentum_window:])
        deviation = (current_price - mean_price) / mean_price if mean_price > 0 else 0
        
        if deviation < -self.mean_reversion_threshold:
            # Price below mean, buy signal
            return ("BUY", min(0.8, abs(deviation) / self.mean_reversion_threshold * 0.5))
        elif deviation > self.mean_reversion_threshold:
            # Price above mean, sell signal
            return ("SELL", min(0.8, abs(deviation) / self.mean_reversion_threshold * 0.5))
        else:
            return ("HOLD", 0.3)
    
    def generate_signal(self, market_data: Dict[str, Any]) -> TradingSignal:
        """Generate trading signal based on momentum and mean reversion."""
        pair = market_data.get('pair', '')
        roostoo_data = market_data.get('roostoo', {}) or {}
        binance_data = market_data.get('binance', {}) or {}
        
        if not pair:
            return TradingSignal(action="HOLD", confidence=0.0, pair=pair)
        
        current_price = roostoo_data.get('LastPrice') or binance_data.get('price')
        if not current_price:
            return TradingSignal(action="HOLD", confidence=0.0, pair=pair)
        
        prices = self.price_history.get(pair, [])
        if len(prices) < self.momentum_window + 1:
            return TradingSignal(action="HOLD", confidence=0.0, pair=pair)
        
        # Calculate momentum signal
        momentum_action, momentum_conf = self._calculate_momentum_signal(prices)
        
        # Calculate mean reversion signal
        mr_action, mr_conf = self._calculate_mean_reversion_signal(prices, current_price)
        
        # Combine signals with weights
        momentum_score = 1.0 if momentum_action == "BUY" else (-1.0 if momentum_action == "SELL" else 0.0)
        mr_score = 1.0 if mr_action == "BUY" else (-1.0 if mr_action == "SELL" else 0.0)
        
        combined_score = (momentum_score * self.momentum_weight * momentum_conf +
                         mr_score * self.mean_reversion_weight * mr_conf)
        
        if combined_score > 0.3:
            action = "BUY"
            confidence = min(0.8, abs(combined_score))
        elif combined_score < -0.3:
            action = "SELL"
            confidence = min(0.8, abs(combined_score))
        else:
            action = "HOLD"
            confidence = 0.3
        
        metadata = {
            'momentum_signal': momentum_action,
            'momentum_confidence': momentum_conf,
            'mean_reversion_signal': mr_action,
            'mean_reversion_confidence': mr_conf,
            'combined_score': combined_score,
            'binance_price': binance_data.get('price'),
            'strategy': self.name
        }
        
        return TradingSignal(
            action=action,
            confidence=confidence,
            pair=pair,
            price=current_price,
            metadata=metadata
        )


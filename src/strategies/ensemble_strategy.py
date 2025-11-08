"""Ensemble Strategy Combining Multiple Strategies"""

from typing import Dict, Any, List
from .base_strategy import BaseStrategy, TradingSignal
from .technical_strategy import TechnicalStrategy
from .baseline_strategy import BaselineStrategy
from .llm_strategy import LLMStrategy
from ..utils.logger import get_logger


class EnsembleStrategy(BaseStrategy):
    """Ensemble strategy that combines multiple strategies with weighted voting."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize ensemble strategy.
        
        Config parameters:
            ensemble:
                technical_weight: Weight for technical strategy (default: 0.4)
                llm_weight: Weight for LLM strategy (default: 0.3)
                baseline_weight: Weight for baseline strategy (default: 0.3)
            technical: Technical strategy config
            baseline: Baseline strategy config
            llm: LLM strategy config
        """
        super().__init__("EnsembleStrategy", config)
        self.logger = get_logger("ensemble_strategy")
        
        ensemble_config = config.get('ensemble', {})
        self.technical_weight = ensemble_config.get('technical_weight', 0.4)
        self.llm_weight = ensemble_config.get('llm_weight', 0.3)
        self.baseline_weight = ensemble_config.get('baseline_weight', 0.3)
        
        # Normalize weights
        total_weight = self.technical_weight + self.llm_weight + self.baseline_weight
        if total_weight > 0:
            self.technical_weight /= total_weight
            self.llm_weight /= total_weight
            self.baseline_weight /= total_weight
        
        # Initialize component strategies
        self.technical_strategy = TechnicalStrategy(config.get('technical', {}))
        self.baseline_strategy = BaselineStrategy(config.get('baseline', {}))
        self.llm_strategy = LLMStrategy(config.get('llm', {}))
        
        self.strategies = [
            (self.technical_strategy, self.technical_weight),
            (self.baseline_strategy, self.baseline_weight),
            (self.llm_strategy, self.llm_weight)
        ]
    
    def update_state(self, market_data: Dict[str, Any]):
        """Update state for all component strategies."""
        for strategy, _ in self.strategies:
            strategy.update_state(market_data)
    
    def generate_signal(self, market_data: Dict[str, Any]) -> TradingSignal:
        """Generate ensemble signal by combining all strategy signals."""
        pair = market_data.get('pair', '')
        
        # Get signals from all strategies
        signals: List[tuple] = []  # (signal, weight)
        
        for strategy, weight in self.strategies:
            try:
                signal = strategy.generate_signal(market_data)
                signals.append((signal, weight))
            except Exception as e:
                self.logger.error(f"Error getting signal from {strategy.name}: {e}")
        
        if not signals:
            return TradingSignal(action="HOLD", confidence=0.0, pair=pair)
        
        # Combine signals with weighted voting
        buy_score = 0.0
        sell_score = 0.0
        hold_score = 0.0
        total_confidence = 0.0
        
        signal_metadata = {}
        
        for signal, weight in signals:
            confidence = signal.confidence * weight
            
            if signal.action == "BUY":
                buy_score += confidence
            elif signal.action == "SELL":
                sell_score += confidence
            else:
                hold_score += confidence
            
            total_confidence += confidence
            signal_metadata[signal.metadata.get('strategy', 'unknown')] = {
                'action': signal.action,
                'confidence': signal.confidence,
                'weight': weight
            }
        
        # Determine final action
        if buy_score > sell_score and buy_score > hold_score:
            action = "BUY"
            confidence = min(0.95, buy_score / max(0.1, total_confidence))
        elif sell_score > buy_score and sell_score > hold_score:
            action = "SELL"
            confidence = min(0.95, sell_score / max(0.1, total_confidence))
        else:
            action = "HOLD"
            confidence = 0.3
        
        # Get price from first available signal
        price = None
        for signal, _ in signals:
            if signal.price:
                price = signal.price
                break
        
        metadata = {
            'buy_score': buy_score,
            'sell_score': sell_score,
            'hold_score': hold_score,
            'total_confidence': total_confidence,
            'component_signals': signal_metadata,
            'weights': {
                'technical': self.technical_weight,
                'baseline': self.baseline_weight,
                'llm': self.llm_weight
            }
        }
        
        return TradingSignal(
            action=action,
            confidence=confidence,
            pair=pair,
            price=price,
            metadata=metadata
        )
    
    def reset(self):
        """Reset all component strategies."""
        super().reset()
        for strategy, _ in self.strategies:
            strategy.reset()


"""Ensemble Strategy Combining Multiple Strategies"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
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
        self.mode = config.get('mode', 'live')
        llm_config = config.get('llm', {})

        self.technical_strategy = TechnicalStrategy(config.get('technical', {}))
        self.baseline_strategy = BaselineStrategy(config.get('baseline', {}))
        self.llm_strategy = LLMStrategy(llm_config)
        self.llm_trigger_confidence = llm_config.get('trigger_confidence', 0.7)
        self.llm_require_divergence = llm_config.get('require_divergence', True)
        capital_cfg = llm_config.get('capital_multipliers', {})
        self.capital_multipliers = {
            'default': capital_cfg.get('default', 0.5),
            'divergence': capital_cfg.get('divergence', 0.7),
            'confidence': capital_cfg.get('confidence', 0.9),
            'llm_confirmed': capital_cfg.get('llm_confirmed', 1.0),
        }
        self.llm_max_calls_per_day = llm_config.get('max_calls_per_day', 2)
        self.llm_max_calls_per_backtest = llm_config.get('max_calls_per_backtest', 1)
        self.llm_enable_in_backtest = llm_config.get('enable_in_backtest', True)
        self.llm_call_log: Dict[str, List[datetime]] = {}
        self.llm_backtest_calls: Dict[str, int] = {}
    
    def update_state(self, market_data: Dict[str, Any]):
        """Update state for all component strategies."""
        self.technical_strategy.update_state(market_data)
        self.baseline_strategy.update_state(market_data)
        self.llm_strategy.update_state(market_data)
    
    def generate_signal(self, market_data: Dict[str, Any]) -> TradingSignal:
        """Generate ensemble signal by combining all strategy signals."""
        pair = market_data.get('pair', '')
        
        # Collect base signals
        signals: List[tuple] = []
        strategy_records: List[tuple] = []

        technical_signal = self._safe_generate(self.technical_strategy, market_data)
        baseline_signal = self._safe_generate(self.baseline_strategy, market_data)

        if technical_signal:
            strategy_records.append(("technical", technical_signal, self.technical_weight))
        if baseline_signal:
            strategy_records.append(("baseline", baseline_signal, self.baseline_weight))

        if not strategy_records:
            return TradingSignal(action="HOLD", confidence=0.0, pair=pair)

        # Determine if LLM should participate
        should_call_llm, trigger_reason = self._should_call_llm(
            pair,
            technical_signal,
            baseline_signal
        )
        llm_signal = None

        if should_call_llm and self.llm_strategy.enabled:
            llm_signal = self._safe_generate(self.llm_strategy, market_data)
            self._register_llm_call(pair)
            if llm_signal:
                strategy_records.append(("llm", llm_signal, self.llm_weight))

        if not strategy_records:
            return TradingSignal(action="HOLD", confidence=0.0, pair=pair)

        total_weight = sum(weight for _, _, weight in strategy_records)
        if total_weight <= 0:
            return TradingSignal(action="HOLD", confidence=0.0, pair=pair)

        for name, signal, weight in strategy_records:
            normalized_weight = weight / total_weight if total_weight else 0
            signals.append((name, signal, normalized_weight))
        
        # Combine signals with weighted voting
        buy_score = 0.0
        sell_score = 0.0
        hold_score = 0.0
        total_confidence = 0.0
        
        signal_metadata = {}
        
        for strategy_name, signal, weight in signals:
            confidence = signal.confidence * weight
            
            if signal.action == "BUY":
                buy_score += confidence
            elif signal.action == "SELL":
                sell_score += confidence
            else:
                hold_score += confidence
            
            total_confidence += confidence
            metadata_name = strategy_name
            if signal.metadata:
                metadata_name = signal.metadata.get('strategy', strategy_name)
            signal_metadata[metadata_name] = {
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
        for _, signal, _ in signals:
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
                name: weight for name, _, weight in signals
            },
            'llm_trigger': trigger_reason,
        }

        capital_multiplier = self._determine_capital_multiplier(trigger_reason, technical_signal, llm_signal)
        metadata['capital_multiplier'] = capital_multiplier
        
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
        self.technical_strategy.reset()
        self.baseline_strategy.reset()
        self.llm_strategy.reset()
        self.llm_call_log.clear()
        self.llm_backtest_calls.clear()

    def _safe_generate(self, strategy: BaseStrategy, market_data: Dict[str, Any]) -> Optional[TradingSignal]:
        try:
            return strategy.generate_signal(market_data)
        except Exception as exc:
            self.logger.error(f"Error getting signal from {strategy.name}: {exc}")
            return None

    def _should_call_llm(
        self,
        pair: str,
        technical_signal: Optional[TradingSignal],
        baseline_signal: Optional[TradingSignal]
    ) -> Tuple[bool, Optional[str]]:
        if not technical_signal or not baseline_signal:
            return False, None

        if self.mode == 'backtest':
            if not self.llm_enable_in_backtest:
                return False, None
            calls = self.llm_backtest_calls.get(pair, 0)
            if calls >= self.llm_max_calls_per_backtest:
                return False, None
        else:
            if self._remaining_llm_calls_today(pair) <= 0:
                return False, None

        divergence = (
            self.llm_require_divergence
            and technical_signal.action != baseline_signal.action
            and technical_signal.action != "HOLD"
            and baseline_signal.action != "HOLD"
        )

        high_confidence = (
            technical_signal.action in {"BUY", "SELL"}
            and technical_signal.confidence >= self.llm_trigger_confidence
        )

        if divergence:
            return True, "divergence"
        if high_confidence:
            return True, "confidence"
        return False, None

    def _determine_capital_multiplier(
        self,
        trigger_reason: Optional[str],
        technical_signal: Optional[TradingSignal],
        llm_signal: Optional[TradingSignal]
    ) -> float:
        multiplier = self.capital_multipliers.get('default', 0.5)

        if trigger_reason == "divergence":
            multiplier = self.capital_multipliers.get('divergence', multiplier)
        elif trigger_reason == "confidence":
            multiplier = self.capital_multipliers.get('confidence', multiplier)

        if trigger_reason and llm_signal and llm_signal.confidence >= 0.6:
            multiplier = max(multiplier, self.capital_multipliers.get('llm_confirmed', multiplier))

        if technical_signal and technical_signal.action == "HOLD":
            multiplier = min(multiplier, 0.5)

        return max(0.0, multiplier)

    def _remaining_llm_calls_today(self, pair: str) -> int:
        now = datetime.now(timezone.utc)
        entries = self.llm_call_log.get(pair, [])
        filtered = [
            ts for ts in entries
            if now - ts < timedelta(days=1)
        ]
        self.llm_call_log[pair] = filtered
        return max(0, self.llm_max_calls_per_day - len(filtered))

    def _register_llm_call(self, pair: str):
        now = datetime.now(timezone.utc)
        self.llm_call_log.setdefault(pair, []).append(now)
        self._remaining_llm_calls_today(pair)  # prune old entries
        if self.mode == 'backtest':
            self.llm_backtest_calls[pair] = self.llm_backtest_calls.get(pair, 0) + 1


"""Technical Analysis Strategy with Indicators"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
from .base_strategy import BaseStrategy, TradingSignal
from ..utils.logger import get_logger


class TechnicalStrategy(BaseStrategy):
    """Technical analysis strategy using RSI, MACD, and Bollinger Bands."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize technical strategy.
        
        Config parameters:
            rsi_period: RSI period (default: 14)
            rsi_oversold: RSI oversold threshold (default: 30)
            rsi_overbought: RSI overbought threshold (default: 70)
            macd_fast: MACD fast period (default: 12)
            macd_slow: MACD slow period (default: 26)
            macd_signal: MACD signal period (default: 9)
            bb_period: Bollinger Bands period (default: 20)
            bb_std: Bollinger Bands standard deviations (default: 2)
        """
        super().__init__("TechnicalStrategy", config)
        self.logger = get_logger("technical_strategy")
        
        # RSI parameters
        self.rsi_period = config.get('rsi_period', 14)
        self.rsi_oversold = config.get('rsi_oversold', 30)
        self.rsi_overbought = config.get('rsi_overbought', 70)
        
        # MACD parameters
        self.macd_fast = config.get('macd_fast', 12)
        self.macd_slow = config.get('macd_slow', 26)
        self.macd_signal = config.get('macd_signal', 9)
        
        # Bollinger Bands parameters
        self.bb_period = config.get('bb_period', 20)
        self.bb_std = config.get('bb_std', 2)
        
        # Price history for indicators
        self.price_history: Dict[str, List[float]] = {}
    
    def _calculate_rsi(self, prices: List[float], period: int) -> float:
        """Calculate Relative Strength Index."""
        if len(prices) < period + 1:
            return 50.0  # Neutral RSI
        
        prices = prices[-period-1:]
        deltas = np.diff(prices)
        
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_macd(self, prices: List[float]) -> Dict[str, float]:
        """Calculate MACD indicator."""
        if len(prices) < self.macd_slow:
            return {'macd': 0, 'signal': 0, 'histogram': 0}
        
        prices = prices[-self.macd_slow:]
        df = pd.Series(prices)
        
        ema_fast = df.ewm(span=self.macd_fast, adjust=False).mean().iloc[-1]
        ema_slow = df.ewm(span=self.macd_slow, adjust=False).mean().iloc[-1]
        
        macd = ema_fast - ema_slow
        
        # For signal line, we need more history
        if len(prices) >= self.macd_slow + self.macd_signal:
            macd_series = []
            for i in range(self.macd_slow, len(prices)):
                fast_ema = df.iloc[i-self.macd_fast:i+1].ewm(span=self.macd_fast, adjust=False).mean().iloc[-1]
                slow_ema = df.iloc[i-self.macd_slow:i+1].ewm(span=self.macd_slow, adjust=False).mean().iloc[-1]
                macd_series.append(fast_ema - slow_ema)
            
            signal = pd.Series(macd_series).ewm(span=self.macd_signal, adjust=False).mean().iloc[-1]
        else:
            signal = macd
        
        histogram = macd - signal
        
        return {'macd': macd, 'signal': signal, 'histogram': histogram}
    
    def _calculate_bollinger_bands(self, prices: List[float]) -> Dict[str, float]:
        """Calculate Bollinger Bands."""
        if len(prices) < self.bb_period:
            return {'upper': 0, 'middle': 0, 'lower': 0}
        
        prices = prices[-self.bb_period:]
        middle = np.mean(prices)
        std = np.std(prices)
        
        upper = middle + (self.bb_std * std)
        lower = middle - (self.bb_std * std)
        
        return {'upper': upper, 'middle': middle, 'lower': lower}
    
    def update_state(self, market_data: Dict[str, Any]):
        """Update price history with new market data."""
        pair = market_data.get('pair', '')
        if not pair:
            return

        binance_data = market_data.get('binance', {}) or {}
        binance_klines = binance_data.get('klines', {}) if isinstance(binance_data, dict) else {}
        closes = binance_klines.get('closes') if isinstance(binance_klines, dict) else None

        if closes:
            max_history = max(300, self.bb_period * 3, self.macd_slow + self.macd_signal + 20)
            self.price_history[pair] = closes[-max_history:]
            return

        roostoo_data = market_data.get('roostoo', {})
        if roostoo_data:
            price = roostoo_data.get('LastPrice')
            if price:
                history = self.price_history.setdefault(pair, [])
                history.append(price)
                if len(history) > 300:
                    self.price_history[pair] = history[-300:]
    
    def generate_signal(self, market_data: Dict[str, Any]) -> TradingSignal:
        """Generate trading signal based on technical indicators."""
        pair = market_data.get('pair', '')
        roostoo_data = market_data.get('roostoo', {}) or {}
        binance_data = market_data.get('binance', {}) or {}

        if not pair:
            return TradingSignal(action="HOLD", confidence=0.0, pair=pair)

        current_price = roostoo_data.get('LastPrice') or binance_data.get('price')
        if not current_price:
            return TradingSignal(action="HOLD", confidence=0.0, pair=pair)
        
        # Get price history
        prices = self.price_history.get(pair, [])
        if len(prices) < max(self.rsi_period, self.macd_slow, self.bb_period):
            return TradingSignal(action="HOLD", confidence=0.0, pair=pair)
        
        # Calculate indicators
        rsi = self._calculate_rsi(prices, self.rsi_period)
        macd_data = self._calculate_macd(prices)
        bb_data = self._calculate_bollinger_bands(prices)
        
        # Generate signals from indicators
        signals = []
        confidence_scores = []
        
        # RSI signals
        if rsi < self.rsi_oversold:
            signals.append("BUY")
            confidence_scores.append(0.6)
        elif rsi > self.rsi_overbought:
            signals.append("SELL")
            confidence_scores.append(0.6)
        else:
            signals.append("HOLD")
            confidence_scores.append(0.3)
        
        # MACD signals
        if macd_data['histogram'] > 0 and macd_data['macd'] > macd_data['signal']:
            signals.append("BUY")
            confidence_scores.append(0.5)
        elif macd_data['histogram'] < 0 and macd_data['macd'] < macd_data['signal']:
            signals.append("SELL")
            confidence_scores.append(0.5)
        else:
            signals.append("HOLD")
            confidence_scores.append(0.2)
        
        # Bollinger Bands signals
        if current_price < bb_data['lower']:
            signals.append("BUY")
            confidence_scores.append(0.4)
        elif current_price > bb_data['upper']:
            signals.append("SELL")
            confidence_scores.append(0.4)
        else:
            signals.append("HOLD")
            confidence_scores.append(0.2)
        
        # Aggregate signals
        buy_count = signals.count("BUY")
        sell_count = signals.count("SELL")
        hold_count = signals.count("HOLD")
        
        if buy_count > sell_count and buy_count > hold_count:
            action = "BUY"
            confidence = min(0.9, sum(confidence_scores) / len(confidence_scores) + 0.2)
        elif sell_count > buy_count and sell_count > hold_count:
            action = "SELL"
            confidence = min(0.9, sum(confidence_scores) / len(confidence_scores) + 0.2)
        else:
            action = "HOLD"
            confidence = 0.3
        
        metadata = {
            'rsi': rsi,
            'macd': macd_data,
            'bollinger_bands': bb_data,
            'signals': signals,
            'strategy': self.name,
            'binance_indicators': binance_data.get('indicators')
        }
        
        return TradingSignal(
            action=action,
            confidence=confidence,
            pair=pair,
            price=current_price,
            metadata=metadata
        )


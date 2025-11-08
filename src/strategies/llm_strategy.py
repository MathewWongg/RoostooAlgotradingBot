"""LLM-Based Strategy for Market Analysis"""

import json
import hashlib
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy, TradingSignal
from ..utils.logger import get_logger


class LLMStrategy(BaseStrategy):
    """LLM-based strategy using OpenAI or Anthropic for market analysis."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize LLM strategy.
        
        Config parameters:
            provider: "openai" or "anthropic" (default: "openai")
            model: Model name (default: "gpt-4" or "claude-3-opus")
            api_key: API key (from environment)
            enabled: Whether LLM is enabled (default: True)
            cache_responses: Whether to cache responses (default: True)
            max_tokens: Maximum tokens for response (default: 200)
        """
        super().__init__("LLMStrategy", config)
        self.logger = get_logger("llm_strategy")
        
        self.provider = config.get('provider', 'openai').lower()
        self.model = config.get('model', 'gpt-4' if self.provider == 'openai' else 'claude-3-opus-20240229')
        self.enabled = config.get('enabled', True)
        self.cache_responses = config.get('cache_responses', True)
        self.max_tokens = config.get('max_tokens', 200)
        
        # Initialize LLM client
        self.llm_client = None
        self.cache: Dict[str, str] = {}
        
        if self.enabled:
            try:
                if self.provider == 'openai':
                    import openai
                    api_key = config.get('api_key') or self._get_env_key('OPENAI_API_KEY')
                    if api_key:
                        self.llm_client = openai.OpenAI(api_key=api_key)
                    else:
                        self.logger.warning("OpenAI API key not found, LLM strategy disabled")
                        self.enabled = False
                elif self.provider == 'anthropic':
                    import anthropic
                    api_key = config.get('api_key') or self._get_env_key('ANTHROPIC_API_KEY')
                    if api_key:
                        self.llm_client = anthropic.Anthropic(api_key=api_key)
                    else:
                        self.logger.warning("Anthropic API key not found, LLM strategy disabled")
                        self.enabled = False
                else:
                    self.logger.warning(f"Unknown LLM provider: {self.provider}")
                    self.enabled = False
            except ImportError:
                self.logger.warning(f"{self.provider} library not installed, LLM strategy disabled")
                self.enabled = False
        
        # Price history for context
        self.price_history: Dict[str, list] = {}
    
    def _get_env_key(self, key: str) -> Optional[str]:
        """Get API key from environment."""
        import os
        return os.getenv(key)
    
    def _get_cache_key(self, market_data: Dict[str, Any]) -> str:
        """Generate cache key from market data."""
        pair = market_data.get('pair', '')
        price = market_data.get('roostoo', {}).get('LastPrice', 0)
        change = market_data.get('roostoo', {}).get('Change', 0)
        
        data_str = f"{pair}:{price}:{change}"
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def _call_openai(self, prompt: str) -> Optional[str]:
        """Call OpenAI API."""
        try:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a crypto trading analyst. Provide concise trading signals: BUY, SELL, or HOLD. Format: ACTION:CONFIDENCE (0.0-1.0)"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            return None
    
    def _call_anthropic(self, prompt: str) -> Optional[str]:
        """Call Anthropic API."""
        try:
            message = self.llm_client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0.3,
                system="You are a crypto trading analyst. Provide concise trading signals: BUY, SELL, or HOLD. Format: ACTION:CONFIDENCE (0.0-1.0)",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return message.content[0].text
        except Exception as e:
            self.logger.error(f"Anthropic API error: {e}")
            return None
    
    def _analyze_with_llm(self, market_data: Dict[str, Any]) -> Optional[str]:
        """Analyze market data with LLM."""
        if not self.enabled or not self.llm_client:
            return None
        
        # Check cache
        if self.cache_responses:
            cache_key = self._get_cache_key(market_data)
            if cache_key in self.cache:
                return self.cache[cache_key]
        
        # Build prompt
        pair = market_data.get('pair', '')
        roostoo_data = market_data.get('roostoo', {})
        
        price = roostoo_data.get('LastPrice', 0)
        change = roostoo_data.get('Change', 0)
        change_pct = change * 100
        
        prices = self.price_history.get(pair, [])
        price_trend = ""
        if len(prices) >= 5:
            recent_avg = sum(prices[-5:]) / 5
            older_avg = sum(prices[-10:-5]) / 5 if len(prices) >= 10 else recent_avg
            if recent_avg > older_avg * 1.02:
                price_trend = "uptrend"
            elif recent_avg < older_avg * 0.98:
                price_trend = "downtrend"
            else:
                price_trend = "sideways"
        
        prompt = f"""Analyze this crypto market data and provide a trading signal:

Pair: {pair}
Current Price: ${price:,.2f}
24h Change: {change_pct:.2f}%
Price Trend: {price_trend}

Based on this data, should I BUY, SELL, or HOLD? Provide your answer as: ACTION:CONFIDENCE
Where ACTION is BUY, SELL, or HOLD, and CONFIDENCE is a number between 0.0 and 1.0."""
        
        # Call LLM
        if self.provider == 'openai':
            response = self._call_openai(prompt)
        elif self.provider == 'anthropic':
            response = self._call_anthropic(prompt)
        else:
            response = None
        
        # Cache response
        if response and self.cache_responses:
            cache_key = self._get_cache_key(market_data)
            self.cache[cache_key] = response
        
        return response
    
    def update_state(self, market_data: Dict[str, Any]):
        """Update price history with new market data."""
        pair = market_data.get('pair', '')
        roostoo_data = market_data.get('roostoo', {})
        
        if pair and roostoo_data:
            price = roostoo_data.get('LastPrice')
            if price:
                if pair not in self.price_history:
                    self.price_history[pair] = []
                self.price_history[pair].append(price)
                
                # Keep only recent history
                if len(self.price_history[pair]) > 20:
                    self.price_history[pair] = self.price_history[pair][-20:]
    
    def generate_signal(self, market_data: Dict[str, Any]) -> TradingSignal:
        """Generate trading signal based on LLM analysis."""
        pair = market_data.get('pair', '')
        roostoo_data = market_data.get('roostoo', {})
        
        if not pair or not roostoo_data:
            return TradingSignal(action="HOLD", confidence=0.0, pair=pair)
        
        current_price = roostoo_data.get('LastPrice')
        if not current_price:
            return TradingSignal(action="HOLD", confidence=0.0, pair=pair)
        
        # If LLM is disabled, return neutral signal
        if not self.enabled:
            return TradingSignal(action="HOLD", confidence=0.3, pair=pair)
        
        # Get LLM analysis
        llm_response = self._analyze_with_llm(market_data)
        
        if not llm_response:
            return TradingSignal(action="HOLD", confidence=0.3, pair=pair)
        
        # Parse LLM response
        action = "HOLD"
        confidence = 0.5
        
        try:
            # Try to parse "ACTION:CONFIDENCE" format
            if ':' in llm_response:
                parts = llm_response.split(':')
                action_str = parts[0].strip().upper()
                if action_str in ['BUY', 'SELL', 'HOLD']:
                    action = action_str
                if len(parts) > 1:
                    try:
                        conf = float(parts[1].strip())
                        confidence = max(0.0, min(1.0, conf))
                    except ValueError:
                        pass
            else:
                # Try to find action in response
                response_upper = llm_response.upper()
                if 'BUY' in response_upper:
                    action = "BUY"
                elif 'SELL' in response_upper:
                    action = "SELL"
                else:
                    action = "HOLD"
        except Exception as e:
            self.logger.warning(f"Error parsing LLM response: {e}")
        
        metadata = {
            'llm_response': llm_response,
            'provider': self.provider,
            'model': self.model
        }
        
        return TradingSignal(
            action=action,
            confidence=confidence,
            pair=pair,
            price=current_price,
            metadata=metadata
        )


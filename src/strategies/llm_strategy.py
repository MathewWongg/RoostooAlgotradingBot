"""LLM-Based Strategy for Market Analysis via OpenRouter/OpenAI/Anthropic"""

import json
import hashlib
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy, TradingSignal
from ..utils.logger import get_logger


class LLMStrategy(BaseStrategy):
    """LLM-based strategy using OpenRouter, OpenAI, or Anthropic for market analysis."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize LLM strategy.
        
        Config parameters:
            provider: "openrouter", "openai", or "anthropic" (default: "openai")
            model: Model name (default: provider-specific)
            api_key: API key (from environment or config)
            enabled: Whether LLM is enabled (default: True)
            cache_responses: Whether to cache responses (default: True)
            max_tokens: Maximum tokens for response (default: 200)
        """
        super().__init__("LLMStrategy", config)
        self.logger = get_logger("llm_strategy")
        
        self.provider = config.get('provider', 'openai').lower()
        provider_default_models = {
            'openai': 'gpt-4',
            'openrouter': 'microsoft/mai-ds-r1:free',
            'anthropic': 'claude-3-opus-20240229',
        }
        self.model = config.get('model', provider_default_models.get(self.provider, 'gpt-4'))
        self.enabled = config.get('enabled', True)
        self.cache_responses = config.get('cache_responses', True)
        self.max_tokens = config.get('max_tokens', 200)
        self.openrouter_config = {
            'base_url': config.get('base_url', 'https://openrouter.ai/api/v1'),
            'default_headers': config.get('default_headers'),
            'extra_body': config.get('extra_body')
        }
        self.openrouter_headers: Dict[str, str] = {}
        self.openrouter_extra_body: Optional[Dict[str, Any]] = None
        
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
                elif self.provider == 'openrouter':
                    import openai
                    api_key = config.get('api_key') or self._get_env_key('OPENROUTER_API_KEY')
                    if api_key:
                        client_kwargs = {
                            'api_key': api_key,
                            'base_url': self.openrouter_config['base_url'],
                        }
                        default_headers = self.openrouter_config.get('default_headers')
                        if isinstance(default_headers, dict) and default_headers:
                            sanitized_headers, missing_headers = self._sanitize_headers(default_headers)
                            if sanitized_headers:
                                self.openrouter_headers = sanitized_headers
                                client_kwargs['default_headers'] = sanitized_headers
                            if missing_headers:
                                self.logger.warning(
                                    "OpenRouter header(s) missing or unset: %s",
                                    ", ".join(missing_headers)
                                )
                        extra_body = self.openrouter_config.get('extra_body')
                        if isinstance(extra_body, dict) and extra_body:
                            self.openrouter_extra_body = extra_body
                        self.llm_client = openai.OpenAI(**client_kwargs)
                    else:
                        self.logger.warning("OpenRouter API key not found, LLM strategy disabled")
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
    
    @staticmethod
    def _sanitize_headers(headers: Dict[str, Any]) -> tuple[Dict[str, str], list]:
        """Validate OpenRouter headers, separating unset placeholders."""
        sanitized = {}
        missing = []
        for key, value in headers.items():
            if isinstance(value, str) and value and "${" not in value:
                sanitized[key] = value
            else:
                missing.append(key)
        return sanitized, missing
    
    def _get_cache_key(self, market_data: Dict[str, Any]) -> str:
        """Generate cache key from market data."""
        pair = market_data.get('pair', '')
        price = market_data.get('roostoo', {}).get('LastPrice', 0)
        change = market_data.get('roostoo', {}).get('Change', 0)
        social = market_data.get('social', {}).get('x', {}) if isinstance(market_data.get('social'), dict) else {}
        sentiment_score = social.get('score', 0)
        sentiment_ts = social.get('fetched_at', '')
        
        data_str = f"{pair}:{price}:{change}:{sentiment_score}:{sentiment_ts}"
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def _call_openai(self, prompt: str) -> Optional[str]:
        """Call OpenAI API."""
        try:
            request_kwargs = {}
            if self.provider == 'openrouter':
                if self.openrouter_headers:
                    request_kwargs['extra_headers'] = self.openrouter_headers
                if isinstance(self.openrouter_extra_body, dict) and self.openrouter_extra_body:
                    request_kwargs['extra_body'] = self.openrouter_extra_body
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a crypto trading analyst. Provide concise trading signals: BUY, SELL, or HOLD. Format: ACTION:CONFIDENCE (0.0-1.0)"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=0.3,
                **request_kwargs
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
        
        social_sentiment = market_data.get('social', {}).get('x') if isinstance(market_data.get('social'), dict) else None
        sentiment_context = self._build_sentiment_context(social_sentiment)
        
        prompt = f"""Analyze this crypto market data and provide a trading signal:

Pair: {pair}
Current Price: ${price:,.2f}
24h Change: {change_pct:.2f}%
Price Trend: {price_trend}
{sentiment_context}

Based on this data, should I BUY, SELL, or HOLD? Provide your answer as: ACTION:CONFIDENCE
Where ACTION is BUY, SELL, or HOLD, and CONFIDENCE is a number between 0.0 and 1.0."""
        
        # Call LLM
        if self.provider == 'openai':
            response = self._call_openai(prompt)
        elif self.provider == 'openrouter':
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
            'model': self.model,
            'strategy': self.name
        }

        if isinstance(market_data.get('social'), dict):
            x_sentiment = market_data['social'].get('x')
            if isinstance(x_sentiment, dict):
                summary = x_sentiment.get('summary', {})
                metadata['sentiment'] = {
                    'x': {
                        'score': x_sentiment.get('score'),
                        'volume': summary.get('volume'),
                        'fetched_at': x_sentiment.get('fetched_at'),
                        'remaining_calls': x_sentiment.get('remaining_calls_today'),
                    }
                }
        
        return TradingSignal(
            action=action,
            confidence=confidence,
            pair=pair,
            price=current_price,
            metadata=metadata
        )

    @staticmethod
    def _trim_text(text: str, limit: int = 140) -> str:
        clean = ' '.join(text.split())
        if len(clean) <= limit:
            return clean
        return clean[: limit - 3] + "..."

    def _build_sentiment_context(self, sentiment: Optional[Dict[str, Any]]) -> str:
        if not isinstance(sentiment, dict):
            return "\nSocial Sentiment: Unavailable."

        summary = sentiment.get('summary', {})
        lines = ["\nSocial Sentiment (X):"]

        score = sentiment.get('score')
        if isinstance(score, (int, float)):
            lines.append(f"- Score: {score:+.2f} (scale -1 bearish to +1 bullish)")

        volume = summary.get('volume')
        if isinstance(volume, int):
            lines.append(f"- Recent Volume: {volume} posts")

        fetched_at = sentiment.get('fetched_at')
        if isinstance(fetched_at, str) and fetched_at:
            lines.append(f"- Last Update: {fetched_at}")

        tags = summary.get('tags') if isinstance(summary, dict) else None
        if isinstance(tags, list) and tags:
            lines.append(f"- Top Tags: {', '.join(tags[:5])}")

        samples = summary.get('sample_posts') if isinstance(summary, dict) else None
        if isinstance(samples, list) and samples:
            lines.append("- Sample Posts:")
            for sample in samples[:2]:
                if isinstance(sample, str) and sample.strip():
                    lines.append(f"  • {self._trim_text(sample)}")

        return "\n".join(lines)


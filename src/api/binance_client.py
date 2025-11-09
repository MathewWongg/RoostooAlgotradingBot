"""Binance Data API Client (Optional for market context)"""

import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..utils.logger import get_logger


class BinanceClient:
    """Client for Binance public API to get market context data."""

    def __init__(self, base_url: str = "https://api.binance.com"):
        """
        Initialize Binance API client (public endpoints only).

        Args:
            base_url: Base URL for Binance API
        """
        self.base_url = base_url.rstrip("/")
        self.logger = get_logger("binance_client")
        self.session = requests.Session()
        self._kline_cache: Dict[Tuple[str, str, int], Dict[str, Any]] = {}

    def get_ticker_price(self, symbol: str) -> Optional[float]:
        """
        Get current ticker price from Binance.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")

        Returns:
            Current price or None
        """
        try:
            url = f"{self.base_url}/api/v3/ticker/price"
            params = {"symbol": symbol}
            response = self.session.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            return float(data.get("price", 0))
        except Exception as exc:
            self.logger.warning(f"Failed to get Binance price for {symbol}: {exc}")
            return None

    def get_24hr_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get 24hr ticker statistics from Binance.

        Args:
            symbol: Trading symbol

        Returns:
            Ticker statistics or None
        """
        try:
            url = f"{self.base_url}/api/v3/ticker/24hr"
            params = {"symbol": symbol}
            response = self.session.get(url, params=params, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            self.logger.warning(f"Failed to get Binance 24hr ticker for {symbol}: {exc}")
            return None

    def get_klines(
        self,
        symbol: str,
        *,
        interval: str = "1h",
        limit: int = 200,
        cache_seconds: int = 300,
    ) -> Optional[List[List[Any]]]:
        """
        Fetch historical klines (candlesticks) for a symbol.

        Args:
            symbol: Binance trading symbol
            interval: Binance interval string (e.g., "1m", "1h")
            limit: Number of klines to fetch (max 1000 per API)
            cache_seconds: Cache TTL to avoid rate-limit issues

        Returns:
            List of klines (raw Binance response) or None if unavailable
        """
        cache_key = (symbol, interval, limit)
        now = time.time()
        cached = self._kline_cache.get(cache_key)

        if cached and now - cached.get("timestamp", 0) < cache_seconds:
            return cached.get("data")

        try:
            url = f"{self.base_url}/api/v3/klines"
            params = {"symbol": symbol, "interval": interval, "limit": limit}
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            self._kline_cache[cache_key] = {"timestamp": now, "data": data}
            return data
        except Exception as exc:
            self.logger.warning(f"Failed to get Binance klines for {symbol}: {exc}")
            # Fallback to cached data even if TTL expired
            if cached:
                return cached.get("data")
            return None


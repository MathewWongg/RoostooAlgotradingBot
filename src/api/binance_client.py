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
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> Optional[List[List[Any]]]:
        """
        Fetch historical klines (candlesticks) for a symbol.

        Args:
            symbol: Binance trading symbol
            interval: Binance interval string (e.g., "1m", "1h")
            limit: Number of klines to fetch (max 1000 per API)
            cache_seconds: Cache TTL to avoid rate-limit issues
            start_time: Start timestamp in milliseconds (optional)
            end_time: End timestamp in milliseconds (optional)

        Returns:
            List of klines (raw Binance response) or None if unavailable
        """
        # Don't cache when fetching specific date ranges
        if start_time or end_time:
            try:
                url = f"{self.base_url}/api/v3/klines"
                params = {"symbol": symbol, "interval": interval}
                if start_time:
                    params["startTime"] = start_time
                if end_time:
                    params["endTime"] = end_time
                if limit:
                    params["limit"] = min(limit, 1000)  # Binance max is 1000
                
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                self.logger.warning(f"Failed to get Binance klines for {symbol}: {exc}")
                return None
        
        # Use cache for recent data requests
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
    
    def get_historical_klines(
        self,
        symbol: str,
        start_time: int,
        end_time: int,
        interval: str = "1h"
    ) -> Optional[List[List[Any]]]:
        """
        Fetch all historical klines for a date range (handles pagination for >1000 klines).

        Args:
            symbol: Binance trading symbol
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds
            interval: Binance interval string (e.g., "1h", "1d")

        Returns:
            List of all klines in the date range or None if unavailable
        """
        all_klines = []
        current_start = start_time
        
        try:
            while current_start < end_time:
                klines = self.get_klines(
                    symbol,
                    interval=interval,
                    limit=1000,
                    start_time=current_start,
                    end_time=end_time,
                    cache_seconds=0  # Don't cache historical fetches
                )
                
                if not klines:
                    break
                
                all_klines.extend(klines)
                
                # If we got less than 1000, we've reached the end
                if len(klines) < 1000:
                    break
                
                # Move start time to the last kline's close time + 1
                last_close_time = klines[-1][6]  # Close time is index 6
                current_start = last_close_time + 1
                
                # Small delay to avoid rate limits
                time.sleep(0.1)
            
            return all_klines if all_klines else None
        except Exception as exc:
            self.logger.error(f"Error fetching historical klines for {symbol}: {exc}")
            return all_klines if all_klines else None


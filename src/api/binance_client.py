"""Binance Data API Client (Optional for market context)"""

import requests
from typing import Dict, Any, Optional
from ..utils.logger import get_logger


class BinanceClient:
    """Client for Binance public API to get market context data."""
    
    def __init__(self, base_url: str = "https://api.binance.com"):
        """
        Initialize Binance API client (public endpoints only).
        
        Args:
            base_url: Base URL for Binance API
        """
        self.base_url = base_url.rstrip('/')
        self.logger = get_logger("binance_client")
        self.session = requests.Session()
    
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
            params = {'symbol': symbol}
            response = self.session.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            return float(data.get('price', 0))
        except Exception as e:
            self.logger.warning(f"Failed to get Binance price for {symbol}: {e}")
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
            params = {'symbol': symbol}
            response = self.session.get(url, params=params, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.warning(f"Failed to get Binance 24hr ticker for {symbol}: {e}")
            return None


"""Data Collection Module for Multi-Source Data Aggregation"""

import time
from typing import Dict, Any, List, Optional

import numpy as np

from ..api.roostoo_client import RoostooClient
from ..api.horus_client import HorusClient
from ..api.binance_client import BinanceClient
from ..api.x_client import XClient
from .data_storage import DataStorage
from ..utils.logger import get_logger


class DataCollector:
    """Collect and aggregate market data from multiple sources."""
    
    def __init__(
        self,
        roostoo_client: RoostooClient,
        data_storage: DataStorage,
        horus_client: Optional[HorusClient] = None,
        binance_client: Optional[BinanceClient] = None,
        social_client: Optional[XClient] = None,
        social_mapping: Optional[Dict[str, str]] = None,
        binance_settings: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize data collector.
        
        Args:
            roostoo_client: Roostoo API client
            data_storage: Data storage instance
            horus_client: Horus API client (optional)
            binance_client: Binance API client (optional)
        """
        self.roostoo_client = roostoo_client
        self.horus_client = horus_client
        self.binance_client = binance_client
        self.data_storage = data_storage
        self.social_client = social_client
        self.social_mapping = social_mapping or {}
        self.binance_settings = binance_settings or {}
        self.binance_settings.setdefault('interval', '1h')
        self.binance_settings.setdefault('limit', 200)
        self.binance_settings.setdefault('cache_seconds', 300)
        self.binance_settings.setdefault('rsi_period', 14)
        self.binance_settings.setdefault('sma_period', 20)
        self.logger = get_logger("data_collector")
        self.exchange_info = None
        self.available_pairs = []
        self._load_exchange_info()
    
    def _load_exchange_info(self):
        """Load exchange information and available trading pairs."""
        try:
            info = self.roostoo_client.get_exchange_info()
            if info and 'TradePairs' in info:
                self.exchange_info = info
                self.available_pairs = list(info['TradePairs'].keys())
                self.logger.info(f"Loaded {len(self.available_pairs)} trading pairs")
            else:
                self.logger.warning("Failed to load exchange info")
        except Exception as e:
            self.logger.error(f"Error loading exchange info: {e}")
    
    def collect_ticker_data(self, pair: Optional[str] = None) -> Dict[str, Any]:
        """
        Collect ticker data for a specific pair or all pairs.
        
        Args:
            pair: Trading pair or None for all pairs
            
        Returns:
            Dictionary of ticker data
        """
        try:
            response = self.roostoo_client.get_ticker(pair)
            if not response or not response.get('Success', True):
                self.logger.warning(f"Failed to get ticker data for {pair}")
                return {}
            
            data = response.get('Data', {})
            server_time = response.get('ServerTime')
            
            # Store data in local database
            if pair:
                if pair in data:
                    self.data_storage.store_ticker_data(pair, data[pair], server_time)
            else:
                for p, ticker_data in data.items():
                    self.data_storage.store_ticker_data(p, ticker_data, server_time)
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error collecting ticker data: {e}")
            return {}
    
    def get_market_data(self, pair: str) -> Dict[str, Any]:
        """
        Get comprehensive market data for a pair from all sources.
        
        Args:
            pair: Trading pair
            
        Returns:
            Aggregated market data dictionary
        """
        market_data = {
            'pair': pair,
            'roostoo': {},
            'binance': {},
            'horus': {},
            'social': {},
        }
        
        # Get Roostoo data
        ticker_data = self.collect_ticker_data(pair)
        if pair in ticker_data:
            market_data['roostoo'] = ticker_data[pair]
        
        # Get Binance data for context (convert pair format)
        if self.binance_client:
            binance_payload = self._get_binance_market_data(pair)
            if binance_payload:
                market_data['binance'] = binance_payload
        
        # Get Horus data (when implemented)
        if self.horus_client:
            horus_data = self.horus_client.get_market_data(pair)
            if horus_data:
                market_data['horus'] = horus_data

        # Get X social sentiment
        if self.social_client:
            coin_key = self._resolve_social_key(pair)
            if coin_key:
                try:
                    sentiment = self.social_client.get_sentiment(coin_key)
                    if sentiment:
                        market_data['social']['x'] = sentiment
                        summary = sentiment.get('summary', {}) if isinstance(sentiment, dict) else {}
                        score = sentiment.get('score')
                        volume = summary.get('volume')
                        self.logger.debug(
                            "X sentiment for %s (%s): score=%s volume=%s remaining_calls=%s",
                            pair,
                            coin_key,
                            score,
                            volume,
                            sentiment.get('remaining_calls_today'),
                        )
                except Exception as exc:
                    self.logger.error(f"Error fetching X sentiment for {pair}: {exc}")

        if not market_data['social']:
            market_data['social'] = {}
        
        return market_data
    
    def _convert_pair_to_binance(self, pair: str) -> Optional[str]:
        """Convert Roostoo pair format to Binance symbol format."""
        # Roostoo: "BTC/USD" -> Binance: "BTCUSDT" (approximation)
        if '/' in pair:
            base, quote = pair.split('/')
            if quote == 'USD':
                return f"{base}USDT"
        return None

    def _resolve_social_key(self, pair: str) -> Optional[str]:
        if pair in self.social_mapping:
            return self.social_mapping[pair]
        if '/' in pair:
            base, _ = pair.split('/')
            return self.social_mapping.get(base, base)
        return None

    def _get_binance_market_data(self, pair: str) -> Optional[Dict[str, Any]]:
        symbol = self._convert_pair_to_binance(pair)
        if not symbol:
            return None

        data: Dict[str, Any] = {}
        try:
            price = self.binance_client.get_ticker_price(symbol)
            if price:
                data['price'] = price

            interval = self.binance_settings.get('interval', '1h')
            limit = int(self.binance_settings.get('limit', 200))
            cache_seconds = int(self.binance_settings.get('cache_seconds', 300))

            klines = self.binance_client.get_klines(
                symbol,
                interval=interval,
                limit=limit,
                cache_seconds=cache_seconds,
            )
            if klines:
                closes = [float(item[4]) for item in klines]
                timestamps = [int(item[0]) for item in klines]
                data['klines'] = {
                    'interval': interval,
                    'limit': len(closes),
                    'closes': closes,
                    'timestamps': timestamps,
                }
                data['indicators'] = self._compute_binance_indicators(closes)
        except Exception as exc:
            self.logger.error(f"Error fetching Binance data for {pair}: {exc}")

        return data or None

    def _compute_binance_indicators(self, closes: List[float]) -> Dict[str, float]:
        indicators: Dict[str, float] = {}
        if not closes:
            return indicators

        sma_period = int(self.binance_settings.get('sma_period', 20))
        if len(closes) >= sma_period:
            indicators['sma'] = float(np.mean(closes[-sma_period:]))

        rsi_period = int(self.binance_settings.get('rsi_period', 14))
        if len(closes) >= rsi_period + 1:
            window = closes[-(rsi_period + 1):]
            deltas = np.diff(window)
            gains = np.clip(deltas, a_min=0, a_max=None)
            losses = np.clip(-deltas, a_min=0, a_max=None)
            avg_gain = float(np.mean(gains))
            avg_loss = float(np.mean(losses))

            if avg_loss == 0:
                indicators['rsi'] = 100.0
            elif avg_gain == 0:
                indicators['rsi'] = 0.0
            else:
                rs = avg_gain / avg_loss
                indicators['rsi'] = 100 - (100 / (1 + rs))

        return indicators
    
    def get_historical_data(self, pair: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get historical ticker data from local storage.
        
        Args:
            pair: Trading pair
            limit: Number of records to retrieve
            
        Returns:
            List of historical ticker data
        """
        return self.data_storage.get_ticker_history(pair, limit=limit)
    
    def start_collection_loop(self, pairs: List[str], interval: int = 60):
        """
        Start continuous data collection loop (for background thread).
        
        Args:
            pairs: List of pairs to collect
            interval: Collection interval in seconds
        """
        self.logger.info(f"Starting data collection loop for {len(pairs)} pairs (interval: {interval}s)")
        
        while True:
            try:
                for pair in pairs:
                    self.collect_ticker_data(pair)
                    time.sleep(1)  # Small delay between pairs
                
                # Cleanup old data periodically
                self.data_storage.cleanup_old_data()
                
                time.sleep(interval)
                
            except KeyboardInterrupt:
                self.logger.info("Data collection loop stopped")
                break
            except Exception as e:
                self.logger.error(f"Error in data collection loop: {e}")
                time.sleep(interval)


"""Roostoo API Client with HMAC SHA256 Authentication"""

import time
import hmac
import hashlib
import requests
from typing import Dict, Any, Optional, List
from ..utils.logger import get_logger, log_api_request


class RoostooClient:
    """Client for Roostoo API with authentication and error handling."""
    
    def __init__(self, api_key: str, secret_key: str, base_url: str = "https://mock-api.roostoo.com"):
        """
        Initialize Roostoo API client.
        
        Args:
            api_key: Roostoo API key
            secret_key: Roostoo secret key
            base_url: Base URL for API (default: mock API)
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url.rstrip('/')
        self.logger = get_logger("roostoo_client")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RoostooTradingBot/1.0'
        })
    
    def _get_timestamp(self) -> str:
        """Get 13-digit millisecond timestamp as string."""
        return str(int(time.time() * 1000))
    
    def _get_signed_headers(self, payload: Dict[str, Any] = None) -> tuple:
        """
        Generate signed headers and totalParams for RCL_TopLevelCheck endpoints.
        
        Args:
            payload: Request payload dictionary
            
        Returns:
            Tuple of (headers, payload, total_params)
        """
        if payload is None:
            payload = {}
        
        payload['timestamp'] = self._get_timestamp()
        
        # Sort parameters by key and create query string
        sorted_keys = sorted(payload.keys())
        total_params = "&".join(f"{k}={payload[k]}" for k in sorted_keys)
        
        # Generate HMAC SHA256 signature
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            total_params.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            'RST-API-KEY': self.api_key,
            'MSG-SIGNATURE': signature
        }
        
        return headers, payload, total_params
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
        retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Make HTTP request to API endpoint.
        
        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint path
            params: Request parameters
            signed: Whether to use signed authentication
            retries: Number of retry attempts
            
        Returns:
            Response JSON or None if failed
        """
        url = f"{self.base_url}{endpoint}"
        params = params or {}
        
        if signed:
            headers, payload, total_params = self._get_signed_headers(params)
        else:
            headers = {}
            payload = params
            total_params = None
        
        for attempt in range(retries):
            try:
                if method.upper() == 'GET':
                    response = self.session.get(url, headers=headers, params=payload, timeout=10)
                elif method.upper() == 'POST':
                    if signed:
                        headers['Content-Type'] = 'application/x-www-form-urlencoded'
                        response = self.session.post(url, headers=headers, data=total_params, timeout=10)
                    else:
                        response = self.session.post(url, headers=headers, json=payload, timeout=10)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                result = response.json()
                
                # Log successful request
                log_api_request(
                    self.logger,
                    method,
                    endpoint,
                    params,
                    success=True,
                    response=result
                )
                
                return result
                
            except requests.exceptions.RequestException as e:
                error_msg = str(e)
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_msg = e.response.text
                    except:
                        pass
                
                if attempt < retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    self.logger.warning(f"Request failed (attempt {attempt + 1}/{retries}), retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    # Log failed request
                    log_api_request(
                        self.logger,
                        method,
                        endpoint,
                        params,
                        success=False,
                        error=error_msg
                    )
                    self.logger.error(f"API request failed after {retries} attempts: {error_msg}")
                    return None
        
        return None
    
    # Public Endpoints
    
    def check_server_time(self) -> Optional[Dict[str, Any]]:
        """Check API server time."""
        return self._make_request('GET', '/v3/serverTime', signed=False)
    
    def get_exchange_info(self) -> Optional[Dict[str, Any]]:
        """Get exchange trading pairs and information."""
        return self._make_request('GET', '/v3/exchangeInfo', signed=False)
    
    def get_ticker(self, pair: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get ticker for one or all pairs.
        
        Args:
            pair: Trading pair (e.g., "BTC/USD") or None for all pairs
        """
        params = {'timestamp': self._get_timestamp()}
        if pair:
            params['pair'] = pair
        return self._make_request('GET', '/v3/ticker', params=params, signed=False)
    
    # Signed Endpoints
    
    def get_balance(self) -> Optional[Dict[str, Any]]:
        """Get wallet balances."""
        return self._make_request('GET', '/v3/balance', signed=True)
    
    def get_pending_count(self) -> Optional[Dict[str, Any]]:
        """Get total pending order count."""
        return self._make_request('GET', '/v3/pending_count', signed=True)
    
    def place_order(
        self,
        pair: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        price: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Place a LIMIT or MARKET order.
        
        Args:
            pair: Trading pair (e.g., "BTC/USD")
            side: Order side ("BUY" or "SELL")
            quantity: Order quantity
            order_type: Order type ("MARKET" or "LIMIT")
            price: Order price (required for LIMIT orders)
            
        Returns:
            Order response or None if failed
        """
        if order_type == "LIMIT" and price is None:
            self.logger.error("LIMIT orders require 'price' parameter")
            return None
        
        payload = {
            'pair': pair,
            'side': side.upper(),
            'type': order_type.upper(),
            'quantity': str(quantity)
        }
        
        if order_type == "LIMIT":
            payload['price'] = str(price)
        
        return self._make_request('POST', '/v3/place_order', params=payload, signed=True)
    
    def query_order(
        self,
        order_id: Optional[int] = None,
        pair: Optional[str] = None,
        pending_only: Optional[bool] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Query order history or pending orders.
        
        Args:
            order_id: Specific order ID
            pair: Trading pair filter
            pending_only: Only return pending orders
            offset: Pagination offset
            limit: Pagination limit
        """
        payload = {}
        
        if order_id:
            payload['order_id'] = str(order_id)
        else:
            if pair:
                payload['pair'] = pair
            if pending_only is not None:
                payload['pending_only'] = 'TRUE' if pending_only else 'FALSE'
            if offset is not None:
                payload['offset'] = str(offset)
            if limit is not None:
                payload['limit'] = str(limit)
        
        return self._make_request('POST', '/v3/query_order', params=payload, signed=True)
    
    def cancel_order(
        self,
        order_id: Optional[int] = None,
        pair: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Cancel specific or all pending orders.
        
        Args:
            order_id: Specific order ID to cancel
            pair: Cancel all pending orders for a pair
        """
        payload = {}
        
        if order_id:
            payload['order_id'] = str(order_id)
        elif pair:
            payload['pair'] = pair
        
        return self._make_request('POST', '/v3/cancel_order', params=payload, signed=True)


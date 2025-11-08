"""Order Management Module"""

import time
from typing import Dict, Any, Optional, List
from ..api.roostoo_client import RoostooClient
from ..strategies.base_strategy import TradingSignal
from ..utils.logger import get_logger, log_trade
from ..utils.performance import TradeRecord, PerformanceTracker


class OrderManager:
    """Manage order placement, tracking, and execution."""
    
    def __init__(
        self,
        roostoo_client: RoostooClient,
        config: Dict[str, Any],
        performance_tracker: Optional[PerformanceTracker] = None
    ):
        """
        Initialize order manager.
        
        Args:
            roostoo_client: Roostoo API client
            config: Trading configuration
            performance_tracker: Performance tracker instance
        """
        self.roostoo_client = roostoo_client
        self.config = config
        self.performance_tracker = performance_tracker
        self.logger = get_logger("order_manager")
        
        self.order_type = config.get('order_type', 'MARKET')
        self.exchange_info = None
        self.pair_info: Dict[str, Dict[str, Any]] = {}
        self._load_exchange_info()
    
    def _load_exchange_info(self):
        """Load exchange information and trading pair details."""
        try:
            info = self.roostoo_client.get_exchange_info()
            if info and 'TradePairs' in info:
                self.exchange_info = info
                self.pair_info = info['TradePairs']
                self.logger.info(f"Loaded exchange info for {len(self.pair_info)} pairs")
        except Exception as e:
            self.logger.error(f"Error loading exchange info: {e}")
    
    def _round_quantity(self, pair: str, quantity: float) -> float:
        """Round quantity to exchange precision."""
        if pair not in self.pair_info:
            return round(quantity, 6)
        
        precision = self.pair_info[pair].get('AmountPrecision', 6)
        return round(quantity, precision)
    
    def _round_price(self, pair: str, price: float) -> float:
        """Round price to exchange precision."""
        if pair not in self.pair_info:
            return round(price, 2)
        
        precision = self.pair_info[pair].get('PricePrecision', 2)
        return round(price, precision)
    
    def _validate_order(self, pair: str, quantity: float, price: Optional[float] = None):
        """Validate order parameters."""
        if pair not in self.pair_info:
            return False, f"Pair {pair} not found in exchange info"
        
        pair_info = self.pair_info[pair]
        
        if not pair_info.get('CanTrade', False):
            return False, f"Pair {pair} is not tradeable"
        
        # Check minimum order size
        min_order = pair_info.get('MiniOrder', 1.0)
        order_value = quantity * (price or 0)
        
        if price and order_value < min_order:
            return False, f"Order value {order_value} below minimum {min_order}"
        
        return True, "OK"
    
    def execute_signal(
        self,
        signal: TradingSignal,
        quantity: float,
        price: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Execute a trading signal.
        
        Args:
            signal: Trading signal
            quantity: Order quantity
            price: Order price (for LIMIT orders)
            
        Returns:
            Order response or None if failed
        """
        if signal.action == "HOLD":
            return None
        
        pair = signal.pair
        side = signal.action
        
        # Round quantities and prices
        quantity = self._round_quantity(pair, quantity)
        if price:
            price = self._round_price(pair, price)
        
        # Validate order
        is_valid, error_msg = self._validate_order(pair, quantity, price)
        if not is_valid:
            self.logger.error(f"Order validation failed: {error_msg}")
            return None
        
        # Place order
        order_response = self.roostoo_client.place_order(
            pair=pair,
            side=side,
            quantity=quantity,
            order_type=self.order_type,
            price=price
        )
        
        if not order_response or not order_response.get('Success', False):
            error_msg = order_response.get('ErrMsg', 'Unknown error') if order_response else 'No response'
            self.logger.error(f"Order placement failed: {error_msg}")
            log_trade(
                self.logger,
                "PLACE_FAILED",
                pair,
                side,
                quantity,
                price,
                error=error_msg
            )
            return None
        
        order_detail = order_response.get('OrderDetail', {})
        order_id = order_detail.get('OrderID')
        status = order_detail.get('Status', 'UNKNOWN')
        
        # Log trade
        log_trade(
            self.logger,
            "PLACED",
            pair,
            side,
            quantity,
            price,
            order_id=order_id,
            status=status
        )
        
        # Record trade in performance tracker
        if self.performance_tracker and order_detail:
            trade_record = TradeRecord(
                timestamp=time.strftime('%Y-%m-%dT%H:%M:%S'),
                pair=pair,
                side=side,
                quantity=quantity,
                price=order_detail.get('Price', price or 0),
                order_id=order_id,
                status=status,
                filled_quantity=order_detail.get('FilledQuantity', 0),
                filled_avg_price=order_detail.get('FilledAverPrice', 0),
                commission=order_detail.get('CommissionChargeValue', 0)
            )
            self.performance_tracker.record_trade(trade_record)
        
        return order_response
    
    def query_order(self, order_id: Optional[int] = None, pair: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Query order status."""
        return self.roostoo_client.query_order(order_id=order_id, pair=pair)
    
    def cancel_order(self, order_id: Optional[int] = None, pair: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Cancel an order."""
        response = self.roostoo_client.cancel_order(order_id=order_id, pair=pair)
        
        if response and response.get('Success', False):
            canceled_list = response.get('CanceledList', [])
            self.logger.info(f"Canceled {len(canceled_list)} order(s)")
            # Log cancellation
            for order_id in canceled_list:
                log_trade(
                    self.logger,
                    "CANCELED",
                    pair or "ALL",
                    "N/A",
                    0,
                    order_id=order_id,
                    status="CANCELED"
                )
        
        return response
    
    def get_pending_orders(self) -> List[Dict[str, Any]]:
        """Get all pending orders."""
        response = self.roostoo_client.query_order(pending_only=True)
        
        if response and response.get('Success', False):
            return response.get('OrderMatched', [])
        
        return []
    
    def check_order_fills(self, order_id: int) -> Optional[Dict[str, Any]]:
        """Check if an order has been filled."""
        response = self.query_order(order_id=order_id)
        
        if response and response.get('Success', False):
            orders = response.get('OrderMatched', [])
            if orders:
                order = orders[0]
                if order.get('Status') == 'FILLED':
                    # Update performance tracker with PnL if available
                    if self.performance_tracker:
                        # Calculate PnL (simplified - would need position tracking)
                        filled_price = order.get('FilledAverPrice', 0)
                        filled_qty = order.get('FilledQuantity', 0)
                        side = order.get('Side')
                        # PnL calculation would require entry price tracking
                        # For now, just update the record
                        pass
                    
                    return order
        
        return None


"""Risk Management Module"""

from typing import Dict, Any, Optional
from ..api.roostoo_client import RoostooClient
from ..utils.logger import get_logger


class RiskManager:
    """Manage trading risk with position sizing and limits."""
    
    def __init__(self, config: Dict[str, Any], roostoo_client: Optional[RoostooClient] = None):
        """
        Initialize risk manager.
        
        Args:
            config: Risk management configuration
            roostoo_client: Roostoo API client (optional, for backtesting)
        """
        self.config = config
        self.roostoo_client = roostoo_client
        self.logger = get_logger("risk_manager")
        
        # Core sizing and limits
        self.spot_only = config.get('spot_only', True)
        self.position_size_pct = config.get('position_size_pct', 0.1)  # fallback
        self.max_position_pct = config.get('max_position_pct', None)  # preferred for equity-based sizing
        self.max_portfolio_exposure_pct = config.get('max_portfolio_exposure_pct', None)
        self.max_concurrent_positions = config.get('max_concurrent_positions', config.get('max_positions', 3))
        self.min_order_size = config.get('min_order_size', 1.0)
        self.max_order_size = config.get('max_order_size', None)
        self.min_take_profit_pct = config.get('min_take_profit_pct', None)
        self.stop_loss_pct = config.get('stop_loss_pct', None)
        
        # Load pair weights and normalize them
        pair_weights = config.get('pair_weights', {})
        if pair_weights:
            total_weight = sum(pair_weights.values())
            if total_weight > 0:
                self.pair_weights = {pair: weight / total_weight for pair, weight in pair_weights.items()}
            else:
                self.pair_weights = {}
        else:
            self.pair_weights = {}
        
        # Track positions
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.last_trade_time: Dict[str, float] = {}
        self.cooldown_period = config.get('cooldown_period', 300)  # 5 minutes
    
    def get_position_size(
        self,
        pair: str,
        price: float,
        balance: float,
        signal_confidence: float,
        capital_multiplier: float = 1.0
    ) -> float:
        """
        Calculate position size based on risk parameters and pair weights.
        
        Args:
            pair: Trading pair
            price: Current price
            balance: Equity (preferred) or available balance proxy
            signal_confidence: Signal confidence (0.0-1.0)
            
        Returns:
            Position size in base currency
        """
        # Base position size from equity percentage (preferred), fallback to legacy position_size_pct
        if self.max_position_pct is not None:
            base_size = balance * float(self.max_position_pct)
        else:
            base_size = balance * float(self.position_size_pct)
        
        # Apply pair weight if configured (normalized weight multiplies the base size)
        if self.pair_weights and pair in self.pair_weights:
            pair_weight = self.pair_weights[pair]
            # Weighted size: if weight is 0.2 (20%), use 0.2 of base_size
            # If weight is 0.8 (80%), use 0.8 of base_size
            weighted_size = base_size * pair_weight
        else:
            # If no weight configured, use equal allocation
            weighted_size = base_size
        
        # Adjust based on confidence
        adjusted_size = weighted_size * signal_confidence * max(capital_multiplier, 0.0)
        
        # Convert to quantity
        quantity = adjusted_size / price if price > 0 else 0
        
        # Apply limits
        if quantity < self.min_order_size:
            quantity = 0
        elif self.max_order_size and quantity > self.max_order_size:
            quantity = self.max_order_size
        
        return quantity
    
    def can_trade(self, pair: str):
        """
        Check if trading is allowed for a pair.
        
        Args:
            pair: Trading pair
            
        Returns:
            Tuple of (can_trade, reason)
        """
        # Check cooldown period
        if pair in self.last_trade_time:
            time_since_last = self._get_current_time() - self.last_trade_time[pair]
            if time_since_last < self.cooldown_period:
                return False, f"Cooldown period active ({int(self.cooldown_period - time_since_last)}s remaining)"
        
        # Check max positions
        active_positions = len([p for p in self.positions.values() if p.get('status') == 'active'])
        if active_positions >= self.max_positions:
            return False, f"Maximum positions limit reached ({self.max_positions})"
        
        return True, "OK"
    
    def record_trade(self, pair: str, side: str, quantity: float, price: float, order_id: int):
        """Record a new trade."""
        self.positions[pair] = {
            'side': side,
            'quantity': quantity,
            'price': price,
            'order_id': order_id,
            'status': 'active',
            'timestamp': self._get_current_time()
        }
        self.last_trade_time[pair] = self._get_current_time()
    
    def update_position(self, pair: str, status: str, **kwargs):
        """Update position status."""
        if pair in self.positions:
            self.positions[pair]['status'] = status
            self.positions[pair].update(kwargs)
    
    def get_active_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get all active positions."""
        return {k: v for k, v in self.positions.items() if v.get('status') == 'active'}
    
    def _get_current_time(self) -> float:
        """Get current timestamp."""
        import time
        return time.time()
    
    def check_balance_sufficient(self, required_amount: float, balance: float) -> bool:
        """Check if balance is sufficient for trade."""
        return balance >= required_amount * 1.1  # 10% buffer


"""Base Strategy Abstract Class"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class TradingSignal:
    """Trading signal with action and confidence."""
    action: str  # "BUY", "SELL", or "HOLD"
    confidence: float  # 0.0 to 1.0
    pair: str
    price: Optional[float] = None
    quantity: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies."""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize strategy.
        
        Args:
            name: Strategy name
            config: Strategy configuration dictionary
        """
        self.name = name
        self.config = config or {}
        self.state = {}
    
    @abstractmethod
    def generate_signal(self, market_data: Dict[str, Any]) -> TradingSignal:
        """
        Generate trading signal based on market data.
        
        Args:
            market_data: Market data dictionary
            
        Returns:
            TradingSignal object
        """
        pass
    
    def update_state(self, market_data: Dict[str, Any]):
        """Update internal strategy state with new market data."""
        pass
    
    def reset(self):
        """Reset strategy state."""
        self.state = {}
    
    def get_state(self) -> Dict[str, Any]:
        """Get current strategy state."""
        return self.state.copy()


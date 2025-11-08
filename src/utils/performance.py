"""Performance Tracking Module"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class TradeRecord:
    """Record of a single trade."""
    timestamp: str
    pair: str
    side: str
    quantity: float
    price: float
    order_id: int
    status: str
    filled_quantity: float
    filled_avg_price: float
    commission: float
    pnl: Optional[float] = None


@dataclass
class PerformanceMetrics:
    """Performance metrics summary."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_volume: float
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    avg_win: Optional[float] = None
    avg_loss: Optional[float] = None


class PerformanceTracker:
    """Track trading performance and calculate metrics."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.trades_file = self.data_dir / "trades.json"
        self.performance_file = self.data_dir / "performance.json"
        self.trades: List[TradeRecord] = []
        self._load_trades()
    
    def _load_trades(self):
        """Load historical trades from file."""
        if self.trades_file.exists():
            try:
                with open(self.trades_file, 'r') as f:
                    data = json.load(f)
                    self.trades = [TradeRecord(**trade) for trade in data]
            except Exception as e:
                print(f"Error loading trades: {e}")
                self.trades = []
    
    def _save_trades(self):
        """Save trades to file."""
        try:
            with open(self.trades_file, 'w') as f:
                json.dump([asdict(trade) for trade in self.trades], f, indent=2)
        except Exception as e:
            print(f"Error saving trades: {e}")
    
    def record_trade(self, trade: TradeRecord):
        """Record a new trade."""
        self.trades.append(trade)
        self._save_trades()
    
    def update_trade_pnl(self, order_id: int, pnl: float):
        """Update PnL for a completed trade."""
        for trade in self.trades:
            if trade.order_id == order_id:
                trade.pnl = pnl
                self._save_trades()
                break
    
    def calculate_metrics(self) -> PerformanceMetrics:
        """Calculate performance metrics from recorded trades."""
        if not self.trades:
            return PerformanceMetrics(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_pnl=0.0,
                total_volume=0.0
            )
        
        completed_trades = [t for t in self.trades if t.pnl is not None]
        if not completed_trades:
            return PerformanceMetrics(
                total_trades=len(self.trades),
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_pnl=0.0,
                total_volume=sum(t.quantity * t.price for t in self.trades)
            )
        
        winning_trades = [t for t in completed_trades if t.pnl > 0]
        losing_trades = [t for t in completed_trades if t.pnl < 0]
        
        total_pnl = sum(t.pnl for t in completed_trades)
        total_volume = sum(t.quantity * t.price for t in self.trades)
        win_rate = len(winning_trades) / len(completed_trades) if completed_trades else 0.0
        
        avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else None
        avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else None
        
        # Calculate Sharpe ratio (simplified)
        returns = [t.pnl for t in completed_trades]
        sharpe_ratio = None
        if len(returns) > 1:
            import statistics
            mean_return = statistics.mean(returns)
            std_return = statistics.stdev(returns) if len(returns) > 1 else 0
            sharpe_ratio = mean_return / std_return if std_return > 0 else None
        
        # Calculate max drawdown
        cumulative_pnl = []
        running_total = 0
        for trade in completed_trades:
            running_total += trade.pnl
            cumulative_pnl.append(running_total)
        
        max_drawdown = None
        if cumulative_pnl:
            peak = cumulative_pnl[0]
            max_dd = 0
            for pnl in cumulative_pnl:
                if pnl > peak:
                    peak = pnl
                dd = peak - pnl
                if dd > max_dd:
                    max_dd = dd
            max_drawdown = max_dd if peak > 0 else None
        
        return PerformanceMetrics(
            total_trades=len(self.trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            total_pnl=total_pnl,
            total_volume=total_volume,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            avg_win=avg_win,
            avg_loss=avg_loss
        )
    
    def get_daily_summary(self) -> Dict:
        """Get daily performance summary."""
        today = datetime.now().date().isoformat()
        today_trades = [t for t in self.trades if t.timestamp.startswith(today)]
        
        return {
            'date': today,
            'trades_count': len(today_trades),
            'total_volume': sum(t.quantity * t.price for t in today_trades),
            'completed_trades': len([t for t in today_trades if t.pnl is not None]),
            'total_pnl': sum(t.pnl for t in today_trades if t.pnl is not None)
        }
    
    def save_performance_report(self):
        """Save performance report to file."""
        metrics = self.calculate_metrics()
        daily_summary = self.get_daily_summary()
        
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'metrics': asdict(metrics),
            'daily_summary': daily_summary
        }
        
        try:
            with open(self.performance_file, 'w') as f:
                json.dump(report, f, indent=2)
        except Exception as e:
            print(f"Error saving performance report: {e}")


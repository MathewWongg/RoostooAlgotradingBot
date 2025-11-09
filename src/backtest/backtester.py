"""Backtesting Engine for Trading Bot"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import json

from ..data.data_storage import DataStorage
from ..strategies.ensemble_strategy import EnsembleStrategy
from ..execution.risk_manager import RiskManager
from ..utils.config import load_config
from ..utils.logger import setup_logger, get_logger
from ..utils.performance import PerformanceTracker, TradeRecord


@dataclass
class BacktestPosition:
    """Represents an open position in backtesting."""
    pair: str
    side: str  # BUY or SELL
    quantity: float
    entry_price: float
    entry_timestamp: int
    current_price: float
    unrealized_pnl: float = 0.0
    
    def update_pnl(self, current_price: float):
        """Update unrealized PnL based on current price."""
        self.current_price = current_price
        if self.side == "BUY":
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        else:  # SELL
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity


@dataclass
class BacktestResult:
    """Results of a backtest run."""
    start_date: str
    end_date: str
    initial_balance: float
    final_balance: float
    total_return: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: Optional[float]
    avg_win: Optional[float]
    avg_loss: Optional[float]
    trades_by_pair: Dict[str, int]
    pnl_by_pair: Dict[str, float]
    avg_capital_per_trade: Optional[float]
    max_capital_per_trade: Optional[float]
    min_capital_per_trade: Optional[float]


class Backtester:
    """Backtesting engine for trading strategies."""
    
    def __init__(
        self,
        config_path: str = "config/config.yaml",
        initial_balance: float = 50000.0
    ):
        """
        Initialize backtester.
        
        Args:
            config_path: Path to configuration file
            initial_balance: Starting balance for backtest
        """
        self.config = load_config(config_path)
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.logger = setup_logger(
            name="backtester",
            log_file="logs/backtest.log",
            level="INFO"
        )
        
        # Initialize data storage
        data_config = self.config.get('data', {})
        self.data_storage = DataStorage(
            db_path=f"data/{data_config.get('storage', 'sqlite')}.db",
            retention_days=365  # Keep more data for backtesting
        )
        
        # Initialize strategy
        self.strategy = EnsembleStrategy(self.config.get('strategies', {}))
        
        # Initialize risk manager
        trading_config = self.config.get('trading', {})
        self.risk_manager = RiskManager(
            config=trading_config,
            roostoo_client=None  # Not needed for backtesting
        )
        
        # Trading configuration
        self.trading_pairs = trading_config.get('pairs', [])
        self.min_confidence = trading_config.get('min_confidence', 0.5)
        
        # Backtest state
        self.positions: Dict[str, BacktestPosition] = {}  # pair -> position
        self.closed_trades: List[Dict[str, Any]] = []
        self.balance_history: List[Dict[str, Any]] = []
        self.last_trade_time: Dict[str, int] = {}
        self.cooldown_period = trading_config.get('cooldown_period', 300) * 1000  # Convert to ms
        
        self.logger.info(f"Backtester initialized with balance: ${initial_balance:,.2f}")
    
    def load_historical_data(
        self,
        pairs: List[str],
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load historical data for specified pairs.
        
        Args:
            pairs: List of trading pairs
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds
            
        Returns:
            Dictionary mapping pair to list of historical data points
        """
        historical_data = {}
        
        for pair in pairs:
            data = self.data_storage.get_ticker_history(
                pair=pair,
                start_time=start_time,
                end_time=end_time
            )
            
            # Sort by timestamp ascending
            data.sort(key=lambda x: x['timestamp'])
            
            if data:
                historical_data[pair] = data
                self.logger.info(f"Loaded {len(data)} data points for {pair}")
            else:
                self.logger.warning(f"No historical data found for {pair}")
        
        return historical_data
    
    def _can_trade(self, pair: str, timestamp: int) -> bool:
        """Check if trading is allowed for a pair at given timestamp."""
        if pair in self.last_trade_time:
            time_since_last = timestamp - self.last_trade_time[pair]
            if time_since_last < self.cooldown_period:
                return False
        return True
    
    def _calculate_position_size(
        self,
        pair: str,
        price: float,
        signal_confidence: float
    ) -> float:
        """Calculate position size based on risk parameters and pair weights."""
        return self.risk_manager.get_position_size(
            pair=pair,
            price=price,
            balance=self.balance,
            signal_confidence=signal_confidence
        )
    
    def _open_position(
        self,
        pair: str,
        side: str,
        quantity: float,
        price: float,
        timestamp: int
    ):
        """Open a new position."""
        cost = quantity * price
        
        if side == "BUY":
            if self.balance < cost:
                self.logger.warning(f"Insufficient balance for {pair} BUY: ${self.balance:.2f} < ${cost:.2f}")
                return False
            self.balance -= cost
        else:  # SELL
            # Spot-only mode: do not allow opening short positions
            self.logger.info(f"Spot-only: ignoring attempt to OPEN SELL on {pair}")
            return False
        
        position = BacktestPosition(
            pair=pair,
            side=side,
            quantity=quantity,
            entry_price=price,
            entry_timestamp=timestamp,
            current_price=price
        )
        
        self.positions[pair] = position
        self.last_trade_time[pair] = timestamp
        
        # Get pair weight if configured
        pair_weight = None
        if hasattr(self.risk_manager, 'pair_weights') and pair in self.risk_manager.pair_weights:
            pair_weight = self.risk_manager.pair_weights[pair]
        
        order_value = quantity * price
        
        trade_details = [
            f"\n{'='*70}",
            f"TRADE OPENED - {side}",
            f"{'='*70}",
            f"Pair:              {pair}",
            f"Side:               {side}",
            f"Quantity:           {quantity:.6f}",
            f"Price:              ${price:.4f}",
            f"Order Value:        ${order_value:,.2f}"
        ]
        
        if pair_weight:
            trade_details.append(f"Pair Weight:        {pair_weight:.2%}")
        
        trade_details.extend([
            f"Balance:            ${self.balance:,.2f}",
            f"{'='*70}\n"
        ])
        
        self.logger.info("\n".join(trade_details))
        
        return True
    
    def _close_position(
        self,
        pair: str,
        price: float,
        timestamp: int
    ) -> Optional[float]:
        """Close an existing position and calculate PnL."""
        if pair not in self.positions:
            return None
        
        position = self.positions[pair]
        
        # Calculate realized PnL
        if position.side == "BUY":
            pnl = (price - position.entry_price) * position.quantity
            self.balance += position.quantity * price  # Sell to close
        else:  # SELL (short)
            pnl = (position.entry_price - price) * position.quantity
            self.balance -= position.quantity * price  # Buy to close
        
        # Calculate duration
        duration_ms = timestamp - position.entry_timestamp
        duration_seconds = duration_ms / 1000
        duration_minutes = duration_seconds / 60
        duration_hours = duration_minutes / 60
        
        # Format duration
        if duration_hours >= 1:
            duration_str = f"{duration_hours:.1f}h"
        elif duration_minutes >= 1:
            duration_str = f"{duration_minutes:.1f}m"
        else:
            duration_str = f"{duration_seconds:.1f}s"
        
        # Record trade
        trade_record = {
            'timestamp': datetime.fromtimestamp(timestamp / 1000).isoformat(),
            'pair': pair,
            'side': position.side,
            'quantity': position.quantity,
            'entry_price': position.entry_price,
            'exit_price': price,
            'pnl': pnl,
            'pnl_pct': ((price - position.entry_price) / position.entry_price * 100) if position.side == "BUY" else ((position.entry_price - price) / position.entry_price * 100),
            'duration_ms': duration_ms,
            'duration_str': duration_str,
            'entry_value': position.quantity * position.entry_price,
            'exit_value': position.quantity * price,
            'capital_used': position.quantity * position.entry_price
        }
        
        self.closed_trades.append(trade_record)
        
        # Log detailed trade information
        pnl_sign = "+" if pnl >= 0 else ""
        pnl_pct = trade_record['pnl_pct']
        
        self.logger.info(
            f"\n{'='*70}\n"
            f"TRADE CLOSED - {position.side}\n"
            f"{'='*70}\n"
            f"Pair:              {pair}\n"
            f"Side:               {position.side}\n"
            f"Quantity:           {position.quantity:.6f}\n"
            f"Entry Price:        ${position.entry_price:.4f}\n"
            f"Exit Price:         ${price:.4f}\n"
            f"Entry Value:        ${trade_record['entry_value']:,.2f}\n"
            f"Exit Value:         ${trade_record['exit_value']:,.2f}\n"
            f"PnL:                {pnl_sign}${pnl:,.2f} ({pnl_sign}{pnl_pct:.2f}%)\n"
            f"Duration:           {duration_str}\n"
            f"Balance:            ${self.balance:,.2f}\n"
            f"{'='*70}\n"
        )
        
        del self.positions[pair]
        
        return pnl
    
    def _update_positions(self, current_prices: Dict[str, float]):
        """Update unrealized PnL for all open positions."""
        for pair, position in self.positions.items():
            if pair in current_prices:
                position.update_pnl(current_prices[pair])
    
    def _get_total_equity(self, current_prices: Dict[str, float]) -> float:
        """Calculate total equity (balance + unrealized PnL)."""
        equity = self.balance
        for pair, position in self.positions.items():
            if pair in current_prices:
                position.update_pnl(current_prices[pair])
                equity += position.unrealized_pnl
        return equity
    
    def run(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        pairs: Optional[List[str]] = None
    ) -> BacktestResult:
        """
        Run backtest on historical data.
        
        Args:
            start_date: Start date in YYYY-MM-DD format (default: from config, typically 10 days ago)
            end_date: End date in YYYY-MM-DD format (default: today)
            pairs: List of pairs to backtest (default: from config)
            
        Returns:
            BacktestResult with performance metrics
        """
        if pairs is None:
            pairs = self.trading_pairs
        
        # Calculate time range
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            end_dt = datetime.now()
        
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            # Get default days from config
            backtest_config = self.config.get('backtest', {})
            default_days = backtest_config.get('default_start_days', 10)
            start_dt = end_dt - timedelta(days=default_days)
        
        start_timestamp = int(start_dt.timestamp() * 1000)
        end_timestamp = int(end_dt.timestamp() * 1000)
        
        self.logger.info(
            f"Starting backtest from {start_dt.date()} to {end_dt.date()} "
            f"for pairs: {pairs}"
        )
        
        # Load historical data
        historical_data = self.load_historical_data(
            pairs=pairs,
            start_time=start_timestamp,
            end_time=end_timestamp
        )
        
        if not historical_data:
            self.logger.error("No historical data available for backtesting")
            raise ValueError("No historical data available")
        
        # Reset state
        self.balance = self.initial_balance
        self.positions = {}
        self.closed_trades = []
        self.balance_history = []
        self.last_trade_time = {}
        
        # Get all unique timestamps and sort
        all_timestamps = set()
        for pair_data in historical_data.values():
            for point in pair_data:
                all_timestamps.add(point['timestamp'])
        
        sorted_timestamps = sorted(all_timestamps)
        
        self.logger.info(f"Processing {len(sorted_timestamps)} time points")
        
        # Process each timestamp
        for i, timestamp in enumerate(sorted_timestamps):
            # Get current prices for all pairs at this timestamp
            current_prices = {}
            market_data_by_pair = {}
            
            for pair in pairs:
                if pair not in historical_data:
                    continue
                
                # Find data point at or before this timestamp
                pair_data = historical_data[pair]
                data_point = None
                
                for point in pair_data:
                    if point['timestamp'] <= timestamp:
                        data_point = point
                    else:
                        break
                
                if data_point:
                    current_prices[pair] = data_point.get('last_price', 0)
                    
                    # Format market data for strategy
                    market_data_by_pair[pair] = {
                        'pair': pair,
                        'roostoo': {
                            'LastPrice': data_point.get('last_price'),
                            'MaxBid': data_point.get('max_bid'),
                            'MinAsk': data_point.get('min_ask'),
                            'Change': data_point.get('change', 0)
                        }
                    }
            
            # Update unrealized PnL
            self._update_positions(current_prices)
            
            # Process each pair
            for pair in pairs:
                if pair not in market_data_by_pair:
                    continue
                
                market_data = market_data_by_pair[pair]
                
                # Update strategy state
                self.strategy.update_state(market_data)
                
                # Generate signal
                signal = self.strategy.generate_signal(market_data)
                
                # Check if we should trade
                if signal.confidence < self.min_confidence:
                    continue
                
                if not self._can_trade(pair, timestamp):
                    continue
                
                current_price = current_prices.get(pair)
                if not current_price or current_price <= 0:
                    continue
                
                # Check if we have an open position
                if pair in self.positions:
                    position = self.positions[pair]
                    
                    # Spot-only: SELL signal closes existing BUY position
                    if position.side == "BUY" and signal.action == "SELL":
                        self._close_position(pair, current_price, timestamp)
                
                # Open new position only on BUY signal (spot-only)
                if signal.action == "BUY" and pair not in self.positions:
                    # Concurrency cap
                    max_concurrent = getattr(self.risk_manager, 'max_concurrent_positions', None)
                    if max_concurrent is not None and len(self.positions) >= int(max_concurrent):
                        continue

                    # Base position size (equity-based sizing via risk manager; we'll cap by cash/exposure)
                    quantity = self._calculate_position_size(
                        pair=pair,
                        price=current_price,
                        signal_confidence=signal.confidence
                    )

                    # Exposure cap: ensure total notional does not exceed max_portfolio_exposure_pct * equity
                    max_exposure_pct = getattr(self.risk_manager, 'max_portfolio_exposure_pct', None)
                    if max_exposure_pct is not None:
                        # Compute current exposure as sum of position notionals at current prices
                        current_exposure = 0.0
                        for p in self.positions.values():
                            ref_price = current_prices.get(p.pair, p.current_price)
                            current_exposure += (p.quantity * ref_price)
                        # Equity for cap (cash + unrealized)
                        equity_cap = self._get_total_equity(current_prices)
                        allowed_notional = float(max_exposure_pct) * equity_cap - current_exposure
                        if allowed_notional <= 0:
                            quantity = 0.0
                        else:
                            max_qty_by_exposure = allowed_notional / current_price
                            if quantity > max_qty_by_exposure:
                                quantity = max(0.0, max_qty_by_exposure)

                    # Cash cap: cannot spend more cash than available
                    max_qty_by_cash = self.balance / current_price if current_price > 0 else 0.0
                    if quantity > max_qty_by_cash:
                        quantity = max(0.0, max_qty_by_cash)

                    if quantity > 0:
                        self._open_position(
                            pair=pair,
                            side="BUY",
                            quantity=quantity,
                            price=current_price,
                            timestamp=timestamp
                        )
            
            # Record balance history periodically
            if i % 100 == 0 or i == len(sorted_timestamps) - 1:
                equity = self._get_total_equity(current_prices)
                self.balance_history.append({
                    'timestamp': timestamp,
                    'balance': self.balance,
                    'equity': equity,
                    'open_positions': len(self.positions)
                })
        
        # Close all remaining positions at final price
        final_prices = {}
        for pair in pairs:
            if pair in historical_data and historical_data[pair]:
                final_prices[pair] = historical_data[pair][-1].get('last_price', 0)
        
        for pair in list(self.positions.keys()):
            if pair in final_prices:
                self._close_position(pair, final_prices[pair], sorted_timestamps[-1])
        
        # Append final balance/equity snapshot after closing remaining positions
        if sorted_timestamps:
            final_timestamp = sorted_timestamps[-1]
            final_equity = self._get_total_equity(final_prices) if final_prices else self.balance
            self.balance_history.append({
                'timestamp': final_timestamp,
                'balance': self.balance,
                'equity': final_equity,
                'open_positions': len(self.positions)
            })
        
        # Calculate results
        result = self._calculate_results(start_dt, end_dt)
        
        self.logger.info(
            f"Backtest completed: "
            f"Return: {result.total_return_pct:.2f}%, "
            f"Trades: {result.total_trades}, "
            f"Win Rate: {result.win_rate:.2%}"
        )
        
        return result
    
    def _calculate_results(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> BacktestResult:
        """Calculate backtest results and metrics."""
        final_equity = self.balance
        for position in self.positions.values():
            final_equity += position.unrealized_pnl
        
        total_return = final_equity - self.initial_balance
        total_return_pct = (total_return / self.initial_balance) * 100
        
        # Calculate win rate
        winning_trades = [t for t in self.closed_trades if t['pnl'] > 0]
        losing_trades = [t for t in self.closed_trades if t['pnl'] < 0]
        win_rate = len(winning_trades) / len(self.closed_trades) if self.closed_trades else 0.0
        
        # Calculate max drawdown
        max_drawdown = 0.0
        max_drawdown_pct = 0.0
        peak_equity = self.initial_balance
        
        for point in self.balance_history:
            equity = point['equity']
            if equity > peak_equity:
                peak_equity = equity
            
            drawdown = peak_equity - equity
            drawdown_pct = (drawdown / peak_equity) * 100 if peak_equity > 0 else 0
            
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                max_drawdown_pct = drawdown_pct
        
        # Calculate Sharpe ratio
        returns = [t['pnl'] for t in self.closed_trades]
        sharpe_ratio = None
        if len(returns) > 1:
            import statistics
            mean_return = statistics.mean(returns)
            std_return = statistics.stdev(returns) if len(returns) > 1 else 0
            sharpe_ratio = mean_return / std_return if std_return > 0 else None
        
        # Calculate average win/loss
        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else None
        avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else None
        
        # Trades by pair
        trades_by_pair = {}
        pnl_by_pair = {}
        for trade in self.closed_trades:
            pair = trade['pair']
            trades_by_pair[pair] = trades_by_pair.get(pair, 0) + 1
            pnl_by_pair[pair] = pnl_by_pair.get(pair, 0.0) + trade['pnl']

        capital_per_trade = [t['entry_value'] for t in self.closed_trades]
        avg_capital = sum(capital_per_trade) / len(capital_per_trade) if capital_per_trade else None
        max_capital = max(capital_per_trade) if capital_per_trade else None
        min_capital = min(capital_per_trade) if capital_per_trade else None
        
        return BacktestResult(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            initial_balance=self.initial_balance,
            final_balance=final_equity,
            total_return=total_return,
            total_return_pct=total_return_pct,
            total_trades=len(self.closed_trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            total_pnl=sum(t['pnl'] for t in self.closed_trades),
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            avg_win=avg_win,
            avg_loss=avg_loss,
            trades_by_pair=trades_by_pair,
            pnl_by_pair=pnl_by_pair,
            avg_capital_per_trade=avg_capital,
            max_capital_per_trade=max_capital,
            min_capital_per_trade=min_capital
        )
    
    def save_report(self, result: BacktestResult, output_path: str = "data/backtest_report.json"):
        """Save backtest report to file."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        report = {
            'backtest_result': asdict(result),
            'closed_trades': self.closed_trades,
            'balance_history': self.balance_history,
            'config': {
                'pairs': self.trading_pairs,
                'min_confidence': self.min_confidence,
                'pair_weights': self.config.get('trading', {}).get('pair_weights', {})
            }
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.logger.info(f"Backtest report saved to {output_file}")
        
        # Print summary
        print("\n" + "="*70)
        print("BACKTEST RESULTS")
        print("="*70)
        print(f"Period: {result.start_date} to {result.end_date}")
        print(f"Initial Balance: ${result.initial_balance:,.2f}")
        print(f"Final Balance: ${result.final_balance:,.2f}")
        print(f"Total Return: ${result.total_return:,.2f} ({result.total_return_pct:.2f}%)")
        print(f"\nTrades: {result.total_trades}")
        print(f"  Winning: {result.winning_trades}")
        print(f"  Losing: {result.losing_trades}")
        print(f"  Win Rate: {result.win_rate:.2%}")
        print(f"\nMax Drawdown: ${result.max_drawdown:,.2f} ({result.max_drawdown_pct:.2f}%)")
        if result.sharpe_ratio:
            print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
        if result.avg_win:
            print(f"Average Win: ${result.avg_win:,.2f}")
        if result.avg_loss:
            print(f"Average Loss: ${result.avg_loss:,.2f}")
        if result.avg_capital_per_trade is not None:
            print(f"Avg Capital per Trade: ${result.avg_capital_per_trade:,.2f}")
            print(f"Max Capital per Trade: ${result.max_capital_per_trade:,.2f}")
            print(f"Min Capital per Trade: ${result.min_capital_per_trade:,.2f}")
        print(f"\nTrades by Pair:")
        for pair, count in result.trades_by_pair.items():
            pnl = result.pnl_by_pair.get(pair, 0)
            print(f"  {pair}: {count} trades, PnL: ${pnl:,.2f}")
        
        # Print detailed trade list
        if self.closed_trades:
            print(f"\n{'='*70}")
            print("DETAILED TRADE LIST")
            print(f"{'='*70}")
            print(f"{'Timestamp':<20} {'Pair':<12} {'Side':<5} {'Qty':<12} {'Entry':<10} {'Exit':<10} {'Capital':<12} {'PnL':<12} {'PnL%':<8} {'Duration':<10}")
            print("-" * 70)
            
            for trade in self.closed_trades:
                timestamp = trade['timestamp'].split('T')[1].split('.')[0] if 'T' in trade['timestamp'] else trade['timestamp']
                pnl_sign = "+" if trade['pnl'] >= 0 else ""
                pnl_pct_sign = "+" if trade['pnl_pct'] >= 0 else ""
                
                print(
                    f"{timestamp:<20} "
                    f"{trade['pair']:<12} "
                    f"{trade['side']:<5} "
                    f"{trade['quantity']:<12.6f} "
                    f"${trade['entry_price']:<9.4f} "
                    f"${trade['exit_price']:<9.4f} "
                    f"${trade['capital_used']:<11.2f} "
                    f"{pnl_sign}${trade['pnl']:<11.2f} "
                    f"{pnl_pct_sign}{trade['pnl_pct']:<7.2f}% "
                    f"{trade['duration_str']:<10}"
                )
        
        print("="*70 + "\n")


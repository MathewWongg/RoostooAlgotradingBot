"""Main Trading Bot Orchestration Loop"""

import time
import signal
import sys
from typing import List, Dict, Any
from .api.roostoo_client import RoostooClient
from .api.horus_client import HorusClient
from .api.binance_client import BinanceClient
from .data.data_collector import DataCollector
from .data.data_storage import DataStorage
from .strategies.ensemble_strategy import EnsembleStrategy
from .execution.order_manager import OrderManager
from .execution.risk_manager import RiskManager
from .utils.config import load_config
from .utils.logger import setup_logger, get_logger
from .utils.performance import PerformanceTracker


class TradingBot:
    """Main trading bot class."""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize trading bot with configuration."""
        # Load configuration
        self.config = load_config(config_path)
        
        # Setup logging
        log_config = self.config.get('logging', {})
        self.logger = setup_logger(
            name="trading_bot",
            log_file=log_config.get('file', 'logs/bot.log'),
            level=log_config.get('level', 'INFO'),
            max_size_mb=log_config.get('max_size_mb', 100)
        )
        
        self.logger.info("Initializing Trading Bot...")
        
        # Initialize API clients
        roostoo_config = self.config.get('roostoo', {})
        self.roostoo_client = RoostooClient(
            api_key=roostoo_config.get('api_key'),
            secret_key=roostoo_config.get('secret_key'),
            base_url=roostoo_config.get('base_url', 'https://mock-api.roostoo.com')
        )
        
        # Optional clients
        self.horus_client = None
        horus_config = self.config.get('horus', {})
        if horus_config.get('enabled', False):
            self.horus_client = HorusClient(api_key=horus_config.get('api_key'))
        
        self.binance_client = None
        if self.config.get('data', {}).get('sources', []):
            if 'binance' in self.config.get('data', {}).get('sources', []):
                self.binance_client = BinanceClient()
        
        # Initialize data storage and collector
        data_config = self.config.get('data', {})
        self.data_storage = DataStorage(
            db_path=f"data/{data_config.get('storage', 'sqlite')}.db",
            retention_days=data_config.get('data_retention_days', 30)
        )
        
        self.data_collector = DataCollector(
            roostoo_client=self.roostoo_client,
            data_storage=self.data_storage,
            horus_client=self.horus_client,
            binance_client=self.binance_client
        )
        
        # Initialize strategy
        self.strategy = EnsembleStrategy(self.config.get('strategies', {}))
        
        # Initialize performance tracker
        self.performance_tracker = PerformanceTracker(data_dir="data")
        
        # Initialize execution modules
        trading_config = self.config.get('trading', {})
        self.order_manager = OrderManager(
            roostoo_client=self.roostoo_client,
            config=trading_config,
            performance_tracker=self.performance_tracker
        )
        
        self.risk_manager = RiskManager(
            config=trading_config,
            roostoo_client=self.roostoo_client
        )
        
        # Trading configuration
        self.trading_pairs = trading_config.get('pairs', [])
        if self.trading_pairs == "all":
            self.trading_pairs = self.data_collector.available_pairs
        
        self.polling_interval = trading_config.get('polling_interval', 60)
        self.min_confidence = trading_config.get('min_confidence', 0.5)
        
        # Control flags
        self.running = False
        self.iteration_count = 0
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("Trading Bot initialized successfully")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def _get_balance(self) -> Dict[str, float]:
        """Get current account balance."""
        try:
            response = self.roostoo_client.get_balance()
            if response and response.get('Success', False):
                wallet = response.get('Wallet', {})
                balances = {}
                for currency, data in wallet.items():
                    balances[currency] = data.get('Free', 0) + data.get('Lock', 0)
                return balances
        except Exception as e:
            self.logger.error(f"Error getting balance: {e}")
        return {}
    
    def _process_pair(self, pair: str):
        """Process a single trading pair."""
        try:
            # Collect market data
            market_data = self.data_collector.get_market_data(pair)
            
            if not market_data.get('roostoo'):
                self.logger.warning(f"No market data for {pair}")
                return
            
            # Update strategy state
            self.strategy.update_state(market_data)
            
            # Generate signal
            signal = self.strategy.generate_signal(market_data)
            
            self.logger.debug(
                f"{pair}: Signal={signal.action}, Confidence={signal.confidence:.2f}"
            )
            
            # Check if signal is strong enough
            if signal.confidence < self.min_confidence:
                return
            
            # Check if we can trade
            can_trade, reason = self.risk_manager.can_trade(pair)
            if not can_trade:
                self.logger.debug(f"Cannot trade {pair}: {reason}")
                return
            
            # Get balance
            balances = self._get_balance()
            base_currency = pair.split('/')[1] if '/' in pair else 'USD'
            available_balance = balances.get(base_currency, 0)
            
            if available_balance <= 0:
                self.logger.warning(f"Insufficient balance for {pair}")
                return
            
            # Calculate position size
            current_price = signal.price or market_data['roostoo'].get('LastPrice', 0)
            if current_price <= 0:
                return
            
            quantity = self.risk_manager.get_position_size(
                pair=pair,
                price=current_price,
                balance=available_balance,
                signal_confidence=signal.confidence
            )
            
            if quantity <= 0:
                return
            
            # Check balance sufficiency
            required_amount = quantity * current_price
            if not self.risk_manager.check_balance_sufficient(required_amount, available_balance):
                self.logger.warning(f"Insufficient balance for {pair} trade")
                return
            
            # Execute order
            order_price = None
            if self.order_manager.order_type == "LIMIT":
                # For LIMIT orders, use current price with small offset
                if signal.action == "BUY":
                    order_price = current_price * 0.99  # 1% below market
                else:
                    order_price = current_price * 1.01  # 1% above market
            
            order_response = self.order_manager.execute_signal(
                signal=signal,
                quantity=quantity,
                price=order_price
            )
            
            if order_response:
                order_detail = order_response.get('OrderDetail', {})
                order_id = order_detail.get('OrderID')
                
                # Record trade in risk manager
                self.risk_manager.record_trade(
                    pair=pair,
                    side=signal.action,
                    quantity=quantity,
                    price=order_detail.get('Price', current_price),
                    order_id=order_id
                )
                
                self.logger.info(
                    f"Order placed: {signal.action} {quantity} {pair} @ {order_price or 'MARKET'}"
                )
        
        except Exception as e:
            self.logger.error(f"Error processing pair {pair}: {e}", exc_info=True)
    
    def run(self):
        """Main trading loop."""
        self.logger.info("Starting trading bot...")
        self.logger.info(f"Trading pairs: {self.trading_pairs}")
        self.logger.info(f"Polling interval: {self.polling_interval}s")
        self.logger.info(f"Min confidence: {self.min_confidence}")
        
        self.running = True
        
        try:
            while self.running:
                self.iteration_count += 1
                self.logger.info(f"=== Iteration {self.iteration_count} ===")
                
                # Process each trading pair
                for pair in self.trading_pairs:
                    try:
                        self._process_pair(pair)
                    except Exception as e:
                        self.logger.error(f"Error processing {pair}: {e}")
                
                # Check pending orders
                try:
                    pending_orders = self.order_manager.get_pending_orders()
                    if pending_orders:
                        self.logger.debug(f"Pending orders: {len(pending_orders)}")
                except Exception as e:
                    self.logger.error(f"Error checking pending orders: {e}")
                
                # Save performance report periodically
                if self.iteration_count % 10 == 0:
                    try:
                        self.performance_tracker.save_performance_report()
                        metrics = self.performance_tracker.calculate_metrics()
                        self.logger.info(
                            f"Performance: Trades={metrics.total_trades}, "
                            f"Win Rate={metrics.win_rate:.2%}, "
                            f"PnL={metrics.total_pnl:.2f}"
                        )
                    except Exception as e:
                        self.logger.error(f"Error saving performance report: {e}")
                
                # Sleep until next iteration
                if self.running:
                    time.sleep(self.polling_interval)
        
        except KeyboardInterrupt:
            self.logger.info("Trading bot stopped by user")
        except Exception as e:
            self.logger.error(f"Fatal error in trading loop: {e}", exc_info=True)
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Graceful shutdown."""
        self.logger.info("Shutting down trading bot...")
        self.running = False
        
        # Save final performance report
        try:
            self.performance_tracker.save_performance_report()
        except Exception as e:
            self.logger.error(f"Error saving final performance report: {e}")
        
        self.logger.info("Trading bot shutdown complete")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Crypto Trading Bot')
    parser.add_argument(
        '--config',
        type=str,
        default='config/config.yaml',
        help='Path to configuration file'
    )
    
    args = parser.parse_args()
    
    try:
        bot = TradingBot(config_path=args.config)
        bot.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


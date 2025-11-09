"""Logging Module with Structured Logging"""

import logging
import json
import os
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)
        
        return json.dumps(log_data)


def setup_logger(
    name: str = "trading_bot",
    log_file: Optional[str] = "logs/bot.log",
    level: str = "INFO",
    max_size_mb: int = 100,
    backup_count: int = 5
) -> logging.Logger:
    """
    Set up logger with file and console handlers.
    
    Args:
        name: Logger name
        log_file: Path to log file
        level: Logging level
        max_size_mb: Maximum log file size in MB
        backup_count: Number of backup files to keep
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create logs directory if it doesn't exist
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # File handler with rotation
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count
        )
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str = "trading_bot") -> logging.Logger:
    """Get existing logger or create new one."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


def log_api_request(
    logger: logging.Logger,
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    success: bool = True,
    response: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None
):
    """Log API request with structured data."""
    extra_data = {
        'extra_data': {
            'type': 'api_request',
            'method': method,
            'endpoint': endpoint,
            'params': params,
            'success': success,
            'response': response,
            'error': error
        }
    }
    
    if success:
        logger.info(f"API Request: {method} {endpoint}", extra=extra_data)
    else:
        logger.error(f"API Request Failed: {method} {endpoint} - {error}", extra=extra_data)


def log_trade(
    logger: logging.Logger,
    action: str,
    pair: str,
    side: str,
    quantity: float,
    price: Optional[float] = None,
    order_id: Optional[int] = None,
    status: Optional[str] = None,
    **kwargs
):
    """Log trade execution with structured data."""
    extra_data = {
        'extra_data': {
            'type': 'trade',
            'action': action,
            'pair': pair,
            'side': side,
            'quantity': quantity,
            'price': price,
            'order_id': order_id,
            'status': status,
            **kwargs
        }
    }
    
    logger.info(f"Trade {action}: {side} {quantity} {pair} @ {price}", extra=extra_data)


def log_trade_details(
    logger: logging.Logger,
    pair: str,
    side: str,
    quantity: float,
    price: float,
    order_id: Optional[int] = None,
    signal_confidence: Optional[float] = None,
    order_value: Optional[float] = None,
    filled_quantity: Optional[float] = None,
    filled_avg_price: Optional[float] = None,
    commission: Optional[float] = None,
    balance: Optional[float] = None,
    pair_weight: Optional[float] = None,
    **kwargs
):
    """
    Log detailed trade information in a formatted, human-readable way.
    
    Args:
        logger: Logger instance
        pair: Trading pair
        side: BUY or SELL
        quantity: Order quantity
        price: Order price
        order_id: Order ID
        signal_confidence: Signal confidence (0-1)
        order_value: Total order value
        filled_quantity: Filled quantity
        filled_avg_price: Average fill price
        commission: Commission charged
        balance: Account balance after trade
        pair_weight: Pair weight used for position sizing
        **kwargs: Additional trade details
    """
    # Calculate order value if not provided
    if order_value is None:
        order_value = quantity * price
    
    # Build detailed message
    details = []
    details.append(f"\n{'='*70}")
    details.append(f"TRADE EXECUTED - {side}")
    details.append(f"{'='*70}")
    details.append(f"Pair:              {pair}")
    details.append(f"Side:               {side}")
    details.append(f"Quantity:           {quantity:.6f}")
    details.append(f"Price:              ${price:.4f}")
    details.append(f"Order Value:        ${order_value:,.2f}")
    
    if order_id:
        details.append(f"Order ID:           {order_id}")
    
    if signal_confidence is not None:
        details.append(f"Signal Confidence:  {signal_confidence:.2%}")
    
    if pair_weight is not None:
        details.append(f"Pair Weight:        {pair_weight:.2%}")
    
    if filled_quantity is not None:
        details.append(f"Filled Quantity:    {filled_quantity:.6f}")
        fill_pct = (filled_quantity / quantity * 100) if quantity > 0 else 0
        details.append(f"Fill Percentage:    {fill_pct:.2f}%")
    
    if filled_avg_price is not None and filled_avg_price != price:
        details.append(f"Avg Fill Price:     ${filled_avg_price:.4f}")
    
    if commission is not None:
        details.append(f"Commission:         ${commission:.4f}")
    
    if balance is not None:
        details.append(f"Account Balance:   ${balance:,.2f}")
    
    if status := kwargs.get('status'):
        details.append(f"Status:             {status}")
    
    # Add any additional details
    for key, value in kwargs.items():
        if key not in ['status'] and value is not None:
            details.append(f"{key.replace('_', ' ').title():18} {value}")
    
    details.append(f"{'='*70}\n")
    
    # Log the formatted message
    message = "\n".join(details)
    logger.info(message)
    
    # Also log structured data for programmatic access
    log_trade(
        logger,
        "EXECUTED",
        pair,
        side,
        quantity,
        price,
        order_id=order_id,
        status=kwargs.get('status'),
        signal_confidence=signal_confidence,
        order_value=order_value,
        filled_quantity=filled_quantity,
        filled_avg_price=filled_avg_price,
        commission=commission,
        balance=balance,
        pair_weight=pair_weight,
        **{k: v for k, v in kwargs.items() if k != 'status'}
    )

"""Data Storage Module for Local Data Caching"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from ..utils.logger import get_logger


class DataStorage:
    """Local data storage using SQLite."""
    
    def __init__(self, db_path: str = "data/market_data.db", retention_days: int = 30):
        """
        Initialize data storage.
        
        Args:
            db_path: Path to SQLite database file
            retention_days: Number of days to retain data
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        self.logger = get_logger("data_storage")
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Ticker data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticker_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pair TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                max_bid REAL,
                min_ask REAL,
                last_price REAL,
                change REAL,
                coin_trade_value REAL,
                unit_trade_value REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(pair, timestamp)
            )
        ''')
        
        # Create index for faster queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pair_timestamp ON ticker_data(pair, timestamp)')
        
        conn.commit()
        conn.close()
    
    def store_ticker_data(self, pair: str, ticker_data: Dict[str, Any], timestamp: Optional[int] = None):
        """
        Store ticker data.
        
        Args:
            pair: Trading pair
            ticker_data: Ticker data dictionary
            timestamp: Timestamp (default: current time)
        """
        if timestamp is None:
            timestamp = int(datetime.utcnow().timestamp() * 1000)
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO ticker_data 
                (pair, timestamp, max_bid, min_ask, last_price, change, coin_trade_value, unit_trade_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                pair,
                timestamp,
                ticker_data.get('MaxBid'),
                ticker_data.get('MinAsk'),
                ticker_data.get('LastPrice'),
                ticker_data.get('Change'),
                ticker_data.get('CoinTradeValue'),
                ticker_data.get('UnitTradeValue')
            ))
            
            conn.commit()
        except Exception as e:
            self.logger.error(f"Error storing ticker data: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_ticker_history(
        self,
        pair: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get historical ticker data.
        
        Args:
            pair: Trading pair
            start_time: Start timestamp (milliseconds)
            end_time: End timestamp (milliseconds)
            limit: Maximum number of records
            
        Returns:
            List of ticker data dictionaries
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = 'SELECT * FROM ticker_data WHERE pair = ?'
        params = [pair]
        
        if start_time:
            query += ' AND timestamp >= ?'
            params.append(start_time)
        
        if end_time:
            query += ' AND timestamp <= ?'
            params.append(end_time)
        
        query += ' ORDER BY timestamp DESC'
        
        if limit:
            query += ' LIMIT ?'
            params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def cleanup_old_data(self):
        """Remove data older than retention period."""
        cutoff_time = int((datetime.utcnow() - timedelta(days=self.retention_days)).timestamp() * 1000)
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM ticker_data WHERE timestamp < ?', (cutoff_time,))
            deleted = cursor.rowcount
            conn.commit()
            self.logger.info(f"Cleaned up {deleted} old records")
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")
            conn.rollback()
        finally:
                conn.close()


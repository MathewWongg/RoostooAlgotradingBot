"""Oversold Bounce Strategy tuned for meme assets with community filter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy, TradingSignal
from ..utils.logger import get_logger


@dataclass
class OversoldConditions:
    rsi: float
    bollinger_lower: float
    current_price: float
    volume: float
    volume_ema: float
    sma: float
    community_membership: Optional[int]
    rsi_condition: bool
    bollinger_condition: bool
    candle_condition: bool
    volume_condition: bool
    trend_condition: bool
    community_condition: bool

    @property
    def all_passed(self) -> bool:
        return all(
            [
                self.rsi_condition,
                self.bollinger_condition,
                self.candle_condition,
                self.volume_condition,
                self.trend_condition,
                self.community_condition,
            ]
        )


class OversoldBounceStrategy(BaseStrategy):
    """Identifies deep pullbacks within broader uptrends for meme assets."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("OversoldBounceStrategy", config)
        self.logger = get_logger("oversold_bounce_strategy")

        self.enabled = config.get("enabled", True)
        self.rsi_period = int(config.get("rsi_period", 14))
        self.rsi_threshold = float(config.get("rsi_threshold", 25.0))
        self.bb_period = int(config.get("bb_period", 20))
        self.bb_std = float(config.get("bb_std", 2.0))
        self.volume_ema_period = int(config.get("volume_ema_period", 20))
        self.sma_period = int(config.get("sma_period", 200))
        self.community_threshold = int(config.get("community_threshold", 10_000))
        self.community_membership: Dict[str, int] = {
            str(key): int(value)
            for key, value in (config.get("community_membership") or {}).items()
            if value is not None
        }
        self.base_confidence = float(config.get("base_confidence", 0.65))
        self.max_confidence = float(config.get("max_confidence", 0.9))
        self.capital_boost_multiplier = float(config.get("capital_boost_multiplier", 1.2))

        # Maintain latest OHLCV snapshots per pair for indicator calculations
        self.ohlcv_history: Dict[str, Dict[str, List[float]]] = {}

    def update_state(self, market_data: Dict[str, Any]):
        pair = market_data.get("pair", "")
        if not pair:
            return

        binance_klines = (
            market_data.get("binance", {}).get("klines")
            if isinstance(market_data.get("binance"), dict)
            else None
        )
        if isinstance(binance_klines, dict) and binance_klines.get("closes"):
            self.ohlcv_history[pair] = {
                "opens": list(binance_klines.get("opens", [])),
                "highs": list(binance_klines.get("highs", [])),
                "lows": list(binance_klines.get("lows", [])),
                "closes": list(binance_klines.get("closes", [])),
                "volumes": list(binance_klines.get("volumes", [])),
            }

    def generate_signal(self, market_data: Dict[str, Any]) -> TradingSignal:
        pair = market_data.get("pair", "")
        if not pair or not self.enabled:
            return TradingSignal(action="HOLD", confidence=0.0, pair=pair)

        conditions = self._evaluate_conditions(pair, market_data)
        if conditions is None:
            return TradingSignal(action="HOLD", confidence=0.0, pair=pair)

        metadata = {
            "strategy": self.name,
            "rsi": conditions.rsi,
            "bollinger_lower": conditions.bollinger_lower,
            "price": conditions.current_price,
            "volume": conditions.volume,
            "volume_ema": conditions.volume_ema,
            "sma": conditions.sma,
            "conditions": {
                "rsi": conditions.rsi_condition,
                "bollinger": conditions.bollinger_condition,
                "green_candle": conditions.candle_condition,
                "volume_spike": conditions.volume_condition,
                "sma_trend": conditions.trend_condition,
                "community": conditions.community_condition,
            },
            "community_membership": conditions.community_membership,
            "capital_boost": conditions.all_passed,
            "recommended_capital_multiplier": self.capital_boost_multiplier
            if conditions.all_passed
            else 1.0,
        }

        if conditions.all_passed:
            confidence = min(
                self.max_confidence,
                self.base_confidence
                + max(0.0, (self.rsi_threshold - conditions.rsi) / 100.0)
                + 0.05,
            )
            return TradingSignal(
                action="BUY",
                confidence=confidence,
                pair=pair,
                price=conditions.current_price,
                metadata=metadata,
            )

        # Fallback to neutral signal when setup incomplete
        return TradingSignal(
            action="HOLD",
            confidence=0.3,
            pair=pair,
            price=conditions.current_price,
            metadata=metadata,
        )

    # ---- Helpers -----------------------------------------------------------------

    def _evaluate_conditions(
        self, pair: str, market_data: Dict[str, Any]
    ) -> Optional[OversoldConditions]:
        ohlcv = self._get_ohlcv(pair, market_data)
        if ohlcv is None:
            return None

        opens, closes, volumes = ohlcv["opens"], ohlcv["closes"], ohlcv["volumes"]
        if len(closes) < max(self.bb_period, self.sma_period, self.rsi_period + 1, self.volume_ema_period):
            return None

        current_price = self._resolve_price(market_data, closes[-1])
        if current_price is None:
            return None

        rsi = self._calculate_rsi(closes)
        rsi_condition = rsi < self.rsi_threshold

        bollinger_lower = self._calculate_bollinger_lower(closes)
        bollinger_condition = bollinger_lower is not None and current_price < bollinger_lower

        candle_condition = closes[-1] > opens[-1]

        volume_ema = self._calculate_volume_ema(volumes)
        volume_condition = volume_ema is not None and volumes[-1] > volume_ema

        sma = self._calculate_sma(closes)
        trend_condition = sma is not None and current_price > sma

        community_condition, membership = self._check_community(pair, market_data)

        return OversoldConditions(
            rsi=rsi,
            bollinger_lower=bollinger_lower or 0.0,
            current_price=current_price,
            volume=volumes[-1],
            volume_ema=volume_ema or 0.0,
            sma=sma or 0.0,
            community_membership=membership,
            rsi_condition=rsi_condition,
            bollinger_condition=bollinger_condition,
            candle_condition=candle_condition,
            volume_condition=volume_condition,
            trend_condition=trend_condition,
            community_condition=community_condition,
        )

    def _get_ohlcv(
        self, pair: str, market_data: Dict[str, Any]
    ) -> Optional[Dict[str, List[float]]]:
        binance_data = market_data.get("binance", {})
        if isinstance(binance_data, dict):
            klines = binance_data.get("klines")
            if isinstance(klines, dict) and klines.get("closes"):
                required_keys = {"opens", "closes", "volumes"}
                if required_keys.issubset(klines.keys()):
                    return {
                        "opens": list(klines["opens"]),
                        "closes": list(klines["closes"]),
                        "volumes": list(klines["volumes"]),
                    }

        cached = self.ohlcv_history.get(pair)
        if cached and cached.get("closes"):
            return cached
        return None

    def _resolve_price(self, market_data: Dict[str, Any], fallback: float) -> Optional[float]:
        roostoo_price = (
            market_data.get("roostoo", {}).get("LastPrice")
            if isinstance(market_data.get("roostoo"), dict)
            else None
        )
        if isinstance(roostoo_price, (int, float)) and roostoo_price > 0:
            return float(roostoo_price)
        if isinstance(fallback, (int, float)) and fallback > 0:
            return float(fallback)
        return None

    def _calculate_rsi(self, closes: List[float]) -> float:
        if len(closes) < self.rsi_period + 1:
            return 50.0
        window = np.asarray(closes[-(self.rsi_period + 1) :], dtype=float)
        deltas = np.diff(window)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = gains.mean()
        avg_loss = losses.mean()

        if avg_loss == 0:
            return 100.0
        if avg_gain == 0:
            return 0.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _calculate_bollinger_lower(self, closes: List[float]) -> Optional[float]:
        if len(closes) < self.bb_period:
            return None
        window = np.asarray(closes[-self.bb_period :], dtype=float)
        mean = window.mean()
        std = window.std(ddof=0)
        return float(mean - self.bb_std * std)

    def _calculate_volume_ema(self, volumes: List[float]) -> Optional[float]:
        if len(volumes) < self.volume_ema_period:
            return None
        series = pd.Series(volumes[-(self.volume_ema_period * 3) :])
        ema = series.ewm(span=self.volume_ema_period, adjust=False).mean().iloc[-1]
        return float(ema)

    def _calculate_sma(self, closes: List[float]) -> Optional[float]:
        if len(closes) < self.sma_period:
            return None
        window = closes[-self.sma_period :]
        return float(np.mean(window))

    def _check_community(
        self, pair: str, market_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[int]]:
        membership = None
        community_data = market_data.get("community")
        if isinstance(community_data, dict):
            raw = community_data.get("telegram_members")
            if isinstance(raw, (int, float)):
                membership = int(raw)

        if membership is None:
            membership = self._lookup_membership_from_config(pair)

        if membership is None:
            return False, None
        return membership >= self.community_threshold, membership

    def _lookup_membership_from_config(self, pair: str) -> Optional[int]:
        if pair in self.community_membership:
            return self.community_membership[pair]
        if "/" in pair:
            base, _ = pair.split("/", 1)
            if base in self.community_membership:
                return self.community_membership[base]
        return None

    def reset(self):
        super().reset()
        self.ohlcv_history.clear()



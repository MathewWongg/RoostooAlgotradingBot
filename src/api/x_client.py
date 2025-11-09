"""X (Twitter) API client for fetching meme coin sentiment."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from ..utils.logger import get_logger


POSITIVE_KEYWORDS = {
    "bull",
    "bullish",
    "moon",
    "mooning",
    "pump",
    "rocket",
    "surge",
    "win",
    "buy",
    "bid",
    "green",
    "ath",
    "lfg",
}

NEGATIVE_KEYWORDS = {
    "bear",
    "bearish",
    "doom",
    "dump",
    "rug",
    "rekt",
    "sell",
    "short",
    "red",
    "crash",
    "dead",
    "fud",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SentimentEntry:
    """Cached sentiment payload."""

    fetched_at: datetime
    score: float
    posts: List[Dict[str, Any]]
    summary: Dict[str, Any]
    call_log: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fetched_at": self.fetched_at.isoformat(),
            "score": self.score,
            "posts": self.posts,
            "summary": self.summary,
            "call_log": self.call_log,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SentimentEntry":
        fetched_at = datetime.fromisoformat(payload["fetched_at"])
        return cls(
            fetched_at=fetched_at,
            score=payload.get("score", 0.0),
            posts=payload.get("posts", []),
            summary=payload.get("summary", {}),
            call_log=payload.get("call_log", []),
        )


class XClient:
    """Minimal X API v2 client with per-coin daily rate limiting."""

    SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"

    def __init__(
        self,
        bearer_token: str,
        *,
        coin_queries: Dict[str, str],
        requests_per_coin_per_day: int = 2,
        cache_ttl_hours: int = 12,
        cache_path: str = "data/social_cache.json",
        session: Optional[requests.Session] = None,
        max_results: int = 10,
    ):
        self.logger = get_logger("x_client")
        self.bearer_token = bearer_token
        self.coin_queries = coin_queries
        self.requests_per_coin_per_day = requests_per_coin_per_day
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.session = session or requests.Session()
        self.max_results = max(10, min(max_results, 100))

        self.cache: Dict[str, SentimentEntry] = {}
        self._load_cache()

    # --------------------------------------------------------------------- #
    # Cache management helpers
    # --------------------------------------------------------------------- #
    def _load_cache(self) -> None:
        if not self.cache_path.exists():
            return

        try:
            data = json.loads(self.cache_path.read_text())
            for coin, entry in data.items():
                try:
                    self.cache[coin] = SentimentEntry.from_dict(entry)
                except Exception as exc:
                    self.logger.warning(f"Failed to restore sentiment cache for {coin}: {exc}")
        except Exception as exc:
            self.logger.error(f"Error reading X sentiment cache: {exc}")

    def _persist_cache(self) -> None:
        serializable = {coin: entry.to_dict() for coin, entry in self.cache.items()}
        try:
            tmp_path = self.cache_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(serializable, indent=2))
            tmp_path.replace(self.cache_path)
        except Exception as exc:
            self.logger.error(f"Unable to persist X sentiment cache: {exc}")

    def _reset_call_log_if_needed(self, entry: SentimentEntry) -> None:
        today = _utcnow().date()
        filtered = []
        for ts in entry.call_log:
            try:
                dt = datetime.fromisoformat(ts).date()
                if dt == today:
                    filtered.append(ts)
            except ValueError:
                continue
        entry.call_log = filtered

    def _register_call(self, entry: SentimentEntry) -> None:
        entry.call_log.append(_utcnow().isoformat())

    def _remaining_calls(self, entry: SentimentEntry) -> int:
        self._reset_call_log_if_needed(entry)
        return max(self.requests_per_coin_per_day - len(entry.call_log), 0)

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def get_sentiment(self, coin: str, *, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Retrieve sentiment for the requested coin.

        Returns cached data where possible and enforces per-day call limits.
        """
        if coin not in self.coin_queries:
            self.logger.warning(f"No X query configured for coin '{coin}'")
            return None

        entry = self.cache.get(coin)

        if entry and not force_refresh:
            if _utcnow() - entry.fetched_at <= self.cache_ttl:
                return self._to_payload(coin, entry)

            if self._remaining_calls(entry) <= 0:
                self.logger.debug(
                    "Daily quota exhausted for %s; returning cached sentiment from %s",
                    coin,
                    entry.fetched_at,
                )
                return self._to_payload(coin, entry)

        if entry is None:
            entry = SentimentEntry(
                fetched_at=datetime.fromtimestamp(0, tz=timezone.utc),
                score=0.0,
                posts=[],
                summary={},
            )
            self.cache[coin] = entry

        if not force_refresh and _utcnow() - entry.fetched_at <= self.cache_ttl:
            return self._to_payload(coin, entry)

        if not force_refresh and self._remaining_calls(entry) <= 0:
            self.logger.debug(
                "Daily quota exhausted for %s; returning cached sentiment from %s",
                coin,
                entry.fetched_at,
            )
            return self._to_payload(coin, entry)

        raw_posts = self._fetch_posts(coin)
        if raw_posts is None:
            entry.fetched_at = _utcnow()
            if not entry.summary:
                entry.summary = {"score": 0.0, "volume": 0, "status": "unavailable"}
            entry.score = entry.summary.get("score", 0.0)
            self._register_call(entry)
            self._persist_cache()
            return self._to_payload(coin, entry)

        summary = self._summarize_posts(raw_posts)
        entry.fetched_at = _utcnow()
        entry.posts = raw_posts
        entry.summary = summary
        entry.score = summary.get("score", 0.0)
        self._register_call(entry)
        self._persist_cache()

        return self._to_payload(coin, entry)

    # ------------------------------------------------------------------ #
    def _fetch_posts(self, coin: str) -> Optional[List[Dict[str, Any]]]:
        query = self.coin_queries[coin]
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "User-Agent": "QuantCompSentimentBot/1.0",
        }
        params = {
            "query": query,
            "max_results": self.max_results,
            "tweet.fields": "created_at,lang,public_metrics,possibly_sensitive",
        }

        try:
            start = time.perf_counter()
            response = self.session.get(
                self.SEARCH_URL,
                headers=headers,
                params=params,
                timeout=10,
            )
            duration_ms = (time.perf_counter() - start) * 1000
            if response.status_code == 429:
                self.logger.warning("X API rate limit hit for %s", coin)
                return None

            response.raise_for_status()
            payload = response.json()
            posts = payload.get("data", [])
            self.logger.debug(
                "Fetched %s posts for %s in %.0fms",
                len(posts),
                coin,
                duration_ms,
            )
            return posts
        except requests.RequestException as exc:
            self.logger.error(f"Error fetching X data for {coin}: {exc}")
            return None

    def _score_text(self, text: str) -> float:
        text_lower = text.lower()
        positive = sum(1 for word in POSITIVE_KEYWORDS if word in text_lower)
        negative = sum(1 for word in NEGATIVE_KEYWORDS if word in text_lower)

        if positive == negative == 0:
            return 0.0

        score = positive - negative
        scale = positive + negative
        return max(min(score / scale, 1.0), -1.0)

    def _summarize_posts(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not posts:
            return {
                "score": 0.0,
                "volume": 0,
                "sample_posts": [],
                "tags": [],
            }

        samples = []
        total_score = 0.0
        likes = 0
        retweets = 0

        for post in posts:
            text = post.get("text", "")
            if not text:
                continue

            score = self._score_text(text)
            total_score += score

            metrics = post.get("public_metrics", {})
            likes += metrics.get("like_count", 0)
            retweets += metrics.get("retweet_count", 0)

            if len(samples) < 3:
                samples.append(text.strip())

        avg_score = total_score / max(len(posts), 1)
        normalized_score = max(min(avg_score, 1.0), -1.0)

        return {
            "score": round(normalized_score, 3),
            "volume": len(posts),
            "engagement": {
                "likes": likes,
                "retweets": retweets,
            },
            "sample_posts": samples,
            "tags": list({tag for tag in self._extract_tags(samples)}),
        }

    def _extract_tags(self, posts: List[str]) -> List[str]:
        tags: set[str] = set()
        for text in posts:
            for token in text.split():
                token = token.strip()
                if token.startswith(("#", "$")) and len(token) > 1:
                    tags.add(token)
        return list(tags)

    def _to_payload(self, coin: str, entry: SentimentEntry) -> Dict[str, Any]:
        return {
            "coin": coin,
            "fetched_at": entry.fetched_at.isoformat(),
            "score": entry.score,
            "summary": entry.summary,
            "posts": entry.posts,
            "source": "x",
            "remaining_calls_today": self._remaining_calls(entry),
        }



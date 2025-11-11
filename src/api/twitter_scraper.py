"""Twitter scraper using snscrape and Google Gemini API for sentiment analysis."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Lazy imports to avoid compatibility issues
sntwitter = None
genai = None

from ..utils.logger import get_logger


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


class TwitterScraper:
    """Twitter scraper using snscrape with Gemini API sentiment analysis."""

    def __init__(
        self,
        gemini_api_key: str,
        *,
        coin_accounts: Dict[str, str],
        requests_per_coin_per_day: int = 2,
        cache_ttl_hours: int = 12,
        cache_path: str = "data/social_cache.json",
        max_results: int = 25,
        gemini_model: str = "gemini-1.5-flash",
    ):
        """
        Initialize Twitter scraper with Gemini API.
        
        Args:
            gemini_api_key: Google Gemini API key
            coin_accounts: Mapping of coin symbols to Twitter usernames (without @)
            requests_per_coin_per_day: Maximum scraping requests per coin per day
            cache_ttl_hours: Cache TTL in hours
            cache_path: Path to cache file
            max_results: Maximum number of tweets to fetch per request
            gemini_model: Gemini model to use (default: gemini-1.5-flash for free tier)
        """
        self.logger = get_logger("twitter_scraper")
        
        # Lazy import snscrape
        global sntwitter
        if sntwitter is None:
            try:
                import snscrape.modules.twitter as sntwitter
            except (ImportError, AttributeError) as e:
                raise ImportError(
                    f"snscrape is not installed or incompatible with your Python version. "
                    f"Error: {e}. "
                    f"Try: pip install snscrape or use Python 3.10 or earlier. "
                    f"Alternatively, snscrape may need to be installed from git: "
                    f"pip install git+https://github.com/JustAnotherArchivist/snscrape.git"
                ) from e
        
        # Lazy import google.generativeai
        global genai
        if genai is None:
            try:
                import google.generativeai as genai
            except ImportError as e:
                raise ImportError(
                    f"google-generativeai is not installed. Install it with: pip install google-generativeai. "
                    f"Error: {e}"
                ) from e
        
        self.gemini_api_key = gemini_api_key
        self.coin_accounts = coin_accounts
        self.requests_per_coin_per_day = requests_per_coin_per_day
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_results = max(10, min(max_results, 100))
        self.gemini_model = gemini_model

        # Initialize Gemini
        genai.configure(api_key=gemini_api_key)
        self.gemini_client = genai.GenerativeModel(gemini_model)

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
            self.logger.error(f"Error reading Twitter sentiment cache: {exc}")

    def _persist_cache(self) -> None:
        serializable = {coin: entry.to_dict() for coin, entry in self.cache.items()}
        try:
            tmp_path = self.cache_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(serializable, indent=2))
            tmp_path.replace(self.cache_path)
        except Exception as exc:
            self.logger.error(f"Unable to persist Twitter sentiment cache: {exc}")

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
        if coin not in self.coin_accounts:
            self.logger.warning(f"No Twitter account configured for coin '{coin}'")
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

        summary = self._analyze_with_gemini(raw_posts, coin)
        entry.fetched_at = _utcnow()
        entry.posts = raw_posts
        entry.summary = summary
        entry.score = summary.get("score", 0.0)
        self._register_call(entry)
        self._persist_cache()

        return self._to_payload(coin, entry)

    # ------------------------------------------------------------------ #
    def _fetch_posts(self, coin: str) -> Optional[List[Dict[str, Any]]]:
        """Fetch tweets from the configured Twitter account for the coin."""
        username = self.coin_accounts[coin]
        # Remove @ if present
        username = username.lstrip("@")
        
        posts = []
        
        try:
            start = time.perf_counter()
            
            # Try using snscrape first (if available and compatible)
            if sntwitter is not None:
                try:
                    query = f"from:{username}"
                    scraper = sntwitter.TwitterSearchScraper(query)
                    
                    for i, tweet in enumerate(scraper.get_items()):
                        if i >= self.max_results:
                            break
                        
                        # Convert tweet to dict format compatible with existing structure
                        post = {
                            "id": str(tweet.id),
                            "text": tweet.rawContent or tweet.content or "",
                            "created_at": tweet.date.isoformat() if tweet.date else None,
                            "lang": tweet.lang or "en",
                            "public_metrics": {
                                "like_count": tweet.likeCount or 0,
                                "retweet_count": tweet.retweetCount or 0,
                                "reply_count": tweet.replyCount or 0,
                                "quote_count": tweet.quoteCount or 0,
                            },
                            "author": {
                                "username": tweet.user.username if tweet.user else username,
                                "name": tweet.user.displayname if tweet.user and tweet.user.displayname else username,
                            },
                        }
                        posts.append(post)
                except (AttributeError, TypeError) as e:
                    # snscrape compatibility issue, fall back to alternative
                    self.logger.warning(f"snscrape compatibility issue: {e}. Using alternative method.")
                    posts = self._fetch_posts_alternative(username)
            else:
                # Use alternative method
                posts = self._fetch_posts_alternative(username)
            
            duration_ms = (time.perf_counter() - start) * 1000
            self.logger.debug(
                "Fetched %s posts for %s (@%s) in %.0fms",
                len(posts),
                coin,
                username,
                duration_ms,
            )
            return posts if posts else None
        except Exception as exc:
            self.logger.error(f"Error scraping Twitter data for {coin} (@{username}): {exc}")
            return None
    
    def _fetch_posts_alternative(self, username: str) -> List[Dict[str, Any]]:
        """Alternative method to fetch tweets using requests and Twitter's public endpoints."""
        import requests
        from datetime import datetime, timezone
        
        posts = []
        
        try:
            # Use Twitter's public search endpoint (no auth required for public tweets)
            # Note: This is a simplified approach - Twitter may rate limit or block
            url = f"https://twitter.com/i/api/graphql/searchTimeline"
            
            # For now, return empty list and log a message
            # In production, you might want to use a different approach like:
            # 1. Using Twitter API v2 (requires API key but has free tier)
            # 2. Using a headless browser (Playwright/Selenium)
            # 3. Using a third-party service
            
            self.logger.warning(
                f"snscrape not available. Twitter scraping requires either: "
                f"1) Install snscrape from git: pip install git+https://github.com/JustAnotherArchivist/snscrape.git "
                f"2) Use Python 3.10 or earlier "
                f"3) Use Twitter API v2 (requires API key)"
            )
            
            # Return empty list - sentiment analysis will use cached data or return neutral
            return []
            
        except Exception as exc:
            self.logger.error(f"Error in alternative fetch method: {exc}")
            return []

    def _analyze_with_gemini(self, posts: List[Dict[str, Any]], coin: str) -> Dict[str, Any]:
        """Analyze tweets using Gemini API to determine sentiment and trend potential."""
        if not posts:
            return {
                "score": 0.0,
                "volume": 0,
                "sample_posts": [],
                "tags": [],
                "status": "no_posts",
            }

        # Prepare tweet texts for analysis
        tweet_texts = []
        total_likes = 0
        total_retweets = 0
        
        for post in posts:
            text = post.get("text", "")
            if text:
                tweet_texts.append(text)
            metrics = post.get("public_metrics", {})
            total_likes += metrics.get("like_count", 0)
            total_retweets += metrics.get("retweet_count", 0)

        if not tweet_texts:
            return {
                "score": 0.0,
                "volume": len(posts),
                "sample_posts": [],
                "tags": [],
                "status": "no_text",
            }

        # Combine tweets for analysis (limit to avoid token limits)
        combined_text = "\n\n".join(tweet_texts[:20])  # Limit to 20 tweets for analysis
        
        # Create prompt for Gemini
        prompt = f"""Analyze the sentiment and trend potential of these recent tweets about {coin} cryptocurrency:

{combined_text}

Based on these tweets, provide:
1. Overall sentiment score from -1.0 (very bearish/negative) to +1.0 (very bullish/positive)
2. Brief analysis of the trend potential (1-2 sentences)
3. Key themes or topics mentioned

Respond in this exact JSON format:
{{
    "score": <float between -1.0 and 1.0>,
    "analysis": "<brief analysis text>",
    "themes": ["<theme1>", "<theme2>", ...]
}}

Only return the JSON, no other text."""

        try:
            response = self.gemini_client.generate_content(prompt)
            response_text = response.text.strip()
            
            # Extract JSON from response (handle markdown code blocks if present)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(response_text)
            
            score = float(result.get("score", 0.0))
            score = max(-1.0, min(1.0, score))  # Clamp to [-1, 1]
            
            analysis = result.get("analysis", "")
            themes = result.get("themes", [])
            
            # Extract tags from tweets
            tags = self._extract_tags(tweet_texts[:5])
            
            return {
                "score": round(score, 3),
                "volume": len(posts),
                "engagement": {
                    "likes": total_likes,
                    "retweets": total_retweets,
                },
                "sample_posts": tweet_texts[:3],
                "tags": tags,
                "analysis": analysis,
                "themes": themes,
                "status": "analyzed",
            }
        except json.JSONDecodeError as exc:
            self.logger.error(f"Failed to parse Gemini response as JSON: {exc}")
            self.logger.debug(f"Gemini response: {response_text if 'response_text' in locals() else 'N/A'}")
            # Fallback: try to extract score from text
            return self._fallback_sentiment_analysis(posts, tweet_texts, total_likes, total_retweets)
        except Exception as exc:
            self.logger.error(f"Error analyzing tweets with Gemini for {coin}: {exc}")
            return self._fallback_sentiment_analysis(posts, tweet_texts, total_likes, total_retweets)

    def _fallback_sentiment_analysis(
        self, posts: List[Dict[str, Any]], tweet_texts: List[str], total_likes: int, total_retweets: int
    ) -> Dict[str, Any]:
        """Fallback sentiment analysis if Gemini fails."""
        return {
            "score": 0.0,
            "volume": len(posts),
            "engagement": {
                "likes": total_likes,
                "retweets": total_retweets,
            },
            "sample_posts": tweet_texts[:3],
            "tags": self._extract_tags(tweet_texts[:5]),
            "status": "fallback",
        }

    def _extract_tags(self, posts: List[str]) -> List[str]:
        """Extract hashtags and cashtags from tweets."""
        tags: set[str] = set()
        for text in posts:
            for token in text.split():
                token = token.strip()
                if token.startswith(("#", "$")) and len(token) > 1:
                    tags.add(token)
        return list(tags)

    def _to_payload(self, coin: str, entry: SentimentEntry) -> Dict[str, Any]:
        """Convert cache entry to API payload format."""
        return {
            "coin": coin,
            "fetched_at": entry.fetched_at.isoformat(),
            "score": entry.score,
            "summary": entry.summary,
            "posts": entry.posts,
            "source": "x",
            "remaining_calls_today": self._remaining_calls(entry),
        }


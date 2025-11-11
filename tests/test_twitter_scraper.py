"""Unit tests for TwitterScraper sentiment workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.api import twitter_scraper


class _DummyGenAI:
    """Minimal stub for google.generativeai module."""

    configured_with: str | None = None
    last_model_requested: str | None = None

    @staticmethod
    def configure(api_key: str) -> None:
        _DummyGenAI.configured_with = api_key

    class GenerativeModel:
        def __init__(self, model: str):
            _DummyGenAI.last_model_requested = model

        def generate_content(self, prompt: str) -> Any:  # pragma: no cover - not used in test
            raise AssertionError("generate_content should not be called in this test")


@pytest.fixture(autouse=True)
def stub_external_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure lazy imports are satisfied without real dependencies."""
    monkeypatch.setattr(twitter_scraper, "sntwitter", object())
    monkeypatch.setattr(twitter_scraper, "genai", _DummyGenAI)


def test_get_sentiment_fetches_and_caches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_posts: List[Dict[str, Any]] = [
        {
            "id": "1",
            "text": "Dogecoin to the moon! 🚀",
            "created_at": "2024-01-01T00:00:00Z",
            "public_metrics": {"like_count": 42, "retweet_count": 7},
            "author": {"username": "dogecoin", "name": "Dogecoin"},
        }
    ]
    fake_summary: Dict[str, Any] = {
        "score": 0.75,
        "volume": len(fake_posts),
        "analysis": "Strong community excitement.",
        "status": "analyzed",
    }
    fetch_calls: List[str] = []

    def fake_fetch_posts(self, coin: str) -> List[Dict[str, Any]]:
        fetch_calls.append(coin)
        return fake_posts

    def fake_analyze(self, posts: List[Dict[str, Any]], coin: str) -> Dict[str, Any]:
        assert posts == fake_posts
        assert coin == "DOGE"
        return fake_summary

    monkeypatch.setattr(twitter_scraper.TwitterScraper, "_fetch_posts", fake_fetch_posts)
    monkeypatch.setattr(twitter_scraper.TwitterScraper, "_analyze_with_gemini", fake_analyze)

    scraper = twitter_scraper.TwitterScraper(
        gemini_api_key="test-key",
        coin_accounts={"DOGE": "dogecoin"},
        cache_path=str(tmp_path / "cache.json"),
        requests_per_coin_per_day=3,
        cache_ttl_hours=24,
    )

    # Force a fresh fetch
    payload = scraper.get_sentiment("DOGE", force_refresh=True)

    assert payload["coin"] == "DOGE"
    assert payload["summary"] == fake_summary
    assert payload["posts"] == fake_posts
    assert payload["score"] == fake_summary["score"]
    assert payload["source"] == "x"
    assert payload["remaining_calls_today"] == 2  # 3 allowed, 1 used
    assert fetch_calls == ["DOGE"]

    # Subsequent call should use cache (no extra fetch)
    payload_cached = scraper.get_sentiment("DOGE")
    assert payload_cached["summary"] == fake_summary
    assert payload_cached["remaining_calls_today"] == 2
    assert fetch_calls == ["DOGE"]  # still single fetch

    # Ensure Gemini stub was configured
    assert _DummyGenAI.configured_with == "test-key"
    assert _DummyGenAI.last_model_requested == "gemini-1.5-flash"

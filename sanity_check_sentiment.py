"""Quick script to inspect cached sentiment data from the Twitter scraper."""

import argparse
import os
from typing import Iterable

from src.api.twitter_scraper import TwitterScraper
from src.utils.config import load_config


def _format_sentiment(coin: str, payload: dict) -> str:
    score = payload.get("score")
    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    volume = summary.get("volume")
    fetched_at = payload.get("fetched_at")
    remaining = payload.get("remaining_calls_today")
    sample_posts = summary.get("sample_posts") or []

    lines = [
        f"{coin}: score={score}, volume={volume}, fetched_at={fetched_at}, remaining_calls={remaining}",
    ]
    for idx, post in enumerate(sample_posts[:2], start=1):
        if isinstance(post, str):
            lines.append(f"  {idx}. {post}")
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect meme coin sentiment fetched from Twitter.")
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to configuration file.",
    )
    parser.add_argument(
        "--coins",
        type=str,
        nargs="*",
        help="Subset of coins to fetch (default: all configured coins).",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore cache TTL and attempt a fresh API call (counts against quota).",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)

    config = load_config(args.config)
    social_cfg = config.get("social", {}).get("x", {})
    if not social_cfg.get("enabled", False):
        print("Twitter sentiment integration is disabled in config.")
        return 0

    gemini_key = _resolve_gemini_key(social_cfg)
    if not gemini_key:
        print("Missing Gemini API key (social.x.gemini_api_key or environment GEMINI_API_KEY).")
        return 1

    coin_accounts = social_cfg.get("coin_accounts", {})
    if not coin_accounts:
        print("No Twitter accounts configured under social.x.coin_accounts.")
        return 1

    coins = args.coins or list(coin_accounts.keys())
    invalid = [coin for coin in coins if coin not in coin_accounts]
    if invalid:
        print(f"Unknown coin(s): {', '.join(invalid)}")
        return 1

    try:
        scraper = TwitterScraper(
            gemini_api_key=gemini_key,
            coin_accounts=coin_accounts,
            requests_per_coin_per_day=social_cfg.get("requests_per_coin_per_day", 2),
            cache_ttl_hours=social_cfg.get("cache_ttl_hours", 12),
            cache_path=social_cfg.get("cache_path", "data/social_cache.json"),
            max_results=social_cfg.get("max_results", 25),
            gemini_model=social_cfg.get("gemini_model", "gemini-1.5-flash"),
        )
    except ImportError as exc:
        print(f"Twitter scraper dependency error: {exc}")
        return 1
    except Exception as exc:
        print(f"Failed to initialize TwitterScraper: {exc}")
        return 1

    for coin in coins:
        payload = scraper.get_sentiment(coin, force_refresh=args.force_refresh)
        if not payload:
            print(f"{coin}: sentiment unavailable.")
            continue
        print(_format_sentiment(coin, payload))
        print("-" * 60)

    return 0


def _resolve_gemini_key(social_cfg: dict) -> str:
    key = social_cfg.get("gemini_api_key") or ""
    if isinstance(key, str) and key.startswith("${") and key.endswith("}"):
        env_var = key.strip("${}")
        key = os.getenv(env_var, "")
    if not key:
        key = os.getenv("GEMINI_API_KEY", "")
    return key


if __name__ == "__main__":
    raise SystemExit(main())


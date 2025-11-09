"""Quick script to inspect cached sentiment data from X."""

import argparse
import sys
from typing import Iterable

from src.api.x_client import XClient
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
    parser = argparse.ArgumentParser(description="Inspect meme coin sentiment fetched from X.")
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
        print("X sentiment integration is disabled in config.")
        return 0

    bearer_token = social_cfg.get("bearer_token")
    if not bearer_token:
        print("Missing X bearer token (social.x.bearer_token).")
        return 1

    coin_queries = social_cfg.get("coin_queries", {})
    if not coin_queries:
        print("No coin queries configured under social.x.coin_queries.")
        return 1

    coins = args.coins or list(coin_queries.keys())
    invalid = [coin for coin in coins if coin not in coin_queries]
    if invalid:
        print(f"Unknown coin(s): {', '.join(invalid)}")
        return 1

    client = XClient(
        bearer_token=bearer_token,
        coin_queries=coin_queries,
        requests_per_coin_per_day=social_cfg.get("requests_per_coin_per_day", 2),
        cache_ttl_hours=social_cfg.get("cache_ttl_hours", 12),
        cache_path=social_cfg.get("cache_path", "data/social_cache.json"),
        max_results=social_cfg.get("max_results", 25),
    )

    for coin in coins:
        payload = client.get_sentiment(coin, force_refresh=args.force_refresh)
        if not payload:
            print(f"{coin}: sentiment unavailable.")
            continue
        print(_format_sentiment(coin, payload))
        print("-" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


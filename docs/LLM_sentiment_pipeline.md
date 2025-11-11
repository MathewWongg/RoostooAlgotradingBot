## LLM Sentiment + X Scraping Extraction

### Overview
- `src/api/twitter_scraper.py` owns X (Twitter) collection plus Gemini-powered sentiment scoring.
- `src/strategies/llm_strategy.py` consumes market + sentiment data to produce trading signals through Google Gemini.
- `src/data/data_collector.py` wires both pieces by inserting the X payload under `market_data['social']['x']`.

### Key Components
- **TwitterScraper** (`src/api/twitter_scraper.py`)
  - Lazily imports `snscrape` (primary) or logs a warning and returns no posts when unavailable.
  - Wraps Gemini (`google.generativeai`) to transform raw tweets into `score`, `analysis`, `themes`, `sample_posts`, and engagement stats.
  - Caches sentiment per coin (`SentimentEntry`) with TTL, rate limiting, and persistence to `data/social_cache.json`.
  - Public surface: `get_sentiment(coin, force_refresh=False)` → payload with `score`, `summary`, `posts`, `remaining_calls_today`.
- **LLMStrategy** (`src/strategies/llm_strategy.py`)
  - Initializes Google `genai.Client` (from `google-genai`) using `config['api_key']` or `GEMINI_API_KEY` env.
  - Builds prompt combining Roostoo price/change data, simple price-trend heuristic, and X sentiment context.
  - Calls Gemini (`client.models.generate_content`) expecting `ACTION:CONFIDENCE`; parses fallback heuristics.
  - Caches responses keyed by pair/price/sentiment timestamp when `cache_responses` enabled.

### Minimal Usage Example
```python
from src.api.twitter_scraper import TwitterScraper
from src.strategies.llm_strategy import LLMStrategy

scraper = TwitterScraper(
    gemini_api_key="YOUR_GEMINI_KEY",
    coin_accounts={"DOGE": "dogecoin"}
)

sentiment = scraper.get_sentiment("DOGE")

llm = LLMStrategy({
    "provider": "gemini",
    "model": "gemini-2.5-flash",
    "enabled": True,
    "api_key": "YOUR_GEMINI_KEY",
})

market_data = {
    "pair": "DOGE/USD",
    "roostoo": {"LastPrice": 0.12, "Change": 0.015},
    "social": {"x": sentiment},
}

llm.update_state(market_data)
signal = llm.generate_signal(market_data)
print(signal.action, signal.confidence, signal.metadata["llm_response"])
```

### Verification
- Install deps: `pip3 install -r requirements.txt`.
- Run unit test (stubs out external services): `python3 -m pytest tests/test_twitter_scraper.py`.
- Optional manual check: `python3 test_llm_gemini.py` (requires real Gemini key and network access).

### Configuration Checklist
- `config/config.yaml`
  - `social.x.enabled: true`
  - `social.x.gemini_api_key` or `GEMINI_API_KEY` env var set.
  - `social.x.coin_accounts` map coins → usernames.
  - `strategies.llm.enabled: true` with matching `api_key`.
- `.env` (or environment) must provide real API keys; placeholders like `${GEMINI_API_KEY}` auto-resolve to env at runtime.

### Known Limitations & Risks
- `snscrape` can break on Python 3.11+; fallback method currently returns an empty list, so sentiment degrades to neutral unless snscrape works.
- Gemini response parsing assumes a single `ACTION:CONFIDENCE` format; additional colons or verbose text may reduce confidence extraction accuracy.
- No explicit retry/backoff on Gemini failures; `_analyze_with_gemini` falls back to neutral score.
- `LLMStrategy` does not enforce `max_tokens` when calling `models.generate_content`; adjust prompt or upgrade call parameters if responses get truncated.
- Large dependency footprint (both `google-genai` and `google-generativeai`)—ensure these are installed wherever coworkers run the extraction.

### Hand-off Notes
- Share this document plus the two Python modules with coworkers; they can run solely `TwitterScraper` + `LLMStrategy` to replicate sentiment-driven signals.
- Encourage team to add real API keys into a `.env` file and preload cache directory (`data/`).
- For environments without X access, plan alternative sources or implement the placeholder in `_fetch_posts_alternative`.

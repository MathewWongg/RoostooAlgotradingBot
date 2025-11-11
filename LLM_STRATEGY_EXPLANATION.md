# LLM Strategy with Gemini Sentiment - Technical Details

## Overview

The LLM strategy is a sophisticated component of the ensemble trading bot that uses large language models to analyze market conditions and provide trading signals. It integrates with Google Gemini API for Twitter sentiment analysis to enhance decision-making.

## How the LLM Strategy Works

### 1. Triggering Mechanism

The LLM is **not called on every signal**. Instead, it's intelligently triggered when:

**Condition A: Signal Divergence**
- Technical strategy and baseline strategy disagree
- Both strategies return non-HOLD signals (BUY vs SELL or vice versa)
- This indicates uncertainty that the LLM can help resolve

**Condition B: High Confidence**
- Technical strategy has high confidence (>= `trigger_confidence` threshold, default 0.7)
- This indicates a strong signal that the LLM can validate or refine

**Configuration:**
```yaml
strategies:
  llm:
    trigger_confidence: 0.7       # Minimum technical confidence to trigger
    require_divergence: true      # Require divergence OR high confidence
    max_calls_per_day: 2          # Rate limiting per coin per day
    max_calls_per_backtest: 10    # Rate limiting for backtests
```

### 2. Data Collection and Analysis

When triggered, the LLM receives:

**Market Data:**
- Current price
- 24-hour price change percentage
- Price trend classification (uptrend/downtrend/sideways)
- Recent price history (for context)

**Twitter Sentiment (if enabled):**
- Recent tweets from configured accounts (e.g., @dogecoin, @ethereum)
- Sentiment score from Gemini analysis (-1.0 to +1.0)
- Key themes and topics identified
- Engagement metrics (likes, retweets)

**Example Prompt to LLM:**
```
Analyze this crypto market data and provide a trading signal:

Pair: TRUMP/USD
Current Price: $100.00
24h Change: 5.00%
Price Trend: uptrend

Social Sentiment (X):
- Score: +0.70 (scale -1 bearish to +1 bullish)
- Recent Volume: 50 posts
- Top Tags: #TRUMP, $TRUMP
- Sample Posts:
  • Bullish on TRUMP! 🚀
  • Moon incoming

Based on this data, should I BUY, SELL, or HOLD? 
Provide your answer as: ACTION:CONFIDENCE
Where ACTION is BUY, SELL, or HOLD, and CONFIDENCE is a number between 0.0 and 1.0.
```

### 3. Response Processing

The LLM returns a response in the format: `ACTION:CONFIDENCE`

**Example responses:**
- `BUY:0.75` - Strong buy signal with 75% confidence
- `SELL:0.60` - Moderate sell signal with 60% confidence
- `HOLD:0.50` - Neutral position with 50% confidence

The system:
1. Parses the response to extract action and confidence
2. Validates the action is BUY, SELL, or HOLD
3. Clamps confidence to 0.0-1.0 range
4. Caches the response (if enabled) to avoid redundant API calls

### 4. Ensemble Integration

The LLM signal is combined with other strategies using weighted voting:

```yaml
strategies:
  ensemble:
    technical_weight: 0.31
    llm_weight: 0.23
    baseline_weight: 0.23
    oversold_weight: 0.23
```

**Weighted Voting Process:**
1. Each strategy generates a signal (BUY/SELL/HOLD) with confidence
2. Signals are weighted by their assigned weights
3. Scores are calculated: `buy_score`, `sell_score`, `hold_score`
4. Final action is determined by highest score
5. Final confidence is normalized from the winning score

**Example:**
- Technical: BUY (0.8 confidence) × 0.31 weight = 0.248
- LLM: BUY (0.75 confidence) × 0.23 weight = 0.173
- Baseline: HOLD (0.5 confidence) × 0.23 weight = 0.115
- **Result**: BUY with high confidence (0.536 total)

### 5. Capital Multiplier System

When the LLM participates, it can increase position sizing:

```yaml
capital_multipliers:
  default: 1.0
  per_signal_bonus: 0.15      # +15% per aligned BUY signal
  divergence: 0.2             # +20% when triggered by divergence
  confidence: 0.25            # +25% when triggered by high confidence
  llm_confirmed: 0.3          # +30% when LLM confirms with high confidence
```

**Example:**
- Base multiplier: 1.0
- 3 aligned BUY signals: +0.30 (2 × 0.15)
- Triggered by divergence: +0.20
- LLM confirms with 0.7+ confidence: +0.30
- **Total multiplier**: 1.8x (80% larger position)

## Gemini Sentiment Analysis

### Twitter Scraping

1. **Account-Based Scraping**: Fetches tweets from specific accounts:
   - TRUMP → @realDonaldTrump
   - DOGE → @dogecoin
   - ETH → @ethereum
   - SOL → @solana

2. **Free Web Scraping**: Uses `snscrape` library (no API key required)
   - Fetches up to 25 recent tweets per account
   - No rate limits (unlike Twitter API)
   - May have compatibility issues with Python 3.11+

3. **Caching**: Results are cached for 12 hours to minimize scraping

### Gemini Analysis

1. **Sentiment Analysis**: Gemini analyzes tweet collection:
   - Overall sentiment score (-1.0 to +1.0)
   - Trend potential assessment
   - Key themes and topics
   - Brief analysis text

2. **Free Tier Limits**:
   - 60 requests per minute
   - 1,500 requests per day
   - Model: `gemini-1.5-flash` (fast, free)

3. **Integration**: Sentiment data is included in LLM prompt when available

## Performance Tracking

The backtest tracks LLM performance separately:

**Metrics Tracked:**
- Number of trades where LLM participated
- Total PnL contribution (allocated by weight)
- Win rate for LLM-influenced trades
- Average PnL per trade

**Example Output:**
```
STRATEGY PERFORMANCE BREAKDOWN
======================================================================

LLM:
  Trades: 45
  Total PnL: $1,234.56
  Avg PnL per Trade: $27.43
  Win Rate: 68.89%
  Wins: 31, Losses: 14
```

## Configuration Examples

### Maximum LLM Participation (Testing)
```yaml
strategies:
  llm:
    trigger_confidence: 0.3       # Low threshold - triggers often
    require_divergence: false     # Don't require divergence
    max_calls_per_backtest: 100   # Allow many calls
    enable_in_backtest: true
```

### Conservative LLM Usage (Production)
```yaml
strategies:
  llm:
    trigger_confidence: 0.8       # High threshold - only strong signals
    require_divergence: true      # Only when strategies disagree
    max_calls_per_day: 2          # Strict rate limiting
    enable_in_backtest: false     # Disable in backtests to save costs
```

### Gemini Sentiment Enabled
```yaml
social:
  x:
    enabled: true
    gemini_api_key: ${GEMINI_API_KEY}
    gemini_model: "gemini-1.5-flash"
    enable_in_backtest: true
    coin_accounts:
      TRUMP: "realDonaldTrump"
      DOGE: "dogecoin"
```

## Testing

Run the test script to verify LLM strategy is working:

```bash
python test_llm_gemini.py
```

This will:
- Check LLM configuration
- Verify API keys
- Test signal generation
- Show component signal breakdown

## Best Practices

1. **Start Conservative**: Use high `trigger_confidence` and `require_divergence: true` initially
2. **Monitor Costs**: Track API usage, especially for paid providers
3. **Test Thoroughly**: Run backtests with different LLM settings
4. **Review Responses**: Check LLM responses in logs to understand reasoning
5. **Adjust Weights**: Based on backtest performance, adjust `llm_weight` in ensemble
6. **Cache Aggressively**: Enable `cache_responses: true` to minimize API calls

## Troubleshooting

**LLM Not Triggering:**
- Lower `trigger_confidence` threshold
- Set `require_divergence: false`
- Check that other strategies are generating signals

**LLM Always Returns HOLD:**
- Check LLM provider is working (test with `test_llm_gemini.py`)
- Review LLM responses in logs
- Verify market data is being passed correctly

**High API Costs:**
- Enable `cache_responses: true`
- Reduce `max_calls_per_day`
- Use free tier providers (Gemini, OpenRouter free models)
- Consider local Ollama for zero API costs

**Gemini Sentiment Not Working:**
- Verify `GEMINI_API_KEY` is set
- Check Twitter account names are correct
- Review scraping logs for errors
- Bot will use cached sentiment if scraping fails


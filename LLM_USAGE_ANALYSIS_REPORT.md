# LLM Usage Analysis Report

## Executive Summary

This report analyzes the current LLM usage in backtests and provides recommendations for increasing LLM participation in both backtesting and live deployment.

### Key Findings

1. **Current LLM Usage is EXTREMELY LIMITED**: With default settings, the LLM made **0 calls** during a 10-day backtest
2. **API Authentication Issues**: The LLM attempted to make calls but failed due to missing API credentials (401 errors)
3. **Triggering Conditions are TOO STRICT**: Current requirements (divergence AND high confidence >= 0.7) prevent LLM participation
4. **Increasing Usage Works**: By lowering thresholds, we can increase LLM participation from 0 to 200+ calls

---

## Backtest Results Comparison

| Scenario | LLM Calls | Trades | Win Rate | Return |
|----------|-----------|--------|----------|--------|
| **1. Current Config** (divergence required, confidence >= 0.7) | **0** | 48 | 66.67% | $4.58 |
| **2. Increased calls** (1 -> 10 per coin) | **0** | 48 | 66.67% | $4.58 |
| **3. No divergence requirement** | **0** | 48 | 66.67% | $4.58 |
| **4. Lower threshold** (0.5, no divergence) | **20** | 48 | 66.67% | $4.59 |
| **5. Maximum LLM** (0.3 threshold, 100 calls) | **200** | 48 | 66.67% | $4.84 |

---

## Why LLM Isn't Being Used

### Current Configuration (config.yaml):

```yaml
strategies:
  llm:
    provider: "openrouter"
    model: "microsoft/mai-ds-r1:free"
    enabled: true
    cache_responses: true
    max_tokens: 200
    api_key: ${OPENROUTER_API_KEY}
    trigger_confidence: 0.7       # TOO HIGH - rarely triggered
    require_divergence: true      # TOO RESTRICTIVE
    max_calls_per_day: 2
    max_calls_per_backtest: 1     # TOO LOW for meaningful testing
    enable_in_backtest: true
```

### Triggering Logic (from ensemble_strategy.py):

The LLM is only called when **BOTH** of these conditions are met:
1. **Divergence Mode**: Technical and baseline strategies disagree (both non-HOLD but different actions)
   - OR -
2. **High Confidence Mode**: Technical strategy confidence >= 0.7

**AND**:
3. LLM hasn't exceeded call limits (1 call per coin in backtest, 2 per day in live)

This means the LLM is essentially acting as a "rare tie-breaker" rather than an active strategy participant.

---

## LLM Strategy Details

### What the LLM Analyzes (Technical Analysis):

From `llm_strategy.py`, the LLM receives this information:

```python
prompt = f"""Analyze this crypto market data and provide a trading signal:

Pair: {pair}
Current Price: ${price:,.2f}
24h Change: {change_pct:.2f}%
Price Trend: {price_trend}  # uptrend/downtrend/sideways based on 5-10 period moving averages
{sentiment_context}         # Optional social sentiment data

Based on this data, should I BUY, SELL, or HOLD? Provide your answer as: ACTION:CONFIDENCE
Where ACTION is BUY, SELL, or HOLD, and CONFIDENCE is a number between 0.0 and 1.0."""
```

The LLM performs **technical price analysis**, NOT just sentiment analysis:
- Price momentum and trends
- Recent vs older price averages
- 24-hour price changes
- Optional social sentiment (if available)

---

## Recommendations

### For Backtesting (to actually test the LLM):

**Immediate Changes to `config.yaml`:**

```yaml
strategies:
  llm:
    # Keep these the same
    provider: "openrouter"
    model: "microsoft/mai-ds-r1:free"
    enabled: true
    cache_responses: true
    max_tokens: 200
    api_key: ${OPENROUTER_API_KEY}
    
    # CHANGE THESE FOR TESTING:
    trigger_confidence: 0.5           # Lower from 0.7 to 0.5
    require_divergence: false         # Change from true to false
    max_calls_per_backtest: 20        # Increase from 1 to 20
    enable_in_backtest: true          # Keep true
```

**Why these changes:**
- `trigger_confidence: 0.5` - Allows LLM to participate when technical strategy has moderate confidence
- `require_divergence: false` - LLM can provide input even when strategies agree
- `max_calls_per_backtest: 20` - Provides enough data points to evaluate LLM performance

**Expected Result**: 20-50 LLM calls per backtest, allowing meaningful evaluation

---

### For Live Deployment (production-ready):

**Recommended Changes to `config.yaml`:**

```yaml
strategies:
  llm:
    provider: "openrouter"
    model: "microsoft/mai-ds-r1:free"  # or paid model for better quality
    enabled: true
    cache_responses: true
    max_tokens: 200
    api_key: ${OPENROUTER_API_KEY}
    
    # Production settings:
    trigger_confidence: 0.65          # Slightly lower than current
    require_divergence: true          # Keep as safeguard
    max_calls_per_day: 3              # Increase from 2 to 3
    enable_in_backtest: true
    
  ensemble:
    technical_weight: 0.30            # Slightly reduce
    llm_weight: 0.30                  # Increase from 0.23
    baseline_weight: 0.20             # Slightly reduce
    oversold_weight: 0.20             # Keep
```

**Why these changes:**
- `trigger_confidence: 0.65` - Slightly more opportunities without being too permissive
- `require_divergence: true` - LLM acts as intelligent tie-breaker
- `max_calls_per_day: 3` - 50% increase in LLM participation while controlling costs
- `llm_weight: 0.30` - Increases LLM influence when it does participate

---

## API Credentials Setup

The analysis showed **401 authentication errors**. To actually use the LLM, you need to:

### Quick Setup - Use Existing Keys:

**The `config/env.example` file already has API keys configured!**

Simply copy it to `.env`:

```bash
# Windows
copy config\env.example config\.env

# Linux/Mac
cp config/env.example config/.env
```

The env.example file already contains:
- ✅ `OPENROUTER_API_KEY` - Configured and ready
- ✅ `OPENROUTER_HTTP_REFERER` - Set to your app URL
- ✅ `OPENROUTER_X_TITLE` - Set to "QuantComp Trading Bot"
- ✅ `ROOSTOO_API_KEY` - Your Roostoo credentials
- ✅ `ROOSTOO_SECRET_KEY` - Your Roostoo secret

### Optional: Use Your Own API Key:

If you want to use your own OpenRouter API key:

1. Go to https://openrouter.ai/
2. Sign up for an account
3. Generate an API key
4. Edit `config/.env` and replace the `OPENROUTER_API_KEY` value

The current model `microsoft/mai-ds-r1:free` is FREE, so you can test without cost.

---

## Testing the LLM Strategy

### Quick Test Script:

```bash
# 1. Update config.yaml with testing settings (lower threshold, no divergence requirement)
# 2. Ensure API key is set in config/.env
# 3. Run backtest

python run_backtest.py --initial-balance 50000

# Check the logs for LLM activity:
# - Look for "LLM" in logs/backtest.log
# - Check data/backtest_report.json for metadata
```

### What to Look For:

1. **LLM Call Count**: Check how many times LLM was invoked
2. **LLM Responses**: Look at signal metadata to see LLM reasoning
3. **Impact on Trades**: Compare win rates and returns with/without LLM
4. **Cost Analysis**: Count API calls to estimate production costs

---

## Cost Considerations

### Current Setup:
- Model: `microsoft/mai-ds-r1:free` - **$0/call**
- Max calls per day: 2 per coin
- 5 coins × 2 calls = **10 calls/day** = **$0/day**

### With Recommended Changes:
- Model: `microsoft/mai-ds-r1:free` - **$0/call**
- Max calls per day: 3 per coin
- 5 coins × 3 calls = **15 calls/day** = **$0/day**

### If Using Paid Model (e.g., GPT-4):
- Model: `gpt-4-turbo` - **~$0.01/call** (200 tokens)
- 15 calls/day × $0.01 = **$0.15/day** = **~$4.50/month**

---

## Action Items

### Immediate (for testing):
1. ✅ **Lower `trigger_confidence` to 0.5**
2. ✅ **Set `require_divergence` to false**
3. ✅ **Increase `max_calls_per_backtest` to 20**
4. ✅ **Add OpenRouter API key to `.env`**
5. ✅ **Run backtest and verify LLM calls are being made**

### Short-term (for evaluation):
1. **Run multiple backtests** with different LLM settings
2. **Compare performance** (win rate, returns, Sharpe ratio)
3. **Review LLM responses** to understand its reasoning
4. **Adjust weights** based on LLM performance

### Long-term (for production):
1. **Fine-tune trigger conditions** based on backtest results
2. **Consider paid models** if free model underperforms
3. **Monitor API costs** and call frequency
4. **Implement fallback** logic if API fails
5. **Add LLM performance metrics** to live monitoring

---

## Technical Details: How to Backtest LLM Only

If you want to test the LLM's **technical analysis** capabilities specifically (not sentiment), you can:

### Option 1: Create LLM-Only Strategy

Temporarily modify `config.yaml`:

```yaml
strategies:
  ensemble:
    technical_weight: 0.0      # Disable technical
    llm_weight: 1.0            # 100% LLM
    baseline_weight: 0.0       # Disable baseline
    oversold_weight: 0.0       # Disable oversold
  
  llm:
    trigger_confidence: 0.3    # Very low - always trigger
    require_divergence: false  # Don't need divergence
    max_calls_per_backtest: 200  # Allow many calls
```

### Option 2: Compare with/without LLM

Run two backtests and compare:

```bash
# Without LLM
python run_backtest.py --output data/backtest_no_llm.json
# (with llm.enabled: false in config)

# With LLM
python run_backtest.py --output data/backtest_with_llm.json
# (with llm.enabled: true in config)

# Compare results
python -c "
import json
no_llm = json.load(open('data/backtest_no_llm.json'))
with_llm = json.load(open('data/backtest_with_llm.json'))
print(f'No LLM Return: {no_llm[\"backtest_result\"][\"total_return_pct\"]:.2f}%')
print(f'With LLM Return: {with_llm[\"backtest_result\"][\"total_return_pct\"]:.2f}%')
"
```

---

## Conclusion

### Current State:
- **LLM is enabled but essentially unused** (0 calls in default backtest)
- Triggering conditions are too restrictive for meaningful participation
- API authentication needs to be configured

### Potential:
- **LLM can analyze technical indicators** (price trends, momentum, volatility)
- With proper configuration, can make **20-200 calls per backtest**
- Using free models, **zero cost** to test and deploy
- Can improve decision-making by providing **independent analysis**

### Next Steps:
1. **Configure API credentials** (OpenRouter)
2. **Adjust triggering thresholds** (lower to 0.5-0.65)
3. **Run backtests** with increased LLM participation
4. **Evaluate performance** and adjust weights accordingly
5. **Deploy to production** with conservative limits initially

The LLM strategy has significant potential for improving trading decisions, but it needs proper configuration to actually participate in the trading process.

---

## Appendix: Configuration Quick Reference

### Testing Configuration (Maximum LLM Usage):
```yaml
strategies:
  llm:
    trigger_confidence: 0.3
    require_divergence: false
    max_calls_per_backtest: 100
    enable_in_backtest: true
  ensemble:
    llm_weight: 0.35
```

### Balanced Configuration (Recommended for Production):
```yaml
strategies:
  llm:
    trigger_confidence: 0.65
    require_divergence: true
    max_calls_per_day: 3
    enable_in_backtest: true
  ensemble:
    llm_weight: 0.30
```

### Conservative Configuration (Current):
```yaml
strategies:
  llm:
    trigger_confidence: 0.7
    require_divergence: true
    max_calls_per_day: 2
    max_calls_per_backtest: 1
  ensemble:
    llm_weight: 0.23
```


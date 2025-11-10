# LLM API Backtest Testing Guide

This guide explains how to test the LLM API integration in backtest mode using simulated market conditions.

## Overview

The `test_llm_backtest.py` script simulates various market scenarios to trigger LLM API calls and verify:
- LLM is called when expected (divergence, high confidence)
- LLM responses are received correctly
- Rate limiting works properly
- X sentiment data is included in LLM analysis

## Prerequisites

1. **LLM API Key**: Ensure your LLM API key is configured in environment variables:
   ```bash
   # For OpenRouter
   export OPENROUTER_API_KEY="your-key-here"
   
   # Or for OpenAI
   export OPENAI_API_KEY="your-key-here"
   ```

2. **Configuration**: The script uses `config/config.yaml` but overrides LLM settings for testing.

## Running the Tests

```bash
python test_llm_backtest.py
```

## Test Scenarios

### Scenario 1: Signal Divergence
- **Purpose**: Test LLM trigger when technical and baseline strategies disagree
- **Setup**: 
  - `require_divergence: true`
  - Simulates price dropping to create conflicting signals
- **Expected**: LLM called when divergence detected

### Scenario 2: High Confidence Trigger
- **Purpose**: Test LLM trigger when technical strategy has high confidence
- **Setup**:
  - `require_divergence: false`
  - `trigger_confidence: 0.6`
  - Simulates strong uptrend
- **Expected**: LLM called when confidence threshold met

### Scenario 3: X Sentiment Integration
- **Purpose**: Test LLM with simulated X/Twitter sentiment data
- **Setup**:
  - Injects bullish sentiment (score: 0.75)
  - Includes sample posts and tags
- **Expected**: LLM receives sentiment data in prompt

### Scenario 4: Rate Limiting
- **Purpose**: Verify rate limiting works correctly
- **Setup**:
  - `max_calls_per_backtest: 3`
  - Generates 20 signals
- **Expected**: Only 3 LLM calls made (not 20)

## Understanding the Output

The script prints:
- **Step-by-step progress**: Shows each market data point processed
- **Signal information**: Action and confidence for each step
- **Component signals**: Breakdown of technical, baseline, and LLM signals
- **LLM trigger status**: When and why LLM was called
- **LLM responses**: Action and confidence from LLM
- **Call statistics**: Total calls made and calls per pair

### Example Output

```
Step 1: Price=$100.00
  Signal: BUY (confidence: 0.65)
  Component signals:
    technical: BUY (conf: 0.70)
    baseline: SELL (conf: 0.60)
  ✅ LLM Triggered: divergence
  LLM Response: BUY (conf: 0.75)

📊 Total LLM calls made: 1
   Calls by pair: {'TRUMP/USD': 1}
```

## Troubleshooting

### LLM Not Being Called

1. **Check configuration**:
   - `enabled: true`
   - `enable_in_backtest: true`
   - `max_calls_per_backtest` is high enough

2. **Check trigger conditions**:
   - For divergence: Technical and baseline must disagree (both non-HOLD)
   - For high confidence: Technical confidence must >= `trigger_confidence`

3. **Check API key**:
   - Verify environment variable is set
   - Test API key works with a simple curl request

### API Errors

If you see API errors:
- Check your API key is valid
- Verify you have credits/quota remaining
- Check network connectivity
- Review error messages for specific issues

### Rate Limiting Issues

If rate limiting isn't working:
- Check `max_calls_per_backtest` setting
- Verify the counter is being incremented
- Check if calls are being made outside the backtest context

## Customizing Tests

You can modify the test scenarios by:

1. **Changing price patterns**:
   ```python
   # Create custom price sequences
   prices = [100, 110, 120, 115, 125, 130]  # Your pattern
   ```

2. **Adjusting sentiment**:
   ```python
   sentiment = create_simulated_x_sentiment(
       score=0.5,  # Neutral to bullish
       volume=200,
       tags=["crypto", "bullish"],
       sample_posts=["Your custom posts"]
   )
   ```

3. **Modifying LLM config**:
   ```python
   strategies_config['llm']['trigger_confidence'] = 0.5
   strategies_config['llm']['max_calls_per_backtest'] = 20
   ```

## Cost Considerations

- **Free models**: Using `microsoft/mai-ds-r1:free` costs $0
- **Paid models**: Check pricing on OpenRouter/OpenAI
- **Rate limits**: The script respects `max_calls_per_backtest` to control costs

## Next Steps

After verifying LLM works in simulation:
1. Run a full backtest with LLM enabled
2. Review LLM responses in backtest report
3. Analyze impact of LLM on trading performance
4. Adjust LLM weights and triggers based on results


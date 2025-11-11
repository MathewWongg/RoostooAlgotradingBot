# Crypto Trading Bot - Roostoo Labs Competition

A sophisticated crypto trading bot for the Roostoo Labs trading competition, featuring a hybrid ensemble strategy combining technical analysis, LLM-based market analysis, and baseline momentum/mean reversion strategies.

## Features

- **Multi-Strategy Ensemble**: Combines technical analysis, LLM insights, and baseline strategies with configurable weights
- **Technical Analysis**: RSI, MACD, and Bollinger Bands indicators
- **LLM Integration**: Multiple LLM providers supported:
  - **Local Ollama** (free, open-source models like gpt-oss:20b)
  - **Google Gemini** (free tier: gemini-1.5-flash)
  - **OpenRouter** (free tier: microsoft/mai-ds-r1:free)
  - **OpenAI** (GPT-4, GPT-3.5)
  - **Anthropic** (Claude models)
- **Social Sentiment**: Twitter scraping with **Google Gemini API** for advanced sentiment analysis:
  - Free web scraping using snscrape (no API limits)
  - Gemini-powered sentiment analysis (free tier available)
  - Analyzes tweets from specific meme coin accounts
  - Provides trend potential and sentiment scores
- **Risk Management**: Position sizing, cooldown periods, and maximum position limits
- **Comprehensive Logging**: Structured JSON logging for all trades and API calls
- **Performance Tracking**: Real-time performance metrics including PnL, win rate, and Sharpe ratio
- **Multi-Source Data**: Support for Roostoo, Horus, and Binance data sources
- **Docker Deployment**: Ready for AWS EC2 deployment

## Project Structure

```
QuantComp_RoostooLabs/
├── src/
│   ├── api/              # API clients (Roostoo, Horus, Binance)
│   ├── strategies/       # Trading strategies
│   ├── data/             # Data collection and storage
│   ├── execution/        # Order and risk management
│   ├── utils/            # Utilities (logging, config, performance)
│   └── main.py           # Main bot orchestration
├── config/
│   └── config.yaml       # Configuration file
├── logs/                 # Log files
├── data/                 # Data storage (SQLite)
├── requirements.txt      # Python dependencies
├── Dockerfile           # Docker container definition
└── docker-compose.yml   # Docker compose configuration
```

## Prerequisites

- Python 3.11+
- Docker (for containerized deployment)
- Roostoo API credentials (API key and secret key)
- (Optional) OpenRouter, OpenAI, or Anthropic API key for LLM strategy
- (Optional) Horus API key for additional data

## Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd QuantComp_RoostooLabs
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the `config/` directory (or set environment variables):

```bash
# Required
export ROOSTOO_API_KEY="your_roostoo_api_key"
export ROOSTOO_SECRET_KEY="your_roostoo_secret_key"

# Optional - for LLM strategy
export OPENROUTER_API_KEY="your_openrouter_api_key"
# Optional headers required by OpenRouter (set to match your app)
export OPENROUTER_HTTP_REFERER="https://your-app-url.example"
export OPENROUTER_X_TITLE="QuantComp Trading Bot"
# Optional - LLM Providers (choose one or more)
# Option 1: Local Ollama (free, requires model download)
export OLLAMA_HOST="http://127.0.0.1:11434"

# Option 2: Google Gemini (free tier available)
export GEMINI_API_KEY="your_gemini_api_key"

# Option 3: OpenRouter (free tier available)
export OPENROUTER_API_KEY="your_openrouter_api_key"
export OPENROUTER_HTTP_REFERER="https://your-app-url.example"
export OPENROUTER_X_TITLE="QuantComp Trading Bot"

# Option 4: OpenAI (paid)
export OPENAI_API_KEY="your_openai_api_key"

# Option 5: Anthropic (paid)
export ANTHROPIC_API_KEY="your_anthropic_api_key"

# Optional - for Horus data
export HORUS_API_KEY="your_horus_api_key"
```

### 4. Configure Trading Parameters

Edit `config/config.yaml` to customize:

- Trading pairs
- Strategy weights
- Risk parameters
- Order types
- Polling intervals

Example configuration:

```yaml
strategies:
  ensemble:
    technical_weight: 0.4
    llm_weight: 0.3
    baseline_weight: 0.3

trading:
  pairs: ["BTC/USD", "ETH/USD"]
  order_type: "MARKET"
  position_size_pct: 0.1
  min_confidence: 0.5
  polling_interval: 60
```

## Usage

### Local Development

Run the bot directly:

```bash
python -m src.main --config config/config.yaml
```

Or use the convenience script:

```bash
python run_bot.py --config config/config.yaml
```

### Backtesting

The bot includes a comprehensive backtesting system that allows you to test strategies on historical data.

#### Running a Backtest

```bash
# Basic backtest (uses last 30 days of data)
python run_backtest.py

# Custom date range
python run_backtest.py --start-date 2024-01-01 --end-date 2024-01-31

# Custom pairs and initial balance
python run_backtest.py --pairs TRUMP/USD SOL/USD --initial-balance 100000

# Save report to custom location
python run_backtest.py --output data/my_backtest_report.json
```

#### Backtest Options

- `--config`: Path to configuration file (default: `config/config.yaml`)
- `--start-date`: Start date in YYYY-MM-DD format (default: 30 days ago)
- `--end-date`: End date in YYYY-MM-DD format (default: today)
- `--pairs`: Trading pairs to backtest (default: from config)
- `--initial-balance`: Starting balance (default: 50000)
- `--output`: Output file path (default: `data/backtest_report.json`)

#### Backtest Report

The backtest generates a comprehensive report including:

- **Performance Metrics**: Total return, return percentage, win rate
- **Risk Metrics**: Max drawdown, Sharpe ratio
- **Trade Statistics**: Total trades, winning/losing trades, average win/loss
- **Pair Analysis**: Trades and PnL breakdown by trading pair
- **Balance History**: Equity curve over time
- **Trade Log**: Detailed log of all executed trades

The report is saved as JSON and also printed to the console.

#### Requirements for Backtesting

1. **Historical Data**: The bot needs historical data in the database. Run the bot in live mode first to collect data, or import historical data.

2. **Data Collection**: Historical data is automatically stored when the bot runs. Ensure you have sufficient data for your backtest period.

3. **Configuration**: The backtest uses the same configuration as live trading, including:
   - Trading pairs and pair weights
   - Strategy parameters
   - Risk management settings
   - Minimum confidence thresholds

### Docker Deployment

#### Build and Run with Docker Compose

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

#### Manual Docker Build

```bash
# Build image
docker build -t roostoo-trading-bot .

# Run container
docker run -d \
  --name trading-bot \
  --env-file config/.env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  roostoo-trading-bot
```

## AWS EC2 Deployment Guide

This guide covers deploying the trading bot to AWS EC2 with LLM strategy and Gemini sentiment analysis.

### Prerequisites

- AWS EC2 instance (t3.medium recommended, us-east-1 region for competition)
- Python 3.10+ (Python 3.11+ may have snscrape compatibility issues)
- 50+ GB EBS storage (for Ollama models if using local LLM)
- Access via AWS Session Manager (no SSH key required)

### 1. Launch and Configure EC2 Instance

#### Launch Instance
- **Instance Type**: t3.medium (competition requirement)
- **Region**: us-east-1 (competition requirement)
- **OS**: Amazon Linux 2023 or Ubuntu 22.04 LTS
- **Storage**: 50 GB EBS (minimum for Ollama models)
- **Security Group**: Allow outbound HTTPS (for API calls)

#### Connect via Session Manager
```bash
# From AWS Console: EC2 > Instances > Connect > Session Manager
# Or use AWS CLI:
aws ssm start-session --target <instance-id>
```

### 2. Initial Setup on EC2

#### Update System and Install Dependencies

**For Amazon Linux 2023:**
```bash
sudo yum update -y
sudo yum install -y python3.10 python3.10-pip git
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
```

**For Ubuntu 22.04:**
```bash
sudo apt-get update
sudo apt-get install -y python3.10 python3-pip git docker.io
sudo systemctl start docker
sudo systemctl enable docker
```

#### Install Python Dependencies
```bash
# Clone repository
git clone <repository-url>
cd QuantComp_RoostooLabs

# Create virtual environment
python3.10 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Note: If snscrape fails on Python 3.11+, install from git:
# pip install git+https://github.com/JustAnotherArchivist/snscrape.git
```

### 3. Configure Environment Variables

```bash
# Copy example env file
cp config/env.example config/.env

# Edit with your API keys
nano config/.env
```

Required environment variables:
```bash
# Required - Roostoo API
ROOSTOO_API_KEY=your_roostoo_api_key
ROOSTOO_SECRET_KEY=your_roostoo_secret_key

# Optional - LLM Provider (choose one)
# Option 1: Local Ollama (free, requires model download)
OLLAMA_HOST=http://127.0.0.1:11434

# Option 2: Google Gemini (free tier available)
GEMINI_API_KEY=your_gemini_api_key

# Option 3: OpenRouter (free tier available)
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_HTTP_REFERER=https://your-app-url.example
OPENROUTER_X_TITLE=QuantComp Trading Bot

# Option 4: OpenAI (paid)
OPENAI_API_KEY=your_openai_api_key

# Option 5: Anthropic (paid)
ANTHROPIC_API_KEY=your_anthropic_api_key
```

### 4. Install and Configure Ollama (Optional - for Local LLM)

If using local Ollama instead of cloud APIs:

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
sudo systemctl enable ollama
sudo systemctl start ollama

# Pull model (14 GB download - takes time)
ollama pull gpt-oss:20b

# Verify installation
curl http://127.0.0.1:11434/api/tags
```

### 5. Configure Trading Bot

Edit `config/config.yaml`:

```yaml
strategies:
  llm:
    provider: "ollama"  # or "gemini", "openrouter", "openai", "anthropic"
    model: "gpt-oss:20b"  # or "gemini-1.5-flash" for Gemini
    enabled: true
    enable_in_backtest: true

social:
  x:
    enabled: true
    gemini_api_key: ${GEMINI_API_KEY}
    gemini_model: "gemini-1.5-flash"
    enable_in_backtest: true
    coin_accounts:
      TRUMP: "realDonaldTrump"
      DOGE: "dogecoin"
      ETH: "ethereum"
      SOL: "solana"
```

### 6. Test the Setup

```bash
# Test LLM strategy
python test_llm_gemini.py

# Run a quick backtest
python run_backtest.py --config config/config.yaml --start-date 2024-01-01 --end-date 2024-01-02
```

### 7. Deploy as Systemd Service (Recommended)

Create systemd service file:

```bash
sudo nano /etc/systemd/system/trading-bot.service
```

Service file content:

```ini
[Unit]
Description=Roostoo Trading Bot
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/QuantComp_RoostooLabs
Environment="PATH=/home/ec2-user/QuantComp_RoostooLabs/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/ec2-user/QuantComp_RoostooLabs/.venv/bin/python run_bot.py --config config/config.yaml
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start service:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (starts on boot)
sudo systemctl enable trading-bot

# Start service
sudo systemctl start trading-bot

# Check status
sudo systemctl status trading-bot

# View logs
sudo journalctl -u trading-bot -f
```

### 8. Alternative: Docker Deployment

If you prefer Docker:

```bash
# Build image
docker build -t roostoo-trading-bot .

# Run container
docker run -d \
  --name trading-bot \
  --restart unless-stopped \
  --env-file config/.env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  roostoo-trading-bot

# View logs
docker logs -f trading-bot
```

### 9. Monitor and Maintain

#### View Logs
```bash
# Systemd logs
sudo journalctl -u trading-bot -f

# Application logs
tail -f logs/bot.log

# Backtest logs
tail -f logs/backtest.log
```

#### Check Performance
```bash
# View performance metrics
cat data/performance.json

# View recent trades
cat data/trades.json | tail -20
```

#### Update Bot
```bash
# Pull latest changes
git pull

# Restart service
sudo systemctl restart trading-bot
```

### 10. Competition Compliance Checklist

- ✅ Single t3.medium instance in us-east-1
- ✅ Spot trading only (enforced in code)
- ✅ 60-second polling interval (configurable)
- ✅ All trades logged to `data/trades.json`
- ✅ All API calls logged to `logs/bot.log`
- ✅ Performance metrics tracked in `data/performance.json`
- ✅ Repository is public for validation

### Troubleshooting

#### Bot Not Starting
```bash
# Check service status
sudo systemctl status trading-bot

# Check logs for errors
sudo journalctl -u trading-bot -n 50

# Verify Python and dependencies
python3 --version
pip list | grep -E "ollama|google-generativeai|openai"
```

#### LLM Not Working
```bash
# Test LLM connection
python test_llm_gemini.py

# Check Ollama (if using)
curl http://127.0.0.1:11434/api/tags
systemctl status ollama

# Verify API keys
cat config/.env | grep -E "GEMINI_API_KEY|OPENAI_API_KEY|OLLAMA_HOST"
```

#### Twitter Scraping Issues
```bash
# Check snscrape installation
python -c "import snscrape.modules.twitter; print('OK')"

# If fails, reinstall from git
pip install --force-reinstall git+https://github.com/JustAnotherArchivist/snscrape.git
```

#### Out of Memory
```bash
# Check memory usage
free -h

# If using Ollama, consider smaller model or cloud API
# Switch to Gemini free tier instead
```

## Configuration Guide

### Strategy Configuration

**Ensemble Weights**: Adjust the relative importance of each strategy:
- `technical_weight`: Technical analysis contribution (default: 0.4)
- `llm_weight`: LLM strategy contribution (default: 0.3)
- `baseline_weight`: Baseline strategy contribution (default: 0.3)

**Technical Strategy**:
- `rsi_period`: RSI calculation period (default: 14)
- `rsi_oversold/overbought`: RSI thresholds (default: 30/70)
- `macd_fast/slow/signal`: MACD periods (default: 12/26/9)

**LLM Strategy**:
- `provider`: "openrouter", "openai", or "anthropic"
- `model`: Model name (e.g., "microsoft/mai-ds-r1:free", "gpt-4", "claude-3-opus-20240229")
- `enabled`: Enable/disable LLM (default: true)
- `cache_responses`: Cache LLM responses to reduce API costs
- `base_url`: Override API base for the selected provider (OpenRouter defaults to https://openrouter.ai/api/v1)
- `default_headers`: Extra request headers (OpenRouter requires `HTTP-Referer` and `X-Title`)
- `trigger_confidence`: Minimum technical confidence before the LLM is consulted
- `require_divergence`: Whether the LLM is only called when technical and baseline signals disagree
- `max_calls_per_day`: Per-coin LLM call cap in live trading (default: 2)
- `max_calls_per_backtest`: Per-coin LLM call cap when backtesting (default: 1)
- `enable_in_backtest`: Toggle LLM usage during backtests to save costs
- `capital_multipliers`: Dynamic sizing multipliers (`default`, `divergence`, `confidence`, `llm_confirmed`) used by the risk manager

**Social Sentiment (X with Gemini)**:
- `enabled`: Enable/disable Twitter sentiment integration (default: false)
- `gemini_api_key`: Google Gemini API key (set via GEMINI_API_KEY environment variable)
- `gemini_model`: Gemini model to use (default: "gemini-1.5-flash" for free tier)
- `requests_per_coin_per_day`: Hard cap on scraping requests per coin per day (default: 2)
- `cache_ttl_hours`: Cache duration before allowing a refresh (default: 12)
- `enable_in_backtest`: Toggle Twitter scraping during backtests (default: true)
- `max_calls_per_backtest`: Backtest-only fetch cap when enabled (default: 10)
- `coin_accounts`: Map of coin symbols to Twitter usernames (e.g., TRUMP: "realDonaldTrump")
- `pair_mapping`: Maps trading pairs to coin symbols for sentiment lookup
- `max_results`: Number of tweets to fetch per request (default: 25, max: 100)
- `cache_path`: Location for cached sentiment JSON (default: `data/social_cache.json`)

**Note on Twitter Scraping:**
- Uses `snscrape` library for free web scraping (no API key required)
- May have compatibility issues with Python 3.11+ - install from git if needed:
  ```bash
  pip install git+https://github.com/JustAnotherArchivist/snscrape.git
  ```
- If snscrape fails, the bot will gracefully degrade and use cached sentiment

**Binance Market Data**:
- `enabled`: Enable/disable Binance integration (default: true when listed under `data.sources`)
- `interval`: Kline interval used when pulling historical candles (default: `1h`)
- `limit`: Number of candles to fetch per request (default: 200)
- `cache_seconds`: TTL before refreshing klines to avoid rate limits (default: 300)
- `rsi_period`: RSI lookback applied to Binance closes before sharing with strategies
- `sma_period`: SMA lookback applied to Binance closes before sharing with strategies

**Baseline Strategy**:
- `momentum_window`: Window for momentum calculation (default: 5)
- `mean_reversion_threshold`: Threshold for mean reversion (default: 0.02)

### Trading Configuration

- `pairs`: List of trading pairs or "all" for all available pairs
- `order_type`: "MARKET" or "LIMIT"
- `position_size_pct`: Percentage of balance per trade (default: 0.1 = 10%)
- `max_positions`: Maximum concurrent positions (default: 3)
- `polling_interval`: Data collection interval in seconds (default: 60)
- `min_confidence`: Minimum signal confidence to execute (default: 0.5)
- `cooldown_period`: Seconds between trades for same pair (default: 300)

## Monitoring and Performance

### Logs

Logs are stored in `logs/bot.log` with JSON formatting. Each log entry includes:
- Timestamp
- Log level
- Module/function
- Message
- Additional metadata (for trades and API calls)

### Performance Metrics

Performance data is stored in `data/performance.json` and includes:
- Total trades
- Win rate
- Total PnL
- Sharpe ratio
- Maximum drawdown
- Average win/loss

View metrics:

```bash
cat data/performance.json
```

### Trade History

All trades are recorded in `data/trades.json` with detailed information:
- Timestamp
- Pair, side, quantity, price
- Order ID and status
- Filled quantity and average price
- Commission and PnL

## Strategy Details

### Technical Strategy

Uses multiple technical indicators:
- **RSI**: Identifies overbought/oversold conditions
- **MACD**: Detects trend changes and momentum
- **Bollinger Bands**: Identifies volatility and potential reversals

Signals are generated based on indicator crossovers and threshold breaches.

### LLM Strategy

Leverages large language models to analyze market conditions:
- **Multi-Provider Support**: Works with Ollama (local), Gemini, OpenRouter, OpenAI, and Anthropic
- **Intelligent Triggering**: Only calls LLM when:
  - Technical and baseline strategies diverge (disagreement), OR
  - Technical strategy has high confidence (>= threshold)
- **Sentiment Integration**: Incorporates Twitter sentiment analysis from Gemini when available
- **Smart Caching**: Caches responses to minimize API costs
- **Performance Tracking**: Tracks LLM contribution to overall strategy performance

**How It Works:**
1. Technical and baseline strategies generate initial signals
2. If they disagree OR technical confidence is high, LLM is consulted
3. LLM analyzes: price trends, 24h changes, Twitter sentiment (if available)
4. LLM returns BUY/SELL/HOLD with confidence score
5. Ensemble combines all signals with weighted voting
6. Final decision considers all strategy contributions

**Gemini Sentiment Analysis:**
- Scrapes tweets from configured accounts (TRUMP, DOGE, ETH, SOL, etc.)
- Uses Gemini API to analyze sentiment and trend potential
- Provides sentiment scores (-1.0 bearish to +1.0 bullish)
- Includes analysis themes and key topics
- Free tier: 60 requests/minute, 1,500 requests/day

### Baseline Strategy

Simple but effective:
- **Momentum**: Buys on upward momentum, sells on downward momentum
- **Mean Reversion**: Trades against short-term deviations from mean

### Ensemble Strategy

Combines all three strategies with weighted voting:
- Each strategy generates a signal with confidence
- Signals are weighted and aggregated
- Final decision based on highest weighted score

## Troubleshooting

### API Authentication Errors

- Verify API keys are correct in `.env` file
- Check timestamp synchronization (bot handles this automatically)
- Ensure API keys have proper permissions

### No Trades Executing

- Check `min_confidence` threshold
- Verify sufficient balance
- Check `max_positions` limit
- Review cooldown periods
- Check logs for specific errors

### LLM Strategy Not Working

- **Test LLM setup**: Run `python test_llm_gemini.py` to verify configuration
- **Verify API key**: Check `config/.env` has correct API key for your provider
- **Check provider**: Ensure `config/config.yaml` has correct `provider` setting
- **Ollama issues**: Verify Ollama is running: `systemctl status ollama` and model is pulled: `ollama list`
- **Gemini issues**: Verify API key is valid and has quota remaining
- **Rate limits**: Check logs for rate limit errors, adjust `max_calls_per_day` if needed
- **Trigger conditions**: LLM may not trigger if `require_divergence: true` and strategies agree, or if `trigger_confidence` is too high

### Twitter Scraping Not Working

- **snscrape compatibility**: If Python 3.11+, install from git: `pip install git+https://github.com/JustAnotherArchivist/snscrape.git`
- **Gemini API key**: Verify `GEMINI_API_KEY` is set in `config/.env`
- **Account names**: Check `coin_accounts` in config match actual Twitter usernames
- **Cache**: Check `data/social_cache.json` for cached sentiment data
- **Logs**: Review logs for scraping errors - bot will use cached data if scraping fails

### Docker Issues

- Ensure Docker is running: `docker ps`
- Check container logs: `docker-compose logs`
- Verify volume mounts are correct
- Check file permissions

## Development

### Running Tests

```bash
# Unit tests (when implemented)
pytest tests/

# Integration tests
pytest tests/integration/
```

### Code Structure

- **Modular Design**: Each component is independent and testable
- **Strategy Pattern**: Easy to add new strategies
- **Configuration-Driven**: Most behavior controlled via config
- **Comprehensive Logging**: All actions are logged for debugging

## Competition Requirements

This bot meets all competition requirements:

- ✅ Spot trading only
- ✅ Open-ended strategy approach (ensemble of multiple strategies)
- ✅ Uses Roostoo platform data via API
- ✅ Supports Horus data integration (placeholder)
- ✅ Deploys on AWS VM
- ✅ Automatic trade execution
- ✅ Comprehensive logging of all trades and API requests
- ✅ Performance tracking

## License

This project is for the Roostoo Labs trading competition.

## Support

For issues or questions:
- Check logs in `logs/bot.log`
- Review configuration in `config/config.yaml`
- Verify API credentials and permissions

## Notes

- The bot uses mock API by default (`https://mock-api.roostoo.com`)
- LLM strategy is optional and can be disabled to reduce costs
- All trades are logged for competition compliance
- Performance metrics are calculated and stored automatically
- The bot handles errors gracefully and continues running

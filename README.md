# Crypto Trading Bot - Roostoo Labs Competition

A sophisticated crypto trading bot for the Roostoo Labs trading competition, featuring a hybrid ensemble strategy combining technical analysis, LLM-based market analysis, and baseline momentum/mean reversion strategies.

## Features

- **Multi-Strategy Ensemble**: Combines technical analysis, LLM insights, and baseline strategies with configurable weights
- **Technical Analysis**: RSI, MACD, and Bollinger Bands indicators
- **LLM Integration**: Optional OpenAI/Anthropic API integration for market sentiment analysis
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
- (Optional) OpenAI or Anthropic API key for LLM strategy
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
export OPENAI_API_KEY="your_openai_api_key"
# OR
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

## AWS Deployment

### 1. Prepare EC2 Instance

- Launch an EC2 instance (Ubuntu 22.04 LTS recommended)
- Install Docker:
  ```bash
  sudo apt-get update
  sudo apt-get install -y docker.io docker-compose
  sudo systemctl start docker
  sudo systemctl enable docker
  ```

### 2. Deploy Bot

```bash
# Clone repository on EC2
git clone <repository-url>
cd QuantComp_RoostooLabs

# Set environment variables
nano config/.env  # Add your API keys

# Start with Docker Compose
docker-compose up -d

# Or use systemd for auto-restart
sudo nano /etc/systemd/system/trading-bot.service
```

Systemd service file example:

```ini
[Unit]
Description=Roostoo Trading Bot
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/QuantComp_RoostooLabs
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable trading-bot
sudo systemctl start trading-bot
```

### 3. Monitor Logs

```bash
# Docker logs
docker-compose logs -f

# Or systemd logs
sudo journalctl -u trading-bot -f
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
- `provider`: "openai" or "anthropic"
- `model`: Model name (e.g., "gpt-4", "claude-3-opus-20240229")
- `enabled`: Enable/disable LLM (default: true)
- `cache_responses`: Cache LLM responses to reduce API costs

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
- Analyzes price trends and 24h changes
- Provides BUY/SELL/HOLD signals with confidence scores
- Caches responses to minimize API costs
- Supports OpenAI GPT-4 and Anthropic Claude models

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

- Verify API key is set correctly
- Check if LLM provider library is installed
- Review API rate limits and quotas
- Check logs for API errors

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

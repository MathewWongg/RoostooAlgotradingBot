# Local LLM Trading Runbook

This single guide replaces the previous `START_HERE.md`, `QUICK_START_LLM_TESTING.md`, and `TEST_LLM_README.md`. Use it as the canonical reference for preparing, testing, and deploying the Roostoo bot with a locally hosted Ollama model.

---

## TL;DR
- Install and start Ollama, then pull OpenAI’s open-weight `gpt-oss:20b` model (≈14 GB download, 128K context window).
- Copy `config/env.example` to `config/.env` so `OLLAMA_HOST` and Roostoo credentials are available.
- Run `setup_llm.(bat|sh)` or execute `python run_backtest.py --config config/config_llm_test.yaml` manually.
- Expect the backtest to log Ollama calls; if you see `model "..." not found`, pull the model first.
- Keep trading cadence at 60 s, respect the 0.1 % commission, and run only one `t3.medium` in `us-east-1` via Session Manager.

---

## 1. Install & Run Ollama

### Local workstation (Windows/macOS/Linux)
1. Download or script-install Ollama:  
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
2. Start the Ollama service and pull the model:  
   ```bash
   ollama serve        # macOS/Linux; Windows users start the Ollama app
   ollama pull gpt-oss:20b
   ```
3. Confirm the API is reachable: `curl http://127.0.0.1:11434/api/tags` should list `gpt-oss:20b`.

### AWS competition environment (`t3.medium`, `us-east-1`)
- Restrictions: one instance only, 50 GB EBS, spot-only trading, connect via Session Manager (no SSH), no IAM/S3/etc.
- Provision the instance, then run:
  ```bash
  sudo yum update -y
  sudo yum install -y git python3-pip
  curl -fsSL https://ollama.com/install.sh | sh
  sudo systemctl enable --now ollama
  ollama pull gpt-oss:20b
  ```
- Keep the default 60 s polling interval to stay clear of high-frequency behaviour.

---

## 2. Project Setup
1. Clone the repository (or pull latest changes) on the target machine.
2. Create and activate a virtual environment (optional but recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Linux/macOS
   .\.venv\Scripts\Activate.ps1     # Windows PowerShell
   ```
3. Install Python dependencies (includes the Ollama client library):
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. Copy environment defaults and confirm `OLLAMA_HOST` is set:
   ```bash
  cp config/env.example config/.env        # Linux/macOS
   # or
   copy config\env.example config\.env     # Windows
   ```
5. If Ollama listens on a non-default host/port, update `config/.env` accordingly.

---

## 3. Quick Start Backtest (LLM Enabled)

### Option A – scripted
```bash
# Windows
setup_llm.bat

# Linux/macOS
chmod +x setup_llm.sh && ./setup_llm.sh
```
The script copies `.env` (if it doesn’t exist), runs the backtest with `config/config_llm_test.yaml`, and prints a summary.

### Option B – manual
```bash
python run_backtest.py --config config/config_llm_test.yaml
```
Watch the logs for lines such as `Ollama inference error: model "gpt-oss:20b" not found`. If you see this, run `ollama pull gpt-oss:20b` before re-running the test. At the end you should see output similar to:
```
LLM API:
  Provider: ollama
  Model: gpt-oss:20b
  Total Calls: 100
```
Even if inference fails, the backtest proceeds; the log output is your signal to install/start the model correctly.

---

## 4. Simulation Test Suite (`test_llm_backtest.py`)
Run targeted scenarios without historical data:
```bash
python test_llm_backtest.py
```
Scenarios covered:
- **Signal divergence** – verifies the LLM triggers when technical and baseline disagree.
- **High confidence trigger** – ensures the LLM fires on strong technical convictions.
- **X sentiment integration** – confirms social data is injected into the prompt when enabled.
- **Rate limiting** – checks `max_calls_per_backtest` caps usage as expected.
Use this script to regression-test configuration changes before live deployment.

---

## 5. Configuration Reference (key fields)
| Setting | Location | Purpose |
|---------|----------|---------|
| `provider: "ollama"` | `config/config.yaml`, `config/config_llm_test.yaml` | Switches the strategy to local inference. |
| `model: "gpt-oss:20b"` | same | OpenAI OSS reasoning model (≈14 GB, 128K context) now used by default. |
| `host` / `OLLAMA_HOST` | env & config | HTTP endpoint for the Ollama daemon. |
| `trigger_confidence` | config | Minimum ensemble confidence before polling the LLM. |
| `require_divergence` | config | Set `false` in tests to maximise LLM activity. |
| `max_calls_per_backtest` | config | Set high (100 k) so the LLM can respond to every signal; lower only if you need to throttle. |
| `enable_in_backtest` | config | Must stay `true` for historical runs to include LLM decisions. |

---

## 6. Troubleshooting Checklist
- **`model "... not found"`** – run `ollama pull gpt-oss:20b` (or the model you configured). This is the most common error; it surfaced during the latest backtest run.
- **Connection refused** – start the Ollama daemon (`ollama serve` or `systemctl status/start ollama`) and verify firewall rules allow localhost access.
- **LLM calls remain at 0** – double-check you are using `config/config_llm_test.yaml`, set `trigger_confidence ≤ 0.5`, and confirm `require_divergence` is `false` for the test profile.
- **401 / auth errors** – only relevant for OpenRouter/OpenAI. Ensure `provider` matches the credentials you supply.
- **Import errors** – run `pip install -r requirements.txt` inside the active virtual environment.
- **High-frequency violations** – leave `polling_interval: 60` and avoid manual loops that spam the APIs.

---

## 7. FAQ
- **Does the local model cost anything?** Running `gpt-oss:20b` is still free (open weight) but needs ~14 GB disk and enough RAM; ensure your EC2 disk has room. Choose a smaller model only if you need to conserve space.
- **Can I still call hosted APIs?** Yes. Change `provider` back to `openrouter`/`openai`/`anthropic` and set the corresponding API keys in `.env`.
- **What data does the LLM see?** Price, change %, trend classification, and optional X sentiment summaries. Responses must follow `ACTION:CONFIDENCE` (e.g., `BUY:0.72`).
- **How is commission handled?** The backtester already applies the 0.1 % fee to every simulated order; no extra work required.
- **What about shorting or leverage?** Disabled. The bot enforces spot-only execution to stay within competition rules.

---

## 8. Next Steps & Compliance Reminders
1. Verify Ollama stays running after reboots (`systemctl enable --now ollama` on Linux).
2. Keep your repository public for validation before deployment, as required by the competition.
3. After testing, port tuned values back into `config/config.yaml` for production runs.
4. Monitor logs for `Ollama inference error` messages; they indicate model/service issues rather than trading faults.
5. When migrating to AWS, remember to operate solely within `us-east-1`, maintain a single `t3.medium`, and connect exclusively through Session Manager.

With this guide consolidated, you can spin up the bot locally or on AWS, validate the LLM contribution, and remain compliant with Roostoo’s trading rules. Happy testing!


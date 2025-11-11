#!/bin/bash
# Quick Setup Script for LLM Testing
# This script sets up the environment and runs a test backtest

echo "================================================================================"
echo "                    LLM Strategy Quick Setup"
echo "================================================================================"
echo

# Check if .env already exists
if [ -f "config/.env" ]; then
    echo "[INFO] config/.env already exists"
    echo "[INFO] Skipping copy to avoid overwriting your configuration"
    echo
    read -p "Do you want to overwrite it with env.example? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "[INFO] Using existing config/.env"
        echo
    else
        echo "[STEP 1/3] Copying config/env.example to config/.env..."
        cp config/env.example config/.env
        if [ $? -ne 0 ]; then
            echo "[ERROR] Failed to copy env.example to .env"
            exit 1
        fi
        echo "[SUCCESS] Environment file created!"
        echo
    fi
else
    echo "[STEP 1/3] Copying config/env.example to config/.env..."
    cp config/env.example config/.env
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to copy env.example to .env"
        exit 1
    fi
    echo "[SUCCESS] Environment file created!"
    echo
fi

echo "[STEP 2/3] Verifying configuration..."
if [ ! -f "config/config_llm_test.yaml" ]; then
    echo "[ERROR] config/config_llm_test.yaml not found!"
    echo "[INFO] Please make sure you have the LLM test configuration file."
    exit 1
fi
echo "[SUCCESS] Configuration file found!"
echo

echo "[STEP 3/3] Running LLM test backtest..."
echo
echo "This will take 1-2 minutes. Look for 'LLM Calls Made' in the output."
echo "Expected: 20-50 LLM calls (vs 0 with default config)"
echo
read -p "Press Enter to continue..."

python run_backtest.py --config config/config_llm_test.yaml

echo
echo "================================================================================"
echo "                         Setup Complete!"
echo "================================================================================"
echo
echo "Next Steps:"
echo "1. Check the output above for 'LLM Calls Made: XX'"
echo "2. Review the backtest results"
echo "3. Compare with/without LLM: Read QUICK_START_LLM_TESTING.md"
echo "4. For production deployment: Read LLM_USAGE_ANALYSIS_REPORT.md"
echo


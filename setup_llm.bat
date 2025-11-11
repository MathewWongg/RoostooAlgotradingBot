@echo off
REM Quick Setup Script for LLM Testing
REM This script sets up the environment and runs a test backtest

echo ================================================================================
echo                    LLM Strategy Quick Setup
echo ================================================================================
echo.

REM Check if .env already exists
if exist "config\.env" (
    echo [INFO] config\.env already exists
    echo [INFO] Skipping copy to avoid overwriting your configuration
    echo.
    choice /C YN /M "Do you want to overwrite it with env.example"
    if errorlevel 2 goto :skip_copy
    if errorlevel 1 goto :do_copy
) else (
    goto :do_copy
)

:do_copy
echo [STEP 1/3] Copying config\env.example to config\.env...
copy config\env.example config\.env
if errorlevel 1 (
    echo [ERROR] Failed to copy env.example to .env
    pause
    exit /b 1
)
echo [SUCCESS] Environment file created!
echo.
goto :continue

:skip_copy
echo [INFO] Using existing config\.env
echo.

:continue
echo [STEP 2/3] Verifying configuration...
if not exist "config\config_llm_test.yaml" (
    echo [ERROR] config\config_llm_test.yaml not found!
    echo [INFO] Please make sure you have the LLM test configuration file.
    pause
    exit /b 1
)
echo [SUCCESS] Configuration file found!
echo.

echo [STEP 3/3] Running LLM test backtest...
echo.
echo This will take 1-2 minutes. Look for "LLM Calls Made" in the output.
echo Expected: 20-50 LLM calls (vs 0 with default config)
echo.
pause

python run_backtest.py --config config/config_llm_test.yaml

echo.
echo ================================================================================
echo                         Setup Complete!
echo ================================================================================
echo.
echo Next Steps:
echo 1. Check the output above for "LLM Calls Made: XX"
echo 2. Review the backtest results
echo 3. Compare with/without LLM: Read QUICK_START_LLM_TESTING.md
echo 4. For production deployment: Read LLM_USAGE_ANALYSIS_REPORT.md
echo.
pause


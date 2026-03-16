@echo off
REM Simple manual run script - use after Python is properly installed

cd /d "%~dp0"

echo ============================================================
echo PICasso - OpenAI Circuit Generation
echo ============================================================
echo.
echo Current directory: %CD%
echo.

echo Step 1: Installing required packages (if needed)...
pip install openai gdsfactory pandas tqdm --quiet

echo.
echo Step 2: Testing OpenAI API connection...
python test_openai_connection.py

if errorlevel 1 (
    echo.
    echo ❌ Test failed. Check your API key in config.py
    pause
    exit /b 1
)

echo.
echo ============================================================
echo ✅ API Test Passed!
echo ============================================================
echo.
echo Ready to generate circuits.
echo.
echo Options:
echo   1. Full generation (20 problems, 2 samples = 40 designs)
echo   2. Quick test (5 problems, 1 sample = 5 designs)
echo   3. Cancel
echo.

set /p CHOICE="Enter choice (1, 2, or 3): "

if "%CHOICE%"=="1" (
    echo.
    echo Running full generation...
    python gen_data_openai_validated.py --problems test_20_problems.txt --output validation_report.csv --samples 2
) else if "%CHOICE%"=="2" (
    echo.
    echo Running quick test...
    python gen_data_openai_validated.py --problems problems.txt --output test_report.csv --samples 1
) else (
    echo Cancelled.
    pause
    exit /b 0
)

echo.
echo ============================================================
echo ✅ Generation Complete!
echo ============================================================
echo.
echo Results:
echo - CSV Report: output\results\
echo - First attempts: output\gds_first_attempt\
echo - Clean dataset: output\PIC_set\gds_clean\
echo.
pause

@echo off
echo ============================================================
echo PICasso - OpenAI Circuit Generation Test
echo ============================================================
echo.

REM Set Python path to use the kl environment
set PYTHON_PATH=C:\Users\deepa\OneDrive\Desktop\picasso\kl\libpython3.11.dll
set PATH=C:\Users\deepa\OneDrive\Desktop\picasso\kl;%PATH%

REM Find Python executable
if exist "C:\Users\deepa\OneDrive\Desktop\picasso\kl\python.exe" (
    set PYTHON=C:\Users\deepa\OneDrive\Desktop\picasso\kl\python.exe
) else if exist "C:\Users\deepa\OneDrive\Desktop\picasso\kl\lib\python3.11\python.exe" (
    set PYTHON=C:\Users\deepa\OneDrive\Desktop\picasso\kl\lib\python3.11\python.exe
) else (
    echo ❌ Python not found in kl environment
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Using Python: %PYTHON%
echo.

echo Step 1: Testing OpenAI API connection...
"%PYTHON%" test_openai_connection.py

if errorlevel 1 (
    echo.
    echo ❌ API test failed. Please check the error above.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo Step 2: Generating photonic circuits...
echo ============================================================
echo.
echo This will generate circuits for the 20-problem dataset.
echo - Problems: test_20_problems.txt
echo - Samples per problem: 2
echo - Total designs: 40
echo - Expected cost: $1-3 USD
echo - Expected time: 15-30 minutes
echo.

set /p CONTINUE="Continue with generation? (y/n): "
if /i not "%CONTINUE%"=="y" (
    echo Generation cancelled.
    pause
    exit /b 0
)

echo.
echo Starting generation...
"%PYTHON%" gen_data_openai_validated.py --problems test_20_problems.txt --output validation_report.csv --samples 2

echo.
echo ============================================================
echo ✅ Generation Complete!
echo ============================================================
echo.
echo Check results:
echo - CSV Report: output\results\validation_report.csv
echo - First attempts: output\gds_first_attempt\
echo - Clean dataset: output\PIC_set\gds_clean\
echo - Python code: output\PIC_set\code_clean\
echo.
pause

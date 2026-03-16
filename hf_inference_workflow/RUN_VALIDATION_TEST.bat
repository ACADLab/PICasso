@echo off
echo ======================================================================
echo PICasso Validation Workflow - Challenging Designs Test
echo ======================================================================
echo.
echo Configuration:
echo   - 3 challenging problems (MZM, 8-QAM, Ring Resonator)
echo   - 2 samples per problem = 6 total designs
echo   - Estimated time: 10-15 minutes
echo   - Model: DeepSeek-Coder-6.7B (via HF Inference API)
echo.
echo Validation stages:
echo   1. P&R (Place and Route) - catches messy layouts
echo   2. DRC (Design Rule Check) - catches fabrication issues
echo   3. SAX (Simulation) - catches functional errors
echo.
echo Press any key to start generation...
pause > nul

echo.
echo ======================================================================
echo Starting validation workflow...
echo ======================================================================
echo.

python gen_data_validated.py --problems test_challenging_problems.txt --output test_results_challenging.csv --samples 2

echo.
echo ======================================================================
echo Generation complete!
echo ======================================================================
echo.
echo Results saved to:
echo   CSV: output\results\test_results_challenging.csv
echo   GDS: output\gds_files\*.gds
echo.
echo Opening results...
type output\results\test_results_challenging.csv
echo.
echo Press any key to exit...
pause

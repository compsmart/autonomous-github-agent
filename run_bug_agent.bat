@echo off
echo ========================================
echo AI Bug Fixer Agent - Fast Mode
echo ========================================
echo.
echo Running with --limit 1 --fast...
echo.

python main.py --limit 1 --fast

echo.
echo ========================================
echo Agent execution completed.
echo Press any key to close this window...
echo ========================================
pause >nul

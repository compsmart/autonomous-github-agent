@echo off
echo ========================================
echo AI Code Review Agent - Fast Mode
echo ========================================
echo.
echo Running with --limit 1 --fast --review...
echo.

python main.py --limit 1 --fast --review

echo.
echo ========================================
echo Code review execution completed.
echo Press any key to close this window...
echo ========================================
pause >nul

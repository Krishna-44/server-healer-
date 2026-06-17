@echo off
cd /d "%~dp0"
where python >nul 2>nul || (echo Python 3 needed: https://www.python.org/downloads/ ^(tick "Add to PATH"^) & pause & exit /b)
python install.py %*
pause
